from __future__ import annotations

from typing import Any

from app import config


def _read_int(data: dict[str, Any], *keys: str) -> tuple[bool, int | None]:
    for key in keys:
        if key not in data:
            continue
        value = data.get(key)
        if value is None or (isinstance(value, str) and not value.strip()):
            return False, None
        try:
            return True, int(value)
        except (TypeError, ValueError):
            return False, None
    return False, None


def evaluate_device_alerts(data: dict[str, Any]) -> list[dict[str, Any]]:
    evaluations: list[dict[str, Any]] = []

    def append_threshold(alert_type: str, level: int, threshold: int, *keys: str) -> None:
        present, value = _read_int(data, *keys)
        if not present or value is None:
            return
        evaluations.append(
            {
                "type": alert_type,
                "level": level,
                "active": value < threshold,
                "value": value,
                "info": f"value={value}, threshold<{threshold}",
            }
        )

    def append_equal(alert_type: str, level: int, abnormal_value: int, *keys: str) -> None:
        present, value = _read_int(data, *keys)
        if not present or value is None:
            return
        evaluations.append(
            {
                "type": alert_type,
                "level": level,
                "active": value == abnormal_value,
                "value": value,
                "info": f"value={value}, abnormal={abnormal_value}",
            }
        )

    append_threshold("battery_low", 2, config.BAT_LOW, "battery", "battery_level", "power")
    append_threshold(
        "btx_low",
        2,
        config.BTX_LOW,
        "btx",
        "batterytx_level",
        "battery_tx",
        "btx_level",
    )
    append_equal(
        "signal_offline",
        3,
        config.SIGNAL_OFFLINE_VALUE,
        "signal_strength",
        "signal_status",
        "signal",
    )
    append_equal("backlog", 2, config.REC_TYPE_BACKLOG, "rec_type", "rectype")

    present, warn_status = _read_int(data, "warn_status", "warn", "warning")
    if present and warn_status is not None:
        evaluations.append(
            {
                "type": "warn_status",
                "level": 3,
                "active": warn_status > 0,
                "value": warn_status,
                "info": f"value={warn_status}, abnormal=>0",
            }
        )

    return evaluations


async def apply_sqlite_alert_states(
    conn: Any,
    uuid: str,
    recorded_at: str,
    evaluations: list[dict[str, Any]],
) -> None:
    for evaluation in evaluations:
        alert_type = str(evaluation["type"])
        async with conn.execute(
            "SELECT active, alert_id FROM alert_states WHERE uuid=? AND type=?",
            (uuid, alert_type),
        ) as cursor:
            state = await cursor.fetchone()

        was_active = bool(state and state["active"])
        alert_id = int(state["alert_id"]) if state and state["alert_id"] else None
        is_active = bool(evaluation["active"])
        value = str(evaluation.get("value", ""))

        if is_active and not was_active:
            cursor = await conn.execute(
                "INSERT INTO alerts(uuid,type,level,status,info,time,notified) "
                "VALUES (?,?,?,?,?,?,0)",
                (
                    uuid,
                    alert_type,
                    int(evaluation["level"]),
                    0,
                    str(evaluation["info"]),
                    recorded_at,
                ),
            )
            alert_id = int(cursor.lastrowid)
        elif not is_active and was_active and alert_id is not None:
            await conn.execute(
                "UPDATE alerts SET resolved_at=? WHERE id=? AND resolved_at IS NULL",
                (recorded_at, alert_id),
            )

        if state or is_active:
            await conn.execute(
                "INSERT INTO alert_states(uuid,type,active,alert_id,last_value,updated_at) "
                "VALUES (?,?,?,?,?,?) "
                "ON CONFLICT(uuid,type) DO UPDATE SET "
                "active=excluded.active, alert_id=excluded.alert_id, "
                "last_value=excluded.last_value, updated_at=excluded.updated_at",
                (uuid, alert_type, int(is_active), alert_id, value, recorded_at),
            )


async def apply_mysql_alert_states(
    cursor: Any,
    uuid: str,
    recorded_at: str,
    evaluations: list[dict[str, Any]],
) -> None:
    for evaluation in evaluations:
        alert_type = str(evaluation["type"])
        await cursor.execute(
            "SELECT active, alert_id FROM alert_states WHERE uuid=%s AND type=%s FOR UPDATE",
            (uuid, alert_type),
        )
        state = await cursor.fetchone()
        was_active = bool(state and state[0])
        alert_id = int(state[1]) if state and state[1] else None
        is_active = bool(evaluation["active"])

        if is_active and not was_active:
            await cursor.execute(
                "INSERT INTO alerts(uuid,type,level,status,info,time,notified) "
                "VALUES (%s,%s,%s,%s,%s,%s,0)",
                (
                    uuid,
                    alert_type,
                    int(evaluation["level"]),
                    0,
                    str(evaluation["info"]),
                    recorded_at,
                ),
            )
            alert_id = int(cursor.lastrowid)
        elif not is_active and was_active and alert_id is not None:
            await cursor.execute(
                "UPDATE alerts SET resolved_at=%s WHERE id=%s AND resolved_at IS NULL",
                (recorded_at, alert_id),
            )

        if state or is_active:
            await cursor.execute(
                "INSERT INTO alert_states(uuid,type,active,alert_id,last_value,updated_at) "
                "VALUES (%s,%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE "
                "active=VALUES(active), alert_id=VALUES(alert_id), "
                "last_value=VALUES(last_value), updated_at=VALUES(updated_at)",
                (
                    uuid,
                    alert_type,
                    int(is_active),
                    alert_id,
                    str(evaluation.get("value", "")),
                    recorded_at,
                ),
            )
