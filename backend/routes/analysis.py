import logging
from fastapi import APIRouter, Depends, Request
from auth.dependencies import require_user
from auth.rate_limit import limiter
from config.settings import settings
from schemas.analysis import AnalysisRequest
from services.analysis_service import analyze_startup
from utils.response_formatter import success_response

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post('/')
@limiter.limit(settings.RATE_LIMIT_ANALYZE)
async def analyze(request: Request, payload: AnalysisRequest, user=Depends(require_user)):
    return await analyze_startup(payload.model_dump(exclude={'user_id'}), user,
                                 request.state.request_id, request.state.deadline)

@router.post('/quick')
@limiter.limit(settings.RATE_LIMIT_ANALYZE)
async def quick_score(request: Request, payload: AnalysisRequest, user=Depends(require_user)):
    result = await analyze(request, payload, user)
    return success_response(data={**{k: result['metrics'][k] for k in
        ('survival_score', 'survival_probability', 'funding_readiness')}, 'report_id': result['report_id']})
