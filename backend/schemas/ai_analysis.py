from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, AfterValidator

SHORT_MAX_WORDS = 25

def words(limit):
    def check(value):
        if not value.strip() or len(value.split()) > limit:
            raise ValueError('Text must be nonempty and within the word limit')
        return value
    return check

Short = Annotated[str, Field(max_length=600), AfterValidator(words(SHORT_MAX_WORDS))]
Summary = Annotated[str, Field(max_length=1200), AfterValidator(words(50))]
Score = Annotated[int, Field(ge=0, le=100)]
Three = Annotated[list[Short], Field(min_length=3, max_length=3)]

class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

class SWOT(StrictModel):
    strengths: Three
    weaknesses: Three
    opportunities: Three
    threats: Three

class Risk(StrictModel):
    category: Short
    description: Short
    severity: Literal['critical', 'high', 'medium', 'low']

class Competitor(StrictModel):
    name: Short
    stage: Short
    funding: Short
    differentiator: Short
    threat: Literal['Critical', 'High', 'Medium', 'Low']

class Recommendation(StrictModel):
    title: Short
    description: Short
    urgency: Short
    impact: Short

class AIAnalysis(StrictModel):
    financial_score: Score
    market_score: Score
    team_score: Score
    product_score: Score
    traction_score: Score
    risk_score: Score
    swot: SWOT
    risks: Annotated[list[Risk], Field(min_length=3, max_length=3)]
    competitors: Annotated[list[Competitor], Field(min_length=3, max_length=3)]
    recommendations: Annotated[list[Recommendation], Field(min_length=4, max_length=4)]
    tam: Short
    sam: Short
    market_projection: Short
    market_analysis: Summary
    executive_summary_overview: Summary
    executive_summary_positioning: Summary
    executive_summary_risks: Summary
    critical_callout: Short
    success_callout: Short
    funding_readiness_summary: Summary

ANALYSIS_JSON_SCHEMA = AIAnalysis.model_json_schema()
