import os
import sys
import asyncio


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


async def main() -> int:
    from app import db

    if db.use_sqlite():
        await db.init_sqlite()
        conn = db.__dict__.get("_sqlite")
        if conn is None:
            raise RuntimeError("sqlite not initialized")
        async with conn.execute("SELECT id FROM users WHERE username='admin'") as cur:
            row = await cur.fetchone()
        if not row:
            async with conn.execute("SELECT id FROM users WHERE role='admin' ORDER BY id LIMIT 1") as cur:
                row = await cur.fetchone()
        if not row:
            raise RuntimeError("admin user not found")
        admin_id = int(row[0])
    else:
        await db.init_pool()
        pool = db.__dict__.get("_pool")
        if pool is None:
            raise RuntimeError("mysql pool not initialized")
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT id FROM users WHERE username=%s", ("admin",))
                row = await cur.fetchone()
                if not row:
                    await cur.execute("SELECT id FROM users WHERE role=%s ORDER BY id LIMIT 1", ("admin",))
                    row = await cur.fetchone()
        if not row:
            raise RuntimeError("admin user not found")
        admin_id = int(row[0])

    token = await db.create_session(admin_id)
    print(token)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

