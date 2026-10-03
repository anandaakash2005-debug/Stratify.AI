from __future__ import annotations

from typing import Any, Optional


def build_analysis_context(analysis: Optional[dict[str, Any]] = None) -> str:
    if not analysis:
        return "No analysis data available."

    metrics = analysis.get("metrics") or {}
    startup = analysis.get("startup") or {}
    risks = analysis.get("risks") or []
    swot = analysis.get("swot") or {}
    funding = analysis.get("funding_readiness") or {}
    exec_summary = analysis.get("executive_summary") or {}
    financial = analysis.get("financial_health") or {}
    market = analysis.get("market_analysis") or {}

    lines = [
        "=== STARTUP ANALYSIS CONTEXT ===",
        f"Startup: {startup.get('name', 'N/A')}",
        f"Industry: {startup.get('industry', 'N/A')}",
        f"Stage: {startup.get('stage', 'N/A')}",
        f"Monthly Revenue: {startup.get('monthly_revenue', 'N/A')}",
        f"Monthly Burn: {startup.get('monthly_burn', 'N/A')}",
        f"Cash in Bank: {startup.get('cash_in_bank', 'N/A')}",
        f"Revenue Growth: {startup.get('revenue_growth', 'N/A')}",
        f"Team Size: {startup.get('team_size', 'N/A')}",
        "",
        "=== METRICS ===",
        f"Survival Score: {metrics.get('survival_score', 'N/A')}/100",
        f"Survival Probability: {metrics.get('survival_probability', 'N/A')}%",
        f"Funding Readiness: {metrics.get('funding_readiness', 'N/A')}/100",
        f"Financial Score: {metrics.get('financial_score', 'N/A')}/100",
        f"Market Score: {metrics.get('market_score', 'N/A')}/100",
        f"Team Score: {metrics.get('team_score', 'N/A')}/100",
        f"Product Score: {metrics.get('product_score', 'N/A')}/100",
        f"Traction Score: {metrics.get('traction_score', 'N/A')}/100",
        f"Risk Score: {metrics.get('risk_score', 'N/A')}/100",
        f"Runway: {metrics.get('runway_months', 'N/A')} months",
        f"Burn Multiple: {metrics.get('burn_multiple', 'N/A')}",
        f"Risk Count: {metrics.get('risk_count', 'N/A')}",
        "",
        "=== RISKS ===",
    ]

    for r in risks:
        lines.append(f"- [{r.get('severity', 'medium').upper()}] {r.get('category', 'Risk')}: {r.get('description', '')}")

    lines.extend([
        "",
        "=== SWOT ===",
        "Strengths: " + ", ".join(swot.get("strengths", []) or []),
        "Weaknesses: " + ", ".join(swot.get("weaknesses", []) or []),
        "Opportunities: " + ", ".join(swot.get("opportunities", []) or []),
        "Threats: " + ", ".join(swot.get("threats", []) or []),
        "",
        "=== FUNDING READINESS ===",
        f"Overall: {funding.get('overall', 'N/A')}/100",
        f"Summary: {funding.get('summary', 'N/A')}",
        "",
        "=== EXECUTIVE SUMMARY ===",
        f"Overview: {exec_summary.get('overview', 'N/A')}",
        f"Positioning: {exec_summary.get('positioning', 'N/A')}",
        f"Risks: {exec_summary.get('risks_headline', 'N/A')}",
        "",
        "=== FINANCIAL HEALTH ===",
        f"MRR: {financial.get('mrr', 'N/A')}",
        f"Burn: {financial.get('burn', 'N/A')}",
        f"Growth: {financial.get('growth', 'N/A')}",
        f"Runway: {financial.get('runway', 'N/A')}",
        f"Gross Margin: {financial.get('gross_margin', 'N/A')}",
        "",
        "=== MARKET ANALYSIS ===",
        f"TAM: {market.get('tam', 'N/A')}",
        f"SAM: {market.get('sam', 'N/A')}",
        f"Projection: {market.get('projection', 'N/A')}",
    ])

    return "\n".join(lines)
