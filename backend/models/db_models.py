"""
models/db_models.py — DB row shapes as Pydantic models.
Used when reading rows back from Supabase (not for API I/O — use schemas/ for that).
Keeps a clean separation: schemas/ = API contract, models/ = DB shape.
"""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class UserModel(BaseModel):
    id:         str
    email:      str
    full_name:  Optional[str] = None
    role:       str = "founder"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class StartupModel(BaseModel):
    id:              str
    user_id:         Optional[str] = None
    name:            Optional[str] = None
    idea:            str
    market:          str
    business_model:  str
    target_audience: str
    stage:           str = "idea"
    created_at:      Optional[datetime] = None


class ReportModel(BaseModel):
    id:              str
    startup_id:      str
    report_type:     str = "full"
    swot:            Optional[dict] = None
    risks:           Optional[list] = None
    competitors:     Optional[list] = None
    recommendations: Optional[list] = None
    gtm_suggestions: Optional[list] = None
    model_used:      Optional[str]  = None
    tokens_used:     Optional[int]  = None
    created_at:      Optional[datetime] = None


class ScoreModel(BaseModel):
    id:                   str
    startup_id:           str
    report_id:            Optional[str] = None
    health_score:         float
    risk_level:           str
    survival_probability: str
    pmf_score:            Optional[float] = None
    competition_score:    Optional[float] = None
    monetization_score:   Optional[float] = None
    team_score:           Optional[float] = None
    market_score:         Optional[float] = None
    scoring_version:      str = "v1"
    created_at:           Optional[datetime] = None
