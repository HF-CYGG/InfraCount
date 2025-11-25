import logging
import os
from logging.handlers import RotatingFileHandler

def setup(level: int = logging.INFO):
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    os.makedirs("data", exist_ok=True)
    path = os.path.join("data", "device_raw.log")
    handler = RotatingFileHandler(path, maxBytes=10*1024*1024, backupCount=5, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    lg = logging.getLogger("device.raw")
    lg.setLevel(level)
    lg.addHandler(handler)
    lg.propagate = False
    return logging.getLogger("infrared")
