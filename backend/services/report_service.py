"""
services/report_service.py — Fetch and manage analysis reports.
"""

import logging
from database.client import table

logger = logging.getLogger(__name__)


class ReportService:

    def get_by_startup(self, startup_id: str, user_id: str) -> list[dict]:
        try:
            res = (
                table("reports")
                .select("*, scores(*), startups!inner(user_id)")
                .eq("startups.user_id", user_id)
                .eq("startup_id", startup_id)
                .order("created_at", desc=True)
                .execute()
            )
            return res.data or []
        except Exception as exc:
            logger.error(f"get_by_startup failed: {exc}")
            return []

    def get_by_id(self, report_id: str) -> dict | None:
        try:
            res = (
                table("reports")
                .select("*, scores(*), startups(*)")
                .eq("id", report_id)
                .single()
                .execute()
            )
            return res.data
        except Exception as exc:
            logger.error(f"get_by_id failed: {exc}")
            return None

    def get_full_report(self, report_id: str, user_id: str) -> dict | None:
        """Return {report, startup, scores} with ownership check."""
        try:
            res = (
                table("reports")
                .select("*, startups!inner(*), scores(*)")
                .eq("id", report_id)
                .maybe_single()
                .execute()
            )
        except Exception as exc:
            logger.error(f"get_full_report query failed: {exc}")
            return None

        if not res.data:
            return None

        row = res.data
        startup = row.pop("startups", None) or {}
        scores_list = row.pop("scores", None) or []
        scores = scores_list[0] if scores_list else {}

        # Ownership check
        if startup.get("user_id") != user_id:
            logger.warning("Ownership mismatch — report=%s user=%s", report_id, user_id)
            return None

        return {"report": row, "startup": startup, "scores": scores}

    def get_recent(self, user_id: str, limit: int = 10) -> list[dict]:
        try:
            res = (
                table("reports")
                .select("id, startup_id, model_used, tokens_used, created_at, scores(*), startups!inner(user_id)")
                .eq("startups.user_id", user_id)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            return res.data or []
        except Exception as exc:
            logger.error(f"get_recent failed: {exc}")
            return []

    def get_timeline(self, user_id: str, limit: int = 50) -> list[dict]:
        """Return [{date, score}] for score progress widget."""
        try:
            res = (
                table("scores")
                .select("created_at, health_score, startups!inner(user_id)")
                .eq("startups.user_id", user_id)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
        except Exception as exc:
            logger.error(f"get_timeline failed: {exc}")
            return []

        timeline = []
        for row in res.data or []:
            timeline.append({
                "date": row.get("created_at"),
                "score": row.get("health_score"),
            })
        # Return in chronological order
        timeline.reverse()
        return timeline


report_service = ReportService()
