"""
utils/scoring.py — THE single source of truth for every metric in the platform.
"""

from __future__ import annotations

import calendar
import math
import re
from datetime import datetime, timedelta
from typing import Any

from utils.response_formatter import (
    clamp,
    normalize_ai_response,
    to_float,
    to_int,
    to_str,
)

COHORT = {
    "median_mrr": 32_000,
    "median_burn": 45_000,
    "median_growth": 12.0,
    "median_runway": 14.0,
    "median_gross_margin": 68.0,
    "median_burn_multiple": 1.2,
    "median_cac_payback": 14.0,
    "label": "Illustrative scoring reference; not a verified cohort",
}

FX_TO_USD = {
    "USD": 1.0,
    "INR": 0.012,
    "EUR": 1.08,
    "GBP": 1.27,
    "AED": 0.272,
    "SGD": 0.74,
}
CURRENCY_SYMBOLS = {"USD": "$", "INR": "₹", "EUR": "€", "GBP": "£", "AED": "AED ", "SGD": "S$"}

WEIGHTS = {
    "financial": 0.25,
    "market": 0.20,
    "traction": 0.20,
    "team": 0.15,
    "product": 0.12,
    "risk": 0.08,
}


def _parse_currency(val: Any) -> float:
    if isinstance(val, (int, float)):
        return float(val)
    s = re.sub(r"[$,\s]", "", str(val or "0"))
    try:
        return float(s)
    except ValueError:
        return 0.0


def _currency_code(form: dict) -> str:
    code = str(form.get("currency") or "USD").upper().strip()
    return code if code in FX_TO_USD else "USD"


def burn_multiple(net_burn: float, net_new_arr: float) -> float:
    """Return net burn divided by net new ARR, the canonical SaaS definition."""
    if net_new_arr <= 0:
        return float("inf")
    return round(net_burn / net_new_arr, 2)


def compute_financial_metrics(form: dict) -> dict:
    currency = _currency_code(form)
    fx_rate = FX_TO_USD[currency]
    original_mrr = _parse_currency(form.get("monthly_revenue") or form.get("mrr", 0))
    original_burn = _parse_currency(form.get("monthly_burn") or form.get("burn_rate") or form.get("burn", 0))
    original_cash = _parse_currency(form.get("cash_in_bank") or form.get("cash_on_hand") or form.get("cash", 0))
    mrr = original_mrr * fx_rate
    burn = original_burn * fx_rate
    cash = original_cash * fx_rate

    raw_growth = form.get("revenue_growth") or form.get("growth", 0)
    growth = to_float(raw_growth)
    growth_pct = growth  # Form contract is percent, including values below 1%.

    net_burn = max(burn - mrr, 0)
    if net_burn > 0 and cash > 0:
        runway_months = round(cash / net_burn, 1)
    elif cash > 0 and net_burn == 0:
        runway_months = 0.0  # No finite runway; see runway_unbounded.
    else:
        runway_months = 0.0

    if mrr > 0 and growth_pct > 0 and burn > 0:
        try:
            n = math.log(burn / mrr) / math.log(1 + growth_pct / 100)
            if n > 0:
                break_even_month = (datetime.now() + timedelta(days=n * 30.44)).strftime("%b %Y")
            else:
                break_even_month = "Already profitable"
        except (ValueError, ZeroDivisionError):
            break_even_month = "—"
    else:
        break_even_month = "—"

    new_arr_monthly = (mrr - mrr / (1 + growth_pct / 100)) * 12 if growth_pct > 0 else 0
    burn_multiple_value = burn_multiple(net_burn, new_arr_monthly)

    gross_margin = to_float(form.get("gross_margin", 0))


    cac_payback = to_float(form.get("cac_payback", 0))


    return {
        "mrr": mrr,
        "burn": burn,
        "cash": cash,
        "currency": currency,
        "fx_rate_to_usd": fx_rate,
        "original_mrr": original_mrr,
        "original_burn": original_burn,
        "original_cash": original_cash,
        "net_burn": net_burn,
        "revenue_status": "revenue-generating" if mrr > 0 else "pre-revenue",
        "revenue_to_expense_ratio": round(mrr / burn, 3) if burn else None,
        "runway_unbounded": net_burn == 0,
        "burn_multiple_available": new_arr_monthly > 0,
        "input_completeness": round(sum(form.get(k) is not None and form.get(k) != "" for k in ("startup_name", "description", "industry", "stage", "monthly_burn", "monthly_revenue", "cash_in_bank")) / 7 * 100),
        "growth_pct": growth_pct,
        "runway_months": runway_months,
        "break_even_month": break_even_month,
        "burn_multiple": burn_multiple_value,
        "burn_multiple_display": burn_multiple_value if math.isfinite(burn_multiple_value) else None,
        "gross_margin": gross_margin,
        "cac_payback": cac_payback,
    }


