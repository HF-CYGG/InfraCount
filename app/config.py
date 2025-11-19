import os

DB_DRIVER = os.getenv("DB_DRIVER", "sqlite")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "infrared")
DB_SQLITE_PATH = os.getenv("DB_SQLITE_PATH", r"e:\项目\书院人流计数器后端\data\infrared.db")

TCP_HOST = os.getenv("TCP_HOST", "0.0.0.0")
TCP_PORT = int(os.getenv("TCP_PORT", "8085"))
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
CSRF_ENABLE = os.getenv("CSRF_ENABLE", "1") == "1"
CSRF_TTL = int(os.getenv("CSRF_TTL", "600"))
TIME_SYNC_DIGITS = os.getenv("TIME_SYNC_DIGITS", "1") == "1"
UPLOAD_INTERVAL = os.getenv("UPLOAD_INTERVAL", "0005")
DATA_START_TIME = os.getenv("DATA_START_TIME", "0000")
DATA_END_TIME = os.getenv("DATA_END_TIME", "2359")
BTX_LOW = int(os.getenv("BTX_LOW", "30"))
