import asyncio
from fastapi import HTTPException, Header
from supabase import AuthApiError

async def require_user(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.startswith('Bearer ') or not authorization[7:].strip():
        raise HTTPException(status_code=401, detail='Authentication required')
    from database.client import get_auth_client
    import httpx
    try:
        async with asyncio.timeout(8):
            user = await asyncio.to_thread(get_auth_client().auth.get_user, authorization[7:])
        if not user or not user.user:
            raise HTTPException(status_code=401, detail='Invalid or expired token')
        return user
    except AuthApiError as exc:
        raise HTTPException(status_code=401, detail='Invalid or expired token') from exc
    except (TimeoutError, httpx.RequestError) as exc:
        raise HTTPException(status_code=503, detail='Authentication service is temporarily unavailable') from exc
