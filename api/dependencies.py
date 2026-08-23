from typing import Any, Awaitable, Callable, Dict, Literal

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from app import config, db, security
from app.services import db_merge as db_merge_service

AuthLevel = Literal["public", "optional_session", "session", "admin"]


def _normalize_path(path: str) -> str:
    p = str(path or "").strip() or "/"
    if len(p) > 1:
        p = p.rstrip("/")
    return p


def classify_api_auth(path: str, method: str) -> AuthLevel:
    p = _normalize_path(path)
    m = str(method or "GET").upper()

    if m == "OPTIONS":
        return "public"
    if not p.startswith("/api/v1"):
        return "public"
    if p == "/api/v1/health":
        return "public"
    if p == "/api/v1/auth/login":
        return "public"
    if p == "/api/v1/auth/logout":
        return "optional_session"
    if p in {"/api/v1/auth/me", "/api/v1/auth/password"}:
        return "session"
    if p == "/api/v1/system/status":
        return "admin"
    if p.startswith("/api/v1/users"):
        return "admin"
    if p.startswith("/api/v1/admin"):
        return "admin"
    if m in {"POST", "PUT", "PATCH", "DELETE"}:
        return "admin"
    return "session"


def session_cookie_kwargs() -> Dict[str, Any]:
    return {
        "key": config.SESSION_COOKIE_NAME,
        "httponly": True,
        "max_age": config.SESSION_MAX_AGE_SEC,
        "samesite": config.SESSION_COOKIE_SAMESITE,
        "secure": config.SESSION_COOKIE_SECURE,
    }


def delete_cookie_kwargs() -> Dict[str, Any]:
    return {
        "key": config.SESSION_COOKIE_NAME,
        "samesite": config.SESSION_COOKIE_SAMESITE,
        "secure": config.SESSION_COOKIE_SECURE,
    }


async def require_session_user(request: Request) -> Dict[str, Any]:
    token = request.cookies.get(config.SESSION_COOKIE_NAME)
    if not token:
        raise HTTPException(401, "Not logged in")
    user = await db.get_user_by_token(token)
    if not user:
        raise HTTPException(401, "Invalid session")
    request.state.user = user
    return user


async def require_admin_user(request: Request) -> Dict[str, Any]:
    user = await require_session_user(request)
    if user.get("role") != "admin":
        raise HTTPException(403, "Access denied")
    return user


async def enforce_api_auth(request: Request) -> None:
    level = classify_api_auth(request.url.path, request.method)
    if level == "public":
        return

    token = request.cookies.get(config.SESSION_COOKIE_NAME)
    if level == "optional_session" and not token:
        return
    if not token:
        raise HTTPException(401, "Not logged in")

    user = await db.get_user_by_token(token)
    if not user:
        if level == "optional_session":
            return
        raise HTTPException(401, "Invalid session")

    request.state.user = user
    if level == "admin" and user.get("role") != "admin":
        raise HTTPException(403, "Access denied")


async def enforce_api_csrf(request: Request) -> None:
    if not config.CSRF_ENABLE:
        return

    method = str(request.method or "GET").upper()
    if method in {"GET", "HEAD", "OPTIONS"}:
        return

    path = _normalize_path(request.url.path)
    if path == "/api/v1/auth/login":
        origin = str(request.headers.get("origin") or "").rstrip("/")
        allowed_origins = {str(item).rstrip("/") for item in config.CORS_ALLOW_ORIGINS}
        if origin and origin not in allowed_origins and "*" not in allowed_origins:
            raise HTTPException(403, "Untrusted request origin")
        return

    session_token = request.cookies.get(config.SESSION_COOKIE_NAME)
    if not session_token:
        return
    if path == "/api/v1/auth/logout" and not getattr(request.state, "user", None):
        return

    csrf_token = str(request.headers.get("x-csrf-token") or "")
    if not security.validate_csrf(csrf_token, session_token):
        raise HTTPException(
            403,
            "CSRF validation failed",
            headers={"X-CSRF-Error": "invalid"},
        )


async def enforce_api_maintenance(request: Request) -> None:
    method = str(request.method or "GET").upper()
    if method in {"GET", "HEAD", "OPTIONS"}:
        return
    path = _normalize_path(request.url.path)
    if path in {"/api/v1/auth/logout", "/api/v1/admin/db-merge/execute"}:
        return
    if await db_merge_service.is_maintenance_active():
        raise HTTPException(
            423,
            "Database maintenance in progress",
            headers={"Retry-After": "5"},
        )


async def api_auth_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Any]],
):
    try:
        await enforce_api_auth(request)
        await enforce_api_maintenance(request)
        await enforce_api_csrf(request)
    except HTTPException as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=getattr(exc, "headers", None),
        )
    return await call_next(request)
