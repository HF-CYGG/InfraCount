from app import config
import os
import sqlite3
import asyncio
from app.events import bus

def _aiomysql():
    try:
        import aiomysql  # type: ignore
        return aiomysql
    except Exception:
        return None

_pool = None
_sqlite = None

def _aiosqlite():
    try:
        import aiosqlite  # type: ignore
        return aiosqlite
    except Exception:
        return None

def use_sqlite():
    return str(getattr(config, "DB_DRIVER", "sqlite")).lower() == "sqlite"

async def init_pool():
    if use_sqlite():
        await init_sqlite()
        return
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
    if use_sqlite():
        await close_sqlite()
        return
    global _pool
    if _pool:
        _pool.close()
        await _pool.wait_closed()
        _pool = None

async def init_sqlite():
    global _sqlite
    aio = _aiosqlite()
    os.makedirs(os.path.dirname(config.DB_SQLITE_PATH), exist_ok=True)
    if aio:
        _sqlite = await aio.connect(config.DB_SQLITE_PATH)
        _sqlite.row_factory = aio.Row
        await _sqlite.execute(
            "CREATE TABLE IF NOT EXISTS device_data (id INTEGER PRIMARY KEY AUTOINCREMENT, uuid TEXT, in_count INTEGER, out_count INTEGER, time TEXT, battery_level INTEGER, signal_status INTEGER, warn_status INTEGER, batterytx_level INTEGER, rec_type INTEGER, create_time TEXT DEFAULT (datetime('now')))"
        )
        try:
            await _sqlite.execute("ALTER TABLE device_data ADD COLUMN warn_status INTEGER")
        except Exception:
            pass
        try:
            await _sqlite.execute("ALTER TABLE device_data ADD COLUMN batterytx_level INTEGER")
        except Exception:
            pass
        try:
            await _sqlite.execute("ALTER TABLE device_data ADD COLUMN rec_type INTEGER")
        except Exception:
            pass
        await _sqlite.execute(
            "CREATE INDEX IF NOT EXISTS idx_device_data_uuid_time ON device_data(uuid, time)"
        )
        await _sqlite.execute(
            "CREATE TABLE IF NOT EXISTS alerts (id INTEGER PRIMARY KEY AUTOINCREMENT, uuid TEXT, type TEXT, level INTEGER, info TEXT, time TEXT DEFAULT (datetime('now')))"
        )
        await _sqlite.execute(
            "CREATE TABLE IF NOT EXISTS device_registry (id INTEGER PRIMARY KEY AUTOINCREMENT, uuid TEXT UNIQUE, name TEXT, category TEXT, create_time TEXT DEFAULT (datetime('now')))"
        )
        await _sqlite.execute(
            "CREATE TABLE IF NOT EXISTS ops_log (id INTEGER PRIMARY KEY AUTOINCREMENT, actor TEXT, action TEXT, target_uuid TEXT, payload TEXT, time TEXT DEFAULT (datetime('now')))"
        )
        await _sqlite.commit()
    else:
        _sqlite = None
        await asyncio.to_thread(_init_sqlite_sync)

def _init_sqlite_sync():
    conn = sqlite3.connect(config.DB_SQLITE_PATH, check_same_thread=False)
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS device_data (id INTEGER PRIMARY KEY AUTOINCREMENT, uuid TEXT, in_count INTEGER, out_count INTEGER, time TEXT, battery_level INTEGER, signal_status INTEGER, warn_status INTEGER, batterytx_level INTEGER, rec_type INTEGER, create_time TEXT DEFAULT (datetime('now')))"
        )
        try:
            conn.execute("ALTER TABLE device_data ADD COLUMN warn_status INTEGER")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE device_data ADD COLUMN batterytx_level INTEGER")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE device_data ADD COLUMN rec_type INTEGER")
        except Exception:
            pass
        try:
            conn.execute("CREATE INDEX IF NOT EXISTS idx_device_data_uuid_time ON device_data(uuid, time)")
        except Exception:
            pass
        conn.execute(
            "CREATE TABLE IF NOT EXISTS alerts (id INTEGER PRIMARY KEY AUTOINCREMENT, uuid TEXT, type TEXT, level INTEGER, info TEXT, time TEXT DEFAULT (datetime('now')))"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS device_registry (id INTEGER PRIMARY KEY AUTOINCREMENT, uuid TEXT UNIQUE, name TEXT, category TEXT, create_time TEXT DEFAULT (datetime('now')))"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS ops_log (id INTEGER PRIMARY KEY AUTOINCREMENT, actor TEXT, action TEXT, target_uuid TEXT, payload TEXT, time TEXT DEFAULT (datetime('now')))"
        )
        conn.commit()
    finally:
        conn.close()

