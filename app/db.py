import os
import time
import asyncio
import logging
import json
from typing import Optional, List, Dict, Any, Callable, Literal, Tuple

import aiomysql
import aiosqlite
from . import config

_pool = None
_sqlite = None

def use_sqlite():
    return config.DB_DRIVER == "sqlite"

import hashlib
import uuid

def hash_password(password: str) -> str:
    # Simple salted hash (SHA256)
    salt = "infrared_salt_v1" # In prod this should be per-user random
    return hashlib.sha256((password + salt).encode()).hexdigest()

async def authenticate_user(username, password):
    p_hash = hash_password(password)
    sql = "SELECT id, username, password_hash, role FROM users WHERE username=?" if use_sqlite() else "SELECT id, username, password_hash, role FROM users WHERE username=%s"
    
    if use_sqlite():
        if not _sqlite: await init_sqlite()
        async with _sqlite.execute(sql, (username,)) as cur:
            row = await cur.fetchone()
    else:
        if not _pool: await init_pool()
        async with _pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql, (username,))
                row = await cur.fetchone()
                
    if row:
        stored_hash = row["password_hash"]
        if stored_hash == p_hash:
            return {"id": row["id"], "username": row["username"], "role": row["role"]}
            
    return None

async def create_session(user_id):
    token = str(uuid.uuid4())
    # Expires in 7 days
    import datetime
    expires = datetime.datetime.now() + datetime.timedelta(days=7)
    
    sql = "INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)" if use_sqlite() else "INSERT INTO sessions (token, user_id, expires_at) VALUES (%s, %s, %s)"
    
    if use_sqlite():
        if not _sqlite: await init_sqlite()
        await _sqlite.execute(sql, (token, user_id, expires))
        await _sqlite.commit()
    else:
        if not _pool: await init_pool()
        async with _pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (token, user_id, expires))
                
    return token

async def get_user_by_token(token):
    sql = """
        SELECT u.id, u.username, u.role 
        FROM sessions s
        JOIN users u ON s.user_id = u.id
        WHERE s.token = ? AND s.expires_at > CURRENT_TIMESTAMP
    """ if use_sqlite() else """
        SELECT u.id, u.username, u.role 
        FROM sessions s
        JOIN users u ON s.user_id = u.id
        WHERE s.token = %s AND s.expires_at > NOW()
    """
    
    if use_sqlite():
        if not _sqlite: await init_sqlite()
        async with _sqlite.execute(sql, (token,)) as cur:
            row = await cur.fetchone()
            if row:
                return {"id": row["id"], "username": row["username"], "role": row["role"]}
    else:
        if not _pool: await init_pool()
        async with _pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql, (token,))
                row = await cur.fetchone()
                if row:
                    return row
    return None

async def delete_session(token):
    sql = "DELETE FROM sessions WHERE token=?" if use_sqlite() else "DELETE FROM sessions WHERE token=%s"
    if use_sqlite():
        if not _sqlite: await init_sqlite()
        await _sqlite.execute(sql, (token,))
        await _sqlite.commit()
    else:
        if not _pool: await init_pool()
        async with _pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (token,))

async def change_password(user_id, new_password):
    p_hash = hash_password(new_password)
    sql = "UPDATE users SET password_hash=? WHERE id=?" if use_sqlite() else "UPDATE users SET password_hash=%s WHERE id=%s"
    
    if use_sqlite():
        if not _sqlite: await init_sqlite()
        await _sqlite.execute(sql, (p_hash, user_id))
        await _sqlite.commit()
    else:
        if not _pool: await init_pool()
        async with _pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (p_hash, user_id))
    return True

async def get_all_users():
    sql = "SELECT id, username, role, created_at, last_login FROM users ORDER BY id" if use_sqlite() else "SELECT id, username, role, created_at, last_login FROM users ORDER BY id"
    # Note: last_login might not exist yet, let's check schema or add it.
    # Looking at init_sqlite, there is no last_login column. I should add it or ignore it.
    # The user requested "last login time" in the profile card.
    # I'll stick to existing columns first: id, username, role, created_at.
    
    sql = "SELECT id, username, role, created_at FROM users ORDER BY id"
    
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

async def create_user(username, password, role="user"):
    p_hash = hash_password(password)
    sql = "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)" if use_sqlite() else "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)"
    
    try:
        if use_sqlite():
            if not _sqlite: await init_sqlite()
            await _sqlite.execute(sql, (username, p_hash, role))
            await _sqlite.commit()
        else:
            if not _pool: await init_pool()
            async with _pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(sql, (username, p_hash, role))
        return True
    except Exception as e:
        logging.error(f"Error creating user: {e}")
        return False

async def update_user(user_id, username=None, password=None, role=None):
    updates = []
    params = []
    
    if username:
        updates.append("username=?")
        params.append(username)
    if password:
        updates.append("password_hash=?")
        params.append(hash_password(password))
    if role:
        updates.append("role=?")
        params.append(role)
        
    if not updates:
        return False
        
    sql_base = "UPDATE users SET " + ", ".join(updates) + " WHERE id=?"
    params.append(user_id)
    
    # Adjust placeholders for MySQL if needed
    if not use_sqlite():
        sql_base = sql_base.replace("?", "%s")
        
    if use_sqlite():
        if not _sqlite: await init_sqlite()
        await _sqlite.execute(sql_base, tuple(params))
        await _sqlite.commit()
    else:
        if not _pool: await init_pool()
        async with _pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql_base, tuple(params))
    return True

