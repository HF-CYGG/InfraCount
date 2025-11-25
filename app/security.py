import secrets
import time
from app import config

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
