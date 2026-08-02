import asyncio
import json
import os
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from api import main as api_main
from app import config, db, security
from app.storage import sqlite as sqlite_storage


class HealthEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def test_health_returns_503_when_database_ping_fails(self):
        with patch.object(
            api_main.db,
            "ping",
            AsyncMock(return_value={"ok": False, "error": "unavailable", "latency_ms": 1}),
        ):
            response = await api_main.health()

        self.assertEqual(response.status_code, 503)
        payload = json.loads(response.body)
        self.assertEqual(payload["status"], "degraded")
        self.assertFalse(payload["db"]["ok"])

    async def test_health_returns_200_when_database_ping_succeeds(self):
        with patch.object(
            api_main.db,
            "ping",
            AsyncMock(return_value={"ok": True, "latency_ms": 1}),
        ):
            response = await api_main.health()

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.body)
        self.assertEqual(payload["status"], "ok")
        self.assertTrue(payload["db"]["ok"])


class SqliteDeliveryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        asyncio.get_running_loop().slow_callback_duration = 1.0

    async def asyncTearDown(self):
        await db.close_pool()

    async def test_sqlite_connection_enables_delivery_pragmas(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = os.path.join(temp_dir, "delivery.db")
            connection = await sqlite_storage.connect(database_path)
            try:
                async with connection.execute("PRAGMA journal_mode") as cursor:
                    journal_mode = (await cursor.fetchone())[0]
                async with connection.execute("PRAGMA foreign_keys") as cursor:
                    foreign_keys = (await cursor.fetchone())[0]
                async with connection.execute("PRAGMA busy_timeout") as cursor:
                    busy_timeout = (await cursor.fetchone())[0]
            finally:
                await connection.close()

        self.assertEqual(journal_mode.lower(), "wal")
        self.assertEqual(foreign_keys, 1)
        self.assertGreaterEqual(busy_timeout, 5000)

    async def test_initial_admin_password_is_required_for_new_database(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = os.path.join(temp_dir, "delivery.db")
            with (
                patch.object(config, "DB_SQLITE_PATH", database_path),
                patch.object(config, "INITIAL_ADMIN_PASSWORD", "", create=True),
            ):
                with self.assertRaisesRegex(RuntimeError, "INITIAL_ADMIN_PASSWORD"):
                    await db.init_sqlite()

    async def test_initial_admin_password_is_used_once_and_not_overwritten(self):
        initial_password = "Strong-Initial-Password-2026"
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = os.path.join(temp_dir, "delivery.db")
            with (
                patch.object(config, "DB_SQLITE_PATH", database_path),
                patch.object(config, "INITIAL_ADMIN_PASSWORD", initial_password, create=True),
            ):
                await db.init_sqlite()
                async with db._sqlite.execute(
                    "SELECT password_hash FROM users WHERE username='admin'"
                ) as cursor:
                    stored_hash = (await cursor.fetchone())[0]
                await db.close_pool()

            self.assertTrue(security.verify_password(initial_password, stored_hash))

            with (
                patch.object(config, "DB_SQLITE_PATH", database_path),
                patch.object(config, "INITIAL_ADMIN_PASSWORD", "", create=True),
            ):
                await db.init_sqlite()
                admin = await db.authenticate_user("admin", initial_password)
                await db.close_pool()

        self.assertIsNotNone(admin)


class MysqlPoolInitializationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await db.close_pool()

    async def asyncTearDown(self):
        await db.close_pool()

    def _make_mysql_pool(self):
        pool = MagicMock()
        pool.close = MagicMock()
        pool.wait_closed = AsyncMock()
        connection = MagicMock()
        cursor = MagicMock()
        pool.acquire.return_value.__aenter__ = AsyncMock(return_value=connection)
        pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
        connection.cursor.return_value.__aenter__ = AsyncMock(return_value=cursor)
        connection.cursor.return_value.__aexit__ = AsyncMock(return_value=None)
        cursor.execute = AsyncMock()
        cursor.fetchone = AsyncMock(side_effect=[("created_at",), None])
        return pool, cursor

    async def test_mysql_missing_initial_admin_password_closes_pool_and_propagates(self):
        pool, _ = self._make_mysql_pool()

        with (
            patch.object(config, "DB_DRIVER", "mysql"),
            patch.object(config, "INITIAL_ADMIN_PASSWORD", "", create=True),
            patch.object(db.aiomysql, "create_pool", AsyncMock(return_value=pool)),
        ):
            with self.assertLogs(level="ERROR") as logs:
                with self.assertRaisesRegex(RuntimeError, "INITIAL_ADMIN_PASSWORD"):
                    await db.init_pool()

        pool.close.assert_called_once_with()
        pool.wait_closed.assert_awaited_once_with()
        self.assertIsNone(db._pool)
        self.assertTrue(any("RuntimeError" in message for message in logs.output))

    async def test_mysql_schema_failure_closes_pool_and_propagates(self):
        pool, cursor = self._make_mysql_pool()
        cursor.execute = AsyncMock(side_effect=ValueError("schema failure"))

        with (
            patch.object(config, "DB_DRIVER", "mysql"),
            patch.object(config, "INITIAL_ADMIN_PASSWORD", "unused", create=True),
            patch.object(db.aiomysql, "create_pool", AsyncMock(return_value=pool)),
        ):
            with self.assertLogs(level="ERROR") as logs:
                with self.assertRaisesRegex(ValueError, "schema failure"):
                    await db.init_pool()

        pool.close.assert_called_once_with()
        pool.wait_closed.assert_awaited_once_with()
        self.assertIsNone(db._pool)
        self.assertTrue(any("ValueError" in message for message in logs.output))

    async def test_mysql_existing_admin_is_not_inserted_or_overwritten(self):
        pool, cursor = self._make_mysql_pool()
        cursor.fetchone = AsyncMock(side_effect=[("created_at",), (1,)])

        with (
            patch.object(config, "DB_DRIVER", "mysql"),
            patch.object(config, "INITIAL_ADMIN_PASSWORD", "replacement-password", create=True),
            patch.object(db, "hash_password") as hash_password,
            patch.object(db.aiomysql, "create_pool", AsyncMock(return_value=pool)),
        ):
            await db.init_pool()

        statements = [call.args[0] for call in cursor.execute.await_args_list]
        self.assertFalse(any("INSERT IGNORE INTO users" in statement for statement in statements))
        hash_password.assert_not_called()


if __name__ == "__main__":
    unittest.main()