async def delete_user(user_id):
    # Don't allow deleting admin (id=1 usually, or check username)
    # But let's just handle deletion here.
    sql = "DELETE FROM users WHERE id=?" if use_sqlite() else "DELETE FROM users WHERE id=%s"
    
    if use_sqlite():
        if not _sqlite: await init_sqlite()
        await _sqlite.execute(sql, (user_id,))
        await _sqlite.commit()
    else:
        if not _pool: await init_pool()
        async with _pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (user_id,))
    return True



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
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password_hash TEXT,
            role TEXT DEFAULT 'user',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    await _sqlite.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER,
            expires_at DATETIME
        )
    """)
    
    # Check if admin exists, if not create default
    async with _sqlite.execute("SELECT id FROM users WHERE username='admin'") as cur:
        if not await cur.fetchone():
            p_hash = hash_password("admin")
            await _sqlite.execute("INSERT INTO users (username, password_hash, role) VALUES ('admin', ?, 'admin')", (p_hash,))

    # Migration: Add created_at if not exists
    try:
        await _sqlite.execute("ALTER TABLE users ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP")
    except Exception:
        pass
    
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
            ip TEXT,
            bound_at DATETIME
        )
    """)
    try:
        await _sqlite.execute("ALTER TABLE registry ADD COLUMN ip TEXT")
    except Exception:
        pass
    try:
        await _sqlite.execute("ALTER TABLE registry ADD COLUMN bound_at DATETIME")
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
    async with _sqlite.execute("PRAGMA table_info(academies)") as cur:
        cols = [r[1] for r in (await cur.fetchall() or []) if r and len(r) > 1]
    if "sort_order" not in cols:
        await _sqlite.execute("ALTER TABLE academies ADD COLUMN sort_order INTEGER DEFAULT 0")
    
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
            status INTEGER DEFAULT 0,
            info TEXT,
            time DATETIME DEFAULT CURRENT_TIMESTAMP,
            notified INTEGER DEFAULT 0,
            notified_at DATETIME,
            notify_error TEXT
        )
    """)
    try:
        await _sqlite.execute("ALTER TABLE alerts ADD COLUMN status INTEGER DEFAULT 0")
    except Exception:
        pass
    try:
        await _sqlite.execute("ALTER TABLE alerts ADD COLUMN notified INTEGER DEFAULT 0")
    except Exception:
        pass
    try:
        await _sqlite.execute("ALTER TABLE alerts ADD COLUMN notified_at DATETIME")
    except Exception:
        pass
    try:
        await _sqlite.execute("ALTER TABLE alerts ADD COLUMN notify_error TEXT")
    except Exception:
        pass
    await _sqlite.execute("""
        CREATE TABLE IF NOT EXISTS location_academy (
            location_name TEXT PRIMARY KEY,
            academy_name TEXT
        )
    """)
    try:
        await _sqlite.execute("""
            UPDATE registry
            SET bound_at = COALESCE(bound_at, CURRENT_TIMESTAMP)
            WHERE name IS NOT NULL
              AND name != ''
              AND name IN (SELECT location_name FROM location_academy)
        """)
    except Exception:
        pass
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
                    CREATE TABLE IF NOT EXISTS users (
                        id BIGINT AUTO_INCREMENT PRIMARY KEY,
                        username VARCHAR(64) UNIQUE,
                        password_hash VARCHAR(128),
                        role VARCHAR(32) DEFAULT 'user',
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                # MySQL Migration for users.created_at
                try:
                    await cur.execute("SHOW COLUMNS FROM users LIKE 'created_at'")
                    if not await cur.fetchone():
                        await cur.execute("ALTER TABLE users ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP")
                except Exception as e:
                    logging.info(f"MySQL Migration failed (users.created_at): {e}")

                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS sessions (
                        token VARCHAR(64) PRIMARY KEY,
                        user_id BIGINT,
                        expires_at DATETIME
                    )
                """)
                # Check admin
                await cur.execute("SELECT id FROM users WHERE username='admin'")
                if not await cur.fetchone():
                    p_hash = hash_password("admin")
                    await cur.execute("INSERT INTO users (username, password_hash, role) VALUES ('admin', %s, 'admin')", (p_hash,))
                
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
                        ip VARCHAR(64),
                        bound_at DATETIME
                    )
                """)
                try:
                    await cur.execute("ALTER TABLE registry ADD COLUMN ip VARCHAR(64)")
                except Exception:
                    pass
                try:
                    await cur.execute("ALTER TABLE registry ADD COLUMN bound_at DATETIME")
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
                        status INT DEFAULT 0,
                        info TEXT,
                        time DATETIME DEFAULT CURRENT_TIMESTAMP,
                        notified INT DEFAULT 0,
                        notified_at DATETIME NULL,
                        notify_error TEXT
                    )
                """)
                try:
                    await cur.execute("ALTER TABLE alerts ADD COLUMN status INT DEFAULT 0")
                except Exception:
                    pass
                try:
                    await cur.execute("ALTER TABLE alerts ADD COLUMN notified INT DEFAULT 0")
                except Exception:
                    pass
                try:
                    await cur.execute("ALTER TABLE alerts ADD COLUMN notified_at DATETIME NULL")
                except Exception:
                    pass
                try:
                    await cur.execute("ALTER TABLE alerts ADD COLUMN notify_error TEXT")
                except Exception:
                    pass
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS location_academy (
                        location_name VARCHAR(128) PRIMARY KEY,
                        academy_name VARCHAR(64)
                    )
                """)
                try:
                    await cur.execute("""
                        UPDATE registry r
                        JOIN location_academy la ON r.name = la.location_name
                        SET r.bound_at = IFNULL(r.bound_at, NOW())
                        WHERE r.name IS NOT NULL AND r.name != ''
                    """)
                except Exception:
                    pass
    except Exception as e:
        logging.error(f"DB init failed: {e}")

async def close_pool():
    global _pool, _sqlite
    if _pool:
        _pool.close()
        await _pool.wait_closed()
    if _sqlite:
        await _sqlite.close()

async def ping() -> Dict[str, Any]:
    start_ts = time.time()
    try:
        if use_sqlite():
            if not _sqlite:
                await init_sqlite()
            async with _sqlite.execute("SELECT 1") as cur:
                await cur.fetchone()
        else:
            if not _pool:
                await init_pool()
            async with _pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT 1")
                    await cur.fetchone()
        return {"ok": True, "latency_ms": int((time.time() - start_ts) * 1000)}
    except Exception as e:
        return {"ok": False, "error": str(e), "latency_ms": int((time.time() - start_ts) * 1000)}

# --- Device / Records ---

async def fetch_latest(uuid: str | None = None):
    """
    获取“每台设备最新一条记录”，并附带 registry 的 name/category。

    设计说明（兼容两类调用场景）：
    1) uuid 为空：返回所有设备的最新记录列表（用于看板/总览）。
    2) uuid 非空：仅返回指定设备的最新记录列表（长度为 0 或 1）。

    返回结构：
    - SQLite：返回 list[dict]，字段为 records 表的列 + name/category；
    - MySQL：返回 list[dict]，字段同上。
    """
    base_sql = """
    SELECT r.*, reg.name, reg.category
    FROM records r
    LEFT JOIN registry reg ON r.uuid = reg.uuid
    """

    params = []
    if uuid:
        sql = (
            base_sql
            + """
    WHERE r.uuid = {uuid_ph}
    ORDER BY r.id DESC
    LIMIT 1
    """
        )
        if use_sqlite():
            sql = sql.format(uuid_ph="?")
            params = [uuid]
        else:
            sql = sql.format(uuid_ph="%s")
            params = [uuid]
    else:
        sql = (
            base_sql
            + """
    WHERE r.id IN (SELECT MAX(id) FROM records GROUP BY uuid)
    """
        )

    if use_sqlite():
        if not _sqlite:
            await init_sqlite()
        async with _sqlite.execute(sql, params) as cur:
            rows = await cur.fetchall()
            return [dict(row) for row in rows]
    else:
        if not _pool:
            await init_pool()
        async with _pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql, params)
                return await cur.fetchall()

async def fetch_history(uuid=None, start=None, end=None, limit=100, order: str = "desc", sort_by: str = "time"):
    where = ["1=1"]
    params = []
    if uuid:
        where.append("uuid = ?" if use_sqlite() else "uuid = %s")
        params.append(uuid)
    sort_by_norm = str(sort_by or "").strip().lower()
    col = "created_at" if sort_by_norm == "created_at" else "time"

    if start:
        where.append(f"{col} >= ?" if use_sqlite() else f"{col} >= %s")
        params.append(start)
    if end:
        where.append(f"{col} <= ?" if use_sqlite() else f"{col} <= %s")
        params.append(end)

    order_norm = str(order or "").strip().lower()
    order_sql = "ASC" if order_norm == "asc" else "DESC"
    sql = f"SELECT * FROM records WHERE {' AND '.join(where)} ORDER BY {col} {order_sql} LIMIT {limit}"
    
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
            return [{"uuid": row[0]} for row in rows]
    else:
        if not _pool: await init_pool()
        async with _pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql)
                rows = await cur.fetchall()
                return [{"uuid": row[0]} for row in rows]

async def get_device_mapping():
    sql = "SELECT uuid, name, category FROM registry"
    if use_sqlite():
        if not _sqlite: await init_sqlite()
        async with _sqlite.execute(sql) as cur:
            rows = await cur.fetchall()
            return {"mapping": {row[0]: {"name": row[1], "category": row[2]} for row in rows}}
    else:
        if not _pool: await init_pool()
        async with _pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql)
                rows = await cur.fetchall()
                return {"mapping": {row[0]: {"name": row[1], "category": row[2]} for row in rows}}

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

async def admin_count_records(uuid=None, start=None, end=None, warn=None, rec_type=None, btx_min=None, btx_max=None):
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
    if warn is not None:
        where.append("warn_status = ?" if use_sqlite() else "warn_status = %s")
        params.append(warn)
    if rec_type is not None:
        where.append("rec_type = ?" if use_sqlite() else "rec_type = %s")
        params.append(rec_type)
    if btx_min is not None:
        where.append("btx >= ?" if use_sqlite() else "btx >= %s")
        params.append(btx_min)
    if btx_max is not None:
        where.append("btx <= ?" if use_sqlite() else "btx <= %s")
        params.append(btx_max)

    sql = f"SELECT COUNT(*) FROM records WHERE {' AND '.join(where)}"
    
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

async def admin_list_records(
    page=1,
    limit=50,
    uuid=None,
    start=None,
    end=None,
    warn=None,
    rec_type=None,
    btx_min=None,
    btx_max=None,
    order: str = "desc",
    sort_by: str = "time",
):
    """
    管理视图：按条件分页列出 records。

    与 fetch_history 的差异：
    - fetch_history：面向“轻量历史查询”，只支持 limit，不返回 total；
    - admin_list_records：面向“管理后台表格”，支持 page/limit（并配合 admin_count_records 返回 total）。

    额外能力：
    - 支持排序字段：time / created_at
    - 支持排序方向：asc / desc
    """
    offset = (page - 1) * limit
    where = ["1=1"]
    params = []
    if uuid:
        where.append("uuid = ?" if use_sqlite() else "uuid = %s")
        params.append(uuid)
    sort_by_norm = str(sort_by or "").strip().lower()
    col = "created_at" if sort_by_norm == "created_at" else "time"
    if start:
        where.append(f"{col} >= ?" if use_sqlite() else f"{col} >= %s")
        params.append(start)
    if end:
        where.append(f"{col} <= ?" if use_sqlite() else f"{col} <= %s")
        params.append(end)
    if warn is not None:
        where.append("warn_status = ?" if use_sqlite() else "warn_status = %s")
        params.append(warn)
    if rec_type is not None:
        where.append("rec_type = ?" if use_sqlite() else "rec_type = %s")
        params.append(rec_type)
    if btx_min is not None:
        where.append("btx >= ?" if use_sqlite() else "btx >= %s")
        params.append(btx_min)
    if btx_max is not None:
        where.append("btx <= ?" if use_sqlite() else "btx <= %s")
        params.append(btx_max)

    order_norm = str(order or "").strip().lower()
    order_sql = "ASC" if order_norm == "asc" else "DESC"

    sql = f"SELECT * FROM records WHERE {' AND '.join(where)} ORDER BY {col} {order_sql} LIMIT {limit} OFFSET {offset}"
    
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
    """
    保存设备上报数据到 records，并更新 registry 的 last_seen/ip。

    兼容性说明（本函数的核心目标）：
    - 兼容 parse_sensor_xml 的输出：in/out/batterytx_level/rec_type/warn_status 等；
    - 同时兼容历史/导入场景可能使用的字段：in_count/out_count/btx/battery/signal_strength 等；
    - 最终统一写入 records 表的标准字段：in_count/out_count/battery/btx/rec_type/signal_strength/warn_status/activity_type。
    """
    # 1) 解析并校验 UUID：设备唯一标识，缺失则不入库
    uuid = (data.get("uuid") or "").strip()
    if not uuid:
        return

    def _safe_int(v, default: int | None = 0) -> int | None:
        """
        将任意输入安全转换为 int：
        - v 为 None/空串/不可转数字时返回 default；
        - v 已是数字时直接转换；
        - 该函数用于“入库前强制类型兜底”，避免因脏数据导致写入异常。
        """
        if v is None:
            return default
        if isinstance(v, bool):
            return int(v)
        if isinstance(v, (int, float)):
            try:
                return int(v)
            except Exception:
                return default
        s = str(v).strip()
        if s == "":
            return default
        try:
            return int(s)
        except Exception:
            return default

    def _pick_int(*keys: str, default: int = 0) -> int:
        """
        在 data 中按 keys 的顺序尝试取值并转为 int：
        - 只要遇到一个非 None/非空的值且可转换，就立即返回；
        - 全部失败则返回 default；
        - 用于处理“同一语义字段多种命名”的兼容写入。
        """
        for k in keys:
            if k in data:
                v = data.get(k)
                if v is None:
                    continue
                if isinstance(v, str) and v.strip() == "":
                    continue
                n = _safe_int(v, default=None)  # 先用 None 表示“转换失败”
                if n is not None:
                    return n
        return default

    def _pick_str(*keys: str, default: str = "") -> str:
        """
        在 data 中按 keys 的顺序尝试取值并转为 str：
        - 只要遇到一个非空字符串（或可转为非空字符串的值）就返回；
        - 全部失败则返回 default。
        """
        for k in keys:
            if k in data:
                v = data.get(k)
                if v is None:
                    continue
                s = str(v).strip()
                if s != "":
                    return s
        return default

    # 2) 时间字段兼容：
    # - parse_sensor_xml 会提供 "time"（通常为 "YYYY-MM-DD HH:MM:SS"）；
    # - 兼容极少数场景传 compact 格式 "YYYYMMDDHHMMSS"；
    # - 若缺失则使用服务器当前时间。
    ts = _pick_str("time", "timestamp", "datetime", "record_time", default=time.strftime("%Y-%m-%d %H:%M:%S"))
    if len(ts) == 14 and ts.isdigit():
        try:
            import datetime as _dt
            dt = _dt.datetime.strptime(ts, "%Y%m%d%H%M%S")
            ts = dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            ts = time.strftime("%Y-%m-%d %H:%M:%S")

    # 3) 字段映射（重点修复）：
    # - in/out ↔ in_count/out_count
    # - batterytx_level ↔ btx
    # - warn_status ↔ warn
    # - rec_type ↔ rec_type
    # - battery_level ↔ battery
    # - signal_status ↔ signal_strength
    in_count = _pick_int("in_count", "in", "IN", default=0)
    out_count = _pick_int("out_count", "out", "OUT", default=0)
    battery = _pick_int("battery", "battery_level", "power", default=0)
    btx = _pick_int("btx", "batterytx_level", "battery_tx", "btx_level", default=0)
    rec_type = _pick_int("rec_type", "rectype", default=0)
    warn_status = _pick_int("warn_status", "warn", "warning", default=0)
    signal_strength = _pick_int("signal_strength", "signal_status", "signal", default=0)

    # 4) 业务扩展字段：
    # - activity_type 主要用于管理后台/活动归属，设备上报通常不带；
    # - 兼容 data 已携带 activity_type 的情况；否则维持历史默认值 "default"。
    activity_type = _pick_str("activity_type", "activity", default="default")

    # 5) 入库：统一写入 records 标准字段
    rec = {
        "uuid": uuid,
        "time": ts,
        "in_count": in_count,
        "out_count": out_count,
        "battery": battery,
        "btx": btx,
        "rec_type": rec_type,
        "signal_strength": signal_strength,
        "warn_status": warn_status,
        "activity_type": activity_type,
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

async def list_unnotified_critical_alerts(limit: int = 20):
    sql = f"SELECT * FROM alerts WHERE level >= 2 AND (status IS NULL OR status = 0) AND (notified IS NULL OR notified = 0) ORDER BY time DESC LIMIT {int(limit or 0)}"
    params: list = []
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

async def mark_alert_notified(alert_id: int, status: int = 1, error: str | None = None):
    sid = int(alert_id)
    st = int(status)
    err = (str(error)[:800] if error else None)
    if use_sqlite():
        if not _sqlite: await init_sqlite()
        await _sqlite.execute(
            "UPDATE alerts SET notified=?, notified_at=CURRENT_TIMESTAMP, notify_error=? WHERE id=?",
            (st, err, sid),
        )
        await _sqlite.commit()
        return True
    else:
        if not _pool: await init_pool()
        async with _pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "UPDATE alerts SET notified=%s, notified_at=NOW(), notify_error=%s WHERE id=%s",
                    (st, err, sid),
                )
                return True

async def set_alert_status(alert_id: int, status: int = 1):
    sid = int(alert_id)
    st = int(status)
    if use_sqlite():
        if not _sqlite: await init_sqlite()
        await _sqlite.execute(
            "UPDATE alerts SET status=? WHERE id=?",
            (st, sid),
        )
        await _sqlite.commit()
        return True
    else:
        if not _pool: await init_pool()
        async with _pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "UPDATE alerts SET status=%s WHERE id=%s",
                    (st, sid),
                )
                return True

# --- Activity Events (Preserved) ---

async def activity_bulk_insert(events: list[dict], mode: str = "skip"):
    if not events:
        return {"inserted": 0, "updated": 0, "duplicates": []}
    
    # 1. Prepare
    # Normalize keys for comparison. Key: (date, start_time, location, activity_name)
    dates = [e.get("date") for e in events if e.get("date")]
    if not dates:
        return {"inserted": 0, "updated": 0, "duplicates": []}

    min_date, max_date = min(dates), max(dates)
    
    # Fetch existing signatures in range with IDs
    # Map: (date, start_time, location, activity_name) -> id
    existing_map = {}
    
    cols = ["date", "weekday", "start_time", "end_time", "duration_minutes", "academy", "location", "activity_name", "activity_type", "audience_count", "notes"]
    
    check_sql = "SELECT id, date, start_time, location, activity_name FROM activity_events WHERE date >= ? AND date <= ?" if use_sqlite() else \
                "SELECT id, date, start_time, location, activity_name FROM activity_events WHERE date >= %s AND date <= %s"
    
    rows = await run_query(check_sql, [min_date, max_date])
    for r in rows:
        # Tuple of (date, start_time, location, activity_name) -> id
        sig = (r[1], r[2], r[3], r[4])
        existing_map[sig] = r[0]
        
    to_insert = []
    to_delete_ids = []
    duplicate_indices = []
    
    # Track signatures processed in this batch to handle internal duplicates
    batch_sigs = set()

    for i, e in enumerate(events):
        sig = (e.get("date"), e.get("start_time"), e.get("location"), e.get("activity_name"))
        
        # Check against DB
        db_id = existing_map.get(sig)
        
        # Check against current batch (internal duplicates)
        is_internal_dup = sig in batch_sigs
        
        if db_id is not None:
            # Exists in DB
            if mode == "overwrite":
                if not is_internal_dup:
                    to_delete_ids.append(db_id)
                    to_insert.append(e)
                    batch_sigs.add(sig)
                else:
                    # If it's an internal duplicate and we are overwriting, 
                    # we essentially just want the last one or first one?
                    # Let's assume we append it to insert, but since we deleted the DB one, 
                    # we will have multiple copies in DB unless we dedup inputs.
                    # Standard behavior: insert all provided inputs.
                    to_insert.append(e)
            else:
                duplicate_indices.append(i)
        else:
            # Not in DB
            to_insert.append(e)
            batch_sigs.add(sig)

    inserted_count = 0
    updated_count = 0
    
    # Connection Management
    conn = None
    cur = None
    should_close = False
    
    try:
        if use_sqlite():
            if _sqlite is None: await init_sqlite()
            conn = _sqlite
            # SQLite doesn't need explicit cursor for execute/executemany on connection object usually, 
            # but for transaction control we rely on the connection.
        else:
            if _pool is None: await init_pool()
            conn = await _pool.acquire()
            cur = await conn.cursor()
            should_close = True
            await conn.begin() # Start transaction for MySQL

        # 2. Bulk Delete (for Overwrite)
        if to_delete_ids:
            # SQLite limit is usually 999 vars, MySQL packet size limit. Safe batch: 500.
            BATCH_SIZE = 500
            for i in range(0, len(to_delete_ids), BATCH_SIZE):
                chunk_ids = to_delete_ids[i:i + BATCH_SIZE]
                placeholders = ",".join(["?" if use_sqlite() else "%s"] * len(chunk_ids))
                del_sql = f"DELETE FROM activity_events WHERE id IN ({placeholders})"
                
                if use_sqlite():
                    await conn.execute(del_sql, chunk_ids)
                else:
                    await cur.execute(del_sql, chunk_ids)
            
            updated_count = len(to_delete_ids)

        # 3. Bulk Insert (New + Overwritten)
        if to_insert:
            BATCH_SIZE = 500
            for i in range(0, len(to_insert), BATCH_SIZE):
                chunk = to_insert[i:i + BATCH_SIZE]
                
                vals = []
                for e in chunk:
                    vals.extend([e.get(c) for c in cols])
                
                placeholders = ",".join(["?" if use_sqlite() else "%s"] * len(cols))
                row_placeholder = f"({placeholders})"
                all_placeholders = ",".join([row_placeholder] * len(chunk))
                
                insert_sql = f"INSERT INTO activity_events({','.join(cols)}) VALUES {all_placeholders}"
                
                if use_sqlite():
                    await conn.execute(insert_sql, vals)
                else:
                    await cur.execute(insert_sql, vals)
            
            inserted_count = len(to_insert) - updated_count # True new inserts
            # Wait, if mode=overwrite, inserted_count should probably reflect total inserted?
            # Or "inserted" = new records, "updated" = replaced records.
            # If I delete 10 and insert 15 (10 replaced + 5 new), then updated=10, inserted=5?
            # Simpler: inserted = len(to_insert) if mode!=overwrite else len(to_insert) - len(to_delete_ids)
            # Actually return raw counts makes more sense
            inserted_count = len(to_insert)

        # Commit Transaction
        if use_sqlite():
            await conn.commit()
        else:
            await conn.commit()
            
    except Exception as e:
        if not use_sqlite() and conn:
            await conn.rollback()
        logging.error(f"Bulk insert failed: {e}")
        raise e
    finally:
        if should_close and cur:
            await cur.close()
        if should_close and conn:
            # release back to pool
            _pool.release(conn)

    return {"inserted": inserted_count, "updated": updated_count, "duplicates": duplicate_indices}

async def activity_list(start_date: str = None, end_date: str = None, locations: list = None, types: list = None, academies: list = None, weekdays: list = None, start_times: list = None, page: int = 1, page_size: int = 50):
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
        placeholders = ",".join(["?" if use_sqlite() else "%s"] * len(weekdays))
        sql += f" AND weekday IN ({placeholders})"
        params.extend(weekdays)
    if start_times:
        placeholders = ",".join(["?" if use_sqlite() else "%s"] * len(start_times))
        sql += f" AND start_time IN ({placeholders})"
        params.extend(start_times)
    
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
            w_cur = await _sqlite.execute("SELECT DISTINCT weekday FROM activity_events ORDER BY weekday")
            weekdays = [r[0] for r in await w_cur.fetchall() if r[0]]
            s_cur = await _sqlite.execute("SELECT DISTINCT start_time FROM activity_events ORDER BY start_time")
            times = [r[0] for r in await s_cur.fetchall() if r[0]]
            return {"locations": locations, "types": types, "academies": academies, "weekdays": weekdays, "times": times}
    
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
                await cur.execute("SELECT DISTINCT weekday FROM activity_events ORDER BY weekday")
                weekdays = [r[0] for r in await cur.fetchall() if r[0]]
                await cur.execute("SELECT DISTINCT start_time FROM activity_events ORDER BY start_time")
                times = [r[0] for r in await cur.fetchall() if r[0]]
                return {"locations": locations, "types": types, "academies": academies, "weekdays": weekdays, "times": times}
    return {"locations": [], "types": [], "academies": [], "weekdays": [], "times": []}

async def activity_stats(start_date: str = None, end_date: str = None, locations: list = None, types: list = None, academies: list = None, weekdays: list = None, start_times: list = None):
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
    if weekdays:
        placeholders = ",".join(["?" if use_sqlite() else "%s"] * len(weekdays))
        where += f" AND weekday IN ({placeholders})"
        params.extend(weekdays)
    if start_times:
        placeholders = ",".join(["?" if use_sqlite() else "%s"] * len(start_times))
        where += f" AND start_time IN ({placeholders})"
        params.extend(start_times)

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

async def admin_get_record_ids(uuid=None, start=None, end=None):
    where = " WHERE 1=1"
    params = []
    if uuid:
        where += " AND uuid = ?" if use_sqlite() else " AND uuid = %s"
        params.append(uuid)
    if start:
        where += " AND time >= ?" if use_sqlite() else " AND time >= %s"
        params.append(start)
    if end:
        where += " AND time <= ?" if use_sqlite() else " AND time <= %s"
        params.append(end)
        
    sql = f"SELECT id FROM records {where}"
    rows = await run_query(sql, params)
    return [r[0] for r in rows]

async def admin_get_record_id_map_by_times(uuid: str, times: list):
    if not uuid or not times:
        return {}

    placeholders = ",".join(["?" if use_sqlite() else "%s"] * len(times))
    sql = f"SELECT id, time FROM records WHERE uuid = {'?' if use_sqlite() else '%s'} AND time IN ({placeholders})"
    params = [uuid]
    params.extend(times)
    rows = await run_query(sql, params)
    return {str(r[1]): r[0] for r in rows}

async def admin_batch_delete(ids):
    if not ids: return
    placeholders = ",".join(["?" if use_sqlite() else "%s"] * len(ids))
    sql = f"DELETE FROM records WHERE id IN ({placeholders})"
    
    if use_sqlite():
        if _sqlite is None: await init_sqlite()
        if _sqlite:
            await _sqlite.execute(sql, ids)
            await _sqlite.commit()
    elif not _pool: await init_pool()
    if _pool:
        async with _pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, ids)

async def run_query(sql: str, params: list):
    if use_sqlite():
        if not _sqlite: await init_sqlite()
        async with _sqlite.execute(sql, params) as cur:
            return await cur.fetchall()
    else:
        if not _pool: await init_pool()
        async with _pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, params)
                return await cur.fetchall()

async def walkin_preview(devices: list, start: str, end: str):
    # Query records
    where = " WHERE 1=1"
    params = []
    
    if devices:
        placeholders = ",".join(["?" if use_sqlite() else "%s"] * len(devices))
        where += f" AND uuid IN ({placeholders})"
        params.extend(devices)
        
    if start:
        where += " AND time >= ?" if use_sqlite() else " AND time >= %s"
        params.append(start)
    if end:
        where += " AND time <= ?" if use_sqlite() else " AND time <= %s"
        params.append(end)
        
    sql = f"SELECT uuid, time, in_count FROM records {where} ORDER BY uuid, time"
    
    rows = await run_query(sql, params)
    if not rows: return []
    
    import datetime

    def to_dt(v):
        if v is None:
            return None
        if isinstance(v, datetime.datetime):
            return v
        if isinstance(v, datetime.date):
            return datetime.datetime(v.year, v.month, v.day, 0, 0, 0)
        s = str(v).strip()
        if not s:
            return None
        s = s.replace("T", " ")
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M"):
            try:
                return datetime.datetime.strptime(s, fmt)
            except Exception:
                continue
        return None

    data_map = {}  # (uuid, date, interval_idx) -> {"sum": int}
    
    # 30 min intervals
    def get_interval(dt):
        idx = dt.hour * 2 + (1 if dt.minute >= 30 else 0)
        return idx
        
    for r in rows:
        uuid = r[0]
        dt = to_dt(r[1])
        in_c = r[2]
        if dt is None or in_c is None:
            continue
            
        date = dt.strftime("%Y-%m-%d")
        idx = get_interval(dt)
        
        key = (uuid, date, idx)
        if key not in data_map:
            data_map[key] = {"sum": 0}
        try:
            v = int(in_c)
        except Exception:
            continue
        if v > 0:
            data_map[key]["sum"] += v
            
    # Generate Events
    events = []
    mapping_res = await get_device_mapping()
    mapping = (mapping_res or {}).get("mapping") or {}
    loc_academy = await get_location_academy_mapping()
    
    wd_map = {1:"周一", 2:"周二", 3:"周三", 4:"周四", 5:"周五", 6:"周六", 7:"周日"}
    
    for (uuid, date, idx), val in data_map.items():
        count = int(val.get("sum") or 0)
        if count <= 0: continue
        
        # Start Time
        h = idx // 2
        m = (idx % 2) * 30
        s_time = f"{h:02d}:{m:02d}"
        
        # End Time
        end_idx = idx + 1
        eh = end_idx // 2
        em = (end_idx % 2) * 30
        if eh >= 24: 
             e_time = "23:59"
        else:
             e_time = f"{eh:02d}:{em:02d}"
             
        dt = datetime.datetime.strptime(date, "%Y-%m-%d")
        weekday = wd_map.get(dt.isoweekday(), "")
        dev = mapping.get(uuid) or {}
        loc_name = str((dev.get("name") or "")).strip() or uuid
        academy = str((loc_academy.get(loc_name) or dev.get("category") or "公共")).strip() or "公共"
        
        events.append({
            "date": date,
            "weekday": weekday,
            "start_time": s_time,
            "end_time": e_time,
            "duration_minutes": 30,
            "academy": academy, 
            "location": loc_name, 
            "activity_name": "散客",
            "activity_type": "散客访问",
            "audience_count": count,
            "notes": f"from device {uuid}"
        })
    
    # Sort by date, time
    events.sort(key=lambda x: (x['date'], x['start_time']))
    return events


async def walkin_available_dates(devices: list):
    if not devices:
        return {"dates": [], "min_date": None, "max_date": None}
    placeholders = ",".join(["?" if use_sqlite() else "%s"] * len(devices))
    if use_sqlite():
        d_expr = "strftime('%Y-%m-%d', time)"
        sql = f"SELECT {d_expr} as d FROM records WHERE uuid IN ({placeholders}) AND time IS NOT NULL GROUP BY d ORDER BY d"
    else:
        d_expr = "DATE(time)"
        sql = f"SELECT {d_expr} as d FROM records WHERE uuid IN ({placeholders}) AND time IS NOT NULL GROUP BY d ORDER BY d"
    rows = await run_query(sql, devices)
    dates = []
    for r in rows or []:
        if not r:
            continue
        v = r[0]
        if v is None:
            continue
        s = str(v).split(" ")[0].strip()
        if s:
            dates.append(s)
    dates = sorted(list(dict.fromkeys(dates)))
    return {"dates": dates, "min_date": (dates[0] if dates else None), "max_date": (dates[-1] if dates else None)}


async def walkin_preview_by_dates(devices: list, dates: list[str]):
    if not devices or not dates:
        return []
    placeholders_u = ",".join(["?" if use_sqlite() else "%s"] * len(devices))
    placeholders_d = ",".join(["?" if use_sqlite() else "%s"] * len(dates))
    params = []
    params.extend(devices)
    params.extend(dates)
    if use_sqlite():
        d_expr = "strftime('%Y-%m-%d', time)"
        sql = f"SELECT uuid, time, in_count FROM records WHERE uuid IN ({placeholders_u}) AND time IS NOT NULL AND {d_expr} IN ({placeholders_d}) ORDER BY uuid, time"
    else:
        d_expr = "DATE(time)"
        sql = f"SELECT uuid, time, in_count FROM records WHERE uuid IN ({placeholders_u}) AND time IS NOT NULL AND {d_expr} IN ({placeholders_d}) ORDER BY uuid, time"
    rows = await run_query(sql, params)
    if not rows:
        return []

    import datetime

    def to_dt(v):
        if v is None:
            return None
        if isinstance(v, datetime.datetime):
            return v
        if isinstance(v, datetime.date):
            return datetime.datetime(v.year, v.month, v.day, 0, 0, 0)
        s = str(v).strip()
        if not s:
            return None
        s = s.replace("T", " ")
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M"):
            try:
                return datetime.datetime.strptime(s, fmt)
            except Exception:
                continue
        return None

    def get_interval(dt):
        return dt.hour * 2 + (1 if dt.minute >= 30 else 0)

    data_map = {}
    for r in rows:
        uuid = r[0]
        dt = to_dt(r[1])
        in_c = r[2]
        if dt is None or in_c is None:
            continue
        date = dt.strftime("%Y-%m-%d")
        idx = get_interval(dt)
        key = (uuid, date, idx)
        if key not in data_map:
            data_map[key] = {"sum": 0}
        try:
            v = int(in_c)
        except Exception:
            continue
        if v > 0:
            data_map[key]["sum"] += v

    events = []
    mapping_res = await get_device_mapping()
    mapping = (mapping_res or {}).get("mapping") or {}
    loc_academy = await get_location_academy_mapping()

    wd_map = {1: "周一", 2: "周二", 3: "周三", 4: "周四", 5: "周五", 6: "周六", 7: "周日"}

    for (uuid, date, idx), val in data_map.items():
        count = int(val.get("sum") or 0)
        if count <= 0:
            continue
        h = idx // 2
        m = (idx % 2) * 30
        s_time = f"{h:02d}:{m:02d}"
        end_idx = idx + 1
        eh = end_idx // 2
        em = (end_idx % 2) * 30
        if eh >= 24:
            e_time = "23:59"
        else:
            e_time = f"{eh:02d}:{em:02d}"

        dt_d = datetime.datetime.strptime(date, "%Y-%m-%d").date()
        weekday = wd_map.get(dt_d.isoweekday(), "")

        dev = mapping.get(uuid) or {}
        loc_name = str((dev.get("name") or "")).strip() or uuid
        academy = str((loc_academy.get(loc_name) or dev.get("category") or "公共")).strip() or "公共"

        events.append({
            "date": date,
            "weekday": weekday,
            "start_time": s_time,
            "end_time": e_time,
            "duration_minutes": 30,
            "academy": academy,
            "location": loc_name,
            "activity_name": "散客",
            "activity_type": "散客访问",
            "audience_count": count,
            "notes": f"from device {uuid}"
        })
    events.sort(key=lambda x: (x.get("date") or "", x.get("start_time") or "", x.get("location") or ""))
    return events

async def _walkin_eligible_devices(devices: list | None = None):
    mapping_res = await get_device_mapping()
    mapping = (mapping_res or {}).get("mapping") or {}
    loc_academy = await get_location_academy_mapping()
    target = devices or list(mapping.keys())

    eligible = []
    skipped = []
    for uuid in target:
        dev = mapping.get(uuid) or {}
        loc_name = str((dev.get("name") or "")).strip()
        if not loc_name:
            skipped.append({"uuid": uuid, "reason": "unbound"})
            continue
        if loc_name not in loc_academy:
            skipped.append({"uuid": uuid, "reason": "not_in_standard_library", "location": loc_name})
            continue
        eligible.append(uuid)
    return eligible, skipped

async def activity_sync_visitors(date: str = None, devices: list = None, start: str = None, end: str = None, mode: str = "overwrite"):
    if date:
        d = str(date).split(" ")[0].strip()
        if not d:
            raise ValueError("date is required")
        start = f"{d} 00:00:00"
        end = f"{d} 23:59:59"

    eligible_devices, skipped = await _walkin_eligible_devices(devices)
    if not eligible_devices:
        return {"count": 0, "skipped": skipped}

    total = 0
    if start or end:
        if start and not end:
            d = str(start).split(" ")[0].strip()
            end = f"{d} 23:59:59"
        if end and not start:
            d = str(end).split(" ")[0].strip()
            start = f"{d} 00:00:00"

        items = await walkin_preview(eligible_devices, start, end)
        res = await activity_bulk_insert(items, mode=mode)
        if isinstance(res, dict):
            total += int(res.get("inserted") or 0) + int(res.get("updated") or 0)
        else:
            total += int(res or 0)
        return {"count": total, "skipped": skipped}

    import datetime
    placeholders = ",".join(["?" if use_sqlite() else "%s"] * len(eligible_devices))
    if use_sqlite():
        d_expr = "strftime('%Y-%m-%d', time)"
        range_sql = f"SELECT MIN({d_expr}) as min_d, MAX({d_expr}) as max_d FROM records WHERE uuid IN ({placeholders}) AND time IS NOT NULL"
    else:
        d_expr = "DATE(time)"
        range_sql = f"SELECT MIN({d_expr}) as min_d, MAX({d_expr}) as max_d FROM records WHERE uuid IN ({placeholders}) AND time IS NOT NULL"

    range_rows = await run_query(range_sql, eligible_devices)
    min_d = None
    max_d = None
    if range_rows and range_rows[0]:
        min_d = range_rows[0][0]
        max_d = range_rows[0][1] if len(range_rows[0]) > 1 else None

    def parse_date(v):
        if v is None:
            return None
        s = str(v).split(" ")[0].strip()
        if not s:
            return None
        try:
            return datetime.datetime.strptime(s, "%Y-%m-%d").date()
        except Exception:
            return None

    start_date = parse_date(min_d)
    end_date = parse_date(max_d)
    if not start_date or not end_date:
        return {"count": 0, "skipped": skipped}
    if end_date < start_date:
        start_date, end_date = end_date, start_date

    cur = start_date
    while cur <= end_date:
        d = cur.strftime("%Y-%m-%d")
        day_start = f"{d} 00:00:00"
        day_end = f"{d} 23:59:59"
        items = await walkin_preview(eligible_devices, day_start, day_end)
        if items:
            res = await activity_bulk_insert(items, mode=mode)
            if isinstance(res, dict):
                total += int(res.get("inserted") or 0) + int(res.get("updated") or 0)
            else:
                total += int(res or 0)
        cur = cur + datetime.timedelta(days=1)

    return {"count": total, "skipped": skipped}

# --- Location-Academy Mapping ---

async def get_location_academy_mapping():
    """Returns {location_name: academy_name}"""
    sql = "SELECT location_name, academy_name FROM location_academy"
    if use_sqlite():
        if not _sqlite: await init_sqlite()
        async with _sqlite.execute(sql) as cur:
            rows = await cur.fetchall()
            return {row[0]: row[1] for row in rows}
    else:
        if not _pool: await init_pool()
        async with _pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql)
                rows = await cur.fetchall()
                return {row[0]: row[1] for row in rows}

async def update_location_academy_mapping(location_name: str, academy_name: str):
    """Updates or inserts a mapping"""
    # Upsert logic
    if use_sqlite():
        if not _sqlite: await init_sqlite()
        await _sqlite.execute("INSERT OR REPLACE INTO location_academy (location_name, academy_name) VALUES (?, ?)", (location_name, academy_name))
        await _sqlite.commit()
    else:
        if not _pool: await init_pool()
        async with _pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    INSERT INTO location_academy (location_name, academy_name) 
                    VALUES (%s, %s) 
                    ON DUPLICATE KEY UPDATE academy_name=%s
                """, (location_name, academy_name, academy_name))

