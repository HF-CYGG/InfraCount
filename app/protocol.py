import struct
from datetime import datetime
import xml.etree.ElementTree as ET
from app import config

HEAD = b"\xFA\xF5\xF6"
TAIL = b"\xFA\xF6\xF5"

def parse_packet(packet: bytes):
    if not (packet.startswith(HEAD) and packet.endswith(TAIL)):
        return None
    body = packet[3:-3]
    if len(body) < 5:
        return None
    seq, typ, length = struct.unpack(">HBH", body[:5])
    data = body[5:5 + length]
    xml = data.decode("utf-8", errors="ignore")
    return {"seq": seq, "type": typ, "xml": xml}

def _get_text(root, names):
    for name in names:
        el = root.find(name)
        if el is not None and el.text is not None:
            return el.text.strip()
    return None

def parse_sensor_xml(xml_str: str):
    root = ET.fromstring(xml_str)
    uuid = _get_text(root, ["uuid", "UUID"]) or ""
    def to_int(v):
        try:
            return int(v)
        except Exception:
            return None
    in_count = to_int(_get_text(root, ["in", "IN", "in_count"]))
    out_count = to_int(_get_text(root, ["out", "OUT", "out_count"]))
    battery = to_int(_get_text(root, ["battery", "battery_level", "power"]))
    signal = to_int(_get_text(root, ["signal_status", "signal"]))
    warn_status = to_int(_get_text(root, ["warn_status", "warn"]))
    batterytx_level = to_int(_get_text(root, ["batterytx_level", "battery_tx", "btx"]))
    rec_type = to_int(_get_text(root, ["rec_type"]))
    ts = _get_text(root, ["time", "timestamp", "datetime"]) or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return {
        "uuid": uuid,
        "in": in_count,
        "out": out_count,
        "time": ts,
        "battery_level": battery,
        "signal_status": signal,
        "warn_status": warn_status,
        "batterytx_level": batterytx_level,
        "rec_type": rec_type,
    }

def build_ack_xml(uuid: str, ret: int = 0):
    r = 0 if ret is None else int(ret)
    return f"<UP_SENSOR_DATA_RES><uuid>{uuid}</uuid><ret>{r}</ret></UP_SENSOR_DATA_RES>"

def build_time_sync_xml(uuid: str):
    now = datetime.now().strftime("%Y%m%d%H%M%S")
    return (
        f"<TIME_SYSNC_RES>"
        f"<uuid>{uuid}</uuid>"
        f"<ret>0</ret>"
        f"<time>{now}</time>"
        f"<uploadInterval>{getattr(config,'UPLOAD_INTERVAL','0005')}</uploadInterval>"
        f"<dataStartTime>{getattr(config,'DATA_START_TIME','0000')}</dataStartTime>"
        f"<dataEndTime>{getattr(config,'DATA_END_TIME','2359')}</dataEndTime>"
        f"</TIME_SYSNC_RES>"
    )

def build_frame(typ: int, xml: str, seq: int = 0) -> bytes:
    data = xml.encode("utf-8")
    hdr = struct.pack(">HBH", seq & 0xFFFF, typ & 0xFF, len(data))
    return HEAD + hdr + data + TAIL