async def close_sqlite():
    global _sqlite
    if _sqlite:
        await _sqlite.close()
        _sqlite = None

async def save_device_data(d):
    if use_sqlite():
        global _sqlite
        if _sqlite is None:
            await init_sqlite()
        if _sqlite:
            await _sqlite.execute(
                "INSERT INTO device_data(uuid,in_count,out_count,time,battery_level,signal_status,warn_status,batterytx_level,rec_type) VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    d.get("uuid"),
                    d.get("in"),
                    d.get("out"),
                    d.get("time"),
                    d.get("battery_level"),
                    d.get("signal_status"),
                    d.get("warn_status"),
                    d.get("batterytx_level"),
                    d.get("rec_type"),
                ),
            )
            await _sqlite.commit()
            await bus.publish(d.get("uuid"), {
                "type": "update",
                "data": d,
            })
            await _maybe_alert(d)
            return
        else:
            await asyncio.to_thread(_sqlite_exec_sync,
                "INSERT INTO device_data(uuid,in_count,out_count,time,battery_level,signal_status,warn_status,batterytx_level,rec_type) VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    d.get("uuid"),
                    d.get("in"),
                    d.get("out"),
                    d.get("time"),
                    d.get("battery_level"),
                    d.get("signal_status"),
                    d.get("warn_status"),
                    d.get("batterytx_level"),
                    d.get("rec_type"),
                )
            )
            await bus.publish(d.get("uuid"), {
                "type": "update",
                "data": d,
            })
            await _maybe_alert(d)
            return
    global _pool
    if _pool is None:
        await init_pool()
    if _pool is None:
        return
    async with _pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "CREATE TABLE IF NOT EXISTS device_data (id BIGINT AUTO_INCREMENT PRIMARY KEY, uuid VARCHAR(64), in_count INT, out_count INT, time VARCHAR(32), battery_level INT, signal_status INT, warn_status INT, batterytx_level INT, rec_type INT, create_time DATETIME DEFAULT CURRENT_TIMESTAMP)"
            )
            await cur.execute(
                "INSERT INTO device_data(uuid,in_count,out_count,time,battery_level,signal_status,warn_status,batterytx_level,rec_type) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    d.get("uuid"),
                    d.get("in"),
                    d.get("out"),
                    d.get("time"),
                    d.get("battery_level"),
                    d.get("signal_status"),
                    d.get("warn_status"),
                    d.get("batterytx_level"),
                    d.get("rec_type"),
                ),
            )
            await bus.publish(d.get("uuid"), {
                "type": "update",
                "data": d,
            })
            await _maybe_alert(d)

async def fetch_latest(uuid: str):
    if use_sqlite():
        global _sqlite
        if _sqlite is None:
            await init_sqlite()
        if _sqlite:
            cur = await _sqlite.execute(
                "SELECT uuid,in_count,out_count,time,battery_level,signal_status FROM device_data WHERE uuid=? ORDER BY id DESC LIMIT 1",
                (uuid,),
            )
            row = await cur.fetchone()
            return dict(row) if row else None
        else:
            row = await asyncio.to_thread(_sqlite_query_one,
                "SELECT uuid,in_count,out_count,time,battery_level,signal_status FROM device_data WHERE uuid=? ORDER BY id DESC LIMIT 1",
                (uuid,)
            )
            return row
    if _pool is None:
        await init_pool()
    if _pool is None:
        return None
    async with _pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT uuid,in_count,out_count,time,battery_level,signal_status FROM device_data WHERE uuid=%s ORDER BY id DESC LIMIT 1",
                (uuid,),
            )
            row = await cur.fetchone()
            if not row:
                return None
            return {
                "uuid": row[0],
                "in_count": row[1],
                "out_count": row[2],
                "time": row[3],
                "battery_level": row[4],
                "signal_status": row[5],
            }

