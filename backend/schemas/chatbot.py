from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    analysis: Optional[dict[str, Any]] = None
    report_id: Optional[str] = None
    conversation_id: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    intent: str
    confidence: float