async def delete_location_academy_mapping(location_name: str):
    """Deletes a mapping"""
    sql = "DELETE FROM location_academy WHERE location_name=?" if use_sqlite() else "DELETE FROM location_academy WHERE location_name=%s"
    if use_sqlite():
        if not _sqlite: await init_sqlite()
        await _sqlite.execute(sql, (location_name,))
        await _sqlite.commit()
    else:
        if not _pool: await init_pool()
        async with _pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (location_name,))

async def get_all_activity_locations():
    """Returns list of distinct locations from activity_events"""
    sql = "SELECT DISTINCT location FROM activity_events ORDER BY location"
    if use_sqlite():
        if not _sqlite: await init_sqlite()
        async with _sqlite.execute(sql) as cur:
            rows = await cur.fetchall()
            return [row[0] for row in rows if row[0]]
    else:
        if not _pool: await init_pool()
        async with _pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql)
                rows = await cur.fetchall()
                return [row[0] for row in rows if row[0]]

async def correct_location_data(target_location: str, target_academy: str, merge_locations: list = None):
    """
    Updates academy for target_location.
    Optionally merges other locations into target_location (renaming them and setting academy).
    Returns total modified rows.
    """
    count = 0
    
    # 1. Fix exact matches (update academy only)
    sql_exact = "UPDATE activity_events SET academy = ? WHERE location = ?" if use_sqlite() else "UPDATE activity_events SET academy = %s WHERE location = %s"
    params_exact = (target_academy, target_location)
    
    # 2. Merge similar locations (update location AND academy)
    sql_merge = None
    params_merge = []
    if merge_locations:
        placeholders = ",".join(["?" if use_sqlite() else "%s"] * len(merge_locations))
        sql_merge = f"UPDATE activity_events SET location = ?, academy = ? WHERE location IN ({placeholders})"
        if use_sqlite():
            params_merge = [target_location, target_academy] + merge_locations
        else:
            # MySQL might need distinct params structure depending on driver, usually list is fine
            params_merge = [target_location, target_academy] + merge_locations

    if use_sqlite():
        if not _sqlite: await init_sqlite()
        async with _sqlite.execute(sql_exact, params_exact) as cur:
            count += cur.rowcount
        if sql_merge:
            async with _sqlite.execute(sql_merge, params_merge) as cur:
                count += cur.rowcount
        await _sqlite.commit()
    else:
        if not _pool: await init_pool()
        async with _pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql_exact, params_exact)
                count += cur.rowcount
                if sql_merge:
                    await cur.execute(sql_merge, params_merge)
                    count += cur.rowcount
            # aiomysql pool connection commits automatically on context exit or needs explicit commit? 
            # Usually autocommit is off by default.
            await conn.commit()
            
    return count


