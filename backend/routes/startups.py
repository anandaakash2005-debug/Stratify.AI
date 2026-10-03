"""
routes/startups.py — Startup CRUD endpoints.
GET /startups, GET /startups/{id}, DELETE /startups/{id}
"""

from fastapi import APIRouter, Depends, HTTPException, Query
import logging

from auth.dependencies import require_user
from services.startup_service import startup_service
from utils.response_formatter import success_response, error_response, paginated_response

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/", summary="List all startups")
async def list_startups(
    limit:  int = Query(20, ge=1, le=100),
    offset: int = Query(0,  ge=0),
    user=Depends(require_user),
):
    data = startup_service.get_all(user.user.id, limit=limit, offset=offset)
    return paginated_response(data=data, total=len(data), page=offset // limit + 1, page_size=limit)


@router.get("/{startup_id}", summary="Get startup by ID")
async def get_startup(startup_id: str, user=Depends(require_user)):
    data = startup_service.get_by_id(startup_id, user.user.id)
    if not data:
        raise HTTPException(status_code=404, detail=f"Startup {startup_id} not found")
    return success_response(data=data)


@router.get("/user/{user_id}", summary="Get startups by user")
async def get_user_startups(user_id: str, user=Depends(require_user)):
    if user_id != user.user.id:
        raise HTTPException(status_code=404, detail="User not found")
    data = startup_service.get_by_user(user_id)
    return success_response(data=data)


@router.delete("/{startup_id}", summary="Delete a startup")
async def delete_startup(startup_id: str, user=Depends(require_user)):
    success = startup_service.delete(startup_id, user.user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Startup not found or delete failed")
    return success_response(data={"deleted_id": startup_id}, message="Startup deleted")
