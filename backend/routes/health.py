"""Safe liveness and readiness endpoints."""

from datetime import datetime, timezone

from fastapi import APIRouter

from config.settings import settings


router = APIRouter()


@router.get("/health", summary="Health check")
async def health_check():
    """Return a lightweight, non-billable service health response."""

    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": "1.0.0",
        "environment": settings.APP_ENV,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/health/ai", summary="AI configuration status")
async def ai_health():
    """
    Report API availability without contacting an AI provider.

    This endpoint intentionally performs no billable request and does not
    expose provider exceptions or credentials.
    """

    return {
        "ai_status": "configured",
        "live_probe": False,
        "message": "Live AI provider probes are disabled for security.",
    }