import os
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from api import dependencies
from app import config, db
from app.services import db_merge
from tests.test_csrf_policy import make_request


class DatabaseMaintenanceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncTearDown(self):
        await db.close_pool()
        db_merge.release_process_lock()

    async def test_maintenance_is_persisted_and_blocks_device_writes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = os.path.join(temp_dir, "maintenance.db")
            with (
                patch.object(config, "DB_DRIVER", "sqlite"),
                patch.object(config, "DB_SQLITE_PATH", database_path),
                patch.object(config, "INITIAL_ADMIN_PASSWORD", "initial-password"),
            ):
                await db.init_sqlite()
                owner = await db_merge.start_maintenance("admin")
                try:
                    self.assertTrue(await db_merge.is_maintenance_active())
                    with self.assertRaises(db_merge.DatabaseMaintenanceError):
                        await db.save_device_data({"uuid": "dev-1", "in": 1})
                    with self.assertRaises(db_merge.MergeAlreadyRunningError):
                        await db_merge.start_maintenance("other-admin")
                finally:
                    await db_merge.finish_maintenance(owner)

                self.assertFalse(await db_merge.is_maintenance_active())
                await db.close_pool()

    async def test_http_writes_return_423_during_maintenance(self):
        request = make_request("POST", "/api/v1/users", session_token="session-a")
        with patch.object(
            dependencies.db_merge_service,
            "is_maintenance_active",
            AsyncMock(return_value=True),
        ):
            with self.assertRaises(HTTPException) as error:
                await dependencies.enforce_api_maintenance(request)

        self.assertEqual(error.exception.status_code, 423)
        self.assertEqual(error.exception.headers.get("Retry-After"), "5")


if __name__ == "__main__":
    unittest.main()
