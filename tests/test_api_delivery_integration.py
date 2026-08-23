import os
import tempfile
import unittest
from unittest.mock import patch

try:
    import httpx
except ImportError:  # pragma: no cover - local minimal venv
    httpx = None

from api import main as api_main
from app import config, db


@unittest.skipIf(httpx is None, "httpx is not installed in the active environment")
class ApiDeliveryIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncTearDown(self):
        await db.close_pool()

    async def test_login_csrf_and_admin_write_flow(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = os.path.join(temp_dir, "api.db")
            with (
                patch.object(config, "DB_DRIVER", "sqlite"),
                patch.object(config, "DB_SQLITE_PATH", database_path),
                patch.object(config, "INITIAL_ADMIN_PASSWORD", "initial-password"),
                patch.object(config, "AUTO_SYNC_WALKIN_ENABLE", False),
                patch.object(config, "ALERT_EMAIL_ENABLE", False),
            ):
                await api_main.startup_event()
                transport = httpx.ASGITransport(app=api_main.app)
                async with httpx.AsyncClient(
                    transport=transport,
                    base_url="http://testserver",
                ) as client:
                    login = await client.post(
                        "/api/v1/auth/login",
                        json={"username": "admin", "password": "initial-password"},
                    )
                    self.assertEqual(login.status_code, 200)

                    missing = await client.post(
                        "/api/v1/users",
                        json={"username": "user-a", "password": "password", "role": "user"},
                    )
                    self.assertEqual(missing.status_code, 403)

                    csrf = await client.get("/api/v1/auth/csrf")
                    self.assertEqual(csrf.status_code, 200)
                    token = csrf.json()["csrf_token"]
                    created = await client.post(
                        "/api/v1/users",
                        headers={"X-CSRF-Token": token},
                        json={"username": "user-a", "password": "password", "role": "user"},
                    )
                    self.assertEqual(created.status_code, 200)
                await api_main.shutdown_event()


if __name__ == "__main__":
    unittest.main()
