import os


def _env_bool(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _env_csv(name: str, default: str) -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]

DB_DRIVER = os.getenv("DB_DRIVER", "sqlite")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "infrared")
DB_SQLITE_PATH = os.getenv("DB_SQLITE_PATH", os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "infrared.db"))
INITIAL_ADMIN_PASSWORD = os.getenv("INITIAL_ADMIN_PASSWORD", "").strip()

SESSION_COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", "session_token")
SESSION_MAX_AGE_SEC = int(os.getenv("SESSION_MAX_AGE_SEC", str(7 * 24 * 3600)))
SESSION_COOKIE_SECURE = _env_bool("SESSION_COOKIE_SECURE", "0")
SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "lax")
CORS_ALLOW_ORIGINS = _env_csv(
    "CORS_ALLOW_ORIGINS",
    "http://localhost:8000,http://127.0.0.1:8000,http://localhost:5173,http://127.0.0.1:5173",
)

TCP_HOST = os.getenv("TCP_HOST", "0.0.0.0")
TCP_PORT = int(os.getenv("TCP_PORT", "8085"))
CSRF_ENABLE = os.getenv("CSRF_ENABLE", "1") == "1"
CSRF_TTL = int(os.getenv("CSRF_TTL", "600"))
ACTIVITY_CSV_MAX_BYTES = int(os.getenv("ACTIVITY_CSV_MAX_BYTES", str(10 * 1024 * 1024)))
ACTIVITY_EXCEL_MAX_BYTES = int(os.getenv("ACTIVITY_EXCEL_MAX_BYTES", str(25 * 1024 * 1024)))
DEVICE_LOG_MAX_BYTES = int(os.getenv("DEVICE_LOG_MAX_BYTES", str(25 * 1024 * 1024)))
DB_MERGE_MAX_BYTES = int(os.getenv("DB_MERGE_MAX_BYTES", str(512 * 1024 * 1024)))
TIME_SYNC_DIGITS = os.getenv("TIME_SYNC_DIGITS", "1") == "1"
UPLOAD_INTERVAL = os.getenv("UPLOAD_INTERVAL", "0005")
DATA_START_TIME = os.getenv("DATA_START_TIME", "0000")
DATA_END_TIME = os.getenv("DATA_END_TIME", "2359")
BTX_LOW = int(os.getenv("BTX_LOW", "30"))
BAT_LOW = int(os.getenv("BAT_LOW", "20"))
SIGNAL_OFFLINE_VALUE = int(os.getenv("SIGNAL_OFFLINE_VALUE", "1"))
REC_TYPE_BACKLOG = int(os.getenv("REC_TYPE_BACKLOG", "1"))

AUTO_SYNC_WALKIN_ENABLE = os.getenv("AUTO_SYNC_WALKIN_ENABLE", "1") == "1"
AUTO_SYNC_WALKIN_INTERVAL_SEC = int(os.getenv("AUTO_SYNC_WALKIN_INTERVAL_SEC", "1800"))
AUTO_SYNC_WALKIN_BACKFILL_DAYS = int(os.getenv("AUTO_SYNC_WALKIN_BACKFILL_DAYS", "1"))

ALERT_EMAIL_ENABLE = os.getenv("ALERT_EMAIL_ENABLE", "0") == "1"
ALERT_EMAIL_SCAN_INTERVAL_SEC = int(os.getenv("ALERT_EMAIL_SCAN_INTERVAL_SEC", "60"))
ALERT_EMAIL_MAX_PER_SCAN = int(os.getenv("ALERT_EMAIL_MAX_PER_SCAN", "20"))

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "1") == "1"
SMTP_USE_SSL = os.getenv("SMTP_USE_SSL", "0") == "1"
SMTP_FROM = os.getenv("SMTP_FROM", "")
SMTP_TO = os.getenv("SMTP_TO", "")
SMTP_SUBJECT_PREFIX = os.getenv("SMTP_SUBJECT_PREFIX", "[InfraCount]")
