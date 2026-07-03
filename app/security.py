import base64
import hashlib
import hmac
import secrets
import time

from app import config

PBKDF2_ALGORITHM = "pbkdf2_sha256"
PBKDF2_ITERATIONS = 260000
LEGACY_PASSWORD_SALT = "infrared_salt_v1"

_tokens: dict[str, float] = {}

def issue_csrf() -> str:
    t = secrets.token_urlsafe(32)
    _tokens[t] = time.time() + config.CSRF_TTL
    return t

def validate_csrf(token: str) -> bool:
    if not config.CSRF_ENABLE:
        return True
    exp = _tokens.get(token)
    if not exp:
        return False
    if exp < time.time():
        _tokens.pop(token, None)
        return False
    # one-time token
    _tokens.pop(token, None)
    return True


def hash_password_legacy(password: str) -> str:
    return hashlib.sha256((str(password or "") + LEGACY_PASSWORD_SALT).encode("utf-8")).hexdigest()


def hash_password(password: str, *, iterations: int = PBKDF2_ITERATIONS) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        str(password or "").encode("utf-8"),
        salt,
        iterations,
    )
    salt_b64 = base64.urlsafe_b64encode(salt).decode("ascii").rstrip("=")
    digest_b64 = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return f"{PBKDF2_ALGORITHM}${iterations}${salt_b64}${digest_b64}"


def _decode_urlsafe_b64(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))


def verify_password(password: str, encoded: str | None) -> bool:
    stored = str(encoded or "")
    if stored.startswith(f"{PBKDF2_ALGORITHM}$"):
        try:
            _algorithm, iterations_raw, salt_raw, digest_raw = stored.split("$", 3)
            iterations = int(iterations_raw)
            salt = _decode_urlsafe_b64(salt_raw)
            expected = _decode_urlsafe_b64(digest_raw)
            actual = hashlib.pbkdf2_hmac(
                "sha256",
                str(password or "").encode("utf-8"),
                salt,
                iterations,
            )
            return hmac.compare_digest(actual, expected)
        except Exception:
            return False

    return hmac.compare_digest(hash_password_legacy(password), stored)


def needs_password_rehash(encoded: str | None) -> bool:
    stored = str(encoded or "")
    if not stored.startswith(f"{PBKDF2_ALGORITHM}$"):
        return True
    try:
        _algorithm, iterations_raw, _salt_raw, _digest_raw = stored.split("$", 3)
        return int(iterations_raw) < PBKDF2_ITERATIONS
    except Exception:
        return True
