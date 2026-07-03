import os

import aiosqlite


async def connect(path: str) -> aiosqlite.Connection:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = await aiosqlite.connect(path)
    conn.row_factory = aiosqlite.Row
    return conn