# --- SQLite 数据库合并导入（管理员功能） ---
#
# 设计目标：
# 1) 支持管理员上传一个 SQLite .db 文件，并将其数据“合并导入”到当前运行库（仅支持当前库为 SQLite）。
# 2) 合并流程分两步：
#    - 预览：统计各表“新增/冲突/无效/预计插入/预计更新/预计跳过”；
#    - 执行：在一个事务中完成插入/更新，失败则整体回滚，同时写入 audit_logs 便于审计追溯。
# 3) 合并策略：
#    - merge_mode:
#      - skip_existing：遇到主键/签名冲突则跳过；
#      - update_existing：遇到冲突则更新已有记录（不改变主键/签名字段）。
#    - conflict_preference（仅 update_existing 时生效）：
#      - prefer_import：以导入库字段为准；
#      - prefer_current_non_empty：导入字段为空（NULL/空字符串）时保留当前库字段，否则使用导入值。
#
# 关键说明（“签名键”定义）：
# - records：使用 (uuid, time) 作为签名键（表内不一定有 UNIQUE 约束，但业务上视作唯一）。
# - registry：主键 uuid。
# - activity_events：使用 (date, start_time, location, activity_name) 作为签名键（与现有去重逻辑保持一致）。
# - alerts：使用 (uuid, type, time) 作为签名键（time 作为告警发生时间）。
# - academies：使用 name 作为签名键（name 唯一）。
# - location_academy：主键 location_name。

