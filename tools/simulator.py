import asyncio
import argparse
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
    parser = argparse.ArgumentParser(
        description=(
            "InfraCount TCP 上报模拟器：向目标 TCP Server 发送一次示例 UP_SENSOR_DATA 包。\n"
            "为便于在不同环境（本地/容器/远端）验证，支持通过命令行覆盖 host/port。"
        )
    )
    # 兼容历史行为：不传参数时仍默认连接 127.0.0.1:8085
    parser.add_argument("--host", default="127.0.0.1", help="TCP Server 主机名或 IP（默认 127.0.0.1）")
    parser.add_argument("--port", default=8085, type=int, help="TCP Server 端口（默认 8085）")
    args = parser.parse_args()

    asyncio.run(send_once(host=args.host, port=args.port))
