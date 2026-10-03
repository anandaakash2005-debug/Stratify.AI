"""
backend/services/chatbot_service.py — Context-aware Startup Chatbot.

Pipeline:
  Message → Intent Classifier → Confidence Guard
    ↓
  Load latest report (from payload or DB)
    ↓
  Build intent-specific context
    ↓
  Load last 10 chat messages for memory
    ↓
  OpenRouter with context + history
    ↓
  Parse {reply, action_items} from response
    ↓
  Save to chat_history → Return result
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from database.client import get_client, table
from ml.chatbot_intent_service import chatbot_intent_classifier
from ml.mentor_service import recommend_mentors
from services.chat_history_service import get_chat_history, save_chat_message
from utils.openrouter_client import openrouter, safe_json_parse

logger = logging.getLogger(__name__)

# ── Metrics counters ──
_openrouter_success = 0
_openrouter_failure = 0
_template_fallback_used = 0

CHAT_HISTORY_LIMIT = 5
CHAT_MAX_TOKENS = 800
CHAT_TEMPERATURE = 0.5

CHATBOT_STRUCTURED_PROMPT = """You are GenFusion AI Mentor. You are having a conversation with a founder. You are NOT writing reports.

OUTPUT JSON ONLY. No markdown, no tables, no explanations outside JSON.

Format:
{
  "headline": "Single most important insight — one punchy line",
  "summary": "2-3 sentence explanation grounded in the data",
  "insights": ["Key insight 1", "Key insight 2", "Key insight 3"],
  "action_items": ["Action 1", "Action 2", "Action 3"],
  "follow_up": "One follow-up question to keep the conversation going"
}

Rules:
- Ground every answer in the startup data provided below
- Never create markdown tables or executive summaries
- Never exceed 250 words total across all fields
- Maximum 3 insights, maximum 3 actions
- Always sound like a practical startup advisor
- If data is missing, say so and suggest what to look into
- Include relevant metric values (scores, runway months, revenue) in headline/summary when available"""

NO_REPORT_PROMPT = """You are GenFusion AI Mentor. The founder hasn't run an analysis yet.

OUTPUT JSON ONLY.

Give helpful general advice. Be encouraging. Suggest they run a startup analysis.

Format:
{
  "headline": "Single most important insight",
  "summary": "2-3 sentence explanation",
  "insights": ["Insight 1", "Insight 2"],
  "action_items": ["Action 1", "Action 2"],
  "follow_up": "One follow-up question"
}

