"""
routes/reports.py — Report retrieval endpoints.
GET /reports/{id}, GET /reports/startup/{startup_id}, GET /reports/recent
"""

from fastapi import APIRouter, Depends, HTTPException, Query
import logging

from auth.dependencies import require_user
from database.client import table
from services.report_service import report_service
from utils.response_formatter import success_response, paginated_response

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/history", summary="Get analysis history for the authenticated user")
async def history(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user=Depends(require_user),
):
    user_id = user.user.id
    try:
        res = (
            table("reports")
            .select(
                "id, created_at, competitors, "
                "startups!inner(id, name, market, stage), "
                "scores!inner(health_score, funding_readiness, team_score, market_score, risk_count)"
            )
            .eq("startups.user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
            .range(offset, offset + limit - 1)
            .execute()
        )
    except Exception as exc:
        logger.error("History query failed: %s", exc)
        raise HTTPException(status_code=502, detail="Database query failed") from exc

    data = []
    for row in res.data or []:
        startup = row.get("startups") or {}
        score_rows = row.get("scores") or []
        score = score_rows[0] if isinstance(score_rows, list) and score_rows else (score_rows if isinstance(score_rows, dict) else {})
        competitors = row.get("competitors") or []
        data.append({
            "report_id": row.get("id"),
            "startup_name": startup.get("name", "Unnamed Startup"),
            "industry": startup.get("market"),
            "stage": startup.get("stage"),
            "survival_score": score.get("health_score"),
            "funding_readiness": score.get("funding_readiness"),
            "risk_count": score.get("risk_count"),
            "competitor_count": len(competitors) if isinstance(competitors, list) else 0,
            "created_at": row.get("created_at"),
        })

    return success_response(data=data)


@router.get("/recent", summary="Get recent reports")
async def recent_reports(limit: int = Query(10, ge=1, le=50), user=Depends(require_user)):
    data = report_service.get_recent(user.user.id, limit=limit)
    return success_response(data=data)


@router.get("/timeline", summary="Score timeline for authenticated user")
async def timeline(
    limit: int = Query(50, ge=1, le=200),
    user=Depends(require_user),
):
    data = report_service.get_timeline(user.user.id, limit=limit)
    return success_response(data=data)


@router.get("/{report_id}", summary="Get full report with startup + scores")
async def get_report(report_id: str, user=Depends(require_user)):
    data = report_service.get_full_report(report_id, user.user.id)
    if not data:
        raise HTTPException(status_code=404, detail=f"Report {report_id} not found or access denied")
    return success_response(data=data)


@router.get("/startup/{startup_id}", summary="Get all reports for a startup")
async def get_startup_reports(startup_id: str, user=Depends(require_user)):
    data = report_service.get_by_startup(startup_id, user.user.id)
    return paginated_response(data=data, total=len(data), page=1, page_size=len(data) or 1)
