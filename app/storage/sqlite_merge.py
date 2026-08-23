from __future__ import annotations

import aiosqlite

from app import config
from app.storage import sqlite as sqlite_storage


async def connect() -> aiosqlite.Connection:
    return await sqlite_storage.connect(config.DB_SQLITE_PATH)


async def begin(conn: aiosqlite.Connection) -> None:
    await conn.execute("BEGIN IMMEDIATE")
