import asyncio
import hashlib
import json
import logging
import re
import time
import uuid
from datetime import datetime, timezone
from pydantic import ValidationError
from schemas.analysis import AdditionalContextFacts, AnalysisResponse
from services.persistence_service import claim_analysis, save_analysis, release_analysis
from config.settings import settings
from utils.openrouter_client import generate_ai_analysis
from utils.scoring import calculate_startup_metrics
from utils.analysis_errors import AITimeoutError, AISchemaError, PersistenceError

NUMERIC_AI_FIELDS = {"financial_score", "market_score", "team_score", "product_score", "traction_score", "risk_score"}


def validate_ai_numeric_output(ai_result: dict) -> None:
    """Reject new typed numeric outputs outside the known score fields."""
    def walk(value, path=""):
        if isinstance(value, bool):
            return
        if isinstance(value, (int, float)) and path.rsplit(".", 1)[-1] not in NUMERIC_AI_FIELDS:
            raise AISchemaError(f"AI returned an unapproved numeric field: {path}")
        if isinstance(value, dict):
            for key, child in value.items():
                walk(child, f"{path}.{key}" if path else key)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, f"{path}.{index}")
    walk(ai_result)

logger = logging.getLogger(__name__)


def extract_additional_context(text: str) -> dict:
    """Extract only explicitly stated numeric facts; never infer missing values."""
    text = str(text or "")
    patterns = {
        "customers": r"(?:\b(\d[\d,]*)\s+(?:customers?|clients?|users?)\b|\b(?:customers?|clients?|users?)\s*(?:is|are|:)?\s*(\d[\d,]*)\b)",
        "churn_rate_pct": r"(?:\bchurn(?:\s+rate)?\s*(?:is|at|of|:)?\s*(\d+(?:\.\d+)?)\s*%|\b(\d+(?:\.\d+)?)\s*%\s*churn)",
        "partnerships": r"(?:\b(\d[\d,]*)\s+partnerships?\b|\bpartnerships?\s*(?:is|are|:)?\s*(\d[\d,]*)\b)",
        "letters_of_intent": r"(?:\b(\d[\d,]*)\s+(?:letters?\s+of\s+intent|LOIs?)\b|\b(?:letters?\s+of\s+intent|LOIs?)\s*(?:is|are|:)?\s*(\d[\d,]*)\b)",
    }
    extracted = {}
    for field, pattern in patterns.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            continue
        raw = next((group for group in match.groups() if group), "").replace(",", "")
        try:
            extracted[field] = float(raw) if field == "churn_rate_pct" else int(raw)
        except ValueError:
            continue
    return AdditionalContextFacts.model_validate(extracted).model_dump(exclude_none=True)


def merge_extracted_context(form_data: dict) -> dict:
    merged = dict(form_data)
    if merged.get("churn_rate_pct") is None and merged.get("churn_rate") is not None:
        merged["churn_rate_pct"] = merged["churn_rate"]
    extracted = extract_additional_context(merged.get("additional_context", ""))
    for field, value in extracted.items():
        if merged.get(field) is None:
            merged[field] = value
    return merged

def validated_saved(value):
    try:
        result = AnalysisResponse.model_validate(value).model_dump(by_alias=True)
    except ValidationError as exc:
        raise PersistenceError("The stored report is incomplete. Please contact support.") from exc
    if not result.get("report_id") or not result.get("startup_id"):
        raise PersistenceError("Report storage did not confirm the saved report. Please retry.")
    return result


def _validation_error(detail, exc):
    errors = [
        {
            'path': '.'.join(str(part) for part in error.get('loc', ())) or 'root',
            'message': error.get('msg', 'Invalid value'),
            'type': error.get('type', 'validation_error'),
            'input': repr(error.get('input'))[:200],
        }
        for error in exc.errors()
    ]
    return AISchemaError(f'{detail}: {errors[:10]}')

async def analyze_startup(form_data: dict, user, request_id=None, deadline=None) -> dict:
    started = time.monotonic()
    deadline = deadline or started + settings.ANALYSIS_TIMEOUT
    request_id = request_id or str(uuid.uuid4())
    user_id = user.user.id
    owner = str(uuid.uuid4())
    form_data = merge_extracted_context(form_data)
    fingerprint = hashlib.sha256(json.dumps(form_data, sort_keys=True, allow_nan=False).encode()).hexdigest()
    claimed = False
    try:
        async with asyncio.timeout_at(deadline):
            existing = await claim_analysis(user_id, request_id, fingerprint, owner)
            if existing is not None:
                return validated_saved(existing)
            claimed = True
            ai_result = await generate_ai_analysis(form_data, deadline=deadline)
            validate_ai_numeric_output(ai_result)
            created_at = datetime.now(timezone.utc).isoformat()
            result = calculate_startup_metrics(ai_result, form_data, created_at)
            result.update(created_at=created_at, request_id=request_id)
            try:
                result = AnalysisResponse.model_validate(result).model_dump(by_alias=True)
            except ValidationError as exc:
                raise _validation_error('Response schema validation failed', exc) from exc
            saved = await save_analysis(user_id, form_data, ai_result, result, request_id, owner)
            return validated_saved(saved)
    except TimeoutError as exc:
        raise AITimeoutError(
            f'Analysis reached the {settings.ANALYSIS_TIMEOUT}-second deadline. Please retry.'
        ) from exc
    finally:
        # Bounded cleanup; lease expiry also recovers process crashes. Never extend deadline.
        if claimed:
            try:
                cleanup_task = asyncio.create_task(
                    release_analysis(user_id, request_id, owner))
                try:
                    await asyncio.wait_for(asyncio.shield(cleanup_task), timeout=3)
                except asyncio.TimeoutError:
                    cleanup_task.cancel()
                    await asyncio.gather(cleanup_task, return_exceptions=True)
                    raise
            except Exception as cleanup_error:
                logger.warning('Analysis lease cleanup failed request_id=%s error=%s',
                               request_id, type(cleanup_error).__name__)
            else:
                logger.info('Analysis lease cleanup succeeded request_id=%s', request_id)
        logger.info('Analysis user_id=%s request_id=%s duration=%.3f', user_id, request_id, time.monotonic()-started)
