from app import config

def _aiomysql():
    try:
        import aiomysql  # type: ignore
        return aiomysql
    except Exception:
        return None

_pool = None

async def init_pool():
    global _pool
    try:
        aio = _aiomysql()
        if not aio:
            _pool = None
            return
        _pool = await aio.create_pool(
                host=config.DB_HOST,
                port=config.DB_PORT,
                user=config.DB_USER,
                password=config.DB_PASSWORD,
                db=config.DB_NAME,
                autocommit=True,
                minsize=1,
                maxsize=10,
                charset="utf8mb4",
        )
    except Exception:
        _pool = None

async def close_pool():
    global _pool
    if _pool:
        _pool.close()
        await _pool.wait_closed()
        _pool = None

async def save_device_data(d):
    global _pool
    if _pool is None:
        await init_pool()
    if _pool is None:
        return
    async with _pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO device_data(uuid,in_count,out_count,time,battery_level,signal_status) VALUES(%s,%s,%s,%s,%s,%s)",
                (
                    d.get("uuid"),
                    d.get("in"),
                    d.get("out"),
                    d.get("time"),
                    d.get("battery_level"),
                    d.get("signal_status"),
                ),
            )