MergeMode = Literal["skip_existing", "update_existing"]
ConflictPreference = Literal["prefer_current_non_empty", "prefer_import"]

_DB_MERGE_TABLE_SPECS: Dict[str, Dict[str, Any]] = {
    "records": {
        "key_cols": ["uuid", "time"],
        "insert_cols": [
            "uuid",
            "time",
            "in_count",
            "out_count",
            "battery",
            "btx",
            "rec_type",
            "signal_strength",
            "warn_status",
            "activity_type",
            "created_at",
        ],
        "update_cols": [
            "in_count",
            "out_count",
            "battery",
            "btx",
            "rec_type",
            "signal_strength",
            "warn_status",
            "activity_type",
        ],
        "text_cols": ["activity_type"],
    },
    "registry": {
        "key_cols": ["uuid"],
        "insert_cols": ["uuid", "name", "category", "description", "last_seen", "ip", "bound_at"],
        "update_cols": ["name", "category", "description", "last_seen", "ip", "bound_at"],
        "text_cols": ["name", "category", "description", "ip"],
    },
    "activity_events": {
        "key_cols": ["date", "start_time", "location", "activity_name"],
        "insert_cols": [
            "date",
            "weekday",
            "start_time",
            "end_time",
            "duration_minutes",
            "academy",
            "location",
            "activity_name",
            "activity_type",
            "audience_count",
            "notes",
            "create_time",
        ],
        "update_cols": [
            "weekday",
            "end_time",
            "duration_minutes",
            "academy",
            "activity_type",
            "audience_count",
            "notes",
        ],
        "text_cols": ["weekday", "end_time", "academy", "activity_type", "notes"],
    },
    "alerts": {
        "key_cols": ["uuid", "type", "time"],
        "insert_cols": ["uuid", "type", "level", "status", "info", "time", "notified", "notified_at", "notify_error"],
        "update_cols": ["level", "status", "info", "notified", "notified_at", "notify_error"],
        "text_cols": ["type", "info", "notify_error"],
    },
    "academies": {
        "key_cols": ["name"],
        "insert_cols": ["name", "sort_order"],
        "update_cols": ["sort_order"],
        "text_cols": ["name"],
    },
    "location_academy": {
        "key_cols": ["location_name"],
        "insert_cols": ["location_name", "academy_name"],
        "update_cols": ["academy_name"],
        "text_cols": ["location_name", "academy_name"],
    },
}