def score_financial(ai: dict, fin: dict) -> int:
    s = 50
    runway, burn_m, growth, margin = (36 if fin["runway_unbounded"] else fin["runway_months"]), fin["burn_multiple"], fin["growth_pct"], fin["gross_margin"]
    if runway >= 18: s += 20
    elif runway >= 12: s += 10
    elif runway >= 9: s += 0
    elif runway >= 6: s -= 15
    else: s -= 25
    if not math.isfinite(burn_m): s -= 10
    elif burn_m <= 1.0: s += 10
    elif burn_m <= 1.5: s += 5
    elif burn_m <= 2.0: s += 0
    elif burn_m <= 3.0: s -= 5
    else: s -= 10
    if growth >= 25: s += 10
    elif growth >= 15: s += 5
    elif growth >= 10: s += 0
    elif growth >= 5: s -= 5
    else: s -= 10
    if margin >= 75: s += 5
    elif margin >= 65: s += 2
    else: s -= 3
    return clamp(s)


def score_market(ai: dict, form: dict) -> int:
    market_size = str(form.get("market_size") or form.get("tam", "")).lower()
    s = 50
    if "100b" in market_size or "trillion" in market_size: s = 90
    elif "10b" in market_size or "large" in market_size: s = 80
    elif "1b" in market_size or "medium" in market_size: s = 65
    elif "small" in market_size: s = 40
    return clamp(s)


def score_team(ai: dict, form: dict) -> int:
    s = 50
    experience = str(form.get("founder_experience", "")).lower()
    if "exit" in experience or "acquisition" in experience: s += 25
    elif "domain" in experience or "expert" in experience: s += 15
    elif "first" in experience or "new" in experience: s -= 5
    if form.get("has_cto") in (True, "yes", "Yes", "true", "1") or form.get("has_technical_cofounder"):
        s += 15
    team_size = str(form.get("team_size", ""))
    if any(x in team_size for x in ("6", "11", "15")): s += 5
    return clamp(s)


def score_product(ai: dict, form: dict) -> int:
    s = 55
    diff = str(form.get("differentiator") or form.get("competitive_advantages", "")).lower()
    if "proprietary" in diff or "patent" in diff or "ip" in diff: s += 20
    elif "technology" in diff or "tech" in diff: s += 12
    elif "network" in diff: s += 8
    return clamp(s)


def score_traction(ai: dict, form: dict, fin: dict) -> int:
    s = 45
    growth = fin["growth_pct"]
    stage = str(form.get("stage", "")).lower()
    if "revenue" in stage or "growth" in stage: s = 55
    elif "idea" in stage or "pre" in stage: s = 30
    if growth >= 30: s += 25
    elif growth >= 20: s += 15
    elif growth >= 12: s += 8
    elif growth >= 5: s += 0
    else: s -= 10
    return clamp(s)


def score_risk(ai: dict, risks: list[dict]) -> int:
    base = 80
    severity_penalty = {"critical": 15, "high": 8, "medium": 4, "low": 1}
    for r in risks:
        base -= severity_penalty.get(r.get("severity", "medium"), 4)
    return clamp(base)


def compute_survival_score(financial: int, market: int, team: int, product: int, traction: int, risk: int) -> int:
    composite = (
        financial * WEIGHTS["financial"] + market * WEIGHTS["market"] + traction * WEIGHTS["traction"]
        + team * WEIGHTS["team"] + product * WEIGHTS["product"] + risk * WEIGHTS["risk"]
    )
    return clamp(composite)


def compute_deterministic_scores(form: dict) -> dict:
    """Compute the score inputs passed to the narrator before any model call."""
    fin = compute_financial_metrics(form)
    selected_risks = form.get("risk_categories") or []
    scores = {
        "financial": score_financial({}, fin),
        "market": score_market({}, form),
        "team": score_team({}, form),
        "product": score_product({}, form),
        "traction": score_traction({}, form, fin),
        "risk": score_risk({}, [{"severity": "medium"} for _ in selected_risks]),
    }
    scores["survival_score"] = compute_survival_score(**scores)
    return {**scores, "runway_months": fin["runway_months"], "burn_multiple": fin["burn_multiple_display"]}


