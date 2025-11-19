import asyncio
import struct

HEAD = b"\xFA\xF5\xF6"
TAIL = b"\xFA\xF6\xF5"

def build_packet(seq: int, typ: int, xml: str) -> bytes:
    data = xml.encode("utf-8")
    return HEAD + struct.pack(">HBH", seq, typ, len(data)) + data + TAIL

async def send_once(host: str = "127.0.0.1", port: int = 8085):
    reader, writer = await asyncio.open_connection(host, port)
    xml = (
        "<UP_SENSOR_DATA>"
        "<uuid>SIM-ABC</uuid>"
        "<rec_type>1</rec_type>"
        "<in>12</in>"
        "<out>7</out>"
        "<time>2025-11-12 12:00:00</time>"
        "<battery>18</battery>"
        "<warn_status>2</warn_status>"
        "<batterytx_level>25</batterytx_level>"
        "<signal_status>1</signal_status>"
        "</UP_SENSOR_DATA>"
    )
    pkt = build_packet(1, 0x21, xml)
    writer.write(pkt)
    await writer.drain()
    data = await reader.read(1024)
    print(data.decode("utf-8", errors="ignore"))
    writer.close()
    await writer.wait_closed()

if __name__ == "__main__":
    asyncio.run(send_once())
