"""
main.py — FastAPI Application Entry Point
AI Startup Survival Intelligence Platform
"""

import sys
import asyncio
from contextlib import asynccontextmanager
import logging

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from slowapi import _rate_limit_exceeded_handler

from auth.rate_limit import limiter
from config.settings import settings
from database.client import init_db
from routes import (
    analysis,
    chatbot,
    health,
    mentor,
    mentor_recommendations,
    reports,
    startups,
)

# ── Logging setup ──────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ── Lifespan (startup / shutdown hooks) ───────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Starting AI Startup Survival Intelligence Platform...")
    app.state.db_init_task = asyncio.create_task(init_db())
    logger.info("✅ FastAPI startup complete and responsive; Supabase connectivity will be verified in the background.")
    yield

    db_task = getattr(app.state, "db_init_task", None)
    if db_task and not db_task.done():
        db_task.cancel()
        try:
            await db_task
        except asyncio.CancelledError:
            pass
    logger.info("🛑 Shutting down...")


# ── App factory ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="AI Startup Survival Intelligence Platform",
    description="Multi-agent AI platform for startup analysis, risk scoring, and survival intelligence.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── Rate limiting ───────────────────────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(429, _rate_limit_exceeded_handler)

# ── Middleware ─────────────────────────────────────────────────────────────────
from utils.analysis_http import install_analysis_handlers
install_analysis_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.ALLOWED_HOSTS,
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(health.router,    prefix="/api/v1",          tags=["Health"])
app.include_router(analysis.router,  prefix="/api/v1/analyze",  tags=["Analysis"])
app.include_router(startups.router,  prefix="/api/v1/startups", tags=["Startups"])
app.include_router(mentor.router,                prefix="/api/v1/mentor",   tags=["Mentor"])
app.include_router(mentor_recommendations.router, prefix="/api/v1/mentors",  tags=["Mentor Recommendations"])
app.include_router(chatbot.router,               prefix="/api/v1/chatbot",  tags=["Chatbot"])
app.include_router(reports.router,   prefix="/api/v1/reports",  tags=["Reports"])


# ── Root ──────────────────────────────────────────────────────────────────────
@app.get("/", tags=["Root"])
async def root():
    return {
        "platform": "AI Startup Survival Intelligence Platform",
        "version": "1.0.0",
        "status": "operational",
        "docs": "/docs",
    }