async def fetch_history(uuid: str, start: str | None, end: str | None, limit: int):
    if use_sqlite():
        global _sqlite
        if _sqlite is None:
            await init_sqlite()
        sql = "SELECT id,uuid,in_count,out_count,time,battery_level,signal_status FROM device_data WHERE uuid=?"
        params = [uuid]
        if start:
            sql += " AND time>=?"; params.append(start)
        if end:
            sql += " AND time<=?"; params.append(end)
        sql += " ORDER BY time DESC LIMIT ?"; params.append(limit)
        if _sqlite:
            cur = await _sqlite.execute(sql, params)
            rows = await cur.fetchall()
            return [dict(r) for r in rows]
        else:
            rows = await asyncio.to_thread(_sqlite_query_all, sql, tuple(params))
            return rows
    if _pool is None:
        await init_pool()
    if _pool is None:
        return []
    where = ["uuid=%s"]
    params = [uuid]
    if start:
        where.append("time>=%s"); params.append(start)
    if end:
        where.append("time<=%s"); params.append(end)
    sql = "SELECT uuid,in_count,out_count,time,battery_level,signal_status FROM device_data WHERE " + " AND ".join(where) + " ORDER BY time DESC LIMIT %s"
    params.append(limit)
    async with _pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(sql, params)
            rows = await cur.fetchall()
            return [
                {"uuid": r[0], "in_count": r[1], "out_count": r[2], "time": r[3], "battery_level": r[4], "signal_status": r[5]}
                for r in rows
            ]

async def list_devices(limit: int):
    if use_sqlite():
        global _sqlite
        if _sqlite is None:
            await init_sqlite()
        sql = "SELECT uuid, MAX(time) AS last_time, MAX(id) AS last_id, (SELECT name FROM device_registry WHERE device_registry.uuid=device_data.uuid) AS name, (SELECT category FROM device_registry WHERE device_registry.uuid=device_data.uuid) AS category FROM device_data GROUP BY uuid ORDER BY last_time DESC LIMIT ?"
        if _sqlite:
            cur = await _sqlite.execute(sql, (limit,))
            rows = await cur.fetchall()
            return [{"uuid": r[0], "last_time": r[1], "last_id": r[2], "name": r[3], "category": r[4]} for r in rows]
        else:
            rows = await asyncio.to_thread(_sqlite_query_all, sql, (limit,))
            return rows
    if _pool is None:
        await init_pool()
    if _pool is None:
        return []
    async with _pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT t.uuid, t.last_time, t.last_id, r.name, r.category FROM (SELECT uuid, MAX(time) AS last_time, MAX(id) AS last_id FROM device_data GROUP BY uuid) t LEFT JOIN device_registry r ON r.uuid=t.uuid ORDER BY t.last_time DESC LIMIT %s",
                (limit,),
            )
            rows = await cur.fetchall()
            return [{"uuid": r[0], "last_time": r[1], "last_id": r[2], "name": r[3], "category": r[4]} for r in rows]