def compute_survival_probability(score: int) -> int:
    if score >= 85: return 92
    if score >= 75: return 82
    if score >= 65: return 68
    if score >= 55: return 54
    if score >= 45: return 40
    if score >= 35: return 27
    return 15


def compute_percentile(score: int) -> int:
    if score >= 80: return 10
    if score >= 70: return 28
    if score >= 60: return 45
    if score >= 50: return 60
    if score >= 40: return 75
    return 88


def compute_funding_readiness(ai: dict, fin: dict, form: dict, scores: dict) -> dict:
    overall = clamp(
        scores["traction"] * 0.25 + scores["team"] * 0.20 + scores["market"] * 0.20
        + scores["financial"] * 0.15 + 40 * 0.10 + 60 * 0.10
    )
    growth_pct, runway = fin["growth_pct"], (36 if fin["runway_unbounded"] else fin["runway_months"])
    traction_pct = clamp(int(scores["traction"] * 1.05))
    team_pct = clamp(int(scores["team"] * 1.05))
    market_pct = clamp(int(scores["market"] * 1.05))
    econ_pct = clamp(int(scores["financial"] * 0.90))
    materials_pct = clamp(ai.get("investor_materials_score", 40))
    social_pct = clamp(ai.get("social_proof_score", 60))
    traction_detail = f"{growth_pct:.0f}% MoM growth, enterprise customers, churn data"
    team_detail = to_str(form.get("founder_experience"), "Founding team profile")
    market_detail = f"TAM: {form.get('market_size', '—')}, growth rate, regulatory tailwinds"
    econ_detail = "CAC, LTV, gross margin, payback period"
    materials_detail = to_str(ai.get("investor_materials_note"), "Pitch deck, data room, case studies")
    social_detail = to_str(ai.get("social_proof_note"), "Testimonials, press, analyst mentions")
    runway_note = ""
    if runway < 9:
        runway_note = f"⚠️ Only {runway:.0f} months runway — fundraising is critical."
    elif runway < 12:
        runway_note = f"Runway is {runway:.0f} months — begin fundraising now."
    summary = to_str(ai.get("funding_readiness_summary"), "")
    if not summary:
        summary = (
            f"This startup is <strong>{overall}% funding-ready</strong> for a Seed or Seed-extension round. "
            + (runway_note if runway_note else "")
            + " Closing gaps in investor materials and unit economics documentation "
            + "can push readiness above 80% within 30 days."
        )
    bars = [
        {"name": "Traction Metrics", "detail": traction_detail, "pct": traction_pct, "color": "success"},
        {"name": "Team Strength", "detail": team_detail, "pct": team_pct, "color": "success"},
        {"name": "Market Timing", "detail": market_detail, "pct": market_pct, "color": "success"},
        {"name": "Unit Economics", "detail": econ_detail, "pct": econ_pct,
         "color": "warning" if econ_pct < 65 else "success"},
        {"name": "Investor Materials", "detail": materials_detail, "pct": materials_pct,
         "color": "danger" if materials_pct < 50 else "warning"},
        {"name": "Social Proof", "detail": social_detail, "pct": social_pct,
         "color": "warning" if social_pct < 65 else "success"},
    ]
    return {
        "overall": overall, "summary": summary,
        "traction_pct": traction_pct, "traction_detail": traction_detail,
        "team_pct": team_pct, "team_detail": team_detail,
        "market_pct": market_pct, "market_detail": market_detail,
        "econ_pct": econ_pct, "econ_detail": econ_detail,
        "materials_pct": materials_pct, "materials_detail": materials_detail,
        "social_pct": social_pct, "social_detail": social_detail,
        "bars": bars,
    }


