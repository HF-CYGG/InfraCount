import asyncio
import os
import sqlite3
import sys
from typing import Any

_ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)

from app import db


def _create_import_db(path: str) -> None:
    """
    创建一个最小可用的“导入库”，用于验证 .db 合并导入能力。

    设计说明：
    - 该脚本只用于开发/回归验证，不参与业务运行；
    - 生成的库包含 records/registry/location_academy/academies/alerts/activity_events 的最小字段集；
    - 合并逻辑会按“公共字段交集”处理，因此这里字段可以不完全一致，但签名键字段必须存在。
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        os.remove(path)

    conn = sqlite3.connect(path)
    try:
        conn.execute(
            """
            CREATE TABLE records (
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
                created_at DATETIME
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE registry (
                uuid TEXT PRIMARY KEY,
                name TEXT,
                category TEXT,
                description TEXT,
                last_seen DATETIME,
                ip TEXT,
                bound_at DATETIME
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE location_academy (
                location_name TEXT PRIMARY KEY,
                academy_name TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE academies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                sort_order INTEGER DEFAULT 0
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uuid TEXT,
                type TEXT,
                level INTEGER,
                status INTEGER,
                info TEXT,
                time DATETIME,
                notified INTEGER,
                notified_at DATETIME,
                notify_error TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE activity_events (
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
                create_time DATETIME
            )
            """
        )

        conn.execute(
            """
            INSERT INTO records(uuid,time,in_count,out_count,battery,btx,rec_type,signal_strength,warn_status,activity_type,created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
            """,
            ("MERGE-E2E", "2026-01-02 03:04:05", 9, 2, 80, 33, 1, 1, 0, "e2e"),
        )
        conn.execute(
            "INSERT INTO registry(uuid,name,category,description,last_seen,ip,bound_at) VALUES (?,?,?,?,CURRENT_TIMESTAMP,?,CURRENT_TIMESTAMP)",
            ("MERGE-E2E", "E2E场地", "E2E书院", "用于合并测试", "127.0.0.1"),
        )
        conn.execute("INSERT INTO academies(name,sort_order) VALUES (?,?)", ("E2E书院", 1))
        conn.execute("INSERT INTO location_academy(location_name,academy_name) VALUES (?,?)", ("E2E场地", "E2E书院"))
        conn.execute(
            "INSERT INTO alerts(uuid,type,level,status,info,time,notified) VALUES (?,?,?,?,?,?,?)",
            ("MERGE-E2E", "low_battery", 2, 0, "E2E告警", "2026-01-02 03:04:05", 0),
        )
        conn.execute(
            """
            INSERT INTO activity_events(date,weekday,start_time,end_time,duration_minutes,academy,location,activity_name,activity_type,audience_count,notes,create_time)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
            """,
            ("2026-01-02", "周五", "03:00", "03:30", 30, "E2E书院", "E2E场地", "E2E活动", "测试", 9, "e2e"),
        )
        conn.commit()
    finally:
        conn.close()


async def _run() -> int:
    import_db_path = os.path.join("data", "import_e2e.db")
    _create_import_db(import_db_path)

    await db.init_sqlite()

    preview: dict[str, Any] = await db.sqlite_db_merge_preview(
        import_db_path=import_db_path,
        merge_mode="skip_existing",
        conflict_preference="prefer_current_non_empty",
    )
    print("=== PREVIEW ===")
    print(preview.get("tables", {}).get("records"))

    result: dict[str, Any] = await db.sqlite_db_merge_execute(
        import_db_path=import_db_path,
        actor="e2e",
        merge_mode="skip_existing",
        conflict_preference="prefer_current_non_empty",
    )
    print("=== EXECUTE ===")
    print(result.get("tables", {}).get("records"))

    # 最小验证：确认记录存在（uuid+time 自然键）
    conn = db._sqlite  # type: ignore[attr-defined]
    async with conn.execute(
        "SELECT COUNT(*) FROM records WHERE uuid=? AND time=?",
        ("MERGE-E2E", "2026-01-02 03:04:05"),
    ) as cur:
        row = await cur.fetchone()
    count = int((row or [0])[0] or 0)
    print("=== VERIFY ===")
    print({"records_count": count})
    # 关闭 SQLite 连接，避免 aiosqlite 后台线程导致脚本“看似结束但进程不退出”
    try:
        await db.close_pool()
    except Exception:
        pass
    return 0 if count >= 1 else 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_run()))

