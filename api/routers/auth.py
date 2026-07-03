from typing import Dict

from fastapi import APIRouter, Body, HTTPException, Request, Response

from api.dependencies import delete_cookie_kwargs, require_session_user, session_cookie_kwargs
from app import config
from app.services import auth as auth_service

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login")
async def auth_login(response: Response, payload: Dict[str, str] = Body(...)):
    user = await auth_service.authenticate(payload.get("username"), payload.get("password"))
    if not user:
        raise HTTPException(401, "Invalid credentials")

    session_token = await auth_service.create_session(user["id"])
    response.set_cookie(value=session_token, **session_cookie_kwargs())
    return {"status": "ok", "user": user}


@router.post("/logout")
async def auth_logout(request: Request, response: Response):
    token = request.cookies.get(config.SESSION_COOKIE_NAME)
    if token:
        await auth_service.delete_session(token)
    response.delete_cookie(**delete_cookie_kwargs())
    return {"status": "ok"}


@router.get("/me")
async def auth_me(request: Request):
    user = await require_session_user(request)
    return {"user": user}


@router.post("/password")
async def auth_change_password(request: Request, payload: Dict[str, str] = Body(...)):
    user = await require_session_user(request)
    new_pw = payload.get("new_password")
    if not new_pw:
        raise HTTPException(400, "Missing password")

    await auth_service.change_password(user["id"], new_pw)
    return {"status": "ok"}