def build_financial_health(fin: dict, form: dict, scores: dict) -> dict:
    mrr, burn, growth, runway = fin["mrr"], fin["burn"], fin["growth_pct"], fin["runway_months"]
    margin, bm, cac = fin["gross_margin"], fin["burn_multiple"], fin["cac_payback"]

    def fmt_currency(v: float) -> str:
        if v == 0: return "—"
        if v >= 1_000_000: return f"${v/1_000_000:.1f}M"
        if v >= 1_000: return f"${v:,.0f}"
        return f"${v:.0f}"

    symbol = CURRENCY_SYMBOLS.get(fin.get("currency", "USD"), fin.get("currency", "USD") + " ")

    def fmt_original(v: float) -> str:
        if v == 0: return "—"
        if v >= 1_000_000: return f"{symbol}{v/1_000_000:.1f}M"
        return f"{symbol}{v:,.0f}"

    def assess(val: float, good: float, warn: float, higher_is_better: bool = True) -> tuple[str, str]:
        if higher_is_better:
            if val >= good: return "▲ Above average", "var(--emerald)"
            if val >= warn: return "⚠ Below median", "var(--amber)"
            return "▼ Critical", "var(--rose)"
        if val <= good: return "▲ Efficient", "var(--emerald)"
        if val <= warn: return "⚠ Monitor", "var(--amber)"
        return "▼ High", "var(--rose)"

    runway_status, runway_color = assess(runway, 14, 9, True)
    burn_status, burn_color = assess(burn, COHORT["median_burn"], COHORT["median_burn"] * 1.2, False)
    bm_status, bm_color = assess(bm, 1.0, 1.5, False)

    rows = [
        {"metric": "Monthly Revenue (MRR)", "value": fmt_original(fin["original_mrr"]), "median": f"{symbol}32,000",
         "status": "▲ Above average" if mrr >= COHORT["median_mrr"] else "⚠ Below median",
         "color": "var(--emerald)" if mrr >= COHORT["median_mrr"] else "var(--amber)"},
        {"metric": "Monthly Burn Rate", "value": fmt_original(fin["original_burn"]), "median": f"{symbol}45,000",
         "status": burn_status, "color": burn_color},
        {"metric": "Revenue Growth (MoM)", "value": f"{growth:.0f}%", "median": "12%",
         "status": "▲ Excellent" if growth >= 20 else ("▲ Good" if growth >= 12 else "⚠ Below median"),
         "color": "var(--emerald)" if growth >= 12 else "var(--amber)"},
        {"metric": "Runway", "value": f"{runway:.0f} months", "median": "14 months",
         "status": runway_status, "color": runway_color},
        {"metric": "Gross Margin (est.)", "value": f"~{margin:.0f}%", "median": "68%",
         "status": "▲ Healthy" if margin >= 65 else "⚠ Monitor",
         "color": "var(--emerald)" if margin >= 65 else "var(--amber)"},
        {"metric": "Net Burn Multiple", "value": f"{bm:.2f}×" if math.isfinite(bm) else "Not applicable", "median": "1.2×",
         "status": bm_status, "color": bm_color},
        {"metric": "CAC Payback Period", "value": f"~{cac:.0f} months", "median": "14 months",
         "status": "▲ Above average" if cac <= COHORT["median_cac_payback"] else "⚠ Above median",
         "color": "var(--emerald)" if cac <= COHORT["median_cac_payback"] else "var(--amber)"},
    ]

    callout = ""
    if runway < 9:
        net = burn - mrr
        callout = (
            f"At current burn ({fmt_currency(burn)}/mo) and revenue ({fmt_currency(mrr)}/mo), "
            f"net monthly burn is {fmt_currency(net)}. With ~{fmt_currency(fin['cash'])} in estimated cash, "
            f"effective runway is approximately {runway:.0f} months — below the 12-month safety threshold. "
            f"Fundraising or a significant revenue increase is required within 90 days."
        )
    elif runway < 12:
        callout = (
            f"Runway of {runway:.0f} months is approaching the 12-month safety threshold. "
            f"Begin fundraising preparation now to avoid urgency compression."
        )

    return {
        "mrr": fmt_original(fin["original_mrr"]), "burn": fmt_original(fin["original_burn"]), "growth": f"{growth:.0f}%",
        "runway": f"{runway:.0f} months", "gross_margin": f"~{margin:.0f}%",
        "burn_multiple": f"{bm:.2f}×" if math.isfinite(bm) else "Not applicable", "cac_payback": f"~{cac:.0f} months",
        "callout": callout, "rows": rows,
    }


