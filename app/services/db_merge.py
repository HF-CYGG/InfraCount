from __future__ import annotations

import asyncio
import uuid

from app import config
from app.storage import sqlite as sqlite_storage


class DatabaseMaintenanceError(RuntimeError):
    pass


class MergeAlreadyRunningError(RuntimeError):
    pass


_merge_lock = asyncio.Lock()


async def is_maintenance_active() -> bool:
    if config.DB_DRIVER != "sqlite":
        return False
    conn = await sqlite_storage.connect(config.DB_SQLITE_PATH)
    try:
        async with conn.execute(
            "SELECT active FROM maintenance_state WHERE key='db_merge'"
        ) as cursor:
            row = await cursor.fetchone()
        return bool(row and row[0])
    except Exception as exc:
        if "no such table" in str(exc).lower():
            return False
        raise
    finally:
        await conn.close()


async def start_maintenance(actor: str) -> str:
    if _merge_lock.locked():
        raise MergeAlreadyRunningError("database merge already running")
    await _merge_lock.acquire()
    owner = uuid.uuid4().hex
    try:
        if await is_maintenance_active():
            raise MergeAlreadyRunningError("database merge already running")
        conn = await sqlite_storage.connect(config.DB_SQLITE_PATH)
        try:
            await conn.execute(
                "INSERT INTO maintenance_state(key,active,owner,actor,started_at) "
                "VALUES ('db_merge',1,?,?,CURRENT_TIMESTAMP) "
                "ON CONFLICT(key) DO UPDATE SET active=1, owner=excluded.owner, "
                "actor=excluded.actor, started_at=CURRENT_TIMESTAMP",
                (owner, str(actor or "")),
            )
            await conn.commit()
        finally:
            await conn.close()
        return owner
    except Exception:
        if _merge_lock.locked():
            _merge_lock.release()
        raise


async def finish_maintenance(owner: str) -> None:
    if config.DB_DRIVER == "sqlite":
        conn = await sqlite_storage.connect(config.DB_SQLITE_PATH)
        try:
            await conn.execute(
                "DELETE FROM maintenance_state WHERE key='db_merge' AND owner=?",
                (str(owner or ""),),
            )
            await conn.commit()
        finally:
            await conn.close()
    if _merge_lock.locked():
        _merge_lock.release()


async def clear_stale_maintenance() -> None:
    if config.DB_DRIVER != "sqlite":
        return
    conn = await sqlite_storage.connect(config.DB_SQLITE_PATH)
    try:
        await conn.execute("DELETE FROM maintenance_state WHERE key='db_merge'")
        await conn.commit()
    finally:
        await conn.close()
    release_process_lock()


def release_process_lock() -> None:
    if _merge_lock.locked():
        _merge_lock.release()
