import unittest

from api.dependencies import classify_api_auth


class ApiAuthPolicyTests(unittest.TestCase):
    def test_public_auth_paths_are_explicit(self):
        self.assertEqual(classify_api_auth("/api/v1/health", "GET"), "public")
        self.assertEqual(classify_api_auth("/api/v1/auth/login", "POST"), "public")
        self.assertEqual(classify_api_auth("/api/v1/auth/logout", "POST"), "optional_session")
        self.assertEqual(classify_api_auth("/api/v1/stats/summary", "OPTIONS"), "public")

    def test_business_reads_require_session(self):
        self.assertEqual(classify_api_auth("/api/v1/stats/summary", "GET"), "session")
        self.assertEqual(classify_api_auth("/api/v1/devices", "GET"), "session")
        self.assertEqual(classify_api_auth("/api/v1/activity/events", "GET"), "session")

    def test_admin_and_write_paths_require_admin(self):
        self.assertEqual(classify_api_auth("/api/v1/admin/records", "GET"), "admin")
        self.assertEqual(classify_api_auth("/api/v1/admin/db-merge/upload", "POST"), "admin")
        self.assertEqual(classify_api_auth("/api/v1/users", "GET"), "admin")
        self.assertEqual(classify_api_auth("/api/v1/system/status", "GET"), "admin")
        self.assertEqual(classify_api_auth("/api/v1/activity/upload", "POST"), "admin")
        self.assertEqual(classify_api_auth("/api/v1/locations/correct", "POST"), "admin")
        self.assertEqual(classify_api_auth("/api/v1/alerts/1/ack", "POST"), "admin")


if __name__ == "__main__":
    unittest.main()
