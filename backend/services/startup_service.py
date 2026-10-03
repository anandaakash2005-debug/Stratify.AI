"""Startup reads and mutations always include authenticated ownership."""
from database.client import table

class StartupService:
    def get_all(self, user_id: str, limit: int = 20, offset: int = 0) -> list[dict]:
        return (table('startups').select('*, scores(*)').eq('user_id',user_id)
                .order('created_at',desc=True).range(offset,offset+limit-1).execute()).data or []

    def get_by_id(self, startup_id: str, user_id: str) -> dict | None:
        rows=table('startups').select('*, scores(*)').eq('id',startup_id).eq('user_id',user_id).limit(1).execute().data
        return rows[0] if rows else None

    def get_by_user(self, user_id: str) -> list[dict]:
        return self.get_all(user_id)

    def delete(self, startup_id: str, user_id: str) -> bool:
        return bool(table('startups').delete().eq('id',startup_id).eq('user_id',user_id).execute().data)

startup_service=StartupService()
