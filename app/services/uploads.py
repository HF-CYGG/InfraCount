from __future__ import annotations

import os
from typing import Any


class UploadTooLargeError(ValueError):
    def __init__(self, max_bytes: int):
        self.max_bytes = int(max_bytes)
        super().__init__(f"upload exceeds {self.max_bytes} bytes")


async def read_upload_limited(
    upload: Any,
    *,
    max_bytes: int,
    chunk_size: int = 1024 * 1024,
) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await upload.read(chunk_size)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise UploadTooLargeError(max_bytes)
        chunks.append(chunk)
    return b"".join(chunks)


async def save_upload_limited(
    upload: Any,
    target_path: str,
    *,
    max_bytes: int,
    chunk_size: int = 1024 * 1024,
) -> int:
    total = 0
    try:
        with open(target_path, "wb") as output:
            while True:
                chunk = await upload.read(chunk_size)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise UploadTooLargeError(max_bytes)
                output.write(chunk)
        return total
    except Exception:
        try:
            if os.path.isfile(target_path):
                os.remove(target_path)
        except OSError:
            pass
        raise
