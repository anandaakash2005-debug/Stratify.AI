"""
backend/services/mentor_service.py
GenFusion AI Startup Mentor Chatbot Service

Responsibilities:
  - build_startup_context()
  - get_latest_report() / get_report_by_id()
  - get_welcome_payload()
  - get_chat_history()
  - save_chat_message()
  - generate_response() / generate_response_stream()
  - detect_intent()
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, AsyncGenerator

from supabase import Client

from prompts.mentor_prompt import (
    CONTEXT_TEMPLATE,
    FALLBACK_RESPONSE,
    INTENT_KEYWORDS,
    SYSTEM_PROMPT,
    WELCOME_MESSAGE,
    WELCOME_MESSAGE_NO_CONTEXT,
)
from ml.chatbot_intent_service import chatbot_intent_classifier
from services.chatbot_service import CHATBOT_STRUCTURED_PROMPT
from utils.openrouter_client import openrouter, safe_json_parse
from ml.mentor_service import recommend_mentors

logger = logging.getLogger(__name__)

CHAT_HISTORY_LIMIT = 20
CHAT_TEMPERATURE = 0.3
CHAT_MAX_TOKENS = 450


# ══════════════════════════════════════════════════════════════════════════════
# 1. build_startup_context
# ══════════════════════════════════════════════════════════════════════════════

def build_startup_context(report: dict[str, Any]) -> dict[str, Any]:
    if not report:
        logger.warning("build_startup_context received empty report")
        return _empty_context()

    ai: dict[str, Any] = report.get("raw_ai_response") or report
    metrics: dict[str, Any] = ai.get("metrics") or {}
    startup: dict[str, Any] = ai.get("startup") or report.get("startup") or {}
    swot: dict[str, Any] = ai.get("swot") or {}
    risks: list[dict] = ai.get("risks") or []
    recs: list[Any] = ai.get("recommendations") or []

    top_risks: list[str] = []
    for r in risks[:3]:
        if isinstance(r, dict):
            desc = r.get("description") or r.get("category") or ""
            if desc:
                top_risks.append(str(desc))
        elif isinstance(r, str):
            top_risks.append(r)

    strengths: list[str] = _safe_list(swot.get("strengths"))
    weaknesses: list[str] = _safe_list(swot.get("weaknesses"))

    rec_titles: list[str] = []
    for rec in recs[:5]:
        if isinstance(rec, dict):
            title = rec.get("title") or rec.get("description") or ""
            if title:
                rec_titles.append(str(title))
        elif isinstance(rec, str):
            rec_titles.append(rec)

    survival_score = _safe_int(metrics.get("survival_score"))
    funding_readiness = _safe_int(metrics.get("funding_readiness"))
    runway_months = _safe_int(metrics.get("runway_months"))

    revenue_raw = startup.get("monthly_revenue") or ai.get("financial_health", {}).get("mrr") or "not provided"
    burn_raw = startup.get("monthly_burn") or ai.get("financial_health", {}).get("burn") or "not provided"

    startup_name = (
        startup.get("name")
        or ai.get("idea")
        or report.get("startup_name")
        or "Your Startup"
    )

    industry = startup.get("industry") or ai.get("industry") or report.get("industry") or "Unknown"
    stage = startup.get("stage") or ai.get("stage") or report.get("stage") or "Unknown"

    urgent_flag = None
    if survival_score is not None:
        if survival_score < 35:
            urgent_flag = (
                "Urgent: Very Low Survival Score\n\n"
                f"Your survival score of {survival_score}/100 is critically low. "
                "Focus on reducing burn rate, validating product-market fit, and securing near-term revenue."
            )
        elif survival_score < 50:
            urgent_flag = (
                "Attention Needed\n\n"
                f"Your survival score of {survival_score}/100 is below average. "
                "Consider tightening expenses and accelerating your go-to-market strategy."
            )
        elif survival_score >= 80:
            urgent_flag = (
                "On Track\n\n"
                f"Your survival score of {survival_score}/100 looks strong. "
                "Keep executing and look for growth opportunities."
            )
        else:
            urgent_flag = (
                "Keep Monitoring\n\n"
                f"Your survival score is {survival_score}/100. "
                "Stay focused on your metrics and address medium-level risks proactively."
            )

    return {
        "startup_name": str(startup_name),
        "industry": industry,
        "stage": stage,
        "survival_score": survival_score,
        "funding_readiness": funding_readiness,
        "runway_months": runway_months,
        "mrr": str(revenue_raw),
        "burn": str(burn_raw),
        "monthly_revenue": str(revenue_raw),
        "monthly_burn": str(burn_raw),
        "growth": str(startup.get("revenue_growth") or ai.get("revenue_growth") or "not provided"),
        "customers": str(startup.get("customers") or ai.get("customers") or "not provided"),
        "churn": str(startup.get("churn_rate") or ai.get("churn_rate") or "not provided"),
        "top_risks": top_risks,
        "strengths": strengths[:5],
        "weaknesses": weaknesses[:5],
        "recommendations": rec_titles,
        "urgent_flag": urgent_flag,
    }


# ══════════════════════════════════════════════════════════════════════════════
# 2. Report lookup
# ══════════════════════════════════════════════════════════════════════════════

def _resolve_report_id(report: dict[str, Any] | None) -> str | None:
    """Return the canonical report_id from a report dict."""
    if not report:
        return None
    return report.get("report_id") or report.get("id")


def get_latest_report(supabase: Client, user_id: str) -> dict[str, Any] | None:
    """
    Get the latest report for a user.
    Ownership chain: auth user -> public.users -> startups.user_id -> reports.startup_id
    """
    try:
        # First get startups belonging to this user
        startups_result = (
            supabase
            .table("startups")
            .select("id")
            .eq("user_id", user_id)
            .execute()
        )
        startup_ids = [s["id"] for s in (startups_result.data or [])]

        if not startup_ids:
            logger.info("get_latest_report: user=%s no startups found", user_id)
            return None

        # Then get the latest report from those startups
        result = (
            supabase
            .table("reports")
            .select("*")
            .in_("startup_id", startup_ids)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        report = (result.data or [None])[0]
        if report:
            rid = _resolve_report_id(report)
            logger.debug("get_latest_report: user=%s report_id=%s", user_id, rid)
        else:
            logger.info("get_latest_report: user=%s no reports found", user_id)
        return report
    except Exception as exc:
        logger.error("get_latest_report failed user=%s: %s", user_id, exc, exc_info=True)
        return None


def get_report_by_id(supabase: Client, report_id: str) -> dict[str, Any] | None:
    try:
        result = (
            supabase
            .table("reports")
            .select("*")
            .eq("id", report_id)
            .limit(1)
            .execute()
        )
        report = (result.data or [None])[0]
        if report:
            logger.debug("get_report_by_id: report_id=%s found", report_id)
        else:
            logger.warning("get_report_by_id: report_id=%s not found", report_id)
        return report
    except Exception as exc:
        logger.error("get_report_by_id failed id=%s: %s", report_id, exc, exc_info=True)
        return None


# ══════════════════════════════════════════════════════════════════════════════
# 3. get_welcome_payload
# ══════════════════════════════════════════════════════════════════════════════

def _get_survival_label(score: int) -> str:
    if score >= 80:
        return "Strong"
    if score >= 60:
        return "Moderate"
    if score >= 40:
        return "Fragile"
    return "Critical"


def get_welcome_payload(
    user: dict[str, Any],
    report: dict[str, Any] | None,
) -> dict[str, Any]:
    user_name: str = (user or {}).get("name") or "Founder"

    if report:
        ctx = build_startup_context(report)

        try:
            message = WELCOME_MESSAGE.format(
                user_name=user_name,
                startup_name=ctx.get("startup_name", "your startup"),
                survival_score=ctx.get("survival_score", 0),
                survival_label=_get_survival_label(ctx.get("survival_score", 0)),
                funding_readiness=ctx.get("funding_readiness", 0),
                runway_months=ctx.get("runway_months", 0),
                urgent_flag=ctx.get("urgent_flag", "Keep monitoring your metrics."),
            )
        except KeyError as exc:
            logger.warning("WELCOME_MESSAGE format error: %s", exc)
            message = WELCOME_MESSAGE

        suggestions = [
            "How can I improve my survival score?",
            "What are my biggest risks right now?",
            "Am I ready to raise funding?",
            "How do I extend my runway?",
            "Who are my main competitors?",
        ]
    else:
        try:
            message = WELCOME_MESSAGE_NO_CONTEXT.format(user_name=user_name)
        except KeyError as exc:
            logger.warning("WELCOME_MESSAGE_NO_CONTEXT format error: %s", exc)
            message = WELCOME_MESSAGE_NO_CONTEXT

        suggestions = [
            "How do I find product-market fit?",
            "What metrics matter most for early-stage startups?",
            "How should I think about burn rate?",
            "When should I start fundraising?",
            "How do I build a strong founding team?",
        ]

    logger.info("get_welcome_payload: has_report=%s user=%s", bool(report), user_name)
    return {"message": message, "suggestions": suggestions}


# ══════════════════════════════════════════════════════════════════════════════
# 4. get_chat_history
# ══════════════════════════════════════════════════════════════════════════════

def get_chat_history(supabase: Client, user_id: str) -> list[dict[str, Any]]:
    try:
        result = (
            supabase
            .table("chat_history")
            .select("id, user_id, message, response, intent, confidence, report_id, created_at")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(CHAT_HISTORY_LIMIT)
            .execute()
        )
        rows: list[dict] = result.data or []
        logger.info("get_chat_history: user=%s rows=%d", user_id, len(rows))
        return rows
    except Exception as exc:
        logger.error("get_chat_history failed user=%s: %s", user_id, exc, exc_info=True)
        return []


# ══════════════════════════════════════════════════════════════════════════════
# 5. save_chat_message
# ══════════════════════════════════════════════════════════════════════════════

def save_chat_message(
    supabase: Client,
    *,
    user_id: str,
    message: str,
    response: str,
    intent: str = "general_query",
    confidence: float = 0.0,
    report_id: str | None = None,
) -> dict[str, Any] | None:
    row = {
        "user_id": user_id,
        "message": str(message)[:4000],
        "response": str(response)[:8000],
        "intent": str(intent),
        "confidence": round(float(confidence), 4),
        "report_id": report_id,
    }

    try:
        result = supabase.table("chat_history").insert(row).execute()
        inserted = (result.data or [{}])[0]
        logger.info(
            "save_chat_message: id=%s user=%s intent=%s report_id=%s",
            inserted.get("id"), user_id, intent, report_id,
        )
        return inserted
    except Exception as exc:
        logger.error("save_chat_message failed user=%s intent=%s: %s", user_id, intent, exc, exc_info=True)
        return None


# ══════════════════════════════════════════════════════════════════════════════
# 6. Message building (shared by both response functions)
# ══════════════════════════════════════════════════════════════════════════════

def _build_messages(
    user_message: str,
    startup_context: dict[str, Any] | None,
    chat_history: list[dict[str, Any]] | None = None,
    verified_mentors: list[dict[str, Any]] | None = None,
) -> list[dict[str, str]]:
    """Build the messages array for the OpenRouter call."""
    context_block = ""
    if startup_context:
        try:
            context_block = CONTEXT_TEMPLATE.format(
                startup_name=startup_context.get("startup_name", "Unknown"),
                industry=startup_context.get("industry", "Unknown"),
                stage=startup_context.get("stage", "Unknown"),
                survival_score=startup_context.get("survival_score", "N/A"),
                funding_readiness=startup_context.get("funding_readiness", "N/A"),
                runway_months=startup_context.get("runway_months", "N/A"),
                mrr=startup_context.get("mrr", 0),
                burn=startup_context.get("burn", 0),
                monthly_revenue=startup_context.get("monthly_revenue", "not provided"),
                monthly_burn=startup_context.get("monthly_burn", "not provided"),
                growth=startup_context.get("growth", "not provided"),
                customers=startup_context.get("customers", "not provided"),
                churn=startup_context.get("churn", "not provided"),
                top_risks=_format_list(startup_context.get("top_risks", [])),
                strengths=_format_list(startup_context.get("strengths", [])),
                weaknesses=_format_list(startup_context.get("weaknesses", [])),
                recommendations=_format_list(startup_context.get("recommendations", [])),
                verified_mentors=_format_verified_mentors(verified_mentors or []),
            )
        except KeyError as exc:
            logger.warning("CONTEXT_TEMPLATE format error: %s", exc)
            context_block = ""

    system_content = SYSTEM_PROMPT
    if context_block:
        system_content = f"{SYSTEM_PROMPT}\n\n{context_block}"
    else:
        system_content = SYSTEM_PROMPT.replace("{startup_context}", "No startup data available yet.")

    messages: list[dict[str, str]] = [{"role": "system", "content": system_content}]

    if chat_history:
        for turn in reversed(chat_history[:6]):
            if turn.get("message"):
                messages.append({"role": "user", "content": str(turn["message"])})
            if turn.get("response"):
                messages.append({"role": "assistant", "content": str(turn["response"])})

    messages.append({"role": "user", "content": str(user_message)})
    return messages


def _mentor_search_context(
    message: str,
    startup_context: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    context = startup_context or {}
    try:
        return recommend_mentors(
            str(context.get("industry") or "Technology"),
            str(context.get("stage") or "Seed"),
            message,
            top_k=5,
        )
    except Exception as exc:
        logger.warning("Verified mentor search failed: %s", type(exc).__name__)
        return []


def _format_verified_mentors(mentors: list[dict[str, Any]]) -> str:
    if not mentors:
        return "None found. Say: I couldn't find a verified mentor matching those criteria."
    lines = []
    for mentor in mentors:
        parts = [f"- {mentor.get('name')}"]
        if mentor.get('current_role'):
            parts.append(f"Role: {mentor.get('current_role')}")
        if mentor.get('organization'):
            parts.append(f"Organization: {mentor.get('organization')}")
        skills = mentor.get('skills', [])[:4]
        if skills:
            parts.append(f"Expertise: {', '.join(skills)}")
        if mentor.get('location'):
            parts.append(f"Location: {mentor.get('location')}")
        parts.append(f"ID: {mentor.get('id')}")
        # Only include contact fields if they exist in the verified record
        if mentor.get('email'):
            parts.append(f"Email: {mentor.get('email')}")
        if mentor.get('linkedin'):
            parts.append(f"LinkedIn: {mentor.get('linkedin')}")
        lines.append("; ".join(parts))
    return "\n".join(lines)


def _mentor_response_is_grounded(response: str, mentors: list[dict[str, Any]]) -> bool:
    if not mentors:
        return False
    response_lower = response.lower()
    approved = [str(mentor.get("name", "")).lower() for mentor in mentors]
    if not any(name and name in response_lower for name in approved):
        return False
    approved_text = _format_verified_mentors(mentors).lower()
    for employer in re.findall(r"\bat\s+([A-Z][\w&.-]*(?:\s+[A-Z][\w&.-]*){0,3})", response):
        if employer.lower().strip(" .,;:") not in approved_text:
            return False
    return True


def _verified_mentor_fallback(mentors: list[dict[str, Any]]) -> str:
    if not mentors:
        return "I couldn't find a verified mentor matching those criteria.\n\nYou can search categories such as FinTech compliance, B2B SaaS growth, fundraising, product-market fit, or financial operations."
    lines = ["### Verified mentor matches", ""]
    for mentor in mentors[:5]:
        skills = ", ".join(mentor.get("skills", [])[:3]) or "expertise not provided"
        parts = [f"- **{mentor.get('name')}** — {mentor.get('current_role', 'Role not provided')}. Expertise: {skills}."]
        # Only add contact info if it exists in the verified record
        if mentor.get('email'):
            parts.append(f" Email: {mentor.get('email')}")
        if mentor.get('linkedin'):
            parts.append(f" LinkedIn: {mentor.get('linkedin')}")
        lines.append("".join(parts))
    lines.extend(["", "**Next step:** Choose one verified profile and review its stored expertise before reaching out."])
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# 7. generate_response (non-streaming)
# ══════════════════════════════════════════════════════════════════════════════

async def generate_response(
    user_message: str,
    startup_context: dict[str, Any] | None,
    *,
    chat_history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    intent, confidence = detect_intent(user_message)
    logger.info("generate_response: intent=%s confidence=%.2f", intent, confidence)

    verified_mentors = _mentor_search_context(user_message, startup_context) if intent == "mentor_recommendation" else []
    messages = _build_messages(user_message, startup_context, chat_history, verified_mentors)

    try:
        result = await openrouter.chat(
            user_prompt=user_message,
            system_prompt="",
            max_tokens=CHAT_MAX_TOKENS,
            temperature=CHAT_TEMPERATURE,
            json_mode=False,
            messages=messages,
        )
        content = result.get("content", FALLBACK_RESPONSE)
        return {"response": content, "intent": intent, "confidence": confidence}

    except RuntimeError as exc:
        logger.error("generate_response OpenRouter error: %s", exc)
        return _fallback_payload(intent, confidence)


# ══════════════════════════════════════════════════════════════════════════════
# 8. generate_response_stream (SSE)
# ══════════════════════════════════════════════════════════════════════════════

async def generate_response_stream(
    user_message: str,
    startup_context: dict[str, Any] | None,
    *,
    chat_history: list[dict[str, Any]] | None = None,
    use_structured: bool = False,
) -> AsyncGenerator[str, None]:
    """
    Async generator that yields SSE event strings for the mentor chat.

    The caller (route) is responsible for collecting tokens and saving
    the completed chat.

    Event types (plain mode):
      {"type": "intent",       "intent": str, "confidence": float}
      {"type": "token",        "content": str}
      {"type": "error",        "message": str}

    Event types (structured mode):
      {"type": "intent",        "intent": str, "confidence": float}
      {"type": "structured",    "data": {...}}
      {"type": "error",         "message": str}
    """
    if use_structured:
        async for event in _structured_stream(user_message, startup_context, chat_history=chat_history):
            yield event
        return

    intent, confidence = detect_intent(user_message)
    logger.info("generate_response_stream: intent=%s confidence=%.2f", intent, confidence)

    yield f"data: {json.dumps({'type': 'intent', 'intent': intent, 'confidence': confidence})}\n\n"

    verified_mentors = _mentor_search_context(user_message, startup_context) if intent == "mentor_recommendation" else []
    messages = _build_messages(user_message, startup_context, chat_history, verified_mentors)

    try:
        if intent == "mentor_recommendation":
            result = await openrouter.chat(
                user_prompt="",
                messages=messages,
                json_mode=False,
                max_tokens=CHAT_MAX_TOKENS,
                temperature=CHAT_TEMPERATURE,
            )
            candidate = str(result.get("content") or "")
            reply = candidate if _mentor_response_is_grounded(candidate, verified_mentors) else _verified_mentor_fallback(verified_mentors)
            yield f"data: {json.dumps({'type': 'token', 'content': reply})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return
        async for token in openrouter.chat_stream(
            messages,
            max_tokens=CHAT_MAX_TOKENS,
            temperature=CHAT_TEMPERATURE,
        ):
            yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

    except RuntimeError as exc:
        logger.error("Stream error: %s", exc)
        yield f"data: {json.dumps({'type': 'error', 'message': FALLBACK_RESPONSE})}\n\n"
        return
    except Exception as exc:
        logger.error("Unexpected stream error: %s", exc, exc_info=True)
        yield f"data: {json.dumps({'type': 'error', 'message': FALLBACK_RESPONSE})}\n\n"
        return


async def _structured_stream(
    user_message: str,
    startup_context: dict[str, Any] | None,
    *,
    chat_history: list[dict[str, Any]] | None = None,
) -> AsyncGenerator[str, None]:
    """
    Structured SSE stream: uses ML intent classification + JSON-mode OpenRouter call.

    Yields:
      {"type": "intent",     "intent": str, "confidence": float}
      {"type": "structured", "data": {...}}
      {"type": "error",      "message": str}
    """
    # ── ML intent classification ──
    intent_result = chatbot_intent_classifier.predict(user_message)
    intent = intent_result["intent"]
    confidence = intent_result["confidence"]
    source = intent_result.get("source", "ml")

    if confidence < 0.60 and source != "keyword":
        intent = "founder_copilot"

    logger.info(
        "Structured stream: intent=%s confidence=%.2f source=%s",
        intent, confidence, source,
    )

    yield f"data: {json.dumps({'type': 'intent', 'intent': intent, 'confidence': confidence})}\n\n"

    # ── Build context block ──
    context_block = ""
    if startup_context:
        try:
            context_block = CONTEXT_TEMPLATE.format(
                startup_name=startup_context.get("startup_name", "Unknown"),
                industry=startup_context.get("industry", "Unknown"),
                stage=startup_context.get("stage", "Unknown"),
                survival_score=startup_context.get("survival_score", "N/A"),
                funding_readiness=startup_context.get("funding_readiness", "N/A"),
                runway_months=startup_context.get("runway_months", "N/A"),
                mrr=startup_context.get("mrr", "not provided"),
                burn=startup_context.get("burn", "not provided"),
                monthly_revenue=startup_context.get("monthly_revenue", "not provided"),
                monthly_burn=startup_context.get("monthly_burn", "not provided"),
                growth=startup_context.get("growth", "not provided"),
                customers=startup_context.get("customers", "not provided"),
                churn=startup_context.get("churn", "not provided"),
                top_risks=_format_list(startup_context.get("top_risks", [])),
                strengths=_format_list(startup_context.get("strengths", [])),
                weaknesses=_format_list(startup_context.get("weaknesses", [])),
                recommendations=_format_list(startup_context.get("recommendations", [])),
                verified_mentors="None provided",
            )
        except KeyError as exc:
            logger.warning("CONTEXT_TEMPLATE format error in structured stream: %s", exc)

    system_content = CHATBOT_STRUCTURED_PROMPT
    if context_block:
        system_content = f"{CHATBOT_STRUCTURED_PROMPT}\n\n=== STARTUP DATA ===\n{context_block}"

    messages: list[dict[str, str]] = [{"role": "system", "content": system_content}]

    if chat_history:
        for turn in reversed(chat_history[:6]):
            if turn.get("message"):
                messages.append({"role": "user", "content": str(turn["message"])})
            if turn.get("response"):
                messages.append({"role": "assistant", "content": str(turn["response"])})

    messages.append({"role": "user", "content": user_message})

    # ── Call OpenRouter with json_mode ──
    try:
        result = await openrouter.chat(
            user_prompt="",
            messages=messages,
            json_mode=True,
            max_tokens=CHAT_MAX_TOKENS,
            temperature=CHAT_TEMPERATURE,
        )
        raw = result["content"]
        parsed = safe_json_parse(raw)

        headline = (parsed.get("headline") or "").strip()
        summary = (parsed.get("summary") or "").strip()
        raw_insights = [str(i) for i in (parsed.get("insights") or []) if i]
        action_items = [str(a) for a in (parsed.get("action_items") or []) if a]
        follow_up = (parsed.get("follow_up") or "").strip()
        raw_metrics = parsed.get("metrics") or {}

        # Build plain-text reply for backward compat / deep-dive
        parts = [headline, summary]
        if raw_insights:
            parts.append("Key Insights:\n" + "\n".join(f"• {i}" for i in raw_insights))
        if action_items:
            parts.append("Actions:\n" + "\n".join(f"☐ {a}" for a in action_items))
        if follow_up:
            parts.append(follow_up)
        reply = "\n\n".join(p for p in parts if p)

        structured_data = {
            "type": "startup_mentor",
            "headline": headline,
            "summary": summary,
            "metrics": raw_metrics if isinstance(raw_metrics, dict) else {},
            "insights": raw_insights,
            "action_items": action_items,
            "follow_up": follow_up,
            "reply": reply,
            "intent": intent,
            "confidence": confidence,
            "suggested_questions": _structured_suggestions(intent),
        }

        yield f"data: {json.dumps({'type': 'structured', 'data': structured_data})}\n\n"

    except Exception as exc:
        logger.error("Structured stream error: %s", exc, exc_info=True)
        yield f"data: {json.dumps({'type': 'error', 'message': FALLBACK_RESPONSE})}\n\n"


def _structured_suggestions(intent: str) -> list[str]:
    """Return suggested questions matching the chatbot's intent list."""
    questions = {
        "runway_analysis": ["How do I extend my runway?", "What is a healthy burn rate?", "Should I raise money?"],
        "funding_readiness": ["Improve my investor deck", "What metrics matter to VCs?", "How do I find investors?"],
        "risk_assessment": ["How do I mitigate my top risk?", "What risks should I prioritize?", "Analyze my threats"],
        "competitive_intelligence": ["How do I differentiate?", "Who is my biggest threat?", "Market positioning tips"],
        "growth_strategy": ["Best growth channels for my stage", "How do I improve retention?", "Scaling playbook"],
        "burn_rate_analysis": ["How do I reduce burn?", "What is a healthy burn multiple?", "Extend runway tips"],
        "execution_readiness": ["What am I missing?", "How do I improve execution?", "Team gaps to fill"],
        "investor_readiness": ["Fix my cap table", "Prepare data room", "What do investors ask?"],
        "market_timing": ["Is now the right time?", "How do I test demand?", "Launch strategy"],
        "market_validation": ["How do I validate faster?", "PMF survey questions", "Find early adopters"],
        "startup_action_plan": ["Top priority this month", "30-60-90 day roadmap", "What am I missing?"],
        "startup_health": ["How do I improve survival?", "Weakest metric analysis", "Health improvement plan"],
        "startup_prediction": ["How do I improve odds?", "What metric predicts success?", "Benchmark vs peers"],
        "swot_analysis": ["How do I leverage strengths?", "Fix my weaknesses", "Capitalize on opportunities"],
        "team_health": ["Key hires to make", "Founder alignment tips", "Culture building advice"],
        "traction_analysis": ["How do I accelerate growth?", "Traction benchmarks", "Improve activation rate"],
        "founder_copilot": ["Improve funding readiness", "Analyze my risks", "Growth plan", "Competitor analysis"],
        "mentor_recommendation": ["Find a mentor for fundraising", "Show me AI startup mentors", "Who can help with product strategy?", "Recommend a growth mentor"],
    }
    return questions.get(intent, questions["founder_copilot"])


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def detect_intent(message: str) -> tuple[str, float]:
    text = message.lower()
    scores: dict[str, int] = {}

    for intent, keywords in INTENT_KEYWORDS.items():
        hit = sum(1 for kw in keywords if kw.lower() in text)
        if hit:
            scores[intent] = hit

    if not scores:
        return "general_query", 0.5

    best_intent = max(scores, key=lambda k: scores[k])
    total_keywords = len(INTENT_KEYWORDS.get(best_intent, [1]))
    confidence = round(min(scores[best_intent] / max(total_keywords, 1), 1.0), 2)
    confidence = max(confidence, 0.6)

    return best_intent, confidence


def _fallback_payload(intent: str, confidence: float) -> dict[str, Any]:
    return {"response": FALLBACK_RESPONSE, "intent": intent, "confidence": confidence}


def _empty_context() -> dict[str, Any]:
    return {
        "startup_name": "Unknown",
        "industry": "Unknown",
        "stage": "Unknown",
        "survival_score": 0,
        "funding_readiness": 0,
        "runway_months": 0,
        "mrr": 0,
        "burn": 0,
        "top_risks": [],
        "strengths": [],
        "weaknesses": [],
        "recommendations": [],
        "urgent_flag": None,
    }


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _parse_currency(value: Any) -> int:
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        cleaned = value.replace("$", "").replace(",", "").strip().upper()
        if cleaned.endswith("K"):
            try:
                return int(float(cleaned[:-1]) * 1000)
            except ValueError:
                pass
        try:
            return int(float(cleaned))
        except ValueError:
            pass
    return 0


def _safe_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item]
    return []


def _format_list(items: list[str]) -> str:
    if not items:
        return "None provided"
    return "\n".join(f"  \u2022 {item}" for item in items)
