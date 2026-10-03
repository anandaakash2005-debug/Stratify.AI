"""
routes/health.py — Liveness / readiness probes.
Judges and deployment systems ping GET /api/v1/health to verify the app is up.
"""

from fastapi import APIRouter
from datetime import datetime, timezone

from config.settings import settings

router = APIRouter()


@router.get("/health", summary="Health check")
async def health_check():
    return {
        "status":      "healthy",
        "service":     settings.APP_NAME,
        "version":     "1.0.0",
        "environment": settings.APP_ENV,
        "timestamp":   datetime.now(timezone.utc).isoformat(),
    }


@router.get("/health/ai", summary="AI service reachability check")
async def ai_health():
    """
    Pings OpenRouter with a minimal request to confirm AI connectivity.
    Useful for pre-demo checks.
    """
    from utils.openrouter_client import openrouter
    try:
        result = await openrouter.chat(
            user_prompt="Reply with the single word: OK",
            system_prompt="",
            json_mode=False,
            max_tokens=10,
        )
        return {
            "ai_status":  "reachable",
            "model":      result["model"],
            "response":   result["content"].strip(),
        }
    except Exception as exc:
        return {"ai_status": "unreachable", "error": str(exc)}
