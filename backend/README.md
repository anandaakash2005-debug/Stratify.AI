# AI Startup Survival Intelligence Platform — Backend

FastAPI backend powering multi-agent AI startup analysis, scoring, and survival intelligence.

---

## Quick Start

```bash
# 1. Clone & enter backend directory
cd backend

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# 3. Install local development and test dependencies
pip install -r requirements-dev.txt

# 4. Configure environment
# Create backend/.env directly and populate required values.
# Required variables:
#   ENVIRONMENT=development
#   AI_PROVIDER=ollama (or openrouter)
#   SECRET_KEY
#   SUPABASE_URL
#   SUPABASE_ANON_KEY
#   SUPABASE_SERVICE_KEY
# For OpenRouter, also set OPENROUTER_API_KEY and PRIMARY_MODEL.

# 5. Set up Supabase tables and policies
# Review and apply schema.sql, analysis_pipeline.sql, then chat_history.sql.
# These migrations are not run automatically by the API.

# 6. Start server
uvicorn main:app --reload --port 8000
```

API docs available at: http://localhost:8000/docs

---

## Project Structure

```
backend/
├── main.py                     # App factory, middleware, router registration
├── requirements.txt
├── .env                        # Backend configuration file loaded at startup
├── config/
│   └── settings.py             # All env vars via pydantic-settings
│
├── routes/
│   ├── analysis.py             # POST /analyze  ← primary endpoint
│   ├── startups.py             # CRUD for saved startups
│   ├── reports.py              # Report retrieval
│   └── health.py               # Liveness + AI reachability probes
│
├── services/
│   ├── analysis_service.py     # Core orchestration (AI → score → persist)
│   ├── startup_service.py      # Startup DB operations
│   ├── report_service.py       # Report DB operations
│   └── ml_service.py           # ML prediction stubs (v2 ready)
│
├── schemas/
│   └── analysis.py             # Pydantic request/response models
│
├── models/
│   └── db_models.py            # DB row shapes (separate from API schemas)
│
├── prompts/
│   └── analysis_prompts.py     # All AI prompt templates
│
├── utils/
│   ├── openrouter_client.py    # Async OpenRouter HTTP client
│   ├── scoring.py              # Rule-based startup scoring engine
│   └── response_formatter.py  # Standardised JSON response helpers
│
└── database/
    ├── client.py               # Supabase singleton + helpers
    └── schema.sql              # Run once in Supabase SQL editor
```

---

## Core Endpoint

### POST /api/v1/analyze/

```json
// Request
{
  "startup_idea":    "AI-powered boardroom simulation for startup founders",
  "market":          "B2B SaaS, EdTech",
  "business_model":  "Freemium — $49/mo Pro",
  "target_audience": "Early-stage founders",
  "stage":           "idea",
  "startup_name":    "FounderIQ"
}

// Response
{
  "success": true,
  "data": {
    "health_score": 72.5,
    "risk_level": "Medium",
    "survival_probability": "68%",
    "swot": { "strengths": [...], "weaknesses": [...], ... },
    "risks": [{ "category": "Market Risk", "severity": "High", ... }],
    "competitors": [{ "name": "...", "differentiator": "..." }],
    "recommendations": ["..."],
    "gtm_suggestions": [{ "channel": "...", "timeline": "Week 1" }],
    "score_breakdown": {
      "pmf_score": 65, "competition_score": 55,
      "monetization_score": 70, "market_score": 80, "team_score": 50
    }
  }
}
```

---

## Scoring Algorithm (v1)

| Dimension | Weight | Notes |
|-----------|--------|-------|
| PMF Score | 30% | Product-market fit — biggest killer |
| Monetization | 25% | Clear revenue model |
| Competition | 20% | 100 = blue ocean |
| Market Size | 15% | TAM + growth |
| Team | 10% | Default 50 (no team info) |

Penalties applied for critically low sub-scores.
Health score → Risk Level → Survival Probability (cascading).

---

## Future ML Integration

`services/ml_service.py` contains stubs for:
- Bankruptcy risk prediction
- PMF probability (NLP classifier)
- Funding probability
- Founder conflict risk

Set `ML_ENABLED=true` and `ML_SERVICE_URL=http://your-ml-service` to activate.

---

## Environment Variables

Use `.env.example` as the local template. `ENVIRONMENT` is canonical;
`APP_ENV` remains accepted for existing local configurations. The Python
backend expects JWT-style Supabase keys compatible with the pinned
`supabase-py` client. Keep `SUPABASE_SERVICE_KEY` server-side only.

Production requires `DEBUG=false`, explicit non-wildcard `ALLOWED_ORIGINS` and
`ALLOWED_HOSTS`, and an explicit `PRIMARY_MODEL` when `AI_PROVIDER=openrouter`.
See the root [Render deployment guide](../DEPLOYMENT_RENDER.md) for the
Blueprint setup and service configuration.