Never exceed 200 words."""


# ══════════════════════════════════════════════════════════════════════════════
# 1. Report retrieval
# ══════════════════════════════════════════════════════════════════════════════

def _get_latest_report(user_id: str) -> dict[str, Any] | None:
    try:
        startup_result = (
            table("startups")
            .select("id")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        startup = (startup_result.data or [None])[0]
        if not startup:
            logger.info("get_latest_report: user=%s no startups found", user_id)
            return None
        startup_id = startup["id"]
        report_result = (
            table("reports")
            .select("*")
            .eq("startup_id", startup_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        report = (report_result.data or [None])[0]
        if report:
            logger.debug("get_latest_report: user=%s startup=%s report=%s", user_id, startup_id, report.get("id"))
        else:
            logger.info("get_latest_report: user=%s startup=%s no reports", user_id, startup_id)
        return report
    except Exception as exc:
        logger.error("get_latest_report failed user=%s: %s", user_id, exc)
        return None


def _resolve_report(report: dict[str, Any]) -> dict[str, Any]:
    ai = report.get("raw_ai_response") or report
    if isinstance(ai, str):
        try:
            ai = json.loads(ai)
        except (json.JSONDecodeError, TypeError):
            ai = report
    return ai


# ══════════════════════════════════════════════════════════════════════════════
# 2. Intent-specific context builders
# ══════════════════════════════════════════════════════════════════════════════

def _build_context(report_data: dict[str, Any], intent: str) -> str:
    data = _resolve_report(report_data)
    metrics = data.get("metrics") or {}
    startup = data.get("startup") or {}
    risks = data.get("risks") or []
    swot = data.get("swot") or {}
    funding = data.get("funding_readiness") or {}
    financial = data.get("financial_health") or {}
    market = data.get("market_analysis") or {}
    team = data.get("team_evaluation") or {}
    recs = data.get("recommendations") or []

    sections = {
        "runway_analysis": lambda: _fmt({
            "Runway (months)": metrics.get("runway_months"),
            "Monthly Burn": startup.get("monthly_burn") or financial.get("burn"),
            "Cash in Bank": startup.get("cash_in_bank"),
            "Monthly Revenue": startup.get("monthly_revenue") or financial.get("mrr"),
            "Burn Multiple": metrics.get("burn_multiple"),
            "Revenue Growth": startup.get("revenue_growth"),
        }),
        "funding_readiness": lambda: _fmt({
            "Funding Readiness": f"{metrics.get('funding_readiness', 'N/A')}/100",
            "Overall Score": funding.get("overall"),
            "Summary": funding.get("summary"),
            "Traction Score": f"{metrics.get('traction_score', 'N/A')}/100",
            "Team Score": f"{metrics.get('team_score', 'N/A')}/100",
            "Market Score": f"{metrics.get('market_score', 'N/A')}/100",
            "Monthly Revenue": startup.get("monthly_revenue") or financial.get("mrr"),
            "Revenue Growth": startup.get("revenue_growth"),
        }),
        "risk_assessment": lambda: _fmt_risks(risks) + "\n" + _fmt({
            "Risk Score": f"{metrics.get('risk_score', 'N/A')}/100",
            "Risk Count": metrics.get("risk_count"),
        }),
        "competitive_intelligence": lambda: _fmt({
            "Industry": startup.get("industry"),
            "Stage": startup.get("stage"),
            "Market TAM": market.get("tam"),
            "Market SAM": market.get("sam"),
            "Market Score": f"{metrics.get('market_score', 'N/A')}/100",
            "Positioning": data.get("executive_summary", {}).get("positioning"),
        }),
        "growth_strategy": lambda: _fmt({
            "Monthly Revenue": startup.get("monthly_revenue") or financial.get("mrr"),
            "Revenue Growth": startup.get("revenue_growth"),
            "Market TAM": market.get("tam"),
            "Market Score": f"{metrics.get('market_score', 'N/A')}/100",
            "Traction Score": f"{metrics.get('traction_score', 'N/A')}/100",
            "Product Score": f"{metrics.get('product_score', 'N/A')}/100",
        }),
        "burn_rate_analysis": lambda: _fmt({
            "Monthly Burn": startup.get("monthly_burn") or financial.get("burn"),
            "Monthly Revenue": startup.get("monthly_revenue") or financial.get("mrr"),
            "Cash in Bank": startup.get("cash_in_bank"),
            "Runway (months)": metrics.get("runway_months"),
            "Burn Multiple": metrics.get("burn_multiple"),
            "Gross Margin": financial.get("gross_margin"),
        }),
        "execution_readiness": lambda: _fmt({
            "Stage": startup.get("stage"),
            "Team Score": f"{metrics.get('team_score', 'N/A')}/100",
            "Product Score": f"{metrics.get('product_score', 'N/A')}/100",
            "Team Size": startup.get("team_size"),
            "Overview": data.get("executive_summary", {}).get("overview"),
        }),
        "investor_readiness": lambda: _fmt({
            "Funding Readiness": f"{metrics.get('funding_readiness', 'N/A')}/100",
            "Overall Score": funding.get("overall"),
            "Summary": funding.get("summary"),
            "Traction Score": f"{metrics.get('traction_score', 'N/A')}/100",
            "Team Score": f"{metrics.get('team_score', 'N/A')}/100",
            "Monthly Revenue": startup.get("monthly_revenue") or financial.get("mrr"),
            "Revenue Growth": startup.get("revenue_growth"),
        }),
        "market_timing": lambda: _fmt({
            "Industry": startup.get("industry"),
            "Stage": startup.get("stage"),
            "Market TAM": market.get("tam"),
            "Market SAM": market.get("sam"),
            "Market Projection": market.get("projection"),
            "Market Score": f"{metrics.get('market_score', 'N/A')}/100",
            "Product Score": f"{metrics.get('product_score', 'N/A')}/100",
        }),
        "market_validation": lambda: _fmt({
            "Industry": startup.get("industry"),
            "Stage": startup.get("stage"),
            "Market TAM": market.get("tam"),
            "Market SAM": market.get("sam"),
            "Product Score": f"{metrics.get('product_score', 'N/A')}/100",
            "Market Score": f"{metrics.get('market_score', 'N/A')}/100",
            "Overview": data.get("executive_summary", {}).get("overview"),
        }),
        "startup_action_plan": lambda: _fmt({
            "Survival Score": f"{metrics.get('survival_score', 'N/A')}/100",
            "Funding Readiness": f"{metrics.get('funding_readiness', 'N/A')}/100",
            "Runway (months)": metrics.get("runway_months"),
            "Risk Count": metrics.get("risk_count"),
            "Weaknesses": _safe_list(swot.get("weaknesses")),
            "Recommendations": _fmt_recs(recs),
        }),
        "startup_health": lambda: _fmt({
            "Survival Score": f"{metrics.get('survival_score', 'N/A')}/100",
            "Funding Readiness": f"{metrics.get('funding_readiness', 'N/A')}/100",
            "Financial Score": f"{metrics.get('financial_score', 'N/A')}/100",
            "Market Score": f"{metrics.get('market_score', 'N/A')}/100",
            "Team Score": f"{metrics.get('team_score', 'N/A')}/100",
            "Product Score": f"{metrics.get('product_score', 'N/A')}/100",
            "Traction Score": f"{metrics.get('traction_score', 'N/A')}/100",
            "Risk Score": f"{metrics.get('risk_score', 'N/A')}/100",
            "Runway (months)": metrics.get("runway_months"),
        }),
        "startup_prediction": lambda: _fmt({
            "Survival Score": f"{metrics.get('survival_score', 'N/A')}/100",
            "Survival Probability": f"{metrics.get('survival_probability', 'N/A')}%",
            "Funding Readiness": f"{metrics.get('funding_readiness', 'N/A')}/100",
            "Financial Score": f"{metrics.get('financial_score', 'N/A')}/100",
            "Market Score": f"{metrics.get('market_score', 'N/A')}/100",
            "Team Score": f"{metrics.get('team_score', 'N/A')}/100",
            "Traction Score": f"{metrics.get('traction_score', 'N/A')}/100",
            "Risk Score": f"{metrics.get('risk_score', 'N/A')}/100",
            "Runway (months)": metrics.get("runway_months"),
            "Revenue Growth": startup.get("revenue_growth"),
        }),
        "swot_analysis": lambda: (
            "Strengths: " + ", ".join(_safe_list(swot.get("strengths"))) + "\n"
            "Weaknesses: " + ", ".join(_safe_list(swot.get("weaknesses"))) + "\n"
            "Opportunities: " + ", ".join(_safe_list(swot.get("opportunities"))) + "\n"
            "Threats: " + ", ".join(_safe_list(swot.get("threats")))
        ),
        "team_health": lambda: _fmt({
            "Team Score": f"{metrics.get('team_score', 'N/A')}/100",
            "Team Size": startup.get("team_size"),
            "Stage": startup.get("stage"),
            "Overview": data.get("executive_summary", {}).get("overview"),
        }),
        "traction_analysis": lambda: _fmt({
            "Traction Score": f"{metrics.get('traction_score', 'N/A')}/100",
            "Monthly Revenue": startup.get("monthly_revenue") or financial.get("mrr"),
            "Revenue Growth": startup.get("revenue_growth"),
            "Product Score": f"{metrics.get('product_score', 'N/A')}/100",
            "Market Score": f"{metrics.get('market_score', 'N/A')}/100",
        }),
        "mentor_recommendation": lambda: _fmt({
            "Industry": startup.get("industry") or data.get("industry"),
            "Stage": startup.get("stage") or data.get("stage"),
            "Startup Name": startup.get("name") or data.get("idea"),
            "Survival Score": f"{metrics.get('survival_score', 'N/A')}/100",
            "Team Score": f"{metrics.get('team_score', 'N/A')}/100",
            "Funding Readiness": f"{metrics.get('funding_readiness', 'N/A')}/100",
        }),
        "founder_copilot": lambda: _fmt({
            "Startup Name": startup.get("name") or data.get("idea"),
            "Industry": startup.get("industry"),
            "Stage": startup.get("stage"),
            "Survival Score": f"{metrics.get('survival_score', 'N/A')}/100",
            "Funding Readiness": f"{metrics.get('funding_readiness', 'N/A')}/100",
            "Runway (months)": metrics.get("runway_months"),
            "Monthly Revenue": startup.get("monthly_revenue") or financial.get("mrr"),
            "Monthly Burn": startup.get("monthly_burn") or financial.get("burn"),
            "Risk Count": metrics.get("risk_count"),
            "Team Score": f"{metrics.get('team_score', 'N/A')}/100",
        }),
    }

    builder = sections.get(intent, sections["founder_copilot"])
    return builder()


def _fmt(items: dict[str, Any]) -> str:
    return "\n".join(
        f"{k}: {v}" for k, v in items.items() if v is not None and v != "N/A/100"
    )


def _fmt_risks(risks: list) -> str:
    lines = []
    for r in risks[:5]:
        if isinstance(r, dict):
            sev = r.get("severity", "medium").upper()
            cat = r.get("category", "Risk")
            desc = r.get("description", "")
            lines.append(f"[{sev}] {cat}: {desc}")
        elif isinstance(r, str):
            lines.append(f"[MEDIUM] Risk: {r}")
    return "\n".join(lines) if lines else "No risks identified."


def _fmt_recs(recs: list) -> str:
    items = []
    for r in recs[:5]:
        if isinstance(r, dict):
            title = r.get("title") or r.get("description") or ""
            if title:
                items.append(str(title))
        elif isinstance(r, str):
            items.append(r)
    return "\n".join(f"- {item}" for item in items) if items else "No recommendations."


def _safe_list(val: Any) -> list:
    if isinstance(val, list):
        return [str(v) for v in val if v]
    return []


# ══════════════════════════════════════════════════════════════════════════════
# 2b. Mentor Recommendation helpers
# ══════════════════════════════════════════════════════════════════════════════

def _extract_mentor_query(report: dict[str, Any] | None, message: str) -> tuple[str, str, str, dict[str, Any]]:
    """Extract industry, stage, problem, and rich context from report."""
    industry = "Technology"
    stage = "Seed"
    extra_context: dict[str, Any] = {}

    if report:
        data = _resolve_report(report)
        metrics = data.get("metrics") or {}
        startup = data.get("startup") or {}
        risks = data.get("risks") or []
        industry = startup.get("industry") or data.get("industry") or industry
        stage = startup.get("stage") or data.get("stage") or stage

        extra_context["survival_score"] = metrics.get("survival_score")
        extra_context["funding_readiness"] = metrics.get("funding_readiness")
        extra_context["runway_months"] = metrics.get("runway_months")
        extra_context["top_risks"] = [
            str(r.get("category") or r.get("description", "") if isinstance(r, dict) else r)
            for r in risks[:3]
        ]
        extra_context["startup_name"] = startup.get("name") or data.get("idea") or "your startup"

    return industry, stage, message, extra_context


def _format_mentor_response(
    mentors: list[dict],
    intent: str,
    confidence: float,
    industry: str,
    extra_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a premium structured chatbot response from mentor recommendation results."""
    ctx = extra_context or {}
    startup_name = ctx.get("startup_name", industry)

    if not mentors:
        return {
            "type": "mentor_recommendation",
            "headline": f"No mentors found for {startup_name}",
            "summary": f"We couldn't find mentors matching your {industry} profile. Try different keywords or browse our full directory.",
            "metrics": [],
            "mentors": [],
            "insights": ["Try broadening your industry or stage", "New mentors join every week — check back soon"],
            "action_items": ["Browse the full mentor directory", "Refine your search with different keywords"],
            "follow_up": "What specific challenge are you facing right now?",
            "reply": "No mentors found. Try a different search.",
            "intent": intent,
            "confidence": confidence,
            "suggested_questions": _suggested_questions(intent),
        }

    medal = ["🥇", "🥈", "🥉", "4.", "5."]
    headline = f"🎯 Best Mentors For {startup_name}"
    summary = f"Top {len(mentors)} mentors matched to your {industry} startup based on industry, stage, and needs."

    insights = [
        f"We found {len(mentors)} potential mentors tailored to your startup's profile",
    ]
    action_items = []
    metrics_list = []
    mentors_list = []

    for i, m in enumerate(mentors[:5]):
        name = m.get("name", "Mentor")
        role = m.get("current_role", "Entrepreneur")
        score = m.get("match_score", 0)
        skills = m.get("skills", [])[:3]
        mentor_industries = m.get("industry", [])
        bio = m.get("bio", "")
        rating = m.get("mentor_rating", 0)
        exits = m.get("successful_startups", 0)
        network = m.get("investor_network", False)
        exp = m.get("experience", 0)

        # Build a concise "why" from bio + skills
        why_parts = []
        if bio:
            short_bio = bio.split(".")[0].strip() if bio else ""
            if short_bio:
                why_parts.append(short_bio)
        if skills:
            why_parts.append(f"Expertise: {', '.join(skills)}")
        why = why_parts[0] if why_parts else f"Deep experience in {', '.join(mentor_industries[:2])}"

        badge = medal[i] if i < 3 else f"  {i+1}."

        insights.append(f"{badge} {name} — {role} ({', '.join(mentor_industries[:2])}) — {score}% match")
        action_items.append(f"Connect with {name} — {skills[0] if skills else 'mentorship'}")

        metrics_list.append({
            "label": name,
            "value": f"{score}%",
            "severity": _mentor_severity(score),
        })

        mentors_list.append({
            "rank": i + 1,
            "name": name,
            "role": role,
            "match_score": score,
            "industry": mentor_industries,
            "skills": skills,
            "why": why,
            "rating": rating,
            "successful_startups": exits,
            "investor_network": network,
            "experience": exp,
        })

    # Pick top pick
    top = mentors_list[0] if mentors_list else None
    if top:
        follow_up = f"📌 **Recommended Next Step** — Book a call with **{top['name']}** first.\n\n{top['why']}"
    else:
        follow_up = "Which mentor would you like to learn more about?"

    # Build plain-text reply for backward compat / deep-dive
    reply_parts = [f"🎯 Best Mentors For {startup_name}", summary]
    for i, m in enumerate(mentors[:5]):
        name = m.get("name", "Mentor")
        role = m.get("current_role", "Entrepreneur")
        score = m.get("match_score", 0)
        skills_list = m.get("skills", [])[:3]
        badge = medal[i] if i < 3 else f"{i+1}."
        reply_parts.append(
            f"\n{badge} {name} — {score}% Match\n"
            f"   {role}\n"
            f"   Skills: {', '.join(skills_list)}"
        )
    reply = "\n".join(reply_parts)
    if top:
        reply += f"\n\n📌 Book a call with {top['name']} first — best match for your profile."

    return {
        "type": "mentor_recommendation",
        "headline": headline,
        "summary": summary,
        "metrics": metrics_list,
        "mentors": mentors_list,
        "insights": insights,
        "action_items": action_items[:3],
        "follow_up": follow_up,
        "reply": reply,
        "intent": intent,
        "confidence": confidence,
        "suggested_questions": _suggested_questions(intent),
    }


