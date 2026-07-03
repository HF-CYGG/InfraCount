from typing import Any, Dict, Optional

from app import db


async def authenticate(username: Optional[str], password: Optional[str]) -> Optional[Dict[str, Any]]:
    if not username or not password:
        return None
    return await db.authenticate_user(username, password)


async def create_session(user_id: int) -> str:
    return await db.create_session(user_id)


async def delete_session(token: str) -> None:
    await db.delete_session(token)


async def change_password(user_id: int, new_password: str) -> None:
    await db.change_password(user_id, new_password)