async def stats_daily(uuid: str, start: str | None, end: str | None):
    if use_sqlite():
        global _sqlite
        if _sqlite is None:
            await init_sqlite()
        sql = "SELECT substr(time,1,10) AS day, SUM(in_count) AS in_total, SUM(out_count) AS out_total FROM device_data WHERE uuid=?"
        params = [uuid]
        if start:
            sql += " AND time>=?"; params.append(start)
        if end:
            sql += " AND time<=?"; params.append(end)
        sql += " GROUP BY day ORDER BY day ASC"
        if _sqlite:
            cur = await _sqlite.execute(sql, params)
            rows = await cur.fetchall()
            return [dict(r) for r in rows]
        else:
            rows = await asyncio.to_thread(_sqlite_query_all, sql, tuple(params))
            return rows
    if _pool is None:
        await init_pool()
    if _pool is None:
        return []
    sql = "SELECT DATE(time) AS day, SUM(in_count) AS in_total, SUM(out_count) AS out_total FROM device_data WHERE uuid=%s"
    params = [uuid]
    if start:
        sql += " AND time>=%s"; params.append(start)
    if end:
        sql += " AND time<=%s"; params.append(end)
    sql += " GROUP BY day ORDER BY day ASC"
    async with _pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(sql, params)
            rows = await cur.fetchall()
            return [{"day": r[0], "in_total": r[1], "out_total": r[2]} for r in rows]

async def stats_hourly(uuid: str, date: str):
    if use_sqlite():
        global _sqlite
        if _sqlite is None:
            await init_sqlite()
        sql = "SELECT substr(time,12,2) || ':00' AS hour, SUM(in_count) AS in_total, SUM(out_count) AS out_total FROM device_data WHERE uuid=? AND substr(time,1,10)=? GROUP BY hour ORDER BY hour ASC"
        if _sqlite:
            cur = await _sqlite.execute(sql, (uuid, date))
            rows = await cur.fetchall()
            return [dict(r) for r in rows]
        else:
            rows = await asyncio.to_thread(_sqlite_query_all, sql, (uuid, date))
            return rows
    if _pool is None:
        await init_pool()
    if _pool is None:
        return []
    sql = (
        "SELECT DATE_FORMAT(time, '%H:00') AS hour, SUM(in_count) AS in_total, SUM(out_count) AS out_total FROM device_data WHERE uuid=%s AND DATE(time)=%s GROUP BY hour ORDER BY hour ASC"
    )
    async with _pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(sql, (uuid, date))
            rows = await cur.fetchall()
            return [{"hour": r[0], "in_total": r[1], "out_total": r[2]} for r in rows]

async def stats_summary(uuid: str):
    if use_sqlite():
        global _sqlite
        if _sqlite is None:
            await init_sqlite()
        if _sqlite:
            cur = await _sqlite.execute("SELECT SUM(in_count), SUM(out_count) FROM device_data WHERE uuid=?", (uuid,))
            totals = await cur.fetchone()
            cur2 = await _sqlite.execute("SELECT in_count,out_count,time FROM device_data WHERE uuid=? ORDER BY id DESC LIMIT 1", (uuid,))
            last = await cur2.fetchone()
            return {
                "in_total": (totals[0] or 0) if totals else 0,
                "out_total": (totals[1] or 0) if totals else 0,
                "last_in": last[0] if last else None,
                "last_out": last[1] if last else None,
                "last_time": last[2] if last else None,
            }
        else:
            totals = await asyncio.to_thread(_sqlite_query_one, "SELECT SUM(in_count), SUM(out_count) FROM device_data WHERE uuid=?", (uuid,))
            last = await asyncio.to_thread(_sqlite_query_one, "SELECT in_count,out_count,time FROM device_data WHERE uuid=? ORDER BY id DESC LIMIT 1", (uuid,))
            tv = list(totals.values()) if isinstance(totals, dict) else (totals or [])
            lv = list(last.values()) if isinstance(last, dict) else (last or [])
            return {
                "in_total": (tv[0] if len(tv)>0 else 0) or 0,
                "out_total": (tv[1] if len(tv)>1 else 0) or 0,
                "last_in": lv[0] if len(lv)>0 else None,
                "last_out": lv[1] if len(lv)>1 else None,
                "last_time": lv[2] if len(lv)>2 else None,
            }
    if _pool is None:
        await init_pool()
    if _pool is None:
        return {"in_total": 0, "out_total": 0, "last_in": None, "last_out": None, "last_time": None}
    async with _pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT SUM(in_count), SUM(out_count) FROM device_data WHERE uuid=%s", (uuid,))
            totals = await cur.fetchone()
            await cur.execute("SELECT in_count,out_count,time FROM device_data WHERE uuid=%s ORDER BY id DESC LIMIT 1", (uuid,))
            last = await cur.fetchone()
            return {
                "in_total": (totals[0] or 0) if totals else 0,
                "out_total": (totals[1] or 0) if totals else 0,
                "last_in": last[0] if last else None,
                "last_out": last[1] if last else None,
                "last_time": last[2] if last else None,
            }

