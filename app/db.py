import os
import time
import asyncio
import logging
import json
from typing import Optional, List, Dict, Any

import aiomysql
import aiosqlite
from . import config

_pool = None
_sqlite = None

def use_sqlite():
    return config.DB_DRIVER == "sqlite"

async def init_sqlite():
    global _sqlite
    if _sqlite:
        return
    db_path = config.DB_SQLITE_PATH
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    _sqlite = await aiosqlite.connect(db_path)
    _sqlite.row_factory = aiosqlite.Row
    
    # Init tables
    await _sqlite.execute("""
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uuid TEXT,
            time DATETIME,
            in_count INTEGER,
            out_count INTEGER,
            battery INTEGER,
            btx INTEGER,
            rec_type INTEGER,
            signal_strength INTEGER,
            warn_status INTEGER,
            activity_type TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    await _sqlite.execute("CREATE INDEX IF NOT EXISTS idx_records_uuid_time ON records(uuid, time)")
    
    # Migration: Add activity_type if not exists
    try:
        await _sqlite.execute("ALTER TABLE records ADD COLUMN activity_type TEXT")
    except Exception:
        pass
    
    # Migration: Add warn_status if not exists
    try:
        await _sqlite.execute("ALTER TABLE records ADD COLUMN warn_status INTEGER")
    except Exception:
        pass
    
    await _sqlite.execute("""
        CREATE TABLE IF NOT EXISTS registry (
            uuid TEXT PRIMARY KEY,
            name TEXT,
            category TEXT,
            description TEXT,
            last_seen DATETIME,
            ip TEXT
        )
    """)
    try:
        await _sqlite.execute("ALTER TABLE registry ADD COLUMN ip TEXT")
    except Exception:
        pass
    
    await _sqlite.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor TEXT,
            action TEXT,
            target TEXT,
            details TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    await _sqlite.execute("""
        CREATE TABLE IF NOT EXISTS academies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            sort_order INTEGER DEFAULT 0
        )
    """)
    try:
        await _sqlite.execute("ALTER TABLE academies ADD COLUMN sort_order INTEGER DEFAULT 0")
    except Exception as e:
        logging.info(f"Migration: sort_order column might already exist or failed: {e}")
    
    await _sqlite.execute("""
        CREATE TABLE IF NOT EXISTS activity_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            weekday TEXT,
            start_time TEXT,
            end_time TEXT,
            duration_minutes INTEGER,
            academy TEXT,
            location TEXT,
            activity_name TEXT,
            activity_type TEXT,
            audience_count INTEGER,
            notes TEXT,
            create_time DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    await _sqlite.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uuid TEXT,
            type TEXT,
            level INTEGER,
            info TEXT,
            time DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    await _sqlite.commit()

