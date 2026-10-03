from fastapi import APIRouter, Depends, HTTPException, Query
import logging

from auth.dependencies import require_user
from ml.mentor_service import recommend_mentors

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "/recommend",
    summary="Recommend mentors",
    description="Find top mentor matches based on industry, startup stage, and problem description.",
)
async def recommend(
    industry: str = Query(..., description="Startup industry (e.g. AI, FinTech, HealthTech)"),
    stage: str = Query(..., description="Startup stage (e.g. Pre-Seed, Seed, Series A)"),
    problem: str = Query(..., description="Problem or area needing mentorship (e.g. Fundraising, Product Strategy)"),
    top_k: int = Query(5, ge=1, le=20, description="Number of mentor recommendations"),
    user=Depends(require_user),
):
    try:
        results = recommend_mentors(industry, stage, problem, top_k=top_k)
        return {
            "query": {"industry": industry, "stage": stage, "problem": problem},
            "mentors": results,
        }
    except Exception as e:
        logger.exception("Mentor recommendation failed")
        raise HTTPException(status_code=500, detail=str(e))
