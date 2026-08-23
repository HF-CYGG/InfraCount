import unittest
from unittest.mock import patch

from fastapi import HTTPException, Request

from api import dependencies
from app import config, security


def make_request(
    method: str,
    path: str,
    *,
    session_token: str | None = None,
    csrf_token: str | None = None,
    origin: str | None = None,
) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if session_token:
        headers.append(
            (
                b"cookie",
                f"{config.SESSION_COOKIE_NAME}={session_token}".encode("ascii"),
            )
        )
    if csrf_token:
        headers.append((b"x-csrf-token", csrf_token.encode("ascii")))
    if origin:
        headers.append((b"origin", origin.encode("ascii")))
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": method,
            "scheme": "http",
            "path": path,
            "raw_path": path.encode("ascii"),
            "query_string": b"",
            "headers": headers,
            "client": ("127.0.0.1", 12345),
            "server": ("127.0.0.1", 8000),
        }
    )


class CsrfPolicyTests(unittest.IsolatedAsyncioTestCase):
    async def test_safe_request_does_not_require_token(self):
        request = make_request("GET", "/api/v1/stats/summary", session_token="s")
        await dependencies.enforce_api_csrf(request)

    async def test_authenticated_write_requires_valid_token(self):
        missing = make_request("POST", "/api/v1/users", session_token="session-a")
        with self.assertRaises(HTTPException) as missing_error:
            await dependencies.enforce_api_csrf(missing)
        self.assertEqual(missing_error.exception.status_code, 403)

        forged = make_request(
            "POST",
            "/api/v1/users",
            session_token="session-b",
            csrf_token=security.issue_csrf("session-a"),
        )
        with self.assertRaises(HTTPException) as forged_error:
            await dependencies.enforce_api_csrf(forged)
        self.assertEqual(forged_error.exception.status_code, 403)

        valid = make_request(
            "POST",
            "/api/v1/users",
            session_token="session-a",
            csrf_token=security.issue_csrf("session-a"),
        )
        await dependencies.enforce_api_csrf(valid)

    async def test_login_rejects_untrusted_browser_origin_but_allows_cli(self):
        with patch.object(config, "CORS_ALLOW_ORIGINS", ["http://trusted.test"]):
            cli_request = make_request("POST", "/api/v1/auth/login")
            await dependencies.enforce_api_csrf(cli_request)

            browser_request = make_request(
                "POST",
                "/api/v1/auth/login",
                origin="http://evil.test",
            )
            with self.assertRaises(HTTPException) as error:
                await dependencies.enforce_api_csrf(browser_request)
            self.assertEqual(error.exception.status_code, 403)

    async def test_logout_without_valid_session_remains_idempotent(self):
        request = make_request(
            "POST",
            "/api/v1/auth/logout",
            session_token="expired-session",
        )

        await dependencies.enforce_api_csrf(request)

    def test_csrf_bootstrap_route_requires_session(self):
        self.assertEqual(
            dependencies.classify_api_auth("/api/v1/auth/csrf", "GET"),
            "session",
        )


if __name__ == "__main__":
    unittest.main()
