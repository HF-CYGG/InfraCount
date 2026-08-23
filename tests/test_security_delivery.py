import datetime as dt
import os
import tempfile
import unittest
from unittest.mock import patch

from app import config, db, security


class CsrfTokenTests(unittest.TestCase):
    def test_token_is_bound_to_session_and_expires(self):
        token = security.issue_csrf("session-a", now=1_000)

        self.assertTrue(security.validate_csrf(token, "session-a", now=1_001))
        self.assertFalse(security.validate_csrf(token, "session-b", now=1_001))
        self.assertFalse(
            security.validate_csrf(
                token,
                "session-a",
                now=1_000 + config.CSRF_TTL + 1,
            )
        )

    def test_token_rejects_future_timestamp(self):
        token = security.issue_csrf("session-a", now=2_000)

        self.assertFalse(security.validate_csrf(token, "session-a", now=1_900))


class SessionExpiryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncTearDown(self):
        await db.close_pool()

    async def test_database_expiry_uses_configured_cookie_lifetime(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = os.path.join(temp_dir, "session.db")
            with (
                patch.object(config, "DB_DRIVER", "sqlite"),
                patch.object(config, "DB_SQLITE_PATH", database_path),
                patch.object(config, "INITIAL_ADMIN_PASSWORD", "initial-password"),
                patch.object(config, "SESSION_MAX_AGE_SEC", 120),
            ):
                await db.init_sqlite()
                async with db._sqlite.execute(
                    "SELECT id FROM users WHERE username='admin'"
                ) as cursor:
                    user_id = (await cursor.fetchone())[0]

                before = dt.datetime.utcnow()
                token = await db.create_session(user_id)
                async with db._sqlite.execute(
                    "SELECT expires_at FROM sessions WHERE token=?",
                    (token,),
                ) as cursor:
                    expires_at = (await cursor.fetchone())[0]
                await db.close_pool()

        if isinstance(expires_at, str):
            expires_at = dt.datetime.fromisoformat(expires_at)
        lifetime = (expires_at - before).total_seconds()
        self.assertGreaterEqual(lifetime, 115)
        self.assertLessEqual(lifetime, 125)


if __name__ == "__main__":
    unittest.main()