def build_market_analysis(ai: dict, form: dict) -> dict:
    tam = to_str(ai.get("tam") or ai.get("total_addressable_market") or form.get("market_size") or form.get("tam"), "—")
    sam = to_str(ai.get("sam") or ai.get("serviceable_addressable_market"), "—")
    projection = to_str(ai.get("market_projection") or ai.get("5_year_projection"), "—")
    tam_growth = to_str(ai.get("tam_growth") or ai.get("market_growth_rate"), "")
    analysis_text = to_str(ai.get("market_analysis") or ai.get("market_description"), "")
    callout = to_str(ai.get("market_callout") or ai.get("market_timing_note"), "")
    stats = [
        {"label": "Total Addressable Market", "value": tam,
         "change": f"▲ {tam_growth} YoY growth" if tam_growth else "▲ Market opportunity",
         "color": "gradient-text"},
        {"label": "Serviceable Market (SAM)", "value": sam, "change": "▲ Addressable segment", "color": "var(--cyan)"},
        {"label": "5-Year Growth Projection", "value": projection, "change": "▲ Expected expansion", "color": "var(--emerald)"},
    ]
    return {"tam": tam, "sam": sam, "projection": projection, "tam_growth": tam_growth,
            "analysis": analysis_text, "callout": callout, "stats": stats}


def build_executive_summary(ai, startup, industry, score, probability, percentile, risks, fin) -> dict:
    critical_risks = [r for r in risks if r.get("severity") == "critical"]
    risk_count = len(risks)
    overview = to_str(ai.get("executive_summary_overview") or ai.get("summary_overview"), "")
    if not overview:
        overview = (
            f"<strong>{startup}</strong> is operating in the <strong>{industry}</strong> market. "
            f"The company has demonstrated traction and achieved a Survival Score of "
            f"<strong>{score}/100</strong> based on AI analysis across 14 key signals."
        )
    positioning = to_str(ai.get("executive_summary_positioning") or ai.get("summary_positioning"), "")
    if not positioning:
        tier = "top" if percentile <= 35 else ("middle" if percentile <= 65 else "lower")
        positioning = (
            f"The overall Survival Score of <strong>{score}/100</strong> places {startup} "
            f"in the <strong>{tier} {percentile}th percentile</strong> of seed-stage SaaS/AI startups "
            f"in our benchmark cohort (n=847). The 12-month survival probability is estimated at "
            f"<strong>{probability}%</strong>."
        )
    risks_headline = to_str(ai.get("executive_summary_risks") or ai.get("summary_risks"), "")
    if not risks_headline and risk_count > 0:
        risks_headline = (
            f"The report identifies <strong>{risk_count} active risk{'s' if risk_count > 1 else ''}</strong> "
            f"requiring attention."
            + (f" <strong>{len(critical_risks)} critical</strong> risk(s) require immediate action." if critical_risks else "")
        )
    critical_callout = to_str(ai.get("critical_callout"), "")
    if not critical_callout and critical_risks:
        critical_callout = critical_risks[0].get("description", "")
    if not critical_callout and fin["runway_months"] < 12:
        critical_callout = (
            f"With {fin['runway_months']:.0f} months of runway remaining, the fundraising process "
            f"must begin immediately. Industry data shows Seed rounds average 4–6 months to close."
        )
    success_callout = to_str(ai.get("success_callout") or ai.get("strength_callout"), "")
    return {
        "overview": overview, "positioning": positioning, "risks_headline": risks_headline,
        "critical_callout": critical_callout, "success_callout": success_callout,
    }


def build_financial_signals(fin: dict) -> list[dict]:
    runway, growth, bm = fin["runway_months"], fin["growth_pct"], fin["burn_multiple"]
    return [
        {"label": "Runway", "value": f"{runway:.0f} mo", "benchmark": f"Median: {COHORT['median_runway']:.0f} mo",
         "status": "good" if runway >= 14 else ("warning" if runway >= 9 else "critical")},
        {"label": "Revenue Growth", "value": f"{growth:.0f}%/mo", "benchmark": f"Median: {COHORT['median_growth']:.0f}%",
         "status": "good" if growth >= 15 else ("warning" if growth >= 8 else "critical")},
        {"label": "Burn Multiple", "value": f"{bm:.2f}×", "benchmark": f"Median: {COHORT['median_burn_multiple']:.1f}×",
         "status": "good" if bm <= 1.0 else ("warning" if bm <= 2.0 else "critical")},
        {"label": "Gross Margin", "value": f"{fin['gross_margin']:.0f}%",
         "benchmark": f"Median: {COHORT['median_gross_margin']:.0f}%",
         "status": "good" if fin["gross_margin"] >= 65 else "warning"},
    ]


