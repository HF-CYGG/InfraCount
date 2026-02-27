import argparse
import json
import os
import sqlite3


def main() -> int:
    """
    records 查询小工具（最小验证用）。

    设计目的：
    - 用于本地/测试环境快速验证“设备上报 -> records 入库”是否成功；
    - 不依赖 FastAPI/uvicorn，仅直接读取 SQLite 数据库文件（data/infrared.db）；
    - 支持按 uuid 过滤，并查看最新 N 条记录。

    使用示例：
    - 查询最新 5 条（不筛选 uuid）：
        python tools/query_records.py --limit 5
    - 查询指定设备最新 1 条：
        python tools/query_records.py --uuid SIM-ABC --limit 1
    """
    parser = argparse.ArgumentParser(description="InfraCount records 表查询工具（SQLite）")
    parser.add_argument(
        "--db",
        default=os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "infrared.db"),
        help="SQLite 数据库文件路径（默认 data/infrared.db）",
    )
    parser.add_argument("--uuid", default="", help="按设备 UUID 过滤（默认不筛选）")
    parser.add_argument("--limit", default=1, type=int, help="返回最新 N 条（默认 1）")
    args = parser.parse_args()

    db_path = os.path.abspath(args.db)
    if not os.path.exists(db_path):
        print(f"数据库文件不存在：{db_path}")
        return 2

    # 1) 连接 SQLite（只读场景也允许写锁被占用时读取，避免验证时因锁冲突失败）
    conn = sqlite3.connect(db_path, timeout=3)
    try:
        conn.row_factory = sqlite3.Row

        # 2) 构造查询：按 id 倒序取最新 N 条
        uuid = (args.uuid or "").strip()
        limit = max(1, int(args.limit or 1))

        if uuid:
            sql = """
            SELECT id, uuid, time, in_count, out_count, battery, btx, rec_type, signal_strength, warn_status, activity_type, created_at
            FROM records
            WHERE uuid = ?
            ORDER BY id DESC
            LIMIT ?
            """
            rows = conn.execute(sql, (uuid, limit)).fetchall()
        else:
            sql = """
            SELECT id, uuid, time, in_count, out_count, battery, btx, rec_type, signal_strength, warn_status, activity_type, created_at
            FROM records
            ORDER BY id DESC
            LIMIT ?
            """
            rows = conn.execute(sql, (limit,)).fetchall()

        # 3) 输出：JSON 数组，便于复制/对比/脚本化处理
        print(json.dumps([dict(r) for r in rows], ensure_ascii=False, indent=2))
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())