async def init_pool():
    global _pool, _sqlite
    if use_sqlite():
        await init_sqlite()
        return

    if _pool:
        return
    
    try:
        _pool = await aiomysql.create_pool(
            host=config.DB_HOST,
            port=config.DB_PORT,
            user=config.DB_USER,
            password=config.DB_PASSWORD,
            db=config.DB_NAME,
            autocommit=True
        )
        # Create tables if not exist (MySQL)
        async with _pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS records (
                        id BIGINT AUTO_INCREMENT PRIMARY KEY,
                        uuid VARCHAR(64),
                        time DATETIME,
                        in_count INT,
                        out_count INT,
                        battery INT,
                        btx INT,
                        rec_type INT,
                        signal_strength INT,
                        warn_status INT,
                        activity_type VARCHAR(64),
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        INDEX idx_uuid_time (uuid, time)
                    )
                """)
                # Migration MySQL
                try:
                    await cur.execute("ALTER TABLE records ADD COLUMN activity_type VARCHAR(64)")
                except Exception:
                    pass
                try:
                    await cur.execute("ALTER TABLE records ADD COLUMN warn_status INT")
                except Exception:
                    pass

                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS registry (
                        uuid VARCHAR(64) PRIMARY KEY,
                        name VARCHAR(128),
                        category VARCHAR(64),
                        description TEXT,
                        last_seen DATETIME,
                        ip VARCHAR(64)
                    )
                """)
                try:
                    await cur.execute("ALTER TABLE registry ADD COLUMN ip VARCHAR(64)")
                except Exception:
                    pass
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS audit_logs (
                        id BIGINT AUTO_INCREMENT PRIMARY KEY,
                        actor VARCHAR(128),
                        action VARCHAR(64),
                        target VARCHAR(64),
                        details TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS academies (
                        id BIGINT AUTO_INCREMENT PRIMARY KEY,
                        name VARCHAR(128) UNIQUE,
                        sort_order INT DEFAULT 0
                    )
                """)
                try:
                    await cur.execute("ALTER TABLE academies ADD COLUMN sort_order INT DEFAULT 0")
                except Exception:
                    pass
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS activity_events (
                        id BIGINT AUTO_INCREMENT PRIMARY KEY,
                        date VARCHAR(20),
                        weekday VARCHAR(20),
                        start_time VARCHAR(20),
                        end_time VARCHAR(20),
                        duration_minutes INT,
                        academy VARCHAR(128),
                        location VARCHAR(128),
                        activity_name VARCHAR(255),
                        activity_type VARCHAR(64),
                        audience_count INT,
                        notes TEXT,
                        create_time DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS alerts (
                        id BIGINT AUTO_INCREMENT PRIMARY KEY,
                        uuid VARCHAR(64),
                        type VARCHAR(64),
                        level INT,
                        info TEXT,
                        time DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
    except Exception as e:
        logging.error(f"DB init failed: {e}")

async def close_pool():
    global _pool, _sqlite
    if _pool:
        _pool.close()
        await _pool.wait_closed()
    if _sqlite:
        await _sqlite.close()

# --- Device / Records ---

async def fetch_latest():
    # Return list of latest record per device
    # Join with registry to get names
    sql = """
    SELECT r.*, reg.name, reg.category 
    FROM records r
    LEFT JOIN registry reg ON r.uuid = reg.uuid
    WHERE r.id IN (SELECT MAX(id) FROM records GROUP BY uuid)
    """
    if use_sqlite():
        if not _sqlite: await init_sqlite()
        async with _sqlite.execute(sql) as cur:
            rows = await cur.fetchall()
            return [dict(row) for row in rows]
    else:
        if not _pool: await init_pool()
        async with _pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql)
                return await cur.fetchall()

async def fetch_history(uuid=None, start=None, end=None, limit=100):
    where = ["1=1"]
    params = []
    if uuid:
        where.append("uuid = ?" if use_sqlite() else "uuid = %s")
        params.append(uuid)
    if start:
        where.append("time >= ?" if use_sqlite() else "time >= %s")
        params.append(start)
    if end:
        where.append("time <= ?" if use_sqlite() else "time <= %s")
        params.append(end)
        
    sql = f"SELECT * FROM records WHERE {' AND '.join(where)} ORDER BY time DESC LIMIT {limit}"
    
    if use_sqlite():
        if not _sqlite: await init_sqlite()
        async with _sqlite.execute(sql, params) as cur:
            rows = await cur.fetchall()
            return [dict(row) for row in rows]
    else:
        if not _pool: await init_pool()
        async with _pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql, params)
                return await cur.fetchall()

async def get_device_ip(uuid):
    sql = "SELECT ip FROM registry WHERE uuid=?" if use_sqlite() else "SELECT ip FROM registry WHERE uuid=%s"
    if use_sqlite():
        if not _sqlite: await init_sqlite()
        cur = await _sqlite.execute(sql, (uuid,))
        row = await cur.fetchone()
        return row[0] if row else None
    else:
        if not _pool: await init_pool()
        async with _pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (uuid,))
                row = await cur.fetchone()
                return row[0] if row else None

async def list_devices():
    # Get all unique UUIDs from registry or records
    sql = "SELECT DISTINCT uuid FROM registry UNION SELECT DISTINCT uuid FROM records"
    if use_sqlite():
        if not _sqlite: await init_sqlite()
        async with _sqlite.execute(sql) as cur:
            rows = await cur.fetchall()
            return [row[0] for row in rows]
    else:
        if not _pool: await init_pool()
        async with _pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql)
                rows = await cur.fetchall()
                return [row[0] for row in rows]

async def get_device_mapping():
    sql = "SELECT uuid, name, category FROM registry"
    if use_sqlite():
        if not _sqlite: await init_sqlite()
        async with _sqlite.execute(sql) as cur:
            rows = await cur.fetchall()
            return {row[0]: {"name": row[1], "category": row[2]} for row in rows}
    else:
        if not _pool: await init_pool()
        async with _pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql)
                rows = await cur.fetchall()
                return {row[0]: {"name": row[1], "category": row[2]} for row in rows}

# --- Stats ---

async def stats_daily(uuid=None, start=None, end=None):
    # Group by date
    # SQLite: strftime('%Y-%m-%d', time)
    # MySQL: DATE(time)
    date_func = "strftime('%Y-%m-%d', time)" if use_sqlite() else "DATE(time)"
    where = ["1=1"]
    params = []
    if uuid:
        where.append("uuid = ?" if use_sqlite() else "uuid = %s")
        params.append(uuid)
    if start:
        where.append(f"time >= ?") if use_sqlite() else where.append("time >= %s")
        params.append(start)
    if end:
        where.append(f"time <= ?") if use_sqlite() else where.append("time <= %s")
        params.append(end)
        
    sql = f"SELECT {date_func} as d, SUM(in_count), SUM(out_count) FROM records WHERE {' AND '.join(where)} GROUP BY d ORDER BY d"
    
    if use_sqlite():
        if not _sqlite: await init_sqlite()
        async with _sqlite.execute(sql, params) as cur:
            rows = await cur.fetchall()
            return [{"date": r[0], "in": r[1], "out": r[2]} for r in rows]
    else:
        if not _pool: await init_pool()
        async with _pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, params)
                rows = await cur.fetchall()
                return [{"date": str(r[0]), "in": r[1], "out": r[2]} for r in rows]

async def stats_hourly(uuid=None, start=None, end=None):
    # Group by hour
    # SQLite: strftime('%Y-%m-%d %H:00', time)
    # MySQL: DATE_FORMAT(time, '%Y-%m-%d %H:00')
    date_func = "strftime('%Y-%m-%d %H:00', time)" if use_sqlite() else "DATE_FORMAT(time, '%Y-%m-%d %H:00')"
    where = ["1=1"]
    params = []
    if uuid:
        where.append("uuid = ?" if use_sqlite() else "uuid = %s")
        params.append(uuid)
    if start:
        where.append(f"time >= ?") if use_sqlite() else where.append("time >= %s")
        params.append(start)
    if end:
        where.append(f"time <= ?") if use_sqlite() else where.append("time <= %s")
        params.append(end)
        
    sql = f"SELECT {date_func} as h, SUM(in_count), SUM(out_count) FROM records WHERE {' AND '.join(where)} GROUP BY h ORDER BY h"
    
    if use_sqlite():
        if not _sqlite: await init_sqlite()
        async with _sqlite.execute(sql, params) as cur:
            rows = await cur.fetchall()
            return [{"hour": r[0], "in": r[1], "out": r[2]} for r in rows]
    else:
        if not _pool: await init_pool()
        async with _pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, params)
                rows = await cur.fetchall()
                return [{"hour": str(r[0]), "in": r[1], "out": r[2]} for r in rows]

async def stats_total(uuid=None, start=None, end=None):
    where = ["1=1"]
    params = []
    if uuid:
        where.append("uuid = ?" if use_sqlite() else "uuid = %s")
        params.append(uuid)
    if start:
        where.append(f"time >= ?") if use_sqlite() else where.append("time >= %s")
        params.append(start)
    if end:
        where.append(f"time <= ?") if use_sqlite() else where.append("time <= %s")
        params.append(end)
    
    sql = f"SELECT SUM(in_count), SUM(out_count) FROM records WHERE {' AND '.join(where)}"
    if use_sqlite():
        if not _sqlite: await init_sqlite()
        async with _sqlite.execute(sql, params) as cur:
            row = await cur.fetchone()
            return {"in": row[0] or 0, "out": row[1] or 0}
    else:
        if not _pool: await init_pool()
        async with _pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, params)
                row = await cur.fetchone()
                return {"in": row[0] or 0, "out": row[1] or 0}

async def stats_summary(uuid=None):
    # Simple summary + last update time
    total = await stats_total(uuid)
    
    where = ["1=1"]
    params = []
    if uuid:
        where.append("uuid = ?" if use_sqlite() else "uuid = %s")
        params.append(uuid)
        
    sql = f"SELECT MAX(time) FROM records WHERE {' AND '.join(where)}"
    last_time = None
    
    if use_sqlite():
        if not _sqlite: await init_sqlite()
        async with _sqlite.execute(sql, params) as cur:
            row = await cur.fetchone()
            if row and row[0]:
                last_time = row[0]
    else:
        if not _pool: await init_pool()
        async with _pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, params)
                row = await cur.fetchone()
                if row and row[0]:
                    last_time = str(row[0])
                    
    return {**total, "last_time": last_time}

async def stats_top(limit=10):
    # Top devices by traffic
    sql = f"SELECT uuid, SUM(in_count) + SUM(out_count) as total FROM records GROUP BY uuid ORDER BY total DESC LIMIT {limit}"
    if use_sqlite():
        if not _sqlite: await init_sqlite()
        async with _sqlite.execute(sql) as cur:
            rows = await cur.fetchall()
            return [{"uuid": r[0], "total": r[1]} for r in rows]
    else:
        if not _pool: await init_pool()
        async with _pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql)
                rows = await cur.fetchall()
                return [{"uuid": r[0], "total": r[1]} for r in rows]

# --- Academies ---

async def get_academies():
    sql = "SELECT * FROM academies ORDER BY sort_order ASC, name ASC"
    if use_sqlite():
        if not _sqlite: await init_sqlite()
        async with _sqlite.execute(sql) as cur:
            rows = await cur.fetchall()
            return [{"id": r[0], "name": r[1], "sort_order": r[2] if len(r)>2 else 0} for r in rows]
    else:
        if not _pool: await init_pool()
        async with _pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql)
                rows = await cur.fetchall()
                return [{"id": r[0], "name": r[1], "sort_order": r[2] if len(r)>2 else 0} for r in rows]

async def update_academy_order(order_list: List[int]):
    # order_list is a list of IDs in the desired order
    logging.info(f"Updating academy order: {order_list}")
    if use_sqlite():
        if not _sqlite: await init_sqlite()
        try:
            for idx, aid in enumerate(order_list):
                await _sqlite.execute("UPDATE academies SET sort_order=? WHERE id=?", (idx, aid))
            await _sqlite.commit()
            logging.info("Academy order updated successfully (SQLite)")
            return True
        except Exception as e:
            logging.error(f"Failed to update academy order: {e}")
            return False
    else:
        if not _pool: await init_pool()
        async with _pool.acquire() as conn:
            async with conn.cursor() as cur:
                try:
                    for idx, aid in enumerate(order_list):
                        await cur.execute("UPDATE academies SET sort_order=%s WHERE id=%s", (idx, aid))
                    logging.info("Academy order updated successfully (MySQL)")
                    return True
                except Exception as e:
                    logging.error(f"Failed to update academy order: {e}")
                    return False

async def add_academy(name):
    sql = "INSERT INTO academies (name) VALUES (?)" if use_sqlite() else "INSERT INTO academies (name) VALUES (%s)"
    if use_sqlite():
        if not _sqlite: await init_sqlite()
        try:
            await _sqlite.execute(sql, (name,))
            await _sqlite.commit()
            return True
        except:
            return False
    else:
        if not _pool: await init_pool()
        async with _pool.acquire() as conn:
            async with conn.cursor() as cur:
                try:
                    await cur.execute(sql, (name,))
                    return True
                except:
                    return False

async def delete_academy(id):
    sql = "DELETE FROM academies WHERE id=?" if use_sqlite() else "DELETE FROM academies WHERE id=%s"
    if use_sqlite():
        if not _sqlite: await init_sqlite()
        await _sqlite.execute(sql, (id,))
        await _sqlite.commit()
        return True
    else:
        if not _pool: await init_pool()
        async with _pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (id,))
                return True

# --- Admin ---

async def admin_count_records(uuid=None):
    sql = "SELECT COUNT(*) FROM records"
    params = []
    if uuid:
        sql += " WHERE uuid=?" if use_sqlite() else " WHERE uuid=%s"
        params.append(uuid)
    
    if use_sqlite():
        if not _sqlite: await init_sqlite()
        async with _sqlite.execute(sql, params) as cur:
            row = await cur.fetchone()
            return row[0]
    else:
        if not _pool: await init_pool()
        async with _pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, params)
                row = await cur.fetchone()
                return row[0]

async def admin_list_records(page=1, limit=50, uuid=None):
    offset = (page - 1) * limit
    where = ["1=1"]
    params = []
    if uuid:
        where.append("uuid = ?" if use_sqlite() else "uuid = %s")
        params.append(uuid)
    
    sql = f"SELECT * FROM records WHERE {' AND '.join(where)} ORDER BY time DESC LIMIT {limit} OFFSET {offset}"
    
    if use_sqlite():
        if not _sqlite: await init_sqlite()
        async with _sqlite.execute(sql, params) as cur:
            rows = await cur.fetchall()
            return [dict(row) for row in rows]
    else:
        if not _pool: await init_pool()
        async with _pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql, params)
                return await cur.fetchall()

async def save_device_data(data: dict, ip: str = None):
    uuid = data.get("uuid")
    if not uuid: return
    
    # Insert record
    rec = {
        "uuid": uuid,
        "time": data.get("time") or time.strftime("%Y-%m-%d %H:%M:%S"),
        "in_count": int(data.get("in_count") or 0),
        "out_count": int(data.get("out_count") or 0),
        "battery": int(data.get("battery_level") or 0),
        "signal_strength": int(data.get("signal_status") or 0),
        "btx": 0,
        "rec_type": 0,
        "warn_status": 0,
        "activity_type": "default"
    }
    await admin_create_record(rec)
    
    # Update registry last_seen and ip
    sql_check = "SELECT uuid FROM registry WHERE uuid=?" if use_sqlite() else "SELECT uuid FROM registry WHERE uuid=%s"
    
    if use_sqlite():
        if not _sqlite: await init_sqlite()
        cur = await _sqlite.execute(sql_check, (uuid,))
        row = await cur.fetchone()
        if row:
            sql = "UPDATE registry SET last_seen=CURRENT_TIMESTAMP"
            params = []
            if ip:
                sql += ", ip=?"
                params.append(ip)
            sql += " WHERE uuid=?"
            params.append(uuid)
            await _sqlite.execute(sql, params)
        else:
            await _sqlite.execute("INSERT INTO registry (uuid, last_seen, ip) VALUES (?, CURRENT_TIMESTAMP, ?)", (uuid, ip))
        await _sqlite.commit()
    else:
        if not _pool: await init_pool()
        async with _pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql_check, (uuid,))
                row = await cur.fetchone()
                if row:
                    sql = "UPDATE registry SET last_seen=CURRENT_TIMESTAMP"
                    params = []
                    if ip:
                        sql += ", ip=%s"
                        params.append(ip)
                    sql += " WHERE uuid=%s"
                    params.append(uuid)
                    await cur.execute(sql, params)
                else:
                    await cur.execute("INSERT INTO registry (uuid, last_seen, ip) VALUES (%s, CURRENT_TIMESTAMP, %s)", (uuid, ip))

async def admin_create_record(data):
    # data is dict
    cols = list(data.keys())
    vals = list(data.values())
    placeholders = ["?"] * len(cols) if use_sqlite() else ["%s"] * len(cols)
    sql = f"INSERT INTO records ({','.join(cols)}) VALUES ({','.join(placeholders)})"
    
    if use_sqlite():
        if not _sqlite: await init_sqlite()
        await _sqlite.execute(sql, vals)
        await _sqlite.commit()
        return True
    else:
        if not _pool: await init_pool()
        async with _pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, vals)
                return True

async def admin_update_record(id, data: dict):
    cols = []
    vals = []
    if "time" in data:
        cols.append("time=?") if use_sqlite() else cols.append("time=%s")
        vals.append(data["time"])
    if "in_count" in data:
        cols.append("in_count=?") if use_sqlite() else cols.append("in_count=%s")
        vals.append(data["in_count"])
    if "out_count" in data:
        cols.append("out_count=?") if use_sqlite() else cols.append("out_count=%s")
        vals.append(data["out_count"])
    if "battery" in data:
        cols.append("battery=?") if use_sqlite() else cols.append("battery=%s")
        vals.append(data["battery"])
    if "btx" in data:
        cols.append("btx=?") if use_sqlite() else cols.append("btx=%s")
        vals.append(data["btx"])
    if "activity_type" in data:
        cols.append("activity_type=?") if use_sqlite() else cols.append("activity_type=%s")
        vals.append(data["activity_type"])
    
    if not cols:
        return False
        
    vals.append(id)
    sql = f"UPDATE records SET {','.join(cols)} WHERE id=?" if use_sqlite() else f"UPDATE records SET {','.join(cols)} WHERE id=%s"
    
    if use_sqlite():
        if not _sqlite: await init_sqlite()
        await _sqlite.execute(sql, vals)
        await _sqlite.commit()
        return True
    else:
        if not _pool: await init_pool()
        async with _pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, vals)
                return True

async def admin_batch_update(ids: list, data: dict):
    # Batch update multiple records
    if not ids or not data:
        return False
        
    cols = []
    vals = []
    if "time" in data:
        cols.append("time=?") if use_sqlite() else cols.append("time=%s")
        vals.append(data["time"])
    if "in_count" in data:
        cols.append("in_count=?") if use_sqlite() else cols.append("in_count=%s")
        vals.append(data["in_count"])
    if "out_count" in data:
        cols.append("out_count=?") if use_sqlite() else cols.append("out_count=%s")
        vals.append(data["out_count"])
    if "battery" in data:
        cols.append("battery=?") if use_sqlite() else cols.append("battery=%s")
        vals.append(data["battery"])
    if "btx" in data:
        cols.append("btx=?") if use_sqlite() else cols.append("btx=%s")
        vals.append(data["btx"])
    if "activity_type" in data:
        cols.append("activity_type=?") if use_sqlite() else cols.append("activity_type=%s")
        vals.append(data["activity_type"])
        
    if not cols:
        return False
        
    # Construct WHERE id IN (?,?,?)
    placeholders = ",".join(["?" if use_sqlite() else "%s"] * len(ids))
    where = f"WHERE id IN ({placeholders})"
    
    vals.extend(ids)
    
    sql = f"UPDATE records SET {','.join(cols)} {where}"
    
    if use_sqlite():
        if not _sqlite: await init_sqlite()
        await _sqlite.execute(sql, vals)
        await _sqlite.commit()
        return True
    else:
        if not _pool: await init_pool()
        async with _pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, vals)
                return True

async def admin_batch_save_records(creates: list, updates: list):
    # Batch save records (creates and updates)
    if not creates and not updates:
        return True
        
    if use_sqlite():
        if not _sqlite: await init_sqlite()
        try:
            # Creates
            if creates:
                for c in creates:
                    cols = list(c.keys())
                    vals = list(c.values())
                    sql = f"INSERT INTO records ({','.join(cols)}) VALUES ({','.join(['?']*len(cols))})"
                    await _sqlite.execute(sql, vals)
            # Updates
            if updates:
                for u in updates:
                    uid = u.pop("id", None)
                    if not uid: continue
                    cols = []
                    vals = []
                    for k, v in u.items():
                        cols.append(f"{k}=?")
                        vals.append(v)
                    if cols:
                        vals.append(uid)
                        sql = f"UPDATE records SET {','.join(cols)} WHERE id=?"
                        await _sqlite.execute(sql, vals)
            await _sqlite.commit()
            return True
        except Exception as e:
            logging.error(f"Batch save failed: {e}")
            return False
    else:
        if not _pool: await init_pool()
        async with _pool.acquire() as conn:
            async with conn.cursor() as cur:
                try:
                    # Creates
                    if creates:
                        for c in creates:
                            cols = list(c.keys())
                            vals = list(c.values())
                            sql = f"INSERT INTO records ({','.join(cols)}) VALUES ({','.join(['%s']*len(cols))})"
                            await cur.execute(sql, vals)
                    # Updates
                    if updates:
                        for u in updates:
                            uid = u.pop("id", None)
                            if not uid: continue
                            cols = []
                            vals = []
                            for k, v in u.items():
                                cols.append(f"{k}=%s")
                                vals.append(v)
                            if cols:
                                vals.append(uid)
                                sql = f"UPDATE records SET {','.join(cols)} WHERE id=%s"
                                await cur.execute(sql, vals)
                    return True
                except Exception as e:
                    logging.error(f"Batch save failed: {e}")
                    return False

async def admin_delete_record(id):
    sql = "DELETE FROM records WHERE id=?" if use_sqlite() else "DELETE FROM records WHERE id=%s"
    if use_sqlite():
        if not _sqlite: await init_sqlite()
        await _sqlite.execute(sql, (id,))
        await _sqlite.commit()
        return True
    else:
        if not _pool: await init_pool()
        async with _pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (id,))
                return True

async def admin_delete_range(start, end):
    sql = "DELETE FROM records WHERE time >= ? AND time <= ?" if use_sqlite() else "DELETE FROM records WHERE time >= %s AND time <= %s"
    if use_sqlite():
        if not _sqlite: await init_sqlite()
        await _sqlite.execute(sql, (start, end))
        await _sqlite.commit()
        return True
    else:
        if not _pool: await init_pool()
        async with _pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (start, end))
                return True

async def admin_list_registry():
    sql = "SELECT * FROM registry"
    if use_sqlite():
        if not _sqlite: await init_sqlite()
        async with _sqlite.execute(sql) as cur:
            rows = await cur.fetchall()
            return [dict(row) for row in rows]
    else:
        if not _pool: await init_pool()
        async with _pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql)
                return await cur.fetchall()

async def admin_upsert_registry(uuid, name=None, category=None):
    # Check if exists
    sql_check = "SELECT uuid FROM registry WHERE uuid=?" if use_sqlite() else "SELECT uuid FROM registry WHERE uuid=%s"
    
    if use_sqlite():
        if not _sqlite: await init_sqlite()
        cursor = await _sqlite.execute(sql_check, (uuid,))
        row = await cursor.fetchone()
        if row:
            # Update
            updates = []
            params = []
            if name is not None:
                updates.append("name=?")
                params.append(name)
            if category is not None:
                updates.append("category=?")
                params.append(category)
            if updates:
                params.append(uuid)
                await _sqlite.execute(f"UPDATE registry SET {','.join(updates)} WHERE uuid=?", params)
        else:
            # Insert
            await _sqlite.execute("INSERT INTO registry (uuid, name, category) VALUES (?, ?, ?)", (uuid, name, category))
        await _sqlite.commit()
        return True
    else:
        if not _pool: await init_pool()
        async with _pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql_check, (uuid,))
                row = await cur.fetchone()
                if row:
                    updates = []
                    params = []
                    if name is not None:
                        updates.append("name=%s")
                        params.append(name)
                    if category is not None:
                        updates.append("category=%s")
                        params.append(category)
                    if updates:
                        params.append(uuid)
                        await cur.execute(f"UPDATE registry SET {','.join(updates)} WHERE uuid=%s", params)
                else:
                    await cur.execute("INSERT INTO registry (uuid, name, category) VALUES (%s, %s, %s)", (uuid, name, category))
                return True

async def admin_batch_upsert(items: list):
    for item in items:
        await admin_upsert_registry(item.get("uuid"), item.get("name"), item.get("category"))
    return True

async def admin_write_op(actor, action, target, details):
    sql = "INSERT INTO audit_logs (actor, action, target, details) VALUES (?, ?, ?, ?)" if use_sqlite() else "INSERT INTO audit_logs (actor, action, target, details) VALUES (%s, %s, %s, %s)"
    if use_sqlite():
        if not _sqlite: await init_sqlite()
        await _sqlite.execute(sql, (actor, action, target, details))
        await _sqlite.commit()
    else:
        if not _pool: await init_pool()
        async with _pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (actor, action, target, details))

async def admin_get_categories():
    sql = "SELECT DISTINCT category FROM registry"
    if use_sqlite():
        if not _sqlite: await init_sqlite()
        async with _sqlite.execute(sql) as cur:
            rows = await cur.fetchall()
            return [r[0] for r in rows if r[0]]
    else:
        if not _pool: await init_pool()
        async with _pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql)
                rows = await cur.fetchall()
                return [r[0] for r in rows if r[0]]

async def admin_get_uuids():
    return await list_devices()

async def admin_fetch_range(start, end):
    # Fetch records in range for export
    return await fetch_history(start=start, end=end, limit=100000)

async def list_alerts(uuid=None, limit=100):
    sql = "SELECT * FROM alerts"
    params = []
    if uuid:
        sql += " WHERE uuid=?" if use_sqlite() else " WHERE uuid=%s"
        params.append(uuid)
    
    sql += f" ORDER BY time DESC LIMIT {limit}"
    
    if use_sqlite():
        if not _sqlite: await init_sqlite()
        async with _sqlite.execute(sql, params) as cur:
            rows = await cur.fetchall()
            return [dict(row) for row in rows]
    else:
        if not _pool: await init_pool()
        async with _pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql, params)
                return await cur.fetchall()

# --- Activity Events (Preserved) ---

async def activity_bulk_insert(events: list[dict]):
    if not events:
        return 0
    count = 0
    cols = ["date", "weekday", "start_time", "end_time", "duration_minutes", "academy", "location", "activity_name", "activity_type", "audience_count", "notes"]
    
    if use_sqlite():
        if _sqlite is None:
            await init_sqlite()
        if _sqlite:
            for e in events:
                cur = await _sqlite.execute("SELECT id FROM activity_events WHERE date=? AND start_time=? AND location=? AND activity_name=?", 
                                            (e.get("date"), e.get("start_time"), e.get("location"), e.get("activity_name")))
                row = await cur.fetchone()
                if not row:
                    vals = [e.get(c) for c in cols]
                    await _sqlite.execute(
                        f"INSERT INTO activity_events({','.join(cols)}) VALUES({','.join(['?']*len(cols))})",
                        vals
                    )
                    count += 1
            await _sqlite.commit()
            return count
    
    if _pool is None:
        await init_pool()
    if _pool:
        async with _pool.acquire() as conn:
            async with conn.cursor() as cur:
                 for e in events:
                    await cur.execute("SELECT id FROM activity_events WHERE date=%s AND start_time=%s AND location=%s AND activity_name=%s", 
                                      (e.get("date"), e.get("start_time"), e.get("location"), e.get("activity_name")))
                    row = await cur.fetchone()
                    if not row:
                        vals = [e.get(c) for c in cols]
                        await cur.execute(
                            f"INSERT INTO activity_events({','.join(cols)}) VALUES({','.join(['%s']*len(cols))})",
                            vals
                        )
                        count += 1
    return count

async def activity_list(start_date: str = None, end_date: str = None, locations: list = None, types: list = None, academies: list = None, weekdays: list = None, min_start_time: str = None, page: int = 1, page_size: int = 50):
    offset = (page - 1) * page_size
    sql = "SELECT * FROM activity_events WHERE 1=1"
    params = []
    if start_date:
        sql += " AND date >= ?" if use_sqlite() else " AND date >= %s"
        params.append(start_date)
    if end_date:
        sql += " AND date <= ?" if use_sqlite() else " AND date <= %s"
        params.append(end_date)
    if locations:
        placeholders = ",".join(["?" if use_sqlite() else "%s"] * len(locations))
        sql += f" AND location IN ({placeholders})"
        params.extend(locations)
    if types:
        placeholders = ",".join(["?" if use_sqlite() else "%s"] * len(types))
        sql += f" AND activity_type IN ({placeholders})"
        params.extend(types)
    if academies:
        placeholders = ",".join(["?" if use_sqlite() else "%s"] * len(academies))
        sql += f" AND academy IN ({placeholders})"
        params.extend(academies)
    if weekdays:
        # Weekdays can be int or str, ensure they match DB format.
        # Assuming DB has 'Mon', 'Tue' or '1', '2'.
        # User request says "1-7". If DB has 'Mon', we need mapping. 
        # Assuming we pass what's in DB or frontend handles mapping.
        placeholders = ",".join(["?" if use_sqlite() else "%s"] * len(weekdays))
        sql += f" AND weekday IN ({placeholders})"
        params.extend(weekdays)
    if min_start_time:
        # Activities happening after selected time (including ongoing).
        # Logic: end_time > min_start_time
        sql += " AND end_time > ?" if use_sqlite() else " AND end_time > %s"
        params.append(min_start_time)
    
    sql += " ORDER BY date DESC, start_time DESC"
    
    count_sql_opt = sql.replace("SELECT *", "SELECT COUNT(*)", 1)
    
    total = 0
    items = []
    
    if use_sqlite():
        if _sqlite is None:
            await init_sqlite()
        if _sqlite:
            cur = await _sqlite.execute(count_sql_opt, params)
            row = await cur.fetchone()
            total = row[0] if row else 0
            
            sql += " LIMIT ? OFFSET ?"
            params.extend([page_size, offset])
            cur = await _sqlite.execute(sql, params)
            rows = await cur.fetchall()
            items = [dict(r) for r in rows]
            return {"total": total, "items": items}
            
    if _pool is None:
        await init_pool()
    if _pool:
        async with _pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(count_sql_opt, params)
                row = await cur.fetchone()
                total = row['COUNT(*)'] if row else 0
                
                sql += " LIMIT %s OFFSET %s"
                params.extend([page_size, offset])
                await cur.execute(sql, params)
                rows = await cur.fetchall()
                items = rows
    return {"total": total, "items": items}

async def activity_get_options():
    if use_sqlite():
        if _sqlite is None:
            await init_sqlite()
        if _sqlite:
            l_cur = await _sqlite.execute("SELECT DISTINCT location FROM activity_events ORDER BY location")
            locations = [r[0] for r in await l_cur.fetchall() if r[0]]
            t_cur = await _sqlite.execute("SELECT DISTINCT activity_type FROM activity_events ORDER BY activity_type")
            types = [r[0] for r in await t_cur.fetchall() if r[0]]
            a_cur = await _sqlite.execute("SELECT DISTINCT academy FROM activity_events ORDER BY academy")
            academies = [r[0] for r in await a_cur.fetchall() if r[0]]
            return {"locations": locations, "types": types, "academies": academies}
    
    if _pool is None:
        await init_pool()
    if _pool:
        async with _pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT DISTINCT location FROM activity_events ORDER BY location")
                locations = [r[0] for r in await cur.fetchall() if r[0]]
                await cur.execute("SELECT DISTINCT activity_type FROM activity_events ORDER BY activity_type")
                types = [r[0] for r in await cur.fetchall() if r[0]]
                await cur.execute("SELECT DISTINCT academy FROM activity_events ORDER BY academy")
                academies = [r[0] for r in await cur.fetchall() if r[0]]
                return {"locations": locations, "types": types, "academies": academies}
    return {"locations": [], "types": [], "academies": []}

async def activity_stats(start_date: str = None, end_date: str = None, locations: list = None, types: list = None, academies: list = None):
    where = " WHERE 1=1"
    params = []
    if start_date:
        where += " AND date >= ?" if use_sqlite() else " AND date >= %s"
        params.append(start_date)
    if end_date:
        where += " AND date <= ?" if use_sqlite() else " AND date <= %s"
        params.append(end_date)
    if locations:
        placeholders = ",".join(["?" if use_sqlite() else "%s"] * len(locations))
        where += f" AND location IN ({placeholders})"
        params.extend(locations)
    if types:
        placeholders = ",".join(["?" if use_sqlite() else "%s"] * len(types))
        where += f" AND activity_type IN ({placeholders})"
        params.extend(types)
    if academies:
        placeholders = ",".join(["?" if use_sqlite() else "%s"] * len(academies))
        where += f" AND academy IN ({placeholders})"
        params.extend(academies)

    async def run_query(sql, p):
        if use_sqlite():
             if _sqlite is None: await init_sqlite()
             if _sqlite:
                 cur = await _sqlite.execute(sql, p)
                 return await cur.fetchall()
        elif _pool:
             if not _pool: await init_pool()
             async with _pool.acquire() as conn:
                 async with conn.cursor() as cur:
                     await cur.execute(sql, p)
                     return await cur.fetchall()
        return []

    kpi_sql = f"SELECT COUNT(*), SUM(audience_count), AVG(audience_count) FROM activity_events {where}"
    kpi_res = await run_query(kpi_sql, params)
    kpis = {
        "total_events": kpi_res[0][0] if kpi_res and kpi_res[0][0] else 0,
        "total_audience": kpi_res[0][1] if kpi_res and kpi_res[0][1] else 0,
        "avg_audience": round(kpi_res[0][2], 1) if kpi_res and kpi_res[0][2] else 0
    }

    wd_sql = f"SELECT weekday, COUNT(*), SUM(audience_count) FROM activity_events {where} GROUP BY weekday ORDER BY weekday"
    wd_res = await run_query(wd_sql, params)
    weekday_stats = [{"weekday": r[0], "count": r[1], "audience": r[2]} for r in wd_res]

    if use_sqlite():
        time_sql = f"SELECT substr(start_time, 1, 2) as h, COUNT(*), SUM(audience_count) FROM activity_events {where} GROUP BY h ORDER BY h"
    else:
        time_sql = f"SELECT LEFT(start_time, 2) as h, COUNT(*), SUM(audience_count) FROM activity_events {where} GROUP BY h ORDER BY h"
    
    time_res = await run_query(time_sql, params)
    time_stats = [{"hour": r[0], "count": r[1], "audience": r[2]} for r in time_res]
    
    loc_sql = f"SELECT location, COUNT(*), SUM(audience_count) FROM activity_events {where} GROUP BY location ORDER BY COUNT(*) DESC LIMIT 20"
    loc_res = await run_query(loc_sql, params)
    location_top = [{"location": r[0], "count": r[1], "audience": r[2]} for r in loc_res]
    
    type_sql = f"SELECT activity_type, COUNT(*), SUM(audience_count) FROM activity_events {where} GROUP BY activity_type ORDER BY COUNT(*) DESC"
    type_res = await run_query(type_sql, params)
    type_stats = [{"type": r[0], "count": r[1], "audience": r[2]} for r in type_res]
    
    return {
        "kpis": kpis,
        "weekday": weekday_stats,
        "time_bins": time_stats,
        "location_top": location_top,
        "activity_types": type_stats
    }
