import unittest

from tools.freeze_api_contract import _infer_auth


class ContractAuthInferenceTests(unittest.TestCase):
    def test_infers_public_session_and_admin_auth_levels(self):
        self.assertEqual(_infer_auth("/api/v1/health", ["GET"]), "public")
        self.assertEqual(_infer_auth("/api/v1/auth/logout", ["POST"]), "optional_session")
        self.assertEqual(_infer_auth("/api/v1/auth/me", ["GET"]), "session")
        self.assertEqual(_infer_auth("/api/v1/stats/summary", ["GET"]), "session")
        self.assertEqual(_infer_auth("/api/v1/admin/records", ["GET"]), "admin")
        self.assertEqual(_infer_auth("/api/v1/admin/db-merge/execute", ["POST"]), "admin")
        self.assertEqual(_infer_auth("/api/v1/activity/import-excel", ["POST"]), "admin")
        self.assertEqual(_infer_auth("/api/v1/locations/batch-correct", ["POST"]), "admin")


if __name__ == "__main__":
    unittest.main()
