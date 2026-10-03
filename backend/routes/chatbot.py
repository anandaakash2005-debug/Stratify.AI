from fastapi import APIRouter, Depends, HTTPException, Request
import logging

from auth.dependencies import require_user
from auth.rate_limit import limiter
from config.settings import settings
from schemas.chatbot import ChatRequest, ChatResponse
from services.chatbot_service import chat
from services.chat_history_service import get_chat_history, get_chat_summaries

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/chat", summary="Chat with startup intelligence assistant")
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
async def chat_endpoint(
    request: Request,
    payload: ChatRequest,
    user=Depends(require_user),
) -> ChatResponse:
    logger.info("Chat request received (intent classification pending)")
    try:
        result = await chat(
            payload.message,
            payload.analysis,
            user_id=user.user.id,
            report_id=payload.report_id,
        )
        return ChatResponse(**result)
    except Exception as exc:
        logger.exception("Chat error: %s", exc)
        raise HTTPException(status_code=500, detail="Chat processing failed") from exc


@router.get("/history", summary="Get chat history summaries for sidebar")
async def history_endpoint(
    user=Depends(require_user),
):
    user_id = user.user.id
    summaries = await get_chat_summaries(user_id=user_id)
    return {"history": summaries}


@router.get("/history/raw", summary="Get raw chat messages")
async def history_raw_endpoint(
    user=Depends(require_user),
):
    user_id = user.user.id
    history = await get_chat_history(user_id=user_id)
    return {"history": history}
