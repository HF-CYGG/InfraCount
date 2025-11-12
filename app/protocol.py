import struct
from datetime import datetime
import xml.etree.ElementTree as ET

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
    ts = _get_text(root, ["time", "timestamp", "datetime"]) or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return {
        "uuid": uuid,
        "in": in_count,
        "out": out_count,
        "time": ts,
        "battery_level": battery,
        "signal_status": signal,
    }

def build_ack_xml(uuid: str):
    return f"<UP_SENSOR_DATA_RES><uuid>{uuid}</uuid><ret>0</ret></UP_SENSOR_DATA_RES>"

def build_time_sync_xml():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"<TIME_SYNC_RES><ret>0</ret><time>{now}</time></TIME_SYNC_RES>"