async def stats_top(metric: str, start: str | None, end: str | None, limit: int):
    field = "in_count" if metric == "in" else "out_count"
    if use_sqlite():
        global _sqlite
        if _sqlite is None:
            await init_sqlite()
        if _sqlite is None:
            return []
        sql = f"SELECT uuid, SUM({field}) AS total FROM device_data WHERE 1=1"
        params = []
        if start:
            sql += " AND time>=?"; params.append(start)
        if end:
            sql += " AND time<=?"; params.append(end)
        sql += " GROUP BY uuid ORDER BY total DESC LIMIT ?"; params.append(limit)
        if _sqlite:
            cur = await _sqlite.execute(sql, params)
            rows = await cur.fetchall()
            return [{"uuid": r[0], "total": r[1]} for r in rows]
        else:
            rows = await asyncio.to_thread(_sqlite_query_all, sql, tuple(params))
            return rows
    if _pool is None:
        await init_pool()
    if _pool is None:
        return []
    sql = f"SELECT uuid, SUM({field}) AS total FROM device_data WHERE 1=1"
    params = []
    if start:
        sql += " AND time>=%s"; params.append(start)
    if end:
        sql += " AND time<=%s"; params.append(end)
    sql += " GROUP BY uuid ORDER BY total DESC LIMIT %s"; params.append(limit)
    async with _pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(sql, params)
            rows = await cur.fetchall()
            return [{"uuid": r[0], "total": r[1]} for r in rows]

def _sqlite_exec_sync(sql: str, params: tuple = ()):
    conn = sqlite3.connect(config.DB_SQLITE_PATH, check_same_thread=False)
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        conn.commit()
    finally:
        conn.close()

