import unittest

from app import security


class PasswordHashingTests(unittest.TestCase):
    def test_pbkdf2_hash_verifies_and_uses_versioned_format(self):
        encoded = security.hash_password("admin")

        self.assertTrue(encoded.startswith("pbkdf2_sha256$"))
        self.assertTrue(security.verify_password("admin", encoded))
        self.assertFalse(security.verify_password("wrong", encoded))
        self.assertFalse(security.needs_password_rehash(encoded))

    def test_legacy_sha256_hash_still_verifies_and_requires_rehash(self):
        legacy = security.hash_password_legacy("admin")

        self.assertTrue(security.verify_password("admin", legacy))
        self.assertFalse(security.verify_password("wrong", legacy))
        self.assertTrue(security.needs_password_rehash(legacy))


if __name__ == "__main__":
    unittest.main()