def _add_calendar_months(dt: datetime, months: int) -> datetime:
    """Shift dt by whole calendar months (day clamped to month length)."""
    y = dt.year + (dt.month - 1 + months) // 12
    m = (dt.month - 1 + months) % 12 + 1
    d = min(dt.day, calendar.monthrange(y, m)[1])
    return dt.replace(year=y, month=m, day=d)


def _month_label(dt: datetime) -> str:
    return dt.strftime("%b")


def build_charts(
    fin: dict,
    scores: dict,
    funding_bars: list[dict],
    created_at: str = "",
) -> dict:
    mrr, growth, burn, cash = fin["mrr"], fin["growth_pct"] / 100, fin["burn"], fin["cash"]
    revenue_trend: list[dict] = []
    burn_trend: list[dict] = []
    cash_projection: list[dict] = []

    scale_rate = min(0.025, abs(growth) * 0.4) if mrr > 0 else 0.01
    burn_growth = 0.05

    if created_at:
        analysis_date = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    else:
        analysis_date = datetime.now()
    now = analysis_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Build 12 projected months starting from analysis month.
    for offset in range(0, 12):
        dt = _add_calendar_months(now, offset)
        label = _month_label(dt)

        if offset == 0:
            rev_value = round(mrr, 0)
            burn_value = round(burn, 0)
        else:
            rev_value = round(mrr * ((1 + growth) ** offset), 0) if growth != 0 else round(mrr, 0)
            burn_value = round(burn * ((1 + burn_growth) ** offset), 0)

        revenue_trend.append({"label": label, "value": rev_value})
        burn_trend.append({"label": label, "value": burn_value})

    running_cash = cash
    for offset in range(1, 7):
        dt = _add_calendar_months(now, offset)
        future_mrr = mrr * ((1 + growth) ** offset) if growth != 0 else mrr
        running_cash = running_cash - burn + future_mrr
        cash_projection.append({
            "label": f"{_month_label(dt)} '{str(dt.year)[2:]}",
            "value": max(0, round(running_cash, 0)),
        })
    health_radar = {
        "Financial Health": scores["financial"],
        "Team Strength": scores["team"],
        "Market Opportunity": scores["market"],
        "Product / IP": scores["product"],
        "Traction": scores["traction"],
        "Risk Exposure": scores["risk"],
    }
    score_breakdown = [{"label": k, "score": v} for k, v in health_radar.items()]

    labels_12m = [point["label"] for point in revenue_trend[:12]]
    labels_6m = labels_12m[:6]

    return {
        "revenue_trend": revenue_trend,
        "burn_trend": burn_trend,
        "cash_projection": cash_projection,
        "health_radar": health_radar,
        "funding_bars": funding_bars,
        "score_breakdown": score_breakdown,
        "labels_6m": labels_6m,
        "labels_12m": labels_12m,
        "analysis_month": now.strftime("%B %Y"),
    }


