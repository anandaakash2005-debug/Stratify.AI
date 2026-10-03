"""
schemas/analysis.py

Single source of truth for every field that travels from backend → frontend.
All metric names, types, and defaults are defined here.
Nothing is ever invented by the frontend.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


# ─────────────────────────────────────────────
# REQUEST — accepts full analysis form payload
# ─────────────────────────────────────────────

class AdditionalContextFacts(BaseModel):
    """Facts extracted from free text without interpretation or scoring."""

    customers: Optional[int] = Field(None, ge=0)
    churn_rate_pct: Optional[float] = Field(None, ge=0, le=100)
    partnerships: Optional[int] = Field(None, ge=0)
    letters_of_intent: Optional[int] = Field(None, ge=0)

class AnalysisRequest(BaseModel):
    """Form submission from analysis.html — extra fields allowed."""

    model_config = ConfigDict(extra="allow", allow_inf_nan=False)

    startup_name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=5000)
    startup_idea: Optional[str] = Field(None, max_length=5000)
    industry: Optional[str] = None
    market: Optional[str] = None
    stage: Optional[str] = None
    country_region: Optional[str] = None
    currency: str = "USD"
    business_model: Optional[str] = "Subscription"
    target_audience: Optional[str] = "General users"
    monthly_burn: float = Field(0, ge=0)
    monthly_revenue: float = Field(0, ge=0)
    cash_in_bank: float = Field(0, ge=0)
    revenue_growth: float = Field(0, ge=-100, le=1000)
    customers: Optional[int] = Field(None, ge=0)
    churn_rate_pct: Optional[float] = Field(None, ge=0, le=100)
    partnerships: Optional[int] = Field(None, ge=0)
    letters_of_intent: Optional[int] = Field(None, ge=0)
    user_id: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def default_currency_from_region(cls, value):
        if isinstance(value, dict) and not value.get("currency"):
            region = str(value.get("country_region") or value.get("country") or "").lower()
            value = dict(value)
            value["currency"] = "INR" if "india" in region or region in {"in", "ind"} else "USD"
        return value

    @model_validator(mode="after")
    def require_description(self):
        if not (self.description or self.startup_idea or "").strip():
            raise ValueError("Startup description is required")
        if not self.startup_name.strip():
            raise ValueError("Startup name is required")
        import json
        json.dumps(self.model_dump(), allow_nan=False)
        return self


# ─────────────────────────────────────────────
# SUB-SCHEMAS
# ─────────────────────────────────────────────

class Metrics(BaseModel):
    model_config = ConfigDict(extra="allow")
    survival_score: int = Field(0, ge=0, le=100)
    survival_probability: int = Field(0, ge=0, le=100)
    funding_readiness: int = Field(0, ge=0, le=100)
    funding_gaps: int = Field(0, ge=0)
    financial_score: int = Field(0, ge=0, le=100)
    market_score: int = Field(0, ge=0, le=100)
    team_score: int = Field(0, ge=0, le=100)
    product_score: int = Field(0, ge=0, le=100)
    traction_score: int = Field(0, ge=0, le=100)
    risk_score: int = Field(0, ge=0, le=100)
    runway_months: float = Field(0.0, ge=0)
    break_even_month: str = Field("—")
    burn_multiple: float = Field(0.0, ge=0)
    risk_count: int = Field(0, ge=0)
    cohort: str = Field("SaaS / AI, Seed (n=847)")
    percentile: int = Field(0, ge=0, le=100)


class FinancialSignal(BaseModel):
    label: str
    value: str
    status: str
    benchmark: Optional[str] = None


class ChartPoint(BaseModel):
    label: str
    value: float


class Charts(BaseModel):
    revenue_trend: list[ChartPoint] = Field(default_factory=list)
    burn_trend: list[ChartPoint] = Field(default_factory=list)
    cash_projection: list[ChartPoint] = Field(default_factory=list)
    health_radar: dict[str, int] = Field(default_factory=dict)
    funding_bars: list[dict] = Field(default_factory=list)
    score_breakdown: list[dict] = Field(default_factory=list)


class Risk(BaseModel):
    category: str
    description: str
    severity: str = "medium"


class SwotAnalysis(BaseModel):
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    opportunities: list[str] = Field(default_factory=list)
    threats: list[str] = Field(default_factory=list)


class Competitor(BaseModel):
    name: str
    stage: str = "—"
    funding: str = "—"
    differentiator: str = "—"
    threat: str = "Medium"


class Recommendation(BaseModel):
    title: str
    description: str = ""
    urgency: str = "Medium"
    impact: str = ""


class ExecSummary(BaseModel):
    overview: str = ""
    positioning: str = ""
    risks_headline: str = ""
    critical_callout: str = ""
    success_callout: str = ""


class FinancialHealth(BaseModel):
    mrr: str = "—"
    burn: str = "—"
    growth: str = "—"
    runway: str = "—"
    gross_margin: str = "—"
    burn_multiple: str = "—"
    cac_payback: str = "—"
    callout: str = ""
    rows: list[dict] = Field(default_factory=list)


class MarketAnalysis(BaseModel):
    tam: str = "—"
    sam: str = "—"
    projection: str = "—"
    tam_growth: str = ""
    analysis: str = ""
    callout: str = ""
    stats: list[dict] = Field(default_factory=list)


class FundingReadiness(BaseModel):
    overall: int = 0
    summary: str = ""
    traction_pct: int = 0
    traction_detail: str = ""
    team_pct: int = 0
    team_detail: str = ""
    market_pct: int = 0
    market_detail: str = ""
    econ_pct: int = 0
    econ_detail: str = ""
    materials_pct: int = 0
    materials_detail: str = ""
    social_pct: int = 0
    social_detail: str = ""
    bars: list[dict] = Field(default_factory=list)


class StartupInfo(BaseModel):
    name: str = "Startup"
    industry: str = "—"
    stage: str = "—"
    founded: str = "—"
    team_size: str = "—"
    monthly_revenue: str = "—"
    monthly_burn: str = "—"
    total_raised: str = "—"
    cash_in_bank: str = "—"
    revenue_growth: str = "—"
    last_round: str = "—"
    market_size: str = "—"
    differentiator: str = "—"
    founder_experience: str = "—"
    has_cto: str = "—"


class AnalysisResponse(BaseModel):
    @model_validator(mode="before")
    @classmethod
    def require_complete_report(cls, value):
        if not isinstance(value, dict):
            raise ValueError("Report must be an object")
        sections = {"startup": StartupInfo, "metrics": Metrics, "charts": Charts,
                    "executive_summary": ExecSummary, "financial_health": FinancialHealth,
                    "market_analysis": MarketAnalysis, "funding_readiness": FundingReadiness}
        for name, schema in sections.items():
            section = value.get(name)
            if not isinstance(section, dict) or not set(schema.model_fields).issubset(section):
                raise ValueError("Missing required report section fields")
        for name, count in (("risks",3),("competitors",3),("recommendations",4)):
            if not isinstance(value.get(name),list) or len(value[name]) != count:
                raise ValueError("Incomplete report list")
        swot = value.get("swot")
        if not isinstance(swot,dict) or any(len(swot.get(k,[])) != 3 for k in SwotAnalysis.model_fields):
            raise ValueError("Incomplete SWOT")
        if not value.get("financial_signals") or not value.get("score_breakdown"):
            raise ValueError("Incomplete financial or score signals")
        return value

    report_id: Optional[str] = None
    created_at: Optional[str] = None

    startup: StartupInfo = Field(default_factory=StartupInfo)
    metrics: Metrics = Field(default_factory=Metrics)
    financial_signals: list[FinancialSignal] = Field(default_factory=list)
    charts: Charts = Field(default_factory=Charts)
    risks: list[Risk] = Field(default_factory=list)
    swot: SwotAnalysis = Field(default_factory=SwotAnalysis)
    competitors: list[Competitor] = Field(default_factory=list)
    recommendations: list[Recommendation] = Field(default_factory=list)
    executive_summary: ExecSummary = Field(default_factory=ExecSummary)
    financial_health: FinancialHealth = Field(default_factory=FinancialHealth)
    market_analysis: MarketAnalysis = Field(default_factory=MarketAnalysis)
    funding_readiness: FundingReadiness = Field(default_factory=FundingReadiness)

    form_data: dict[str, Any] = Field(default_factory=dict, alias="_form_data")
    score_breakdown: list[dict] = Field(default_factory=list)

    model_config = ConfigDict(extra="allow", populate_by_name=True)


class APIResponse(BaseModel):
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None
    message: str = ""
