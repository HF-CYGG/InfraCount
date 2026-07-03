from typing import Any, Dict

from fastapi import APIRouter, Body, HTTPException, Request

from api.dependencies import require_admin_user
from app import db

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.get("")
async def list_users(request: Request):
    await require_admin_user(request)
    users = await db.get_all_users()
    return {"users": users}


@router.post("")
async def create_user_api(request: Request, payload: Dict[str, str] = Body(...)):
    await require_admin_user(request)

    username = payload.get("username")
    password = payload.get("password")
    role = payload.get("role", "user")

    if not username or not password:
        raise HTTPException(400, "Missing username or password")

    success = await db.create_user(username, password, role)
    if not success:
        raise HTTPException(400, "Failed to create user (might already exist)")

    return {"status": "ok"}


@router.put("/{user_id}")
async def update_user_api(user_id: int, request: Request, payload: Dict[str, Any] = Body(...)):
    await require_admin_user(request)

    username = payload.get("username")
    password = payload.get("password")
    role = payload.get("role")

    success = await db.update_user(user_id, username, password, role)
    if not success:
        raise HTTPException(400, "Failed to update user")

    return {"status": "ok"}


@router.delete("/{user_id}")
async def delete_user_api(user_id: int, request: Request):
    user = await require_admin_user(request)

    if user["id"] == user_id:
        raise HTTPException(400, "Cannot delete yourself")

    await db.delete_user(user_id)
    return {"status": "ok"}