def _sqlite_query_one(sql: str, params: tuple = ()):
    conn = sqlite3.connect(config.DB_SQLITE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def _sqlite_query_all(sql: str, params: tuple = ()):
    conn = sqlite3.connect(config.DB_SQLITE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

# Admin utilities: list with count, CRUD operations
async def admin_count_records(uuid: str | None, start: str | None, end: str | None):
    if use_sqlite():
        global _sqlite
        if _sqlite is None:
            await init_sqlite()
        if _sqlite is None:
            return 0
        sql = "SELECT COUNT(1) FROM device_data WHERE 1=1"
        params = []
        if uuid:
            sql += " AND uuid=?"; params.append(uuid)
        if start:
            sql += " AND time>=?"; params.append(start)
        if end:
            sql += " AND time<=?"; params.append(end)
        cur = await _sqlite.execute(sql, params)
        row = await cur.fetchone()
        return row[0] if row else 0
    if _pool is None:
        await init_pool()
    if _pool is None:
        return 0
    sql = "SELECT COUNT(1) FROM device_data WHERE 1=1"
    params = []
    if uuid:
        sql += " AND uuid=%s"; params.append(uuid)
    if start:
        sql += " AND time>=%s"; params.append(start)
    if end:
        sql += " AND time<=%s"; params.append(end)
    async with _pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(sql, params)
            row = await cur.fetchone()
            return row[0] if row else 0

async def admin_list_records(uuid: str | None, start: str | None, end: str | None, offset: int, limit: int):
    if use_sqlite():
        global _sqlite
        if _sqlite is None:
            await init_sqlite()
        if _sqlite is None:
            return []
        sql = "SELECT id,uuid,in_count,out_count,time,battery_level,signal_status,warn_status,batterytx_level,rec_type FROM device_data WHERE 1=1"
        params = []
        if uuid:
            sql += " AND uuid=?"; params.append(uuid)
        if start:
            sql += " AND time>=?"; params.append(start)
        if end:
            sql += " AND time<=?"; params.append(end)
        sql += " ORDER BY time DESC LIMIT ? OFFSET ?"; params.extend([limit, offset])
        cur = await _sqlite.execute(sql, params)
        rows = await cur.fetchall()
        return [dict(r) for r in rows]
    if _pool is None:
        await init_pool()
    if _pool is None:
        return []
    sql = "SELECT id,uuid,in_count,out_count,time,battery_level,signal_status,warn_status,batterytx_level,rec_type FROM device_data WHERE 1=1"
    params = []
    if uuid:
        sql += " AND uuid=%s"; params.append(uuid)
    if start:
        sql += " AND time>=%s"; params.append(start)
    if end:
        sql += " AND time<=%s"; params.append(end)
    sql += " ORDER BY time DESC LIMIT %s OFFSET %s"; params.extend([limit, offset])
    async with _pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(sql, params)
            rows = await cur.fetchall()
            return [
                {"id": r[0], "uuid": r[1], "in_count": r[2], "out_count": r[3], "time": r[4], "battery_level": r[5], "signal_status": r[6], "warn_status": r[7], "batterytx_level": r[8], "rec_type": r[9]}
                for r in rows
            ]

async def admin_update_record(record_id: int, fields: dict):
    allowed = ["uuid", "in_count", "out_count", "time", "battery_level", "signal_status", "warn_status", "batterytx_level", "rec_type"]
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return False
    if use_sqlite():
        global _sqlite
        if _sqlite is None:
            await init_sqlite()
        if _sqlite is None:
            return False
        sets = ", ".join([f"{k}=?" for k in updates.keys()])
        params = list(updates.values()) + [record_id]
        await _sqlite.execute(f"UPDATE device_data SET {sets} WHERE id=?", params)
        await _sqlite.commit()
        return True
    if _pool is None:
        await init_pool()
    if _pool is None:
        return False
    sets = ", ".join([f"{k}=%s" for k in updates.keys()])
    params = list(updates.values()) + [record_id]
    async with _pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(f"UPDATE device_data SET {sets} WHERE id=%s", params)
    return True

async def admin_delete_record(record_id: int):
    if use_sqlite():
        global _sqlite
        if _sqlite is None:
            await init_sqlite()
        if _sqlite is None:
            return False
        await _sqlite.execute("DELETE FROM device_data WHERE id=?", (record_id,))
        await _sqlite.commit()
        return True
    if _pool is None:
        await init_pool()
    if _pool is None:
        return False
    async with _pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("DELETE FROM device_data WHERE id=%s", (record_id,))
    return True

async def admin_delete_range(uuid: str, start: str, end: str):
    if use_sqlite():
        global _sqlite
        if _sqlite is None:
            await init_sqlite()
        if _sqlite is None:
            return 0
        cur = await _sqlite.execute("DELETE FROM device_data WHERE uuid=? AND time>=? AND time<=?", (uuid, start, end))
        rc = cur.rowcount if hasattr(cur, "rowcount") else 0
        await _sqlite.commit()
        return rc
    if _pool is None:
        await init_pool()
    if _pool is None:
        return 0
    async with _pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("DELETE FROM device_data WHERE uuid=%s AND time>=%s AND time<=%s", (uuid, start, end))
            return getattr(cur, "rowcount", 0)

async def admin_create_record(d: dict):
    allowed = ["uuid", "in_count", "out_count", "time", "battery_level", "signal_status", "warn_status", "batterytx_level", "rec_type"]
    data = {k: d.get(k) for k in allowed}
    if use_sqlite():
        global _sqlite
        if _sqlite is None:
            await init_sqlite()
        if _sqlite is None:
            return None
        cur = await _sqlite.execute(
            "INSERT INTO device_data(uuid,in_count,out_count,time,battery_level,signal_status,warn_status,batterytx_level,rec_type) VALUES(?,?,?,?,?,?,?,?,?)",
            (data["uuid"], data["in_count"], data["out_count"], data["time"], data["battery_level"], data["signal_status"], data.get("warn_status"), data.get("batterytx_level"), data.get("rec_type")),
        )
        await _sqlite.commit()
        return cur.lastrowid
    if _pool is None:
        await init_pool()
    if _pool is None:
        return None
    async with _pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO device_data(uuid,in_count,out_count,time,battery_level,signal_status,warn_status,batterytx_level,rec_type) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (data["uuid"], data["in_count"], data["out_count"], data["time"], data["battery_level"], data["signal_status"], data.get("warn_status"), data.get("batterytx_level"), data.get("rec_type")),
            )
            return cur.lastrowid if hasattr(cur, "lastrowid") else None
async def _maybe_alert(d: dict):
    uuid = d.get("uuid")
    bat = d.get("battery_level")
    sig = d.get("signal_status")
    ws = d.get("warn_status")
    btx = d.get("batterytx_level")
    rt = d.get("rec_type")
    msgs = []
    if bat is not None and bat < 20:
        msgs.append(("battery_low", bat, f"battery={bat}%"))
    if sig is not None and sig == 1:
        msgs.append(("signal_offline", sig, "signal offline"))
    if ws is not None and ws != 0:
        msgs.append(("device_warn", ws, f"warn_status={ws}"))
    if btx is not None and btx < 30:
        msgs.append(("battery_tx_low", btx, f"batterytx={btx}%"))
    if rt is not None and rt == 1:
        msgs.append(("record_backlog", rt, "rec_type=1"))
    if not msgs:
        return
    if use_sqlite():
        if _sqlite:
            for t, lv, info in msgs:
                await _sqlite.execute("INSERT INTO alerts(uuid,type,level,info) VALUES(?,?,?,?)", (uuid, t, lv, info))
            await _sqlite.commit()
        else:
            for t, lv, info in msgs:
                await asyncio.to_thread(_sqlite_exec_sync, "INSERT INTO alerts(uuid,type,level,info) VALUES(?,?,?,?)", (uuid, t, lv, info))
        return
    if _pool is None:
        await init_pool()
    if _pool is None:
        return
    async with _pool.acquire() as conn:
        async with conn.cursor() as cur:
            for t, lv, info in msgs:
                await cur.execute("INSERT INTO alerts(uuid,type,level,info,time) VALUES(%s,%s,%s,%s,NOW())", (uuid, t, lv, info))

async def list_alerts(uuid: str | None, limit: int = 100):
    if use_sqlite():
        if _sqlite is None:
            await init_sqlite()
        sql = "SELECT id,uuid,type,level,info,time FROM alerts"
        params = []
        if uuid:
            sql += " WHERE uuid=?"; params.append(uuid)
        sql += " ORDER BY id DESC LIMIT ?"; params.append(limit)
        if _sqlite:
            cur = await _sqlite.execute(sql, tuple(params))
            rows = await cur.fetchall()
            return [dict(r) for r in rows]
        return await asyncio.to_thread(_sqlite_query_all, sql, tuple(params))
    if _pool is None:
        await init_pool()
    if _pool is None:
        return []
    sql = "SELECT id,uuid,type,level,info,time FROM alerts"
    params = []
    if uuid:
        sql += " WHERE uuid=%s"; params.append(uuid)
    sql += " ORDER BY id DESC LIMIT %s"; params.append(limit)
    async with _pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(sql, params)
            rows = await cur.fetchall()
            return [
                {"id": r[0], "uuid": r[1], "type": r[2], "level": r[3], "info": r[4], "time": r[5]}
                for r in rows
            ]

async def admin_list_registry(category: str | None, search: str | None, offset: int, limit: int):
    if use_sqlite():
        if _sqlite is None:
            await init_sqlite()
        sql = "SELECT id,uuid,name,category,create_time FROM device_registry WHERE 1=1"
        params = []
        if category:
            sql += " AND category=?"; params.append(category)
        if search:
            sql += " AND (uuid LIKE ? OR name LIKE ?)"; params.extend([f"%{search}%", f"%{search}%"]) 
        sql += " ORDER BY id DESC LIMIT ? OFFSET ?"; params.extend([limit, offset])
        if _sqlite:
            cur = await _sqlite.execute(sql, tuple(params))
            rows = await cur.fetchall()
            return [dict(r) for r in rows]
        return await asyncio.to_thread(_sqlite_query_all, sql, tuple(params))
    if _pool is None:
        await init_pool()
    if _pool is None:
        return []
    async with _pool.acquire() as conn:
        async with conn.cursor() as cur:
            sql = "CREATE TABLE IF NOT EXISTS device_registry (id BIGINT AUTO_INCREMENT PRIMARY KEY, uuid VARCHAR(64) UNIQUE, name VARCHAR(128), category VARCHAR(64), create_time DATETIME DEFAULT CURRENT_TIMESTAMP)"
            await cur.execute(sql)
            sql = "SELECT id,uuid,name,category,create_time FROM device_registry WHERE 1=1"
            params = []
            if category:
                sql += " AND category=%s"; params.append(category)
            if search:
                sql += " AND (uuid LIKE %s OR name LIKE %s)"; params.extend([f"%{search}%", f"%{search}%"]) 
            sql += " ORDER BY id DESC LIMIT %s OFFSET %s"; params.extend([limit, offset])
            await cur.execute(sql, params)
            rows = await cur.fetchall()
            return [
                {"id": r[0], "uuid": r[1], "name": r[2], "category": r[3], "create_time": r[4]}
                for r in rows
            ]

async def admin_upsert_registry(uuid: str, name: str | None, category: str | None):
    if use_sqlite():
        if _sqlite is None:
            await init_sqlite()
        if _sqlite:
            cur = await _sqlite.execute("SELECT id FROM device_registry WHERE uuid=?", (uuid,))
            row = await cur.fetchone()
            if row:
                await _sqlite.execute("UPDATE device_registry SET name=?, category=? WHERE uuid=?", (name, category, uuid))
            else:
                await _sqlite.execute("INSERT INTO device_registry(uuid,name,category) VALUES(?,?,?)", (uuid, name, category))
            await _sqlite.commit()
            return True
        await asyncio.to_thread(_sqlite_exec_sync, "INSERT OR REPLACE INTO device_registry(uuid,name,category) VALUES(?,?,?)", (uuid, name, category))
        return True
    if _pool is None:
        await init_pool()
    if _pool is None:
        return False
    async with _pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("CREATE TABLE IF NOT EXISTS device_registry (id BIGINT AUTO_INCREMENT PRIMARY KEY, uuid VARCHAR(64) UNIQUE, name VARCHAR(128), category VARCHAR(64), create_time DATETIME DEFAULT CURRENT_TIMESTAMP)")
            await cur.execute("SELECT id FROM device_registry WHERE uuid=%s", (uuid,))
            row = await cur.fetchone()
            if row:
                await cur.execute("UPDATE device_registry SET name=%s, category=%s WHERE uuid=%s", (name, category, uuid))
            else:
                await cur.execute("INSERT INTO device_registry(uuid,name,category) VALUES(%s,%s,%s)", (uuid, name, category))
            return True

async def admin_write_op(actor: str | None, action: str, target_uuid: str | None, payload: str | None):
    if use_sqlite():
        if _sqlite is None:
            await init_sqlite()
        if _sqlite:
            await _sqlite.execute("INSERT INTO ops_log(actor,action,target_uuid,payload) VALUES(?,?,?,?)", (actor, action, target_uuid, payload))
            await _sqlite.commit()
            return
        await asyncio.to_thread(_sqlite_exec_sync, "INSERT INTO ops_log(actor,action,target_uuid,payload) VALUES(?,?,?,?)", (actor, action, target_uuid, payload))
        return
    if _pool is None:
        await init_pool()
    if _pool is None:
        return
    async with _pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("CREATE TABLE IF NOT EXISTS ops_log (id BIGINT AUTO_INCREMENT PRIMARY KEY, actor VARCHAR(128), action VARCHAR(64), target_uuid VARCHAR(64), payload TEXT, time DATETIME DEFAULT CURRENT_TIMESTAMP)")
            await cur.execute("INSERT INTO ops_log(actor,action,target_uuid,payload) VALUES(%s,%s,%s,%s)", (actor, action, target_uuid, payload))