def _sqlite_escape_path_for_attach(path: str) -> str:
    """
    将文件路径转为可安全放进 SQLite 字符串字面量的形式。

    说明：
    - ATTACH 不支持参数化占位符传入路径，因此只能拼接 SQL；
    - 这里通过转义单引号来规避注入风险；
    - 路径来源于后端保存的临时文件（非用户直接拼 SQL），仍建议做严格转义。
    """
    return str(path).replace("'", "''")

async def _sqlite_attach_database(conn: aiosqlite.Connection, alias: str, file_path: str) -> None:
    escaped = _sqlite_escape_path_for_attach(os.path.abspath(file_path))
    await conn.execute(f"ATTACH DATABASE '{escaped}' AS {alias}")

async def _sqlite_detach_database(conn: aiosqlite.Connection, alias: str) -> None:
    await conn.execute(f"DETACH DATABASE {alias}")

async def _sqlite_table_exists(conn: aiosqlite.Connection, schema: str, table: str) -> bool:
    sql = f"SELECT 1 FROM {schema}.sqlite_master WHERE type='table' AND name=? LIMIT 1"
    async with conn.execute(sql, (table,)) as cur:
        return (await cur.fetchone()) is not None

async def _sqlite_table_columns(conn: aiosqlite.Connection, schema: str, table: str) -> List[str]:
    sql = f"PRAGMA {schema}.table_info({table})"
    async with conn.execute(sql) as cur:
        rows = await cur.fetchall()
    cols: List[str] = []
    for r in rows or []:
        if not r or len(r) < 2:
            continue
        cols.append(str(r[1]))
    return cols