def _mentor_severity(score: float) -> str:
    if score >= 85:
        return "green"
    elif score >= 70:
        return "yellow"
    return "red"


# ══════════════════════════════════════════════════════════════════════════════
# 3. Chat memory builder
# ══════════════════════════════════════════════════════════════════════════════

async def _build_memory(user_id: str) -> list[dict[str, str]]:
    try:
        history = await get_chat_history(user_id=user_id, limit=CHAT_HISTORY_LIMIT)
        turns = []
        for h in history[-CHAT_HISTORY_LIMIT:]:
            if h.get("message"):
                turns.append({"role": "user", "content": str(h["message"])[:500]})
            if h.get("response"):
                content = str(h["response"])[:500]
                turns.append({"role": "assistant", "content": content})
        return turns
    except Exception as exc:
        logger.warning("Failed to load chat history: %s", exc)
        return []


# ══════════════════════════════════════════════════════════════════════════════
# 4. Main chat function
# ══════════════════════════════════════════════════════════════════════════════

async def chat(
    message: str,
    analysis: Optional[dict[str, Any]] = None,
    user_id: Optional[str] = None,
    report_id: Optional[str] = None,
) -> dict[str, Any]:
    # ── Intent classification ──
    intent_result = chatbot_intent_classifier.predict(message)
    intent = intent_result["intent"]
    confidence = intent_result["confidence"]
    source = intent_result.get("source", "ml")

    if confidence >= 0.60:
        pass
    elif source == "keyword":
        pass
    else:
        intent = "founder_copilot"

    logger.info(
        "Chatbot Intent=%s Confidence=%.2f Source=%s User=%s",
        intent, confidence, source, user_id or "anon",
    )

    # ── Report loading ──
    report = None
    if analysis:
        report = analysis
        logger.debug("Chatbot user=%s using analysis payload for context", user_id)
    elif user_id:
        report = _get_latest_report(user_id)
        if report:
            logger.debug("Chatbot user=%s loaded latest report", user_id)
        else:
            logger.info("Chatbot user=%s no report found — new user flow", user_id)
    else:
        logger.info("Chatbot no user_id — anonymous chat")

    # ── Mentor recommendation routing (skip OpenRouter) ──
    if intent == "mentor_recommendation":
        industry, stage, problem, extra_context = _extract_mentor_query(report, message)
        try:
            mentors = recommend_mentors(industry, stage, problem, top_k=5)
        except Exception as exc:
            logger.warning("Mentor recommendation failed: %s — using fallback", exc)
            mentors = []
        response = _format_mentor_response(mentors, intent, confidence, industry, extra_context)
        if user_id:
            try:
                await save_chat_message(
                    user_id=user_id,
                    report_id=report_id,
                    message=message,
                    response=response["reply"],
                    intent=intent,
                    confidence=confidence,
                )
            except Exception as exc:
                logger.warning("Failed to persist chat message: %s", exc)
        return response

    # ── Build context ──
    has_report = report is not None
    if report:
        context = _build_context(report, intent)
        system_prompt = f"{CHATBOT_STRUCTURED_PROMPT}\n\n=== STARTUP DATA ===\n{context}"
    else:
        system_prompt = NO_REPORT_PROMPT

    logger.info(
        "Chatbot context has_report=%s intent=%s user=%s",
        has_report, intent, user_id or "anon",
    )

    # ── Build messages with chat memory ──
    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]

    if user_id:
        memory = await _build_memory(user_id)
        messages.extend(memory)

    messages.append({"role": "user", "content": message})

    # ── Context size monitoring ──
    total_chars = sum(len(m.get("content", "")) for m in messages)
    logger.info(
        "Chatbot prompt size messages=%d chars=%d intent=%s",
        len(messages), total_chars, intent,
    )

    # ── Call OpenRouter ──
    global _openrouter_success, _openrouter_failure, _template_fallback_used
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

        def _ensure_list(val, default=None):
            if isinstance(val, list):
                return [str(v) for v in val if v]
            return default or []

        headline = (parsed.get("headline") or "").strip()
        summary = (parsed.get("summary") or "").strip()
        raw_insights = _ensure_list(parsed.get("insights"))
        action_items = _ensure_list(parsed.get("action_items"))
        follow_up = (parsed.get("follow_up") or "").strip()
        raw_metrics = parsed.get("metrics") or {}

        # Build reply from structured fields for backward compat
        parts = [headline, summary]
        if raw_insights:
            parts.append("Key Insights:\n" + "\n".join(f"• {i}" for i in raw_insights))
        if action_items:
            parts.append("Actions:\n" + "\n".join(f"☐ {a}" for a in action_items))
        if follow_up:
            parts.append(follow_up)
        reply = "\n\n".join(p for p in parts if p)

        _openrouter_success += 1
    except Exception as exc:
        _openrouter_failure += 1
        _template_fallback_used += 1
        logger.warning(
            "OpenRouter chat failed — fallback used. success=%d failure=%d error=%s",
            _openrouter_success, _openrouter_failure, exc,
        )
        headline = ""
        summary = ""
        raw_insights = []
        action_items = []
        follow_up = ""
        raw_metrics = {}
        reply = _template_fallback(intent)

    # ── Build structured response ──
    response = {
        "type": "startup_mentor",
        "headline": headline if headline else "",
        "summary": summary if summary else "",
        "metrics": raw_metrics if isinstance(raw_metrics, dict) else {},
        "insights": raw_insights if raw_insights else [],
        "action_items": action_items if action_items else [],
        "follow_up": follow_up if follow_up else "",
        "reply": reply or _template_fallback(intent),
        "intent": intent,
        "confidence": confidence,
        "suggested_questions": _suggested_questions(intent),
    }

    # ── Persist ──
    if user_id:
        try:
            await save_chat_message(
                user_id=user_id,
                report_id=report_id,
                message=message,
                response=response["reply"],
                intent=intent,
                confidence=confidence,
            )
        except Exception as exc:
            logger.warning("Failed to persist chat message: %s", exc)

    return response


