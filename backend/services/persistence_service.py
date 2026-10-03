"""Async atomic persistence through the analysis RPCs in database/analysis_pipeline.sql."""
import json
import logging
import httpx
from config.settings import settings
from utils.analysis_errors import (
    AnalysisAlreadyProcessingError,
    AnalysisClaimConflictError,
    AnalysisLeaseExpiredError,
    AnalysisPersistenceError,
    PersistenceError,
)

logger = logging.getLogger(__name__)


def extract_postgrest_error(exc: Exception) -> dict:
    result = {
        "type": type(exc).__name__,
        "code": getattr(exc, "code", None),
        "message": getattr(exc, "message", None),
        "details": getattr(exc, "details", None),
        "hint": getattr(exc, "hint", None),
    }
    if exc.args and isinstance(exc.args[0], dict):
        payload = exc.args[0]
        result["code"] = result["code"] or payload.get("code")
        result["message"] = result["message"] or payload.get("message")
        result["details"] = result["details"] or payload.get("details")
        result["hint"] = result["hint"] or payload.get("hint")
    result["message"] = result["message"] or str(exc)
    return result


def _postgrest_error(payload: object) -> dict:
    if isinstance(payload, dict):
        return extract_postgrest_error(Exception(payload))
    if isinstance(payload, str):
        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError:
            decoded = None
        if isinstance(decoded, dict):
            return extract_postgrest_error(Exception(decoded))
        return extract_postgrest_error(Exception(payload))
    return extract_postgrest_error(Exception(repr(payload)))


def _raise_persistence_error(response: httpx.Response, name: str, request_id=None):
    try:
        payload = response.json()
    except ValueError:
        payload = response.text
    error_info = _postgrest_error(payload)
    if name == "finish_analysis":
        logger.error(
            "finish_analysis RPC failed request_id=%s error_type=%s code=%s "
            "message=%s details=%s hint=%s",
            request_id,
            error_info["type"],
            error_info["code"],
            error_info["message"],
            error_info["details"],
            error_info["hint"],
        )
    message = str(error_info["message"]).lower()
    if "lease" in message or "expired" in message:
        raise AnalysisLeaseExpiredError("The analysis lease expired before persistence completed.")
    if response.status_code == 409:
        raise AnalysisClaimConflictError("This request conflicts with an existing analysis.")
    error = AnalysisPersistenceError("Report storage rejected the analysis result.")
    error.code = "ANALYSIS_PERSISTENCE_FAILED"
    raise error

async def rpc(name, payload, request_id=None):
    async with httpx.AsyncClient(timeout=8) as client:
        try:
            response = await client.post(
                str(settings.SUPABASE_URL).rstrip('/') + '/rest/v1/rpc/' + name,
                headers={'apikey': settings.SUPABASE_SERVICE_KEY,
                         'Authorization': 'Bearer ' + settings.SUPABASE_SERVICE_KEY},
                json=payload)
        except httpx.RequestError as exc:
            raise PersistenceError('Report storage is temporarily unavailable. Please retry.') from exc
    if response.status_code in (400, 404, 406, 409, 500, 502, 503):
        _raise_persistence_error(response, name, request_id or payload.get('p_request'))
    if not response.is_success:
        # Do not expose SQL, provider bodies or credentials.
        raise PersistenceError('Report storage is unavailable or needs its database migration. Please retry later.')
    try:
        return response.json()
    except ValueError as exc:
        raise PersistenceError('Report storage returned an invalid response.') from exc

async def claim_analysis(user_id, request_id, fingerprint, owner):
    result = await rpc('claim_analysis', {'p_user': user_id, 'p_request': request_id,
                       'p_hash': fingerprint, 'p_owner': owner})
    if result['status'] == 'conflict':
        raise AnalysisClaimConflictError('This request ID was already used with different startup data.')
    if result['status'] == 'processing':
        raise AnalysisAlreadyProcessingError('This analysis is already running. Wait, then retry the same request.')
    return result.get('result')

async def release_analysis(user_id, request_id, owner):
    await rpc('release_analysis', {'p_user': user_id, 'p_request': request_id, 'p_owner': owner})

async def save_analysis(user_id, form_data, ai_result, final_analysis, request_id, owner):
    metrics = final_analysis.get("metrics") or {}
    required = ("survival_score", "funding_readiness", "team_score", "market_score",
                "runway_months", "burn_multiple", "risk_count")
    missing = [field for field in required if field not in metrics]
    if missing or not all(final_analysis.get(section) is not None for section in
                          ("swot", "risks", "competitors", "recommendations")):
        raise AnalysisPersistenceError("The final analysis is missing required persistence fields.")
    return await rpc('finish_analysis', {'p_user': user_id, 'p_request': request_id,
                     'p_owner': owner, 'p_form': form_data, 'p_result': final_analysis})
