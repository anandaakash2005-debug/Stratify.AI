"""
database/client.py — Supabase client singleton + table initialisation helpers
Uses the supabase-py async client. All DB interactions funnel through here.
"""

import asyncio
import logging
from typing import Optional

from supabase import Client, create_client
from supabase.lib.client_options import ClientOptions

from config.settings import settings

logger = logging.getLogger(__name__)

# Module-level singletons
_supabase_client: Optional[Client] = None
_auth_client: Optional[Client] = None
_db_ping_timeout_seconds = 5


def get_client() -> Client:
    """Return the cached Supabase client. Creates it on first call."""
    global _supabase_client
    if _supabase_client is None:
        _supabase_client = create_client(
            str(settings.SUPABASE_URL).rstrip("/"),
            settings.SUPABASE_SERVICE_KEY,
            options=ClientOptions(
                auto_refresh_token=True,
                persist_session=False,
            ),
        )
        logger.info("✅ Supabase client initialised")
    return _supabase_client


def get_auth_client() -> Client:
    """Return a Supabase client using the anon key, for user auth verification only."""
    global _auth_client
    if _auth_client is None:
        _auth_client = create_client(
            str(settings.SUPABASE_URL).rstrip("/"),
            settings.SUPABASE_ANON_KEY,
            options=ClientOptions(
                auto_refresh_token=True,
                persist_session=False,
            ),
        )
        logger.info("✅ Supabase auth client initialised")
    return _auth_client


def _ping_supabase() -> None:
    client = get_client()
    client.table("users").select("id").limit(1).execute()


async def init_db() -> None:
    """
    Runs a non-blocking Supabase connectivity check after startup.
    If the check fails or times out, the app continues in degraded mode.
    """
    try:
        await asyncio.wait_for(asyncio.to_thread(_ping_supabase), timeout=_db_ping_timeout_seconds)
        logger.info("✅ Supabase connectivity confirmed")
    except asyncio.TimeoutError:
        logger.warning(
            "⚠️ Supabase ping timed out after %s seconds. "
            "Continuing in degraded mode.",
            _db_ping_timeout_seconds,
        )
    except Exception as exc:
        logger.warning(
            "⚠️ Supabase ping failed — check SUPABASE_URL / keys. "
            "Continuing in degraded mode. Error: %s",
            exc,
        )


# ── Convenience helpers ───────────────────────────────────────────────────────

def table(name: str):
    """Shorthand: table('startups').select(...)"""
    return get_client().table(name)