def _build_invalid_key_condition(key_cols: List[str], table_alias: str = "s") -> str:
    parts: List[str] = []
    for k in key_cols:
        # 统一将字段 cast 成 TEXT 来判空，兼容 time/date 等字段可能的存储类型差异
        parts.append(f"{table_alias}.{k} IS NULL OR trim(CAST({table_alias}.{k} AS TEXT)) = ''")
    return "(" + " OR ".join(parts) + ")"

def _build_key_join_condition(key_cols: List[str], left_alias: str, right_alias: str) -> str:
    return " AND ".join([f"{left_alias}.{k} = {right_alias}.{k}" for k in key_cols])

async def sqlite_db_merge_preview(
    import_db_path: str,
    merge_mode: MergeMode = "skip_existing",
    conflict_preference: ConflictPreference = "prefer_import",
) -> Dict[str, Any]:
    """
    预览合并导入影响范围（仅 SQLite）。

    返回结构示例：
    {
      "db_driver": "sqlite",
      "import_db_path": "...(server path)...",
      "strategy": {"merge_mode": "...", "conflict_preference": "..."},
      "tables": {
        "records": {"exists": true, "total": 123, "invalid": 0, "new": 100, "conflict": 23, "plan": {...}},
        ...
      }
    }
    """
    if not use_sqlite():
        raise RuntimeError("当前数据库不是 SQLite，无法执行 .db 合并导入")
    if not _sqlite:
        await init_sqlite()

    conn = _sqlite
    alias = "importdb"
    await _sqlite_attach_database(conn, alias, import_db_path)
    try:
        out: Dict[str, Any] = {
            "db_driver": "sqlite",
            "import_db_path": os.path.abspath(import_db_path),
            "strategy": {"merge_mode": merge_mode, "conflict_preference": conflict_preference},
            "tables": {},
        }

        for table_name, spec in _DB_MERGE_TABLE_SPECS.items():
            key_cols: List[str] = list(spec.get("key_cols") or [])
            exists = await _sqlite_table_exists(conn, alias, table_name)
            if not exists:
                out["tables"][table_name] = {
                    "exists": False,
                    "reason": "导入库缺少该表",
                    "total": 0,
                    "invalid": 0,
                    "new": 0,
                    "conflict": 0,
                    "plan": {"insert": 0, "update": 0, "skip": 0},
                }
                continue

            main_cols = set(await _sqlite_table_columns(conn, "main", table_name))
            import_cols = set(await _sqlite_table_columns(conn, alias, table_name))
            required_cols = set(key_cols)
            if not required_cols.issubset(main_cols) or not required_cols.issubset(import_cols):
                out["tables"][table_name] = {
                    "exists": True,
                    "reason": "主库/导入库字段不匹配（缺少签名键字段）",
                    "total": 0,
                    "invalid": 0,
                    "new": 0,
                    "conflict": 0,
                    "plan": {"insert": 0, "update": 0, "skip": 0},
                }
                continue

            invalid_cond = _build_invalid_key_condition(key_cols, table_alias="s")
            join_cond = _build_key_join_condition(key_cols, left_alias="s", right_alias="t")

            async with conn.execute(f"SELECT COUNT(*) AS c FROM {alias}.{table_name} s") as cur:
                total = int((await cur.fetchone() or [0])[0] or 0)

            async with conn.execute(
                f"SELECT COUNT(*) AS c FROM {alias}.{table_name} s WHERE {invalid_cond}"
            ) as cur:
                invalid = int((await cur.fetchone() or [0])[0] or 0)

            valid_cond = f"NOT {invalid_cond}"

            async with conn.execute(
                f"""
                SELECT COUNT(*) AS c
                FROM {alias}.{table_name} s
                WHERE {valid_cond}
                  AND NOT EXISTS (
                    SELECT 1 FROM main.{table_name} t WHERE {join_cond}
                  )
                """
            ) as cur:
                new_count = int((await cur.fetchone() or [0])[0] or 0)

            async with conn.execute(
                f"""
                SELECT COUNT(*) AS c
                FROM {alias}.{table_name} s
                WHERE {valid_cond}
                  AND EXISTS (
                    SELECT 1 FROM main.{table_name} t WHERE {join_cond}
                  )
                """
            ) as cur:
                conflict = int((await cur.fetchone() or [0])[0] or 0)

            if merge_mode == "skip_existing":
                plan = {"insert": new_count, "update": 0, "skip": conflict + invalid}
            else:
                plan = {"insert": new_count, "update": conflict, "skip": invalid}

            out["tables"][table_name] = {
                "exists": True,
                "total": total,
                "invalid": invalid,
                "new": new_count,
                "conflict": conflict,
                "plan": plan,
            }

        return out
    finally:
        try:
            await _sqlite_detach_database(conn, alias)
        except Exception:
            # 如果 detach 失败（例如仍处在事务中或连接状态异常），不阻断预览结果返回
            pass

