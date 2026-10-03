"""routes/mentor.py — AI Startup Mentor endpoints"""

from __future__ import annotations

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from auth.dependencies import require_user
from database.client import get_client
from schemas.mentor import MentorChatRequest, MentorResponse
from services.mentor_service import (
    build_startup_context,
    get_chat_history,
    get_latest_report,
    get_report_by_id,
    get_welcome_payload,
    generate_response_stream,
    save_chat_message,
)

logger = logging.getLogger(__name__)

router = APIRouter()


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    report_id: Optional[str] = None
    structured: bool = False


@router.post("/chat")
async def chat(body: ChatRequest, request: Request, user=Depends(require_user)):
    user_id = str(user.user.id) if hasattr(user, 'user') else str(user.id)
    supabase = get_client()

    # Resolve which report to use
    try:
        if body.report_id:
            report = get_report_by_id(supabase, body.report_id)
        else:
            report = get_latest_report(supabase, user_id)
        context = build_startup_context(report) if report else None
    except Exception as e:
        logger.error("Context load error: %s", e)
        context = None

    try:
        history = get_chat_history(supabase, user_id)
    except Exception as e:
        logger.error("History load error: %s", e)
        history = []

    async def event_stream():
        buffer: list[str] = []
        stream_failed = False
        structured_reply: str | None = None
        structured_intent: str = "general_query"
        structured_confidence: float = 0.0

        try:
            async for event in generate_response_stream(
                body.message,
                context,
                chat_history=history,
                use_structured=body.structured,
            ):
                # Forward the event to the client
                yield event

                # Collect content for persistence
                if event.startswith("data: "):
                    try:
                        parsed = json.loads(event[6:])
                        etype = parsed.get("type")
                        if etype == "token":
                            buffer.append(parsed.get("content", ""))
                        elif etype == "structured":
                            d = parsed.get("data", {})
                            structured_reply = d.get("reply", "")
                            structured_intent = d.get("intent", "general_query")
                            structured_confidence = d.get("confidence", 0.0)
                        elif etype == "error":
                            stream_failed = True
                    except (json.JSONDecodeError, IndexError):
                        pass

        except Exception as e:
            logger.error("Stream error in route: %s", e)
            yield f"data: {json.dumps({'type': 'error', 'message': 'The AI mentor is temporarily unavailable. Please try again.'})}\n\n"
            return

        if stream_failed:
            return

        # Determine response text + metadata to persist
        complete = structured_reply or "".join(buffer)

        intent_val = structured_intent
        conf_val = structured_confidence

        result = save_chat_message(
            supabase,
            user_id=user_id,
            message=body.message,
            response=complete,
            intent=intent_val,
            confidence=conf_val,
            report_id=_resolve_report_id(report) if report else body.report_id,
        )
        chat_id = result.get("id") if result else None
        yield f"data: {json.dumps({'type': 'done', 'chat_id': chat_id or ''})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )


def _resolve_report_id(report: dict | None) -> str | None:
    if not report:
        return None
    return report.get("report_id") or report.get("id")


@router.get("/context")
async def get_context(request: Request, user=Depends(require_user)):
    user_id = str(user.user.id) if hasattr(user, 'user') else str(user.id)
    try:
        report = get_latest_report(get_client(), user_id)
        ctx = build_startup_context(report) if report else None
        if not ctx:
            return {
                "has_context": False,
                "startup_name": None, "survival_score": None,
                "funding_readiness": None, "runway_months": None,
                "report_id": None,
            }
        report_id = _resolve_report_id(report)
        return {"has_context": True, "report_id": report_id, **ctx}
    except Exception as e:
        logger.error("Context error: %s", e)
        return {"has_context": False, "error": str(e)}


@router.get("/history")
async def get_history(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
    user=Depends(require_user),
):
    user_id = str(user.user.id) if hasattr(user, 'user') else str(user.id)
    rows = get_chat_history(get_client(), user_id)
    return {"history": rows[:limit], "count": len(rows[:limit])}


@router.get("/welcome")
async def get_welcome(request: Request, user=Depends(require_user)):
    user_id = str(user.user.id) if hasattr(user, 'user') else str(user.id)
    try:
        report = get_latest_report(get_client(), user_id)
    except Exception as e:
        logger.error("Welcome report load error: %s", e)
        report = None

    user_data = {"id": user_id, "name": getattr(user, "name", None)}
    return get_welcome_payload(user_data, report)


@router.delete("/history")
async def clear_history(request: Request, user=Depends(require_user)):
    user_id = str(user.user.id) if hasattr(user, 'user') else str(user.id)
    try:
        get_client().table("chat_history").delete().eq("user_id", user_id).execute()
        return {"success": True, "message": "Chat history cleared"}
    except Exception as e:
        logger.error("Clear history error: %s", e)
        raise HTTPException(status_code=500, detail="Failed to clear history")
