import io
import os
import tempfile
import unittest

from starlette.datastructures import UploadFile

from app.services import uploads


class UploadLimitTests(unittest.IsolatedAsyncioTestCase):
    async def test_read_rejects_content_over_limit(self):
        upload = UploadFile(filename="data.csv", file=io.BytesIO(b"123456"))

        with self.assertRaises(uploads.UploadTooLargeError) as error:
            await uploads.read_upload_limited(upload, max_bytes=5, chunk_size=2)

        self.assertEqual(error.exception.max_bytes, 5)

    async def test_save_removes_partial_file_when_limit_is_exceeded(self):
        upload = UploadFile(filename="import.db", file=io.BytesIO(b"123456"))
        with tempfile.TemporaryDirectory() as temp_dir:
            target = os.path.join(temp_dir, "import.db")

            with self.assertRaises(uploads.UploadTooLargeError):
                await uploads.save_upload_limited(
                    upload,
                    target,
                    max_bytes=5,
                    chunk_size=2,
                )

            self.assertFalse(os.path.exists(target))


if __name__ == "__main__":
    unittest.main()