# ══════════════════════════════════════════════════════════════════════════════
# 5. Template fallback (used when OpenRouter fails)
# ══════════════════════════════════════════════════════════════════════════════

def _suggested_questions(intent: str) -> list[str]:
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


def get_metrics() -> dict[str, int]:
    """Return OpenRouter success/failure counters for observability."""
    return {
        "openrouter_success": _openrouter_success,
        "openrouter_failure": _openrouter_failure,
        "template_fallback_used": _template_fallback_used,
    }


def _template_fallback(intent: str) -> str:
    replies = {
        "founder_copilot": (
            "Hi! I'm your startup copilot. I can help with runway planning, "
            "funding readiness, risk assessment, competitive analysis, and more. "
            "Run a startup analysis and share the data so I can give you specific advice."
        ),
        "runway_analysis": (
            "I can analyze your runway with your financial data. "
            "Share your burn rate and cash position and I'll calculate your runway."
        ),
        "funding_readiness": (
            "Funding readiness covers traction, team, market, and unit economics. "
            "Share your analysis data and I'll walk you through each area."
        ),
        "risk_assessment": (
            "I can analyze your risks and help you prioritize them. "
            "Share your analysis data for a detailed breakdown."
        ),
        "competitive_intelligence": (
            "I can map your competitive landscape and identify opportunities. "
            "Share your market data and I'll compare your positioning."
        ),
        "growth_strategy": (
            "Growth strategy covers channels, acquisition, and scaling. "
            "Tell me about your business and I'll suggest tailored tactics."
        ),
        "burn_rate_analysis": (
            "Burn rate analysis looks at your monthly spend and efficiency. "
            "Share your financials and I'll help optimize your burn."
        ),
        "execution_readiness": (
            "Execution readiness measures your plan, team, and resources. "
            "Share your roadmap and I'll identify gaps."
        ),
        "investor_readiness": (
            "Investor readiness covers cap table, metrics, and story. "
            "Share your data and I'll tell you what's missing."
        ),
        "market_timing": (
            "Market timing is about launching at the right moment. "
            "Share your research and I'll assess the conditions."
        ),
        "market_validation": (
            "Market validation proves demand before building. "
            "Share your experiments and I'll help interpret signals."
        ),
        "startup_action_plan": (
            "I can build a 30-60-90 day action plan. "
            "Share your situation and priorities."
        ),
        "startup_health": (
            "Startup health covers runway, growth, team, and risk. "
            "Share your metrics for a full health assessment."
        ),
        "startup_prediction": (
            "I can estimate success probability based on key indicators. "
            "Share your data for a prediction."
        ),
        "swot_analysis": (
            "I can run a SWOT analysis covering strengths, weaknesses, "
            "opportunities, and threats. Share your context."
        ),
        "team_health": (
            "Team health evaluates your founding team, culture, and gaps. "
            "Share your structure and I'll identify what needs attention."
        ),
        "traction_analysis": (
            "Traction analysis looks at growth, engagement, and momentum. "
            "Share your metrics and I'll benchmark them."
        ),
        "mentor_recommendation": (
            "I can recommend mentors based on your industry, stage, and needs. "
            "Tell me more about your startup and what kind of guidance you're looking for."
        ),
    }
    return replies.get(intent, replies["founder_copilot"])