def calculate_startup_metrics(ai_analysis: dict, form_data: dict, created_at: str = "") -> dict:
    form_data = {k: v for k, v in form_data.items() if v is not None}
    ai = normalize_ai_response(ai_analysis)
    fin = compute_financial_metrics(form_data)

    financial_score = score_financial(ai, fin)
    market_score = score_market(ai, form_data)
    team_score = score_team(ai, form_data)
    product_score = score_product(ai, form_data)
    traction_score = score_traction(ai, form_data, fin)
    risks = ai.get("risks", [])
    risk_score = score_risk(ai, risks)

    scores = {
        "financial": financial_score, "market": market_score, "team": team_score,
        "product": product_score, "traction": traction_score, "risk": risk_score,
    }

    survival_score = compute_survival_score(
        financial_score, market_score, team_score, product_score, traction_score, risk_score
    )
    survival_probability = compute_survival_probability(survival_score)
    percentile = compute_percentile(survival_score)

    swot = ai.get("swot", {})
    competitors = ai.get("competitors", [])
    recommendations = ai.get("recommendations", [])

    funding = compute_funding_readiness(ai, fin, form_data, scores)
    financial_health = build_financial_health(fin, form_data, scores)
    market_analysis = build_market_analysis(ai, form_data)
    executive_summary = build_executive_summary(
        ai, form_data.get("startup_name", "Startup"), form_data.get("industry", "—"),
        survival_score, survival_probability, percentile, risks, fin,
    )
    # Missing financial inputs must never become invented measurements.
    if not form_data.get("gross_margin"):
        financial_health["gross_margin"] = "Unknown"
        financial_health["rows"][4].update(value="Unknown", status="Not supplied")
    if not form_data.get("cac_payback"):
        financial_health["cac_payback"] = "Unknown"
        financial_health["rows"][6].update(value="Unknown", status="Not supplied")
    if fin["runway_unbounded"]:
        financial_health["runway"] = "No net burn"
        financial_health["rows"][3].update(value="No net burn", status="Current revenue covers expenses")
        financial_health["callout"] = "Current revenue covers expenses; no finite runway at this spending level."
    if not fin["burn_multiple_available"]:
        financial_health["burn_multiple"] = "Not applicable"
        financial_health["rows"][5].update(value="Not applicable", status="No positive new ARR")
    for row in financial_health["rows"]:
        row["median"] = "Illustrative reference: " + row["median"]
    financial_signals = build_financial_signals(fin)
    if fin["runway_unbounded"]:
        financial_signals[0].update(value="No net burn", status="good")
    if not fin["burn_multiple_available"]:
        financial_signals[2].update(value="Not applicable", status="warning")
    if not form_data.get("gross_margin"):
        financial_signals[3].update(value="Unknown", status="warning")
    for signal in financial_signals:
        signal["benchmark"] = "Illustrative reference only"

    charts = build_charts(fin, scores, funding["bars"], created_at)

    def _fmt_cash(val: float) -> str:
        if val >= 1_000_000: return f"${val/1_000_000:.1f}M"
        if val >= 1_000: return f"${val:,.0f}"
        return f"${val:.0f}" if val else "—"

    startup = {
        "name": form_data.get("startup_name") or form_data.get("idea", "Startup"),
        "industry": form_data.get("industry", "—"),
        "stage": form_data.get("stage", "—"),
        "founded": form_data.get("founded", "—"),
        "team_size": str(form_data.get("team_size", "—")),
        "monthly_revenue": financial_health["mrr"],
        "monthly_burn": financial_health["burn"],
        "total_raised": str(form_data.get("total_raised") or form_data.get("funding_raised", "—")),
        "cash_in_bank": _fmt_cash(fin["cash"]) if fin["cash"] else str(form_data.get("cash_in_bank", "—")),
        "revenue_growth": financial_health["growth"],
        "last_round": form_data.get("last_round", "—"),
        "market_size": form_data.get("market_size") or form_data.get("tam", "—"),
        "differentiator": form_data.get("differentiator") or form_data.get("competitive_advantages", "—"),
        "founder_experience": form_data.get("founder_experience", "—"),
        "has_cto": str(form_data.get("has_cto") or form_data.get("has_technical_cofounder", "—")),
        "customers": form_data.get("customers"),
        "churn_rate": form_data.get("churn_rate_pct", form_data.get("churn_rate")),
        "partnerships": form_data.get("partnerships"),
        "letters_of_intent": form_data.get("letters_of_intent"),
    }

    funding_gaps = round((100 - funding["overall"]) / 15)

    metrics = {
        "survival_score": survival_score,
        "survival_probability": survival_probability,
        "funding_readiness": funding["overall"],
        "funding_gaps": funding_gaps,
        "financial_score": financial_score,
        "market_score": market_score,
        "team_score": team_score,
        "product_score": product_score,
        "traction_score": traction_score,
        "risk_score": risk_score,
        "runway_months": fin["runway_months"],
        "net_burn": fin["net_burn"],
        "runway_unbounded": fin["runway_unbounded"],
        "burn_multiple_available": fin["burn_multiple_available"],
        "revenue_status": fin["revenue_status"],
        "input_completeness": fin["input_completeness"],
        "break_even_month": fin["break_even_month"],
        "burn_multiple": fin["burn_multiple"] if math.isfinite(fin["burn_multiple"]) else 0.0,
        "risk_count": len(risks),
        "cohort": COHORT["label"],
        "percentile": percentile,
    }

    return {
        "startup": startup,
        "_form_data": form_data,
        "metrics": metrics,
        "financial_health": financial_health,
        "financial_signals": financial_signals,
        "market_analysis": market_analysis,
        "risks": risks,
        "swot": swot,
        "competitors": competitors,
        "funding_readiness": funding,
        "recommendations": recommendations,
        "executive_summary": executive_summary,
        "charts": charts,
        "score_breakdown": charts["score_breakdown"],
    }
