import os
import tempfile
import unittest
from unittest.mock import patch

from app import config, db
from app.services import alerting


class AlertRuleTests(unittest.TestCase):
    def test_all_configured_signals_have_explicit_levels(self):
        with (
            patch.object(config, "BAT_LOW", 20),
            patch.object(config, "BTX_LOW", 30),
            patch.object(config, "SIGNAL_OFFLINE_VALUE", 1),
            patch.object(config, "REC_TYPE_BACKLOG", 1),
        ):
            states = {
                item["type"]: item
                for item in alerting.evaluate_device_alerts(
                    {
                        "battery_level": 19,
                        "batterytx_level": 29,
                        "signal_status": 1,
                        "rec_type": 1,
                        "warn_status": 2,
                    }
                )
            }

        self.assertEqual(states["battery_low"]["level"], 2)
        self.assertEqual(states["btx_low"]["level"], 2)
        self.assertEqual(states["backlog"]["level"], 2)
        self.assertEqual(states["signal_offline"]["level"], 3)
        self.assertEqual(states["warn_status"]["level"], 3)
        self.assertTrue(all(item["active"] for item in states.values()))

    def test_missing_values_do_not_open_or_resolve_alerts(self):
        self.assertEqual(alerting.evaluate_device_alerts({"in": 1, "out": 2}), [])


class AlertPersistenceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncTearDown(self):
        await db.close_pool()

    async def test_alert_state_transitions_are_deduplicated(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = os.path.join(temp_dir, "alerts.db")
            with (
                patch.object(config, "DB_DRIVER", "sqlite"),
                patch.object(config, "DB_SQLITE_PATH", database_path),
                patch.object(config, "INITIAL_ADMIN_PASSWORD", "initial-password"),
                patch.object(config, "BAT_LOW", 20),
            ):
                await db.init_sqlite()

                await db.save_device_data(
                    {"uuid": "dev-1", "battery_level": 10, "time": "2026-01-01 00:00:00"}
                )
                await db.save_device_data(
                    {"uuid": "dev-1", "battery_level": 9, "time": "2026-01-01 00:01:00"}
                )
                await db.save_device_data(
                    {"uuid": "dev-1", "in": 1, "time": "2026-01-01 00:02:00"}
                )

                alerts = await db.list_alerts("dev-1", 100)
                self.assertEqual(len(alerts), 1)
                self.assertIsNone(alerts[0].get("resolved_at"))

                await db.save_device_data(
                    {"uuid": "dev-1", "battery_level": 20, "time": "2026-01-01 00:03:00"}
                )
                recovered = await db.list_alerts("dev-1", 100)
                self.assertIsNotNone(recovered[0].get("resolved_at"))

                await db.save_device_data(
                    {"uuid": "dev-1", "battery_level": 5, "time": "2026-01-01 00:04:00"}
                )
                reopened = await db.list_alerts("dev-1", 100)
                self.assertEqual(len(reopened), 2)
                self.assertIsNone(reopened[0].get("resolved_at"))
                await db.close_pool()

    async def test_failed_email_remains_pending_with_backoff(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = os.path.join(temp_dir, "email-retry.db")
            with (
                patch.object(config, "DB_DRIVER", "sqlite"),
                patch.object(config, "DB_SQLITE_PATH", database_path),
                patch.object(config, "INITIAL_ADMIN_PASSWORD", "initial-password"),
            ):
                await db.init_sqlite()
                cursor = await db._sqlite.execute(
                    "INSERT INTO alerts(uuid,type,level,status,info,notified) "
                    "VALUES ('dev-1','signal_offline',3,0,'offline',0)"
                )
                alert_id = int(cursor.lastrowid)
                await db._sqlite.commit()
                try:
                    await db.mark_alert_notification_failed(alert_id, "smtp unavailable")
                    pending = await db.list_unnotified_critical_alerts(limit=10)
                    async with db._sqlite.execute(
                        "SELECT notified,notified_at,notify_attempts,next_notify_at "
                        "FROM alerts WHERE id=?",
                        (alert_id,),
                    ) as retry_cursor:
                        retry_state = await retry_cursor.fetchone()

                    self.assertEqual([item["id"] for item in pending], [])
                    self.assertEqual(retry_state["notified"], 0)
                    self.assertIsNone(retry_state["notified_at"])
                    self.assertEqual(retry_state["notify_attempts"], 1)
                    self.assertIsNotNone(retry_state["next_notify_at"])
                finally:
                    await db.close_pool()


if __name__ == "__main__":
    unittest.main()