async def sqlite_db_merge_execute(
    import_db_path: str,
    actor: str,
    merge_mode: MergeMode = "skip_existing",
    conflict_preference: ConflictPreference = "prefer_import",
    progress_cb: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> Dict[str, Any]:
    """
    执行合并导入（仅 SQLite，强事务）。

    progress_cb：
    - 用于后台任务实时汇报进度；
    - 回调参数为 dict（可直接序列化给前端）。
    """
    if not use_sqlite():
        raise RuntimeError("当前数据库不是 SQLite，无法执行 .db 合并导入")
    if not _sqlite:
        await init_sqlite()

    conn = _sqlite
    alias = "importdb"

    def emit(payload: Dict[str, Any]) -> None:
        if progress_cb:
            try:
                progress_cb(payload)
            except Exception:
                pass

    await _sqlite_attach_database(conn, alias, import_db_path)
    started_at = time.time()
    emit({"status": "running", "stage": "begin", "started_at": started_at})

    try:
        await conn.execute("BEGIN")
        results: Dict[str, Any] = {
            "db_driver": "sqlite",
            "import_db_path": os.path.abspath(import_db_path),
            "strategy": {"merge_mode": merge_mode, "conflict_preference": conflict_preference},
            "tables": {},
            "audit_log": {"written": False},
        }

        tables = list(_DB_MERGE_TABLE_SPECS.keys())
        total_tables = len(tables)
        done_tables = 0

        for table_name in tables:
            spec = _DB_MERGE_TABLE_SPECS[table_name]
            key_cols: List[str] = list(spec.get("key_cols") or [])
            text_cols: set[str] = set(spec.get("text_cols") or [])

            emit({"status": "running", "stage": "table_start", "table": table_name})

            exists = await _sqlite_table_exists(conn, alias, table_name)
            if not exists:
                results["tables"][table_name] = {"exists": False, "skipped": True, "reason": "导入库缺少该表"}
                done_tables += 1
                emit({"status": "running", "stage": "table_done", "table": table_name, "progress": done_tables / max(1, total_tables)})
                continue

            main_cols = set(await _sqlite_table_columns(conn, "main", table_name))
            import_cols = set(await _sqlite_table_columns(conn, alias, table_name))
            if not set(key_cols).issubset(main_cols) or not set(key_cols).issubset(import_cols):
                results["tables"][table_name] = {"exists": True, "skipped": True, "reason": "缺少签名键字段，无法合并"}
                done_tables += 1
                emit({"status": "running", "stage": "table_done", "table": table_name, "progress": done_tables / max(1, total_tables)})
                continue

            common_cols = main_cols.intersection(import_cols)

            insert_cols: List[str] = []
            for c in (spec.get("insert_cols") or []):
                if c in common_cols and c != "id":
                    insert_cols.append(c)

            update_cols: List[str] = []
            for c in (spec.get("update_cols") or []):
                if c in common_cols and c not in key_cols and c != "id":
                    update_cols.append(c)

            invalid_cond = _build_invalid_key_condition(key_cols, table_alias="s")
            valid_cond = f"NOT {invalid_cond}"
            join_cond = _build_key_join_condition(key_cols, left_alias="s", right_alias="t")

            inserted = 0
            updated = 0
            skipped_invalid = 0

            # 1) 统计无效行（签名键为空）：执行阶段直接计数并作为“跳过”
            async with conn.execute(
                f"SELECT COUNT(*) AS c FROM {alias}.{table_name} s WHERE {invalid_cond}"
            ) as cur:
                skipped_invalid = int((await cur.fetchone() or [0])[0] or 0)

            # 2) 插入新增
            if insert_cols:
                cols_sql = ", ".join(insert_cols)
                select_cols_sql = ", ".join([f"s.{c}" for c in insert_cols])
                await conn.execute(
                    f"""
                    INSERT INTO main.{table_name} ({cols_sql})
                    SELECT {select_cols_sql}
                    FROM {alias}.{table_name} s
                    WHERE {valid_cond}
                      AND NOT EXISTS (
                        SELECT 1 FROM main.{table_name} t WHERE {join_cond}
                      )
                    """
                )
                async with conn.execute("SELECT changes()") as cur:
                    inserted = int((await cur.fetchone() or [0])[0] or 0)
            else:
                inserted = 0

            emit({"status": "running", "stage": "table_insert_done", "table": table_name, "inserted": inserted})

            # 3) 更新冲突（可选）
            if merge_mode == "update_existing" and update_cols:
                # 3.1 构造 UPDATE SQL（使用命名参数，便于按列赋值）
                set_parts: List[str] = []
                for c in update_cols:
                    if conflict_preference == "prefer_current_non_empty":
                        if c in text_cols:
                            set_parts.append(
                                f"{c} = CASE WHEN :{c} IS NULL OR trim(CAST(:{c} AS TEXT)) = '' THEN {c} ELSE :{c} END"
                            )
                        else:
                            # 非文本字段：导入值为 NULL 时保留当前值，其它情况使用导入值
                            set_parts.append(f"{c} = COALESCE(:{c}, {c})")
                    else:
                        # prefer_import：无条件以导入值覆盖
                        set_parts.append(f"{c} = :{c}")
                set_sql = ", ".join(set_parts)

                where_parts = [f"{k} = :__k_{k}" for k in key_cols]
                where_sql = " AND ".join(where_parts)
                update_sql = f"UPDATE main.{table_name} SET {set_sql} WHERE {where_sql}"

                select_cols = key_cols + update_cols
                select_cols_sql = ", ".join([f"s.{c}" for c in select_cols])
                select_sql = f"""
                    SELECT {select_cols_sql}
                    FROM {alias}.{table_name} s
                    WHERE {valid_cond}
                      AND EXISTS (SELECT 1 FROM main.{table_name} t WHERE {join_cond})
                """

                async with conn.execute(select_sql) as cur:
                    while True:
                        rows = await cur.fetchmany(500)
                        if not rows:
                            break
                        params_list: List[Dict[str, Any]] = []
                        for r in rows:
                            # r 的列顺序与 select_cols 一致
                            p: Dict[str, Any] = {}
                            for idx, c in enumerate(select_cols):
                                p[c] = r[idx]
                            for k in key_cols:
                                p[f"__k_{k}"] = p.get(k)
                            params_list.append(p)
                        await conn.executemany(update_sql, params_list)
                        updated += len(params_list)

                emit({"status": "running", "stage": "table_update_done", "table": table_name, "updated": updated})

            results["tables"][table_name] = {
                "exists": True,
                "inserted": inserted,
                "updated": updated,
                "skipped_invalid": skipped_invalid,
            }

            done_tables += 1
            emit({"status": "running", "stage": "table_done", "table": table_name, "progress": done_tables / max(1, total_tables)})

        # 4) 写入审计日志（同一事务内）
        finished_at = time.time()
        details = json.dumps(
            {
                "feature": "sqlite_db_merge_import",
                "import_db_path": os.path.abspath(import_db_path),
                "strategy": results["strategy"],
                "results": results["tables"],
                "duration_sec": round(finished_at - started_at, 3),
            },
            ensure_ascii=False,
        )
        await conn.execute(
            "INSERT INTO audit_logs (actor, action, target, details) VALUES (?, ?, ?, ?)",
            (str(actor or ""), "db_merge_import", "sqlite", details),
        )
        results["audit_log"] = {"written": True}

        await conn.commit()
        results["finished_at"] = finished_at
        results["duration_sec"] = round(finished_at - started_at, 3)
        emit({"status": "done", "stage": "commit", "finished_at": finished_at, "duration_sec": results["duration_sec"]})
        return results
    except Exception as e:
        try:
            await conn.rollback()
        except Exception:
            pass
        emit({"status": "error", "stage": "rollback", "error": str(e)})
        raise
    finally:
        try:
            await _sqlite_detach_database(conn, alias)
        except Exception:
            pass



