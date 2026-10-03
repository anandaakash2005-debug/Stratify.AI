"""
utils/response_formatter.py

AI response normalization (messy AI → clean dict) plus standard API JSON wrappers.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from fastapi.responses import JSONResponse


# ─────────────────────────────────────────────
# PRIMITIVE NORMALIZERS
# ─────────────────────────────────────────────

def to_int(val: Any, default: int = 0) -> int:
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return max(0, int(round(val)))
    s = str(val).strip()
    s = re.sub(r"[%$,\s]", "", s)
    s = re.sub(r"(months?|mo|×|x)", "", s, flags=re.IGNORECASE)
    try:
        return max(0, int(round(float(s))))
    except (ValueError, TypeError):
        return default


def to_float(val: Any, default: float = 0.0) -> float:
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return float(val)
    s = re.sub(r"[%$,\s×xX]", "", str(val).strip())
    s = re.sub(r"(months?|mo)", "", s, flags=re.IGNORECASE)
    try:
        return float(s)
    except (ValueError, TypeError):
        return default


def to_str(val: Any, default: str = "—") -> str:
    if val is None:
        return default
    s = str(val).strip()
    return s if s else default


def to_severity(val: Any) -> str:
    mapping = {
        "critical": "critical", "crit": "critical",
        "high": "high", "h": "high",
        "medium": "medium", "med": "medium", "moderate": "medium",
        "low": "low", "l": "low", "minor": "low",
    }
    return mapping.get(str(val or "medium").strip().lower(), "medium")


def to_threat(val: Any) -> str:
    mapping = {
        "critical": "Critical",
        "high": "High",
        "medium": "Medium",
        "low": "Low",
    }
    return mapping.get(str(val or "medium").strip().lower(), "Medium")


def clamp(val: int | float, lo: int = 0, hi: int = 100) -> int:
    return max(lo, min(hi, int(round(val))))


_KEY_ALIASES: dict[str, str] = {
    "health_score": "survival_score",
    "survival_score_value": "survival_score",
    "overall_score": "survival_score",
    "score": "survival_score",
    "survival_prob": "survival_probability",
    "probability": "survival_probability",
    "survival_rate": "survival_probability",
    "funding_readiness_score": "funding_readiness",
    "fundraising_readiness": "funding_readiness",
    "investor_readiness": "funding_readiness",
    "monthly_recurring_revenue": "mrr",
    "revenue": "mrr",
    "monthly_revenue": "mrr",
    "burn_rate": "burn",
    "monthly_burn": "burn",
    "burn_rate_monthly": "burn",
    "revenue_growth_mom": "growth",
    "mom_growth": "growth",
    "growth_rate": "growth",
    "cash_runway": "runway_months",
    "runway": "runway_months",
    "financial_health_score": "financial_score",
    "market_opportunity_score": "market_score",
    "team_strength_score": "team_score",
    "product_ip_score": "product_score",
    "traction_score_val": "traction_score",
    "risk_exposure_score": "risk_score",
}


def flatten_aliases(raw: dict) -> dict:
    out = {}
    for k, v in raw.items():
        canonical = _KEY_ALIASES.get(k, k)
        if canonical not in out:
            out[canonical] = v
        elif out[canonical] in (None, "", 0, 0.0):
            out[canonical] = v
    return out


def normalize_risks(raw_risks: Any) -> list[dict]:
    if not isinstance(raw_risks, list):
        return []
    out = []
    for r in raw_risks:
        if isinstance(r, str):
            out.append({"category": "Risk", "description": r, "severity": "medium"})
        elif isinstance(r, dict):
            out.append({
                "category": to_str(r.get("category") or r.get("title") or r.get("name"), "Risk"),
                "description": to_str(r.get("description") or r.get("detail") or r.get("body"), ""),
                "severity": to_severity(r.get("severity") or r.get("level") or r.get("risk_level")),
            })
    return out


def normalize_swot(raw_swot: Any) -> dict:
    if not isinstance(raw_swot, dict):
        return {"strengths": [], "weaknesses": [], "opportunities": [], "threats": []}

    def _to_list(val: Any) -> list[str]:
        if isinstance(val, list):
            return [to_str(i) for i in val if i]
        if isinstance(val, str) and val:
            return [s.strip() for s in val.split("\n") if s.strip()]
        return []

    return {
        "strengths": _to_list(raw_swot.get("strengths") or raw_swot.get("strength")),
        "weaknesses": _to_list(raw_swot.get("weaknesses") or raw_swot.get("weakness")),
        "opportunities": _to_list(raw_swot.get("opportunities") or raw_swot.get("opportunity")),
        "threats": _to_list(raw_swot.get("threats") or raw_swot.get("threat")),
    }


def normalize_competitors(raw: Any) -> list[dict]:
    if not isinstance(raw, list):
        return []
    out = []
    for c in raw:
        if not isinstance(c, dict):
            continue
        out.append({
            "name": to_str(c.get("name") or c.get("competitor")),
            "stage": to_str(c.get("stage"), "—"),
            "funding": to_str(c.get("funding") or c.get("amount"), "—"),
            "differentiator": to_str(
                c.get("differentiator") or c.get("key_differentiator") or c.get("strength"), "—"
            ),
            "threat": to_threat(c.get("threat") or c.get("threat_level") or c.get("risk")),
        })
    return out


def normalize_recommendations(raw: Any) -> list[dict]:
    if not isinstance(raw, list):
        return []
    out = []
    for r in raw:
        if isinstance(r, str):
            out.append({"title": r, "description": "", "urgency": "Medium", "impact": ""})
        elif isinstance(r, dict):
            out.append({
                "title": to_str(r.get("title") or r.get("action") or r.get("recommendation")),
                "description": to_str(r.get("description") or r.get("body") or r.get("detail"), ""),
                "urgency": to_str(r.get("urgency") or r.get("priority") or r.get("timeline"), "Medium"),
                "impact": to_str(r.get("impact") or r.get("est_impact") or r.get("expected_impact"), ""),
            })
    return out


def normalize_ai_response(raw: dict) -> dict:
    if not isinstance(raw, dict):
        raw = {}

    data = flatten_aliases(raw)

    int_fields = [
        "survival_score", "survival_probability", "funding_readiness",
        "financial_score", "market_score", "team_score", "product_score",
        "traction_score", "risk_score",
    ]
    for field in int_fields:
        if field in data:
            data[field] = clamp(to_int(data[field]))

    for field in ("runway_months", "burn_multiple"):
        if field in data:
            data[field] = to_float(data[field])

    data["risks"] = normalize_risks(data.get("risks", []))
    data["swot"] = normalize_swot(data.get("swot", {}))
    data["competitors"] = normalize_competitors(
        data.get("competitors") or data.get("competitive_intel", [])
    )
    data["recommendations"] = normalize_recommendations(
        data.get("recommendations") or data.get("action_plan") or data.get("actions", [])
    )

    return data


# ─────────────────────────────────────────────
# API RESPONSE HELPERS (used by other routes)
# ─────────────────────────────────────────────

def success_response(data: Any, message: str = "Success", status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"success": True, "message": message, "data": data, "error": None},
    )


def error_response(
    message: str,
    status_code: int = 400,
    details: Optional[Any] = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"success": False, "message": message, "data": None, "error": details or message},
    )


def paginated_response(
    data: list,
    total: int,
    page: int,
    page_size: int,
    message: str = "Success",
) -> JSONResponse:
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "message": message,
            "data": data,
            "pagination": {
                "total": total,
                "page": page,
                "page_size": page_size,
                "pages": -(-total // page_size),
            },
            "error": None,
        },
    )
