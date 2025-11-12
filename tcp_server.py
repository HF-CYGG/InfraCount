import asyncio
import logging
from app import config
from app.protocol import HEAD, TAIL, parse_packet, parse_sensor_xml, build_ack_xml, build_time_sync_xml
from app.logging import setup as setup_logging

async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    buffer = b""
    try:
        while True:
            data = await reader.read(1024)
            if not data:
                break
            buffer += data
            while True:
                start = buffer.find(HEAD)
                if start == -1:
                    if len(buffer) > 6:
                        buffer = buffer[-6:]
                    break
                if len(buffer) - start < 8:
                    buffer = buffer[start:]
                    break
                body = buffer[start+3:]
                seq_typ_len = body[:5]
                length = int.from_bytes(seq_typ_len[3:5], "big")
                total = 3 + 5 + length + 3
                if len(buffer) - start < total:
                    buffer = buffer[start:]
                    break
                frame = buffer[start:start+total]
                buffer = buffer[start+total:]
                msg = parse_packet(frame)
                if not msg:
                    continue
                if msg["type"] == 0x21:
                    try:
                        d = parse_sensor_xml(msg["xml"])
                        if d and d.get("uuid"):
                            try:
                                from app.db import save_device_data
                                await save_device_data(d)
                            except Exception as e:
                                logging.error("save_device_data error: %s", e)
                            ack = build_ack_xml(d["uuid"])
                            writer.write(ack.encode())
                            await writer.drain()
                    except Exception as e:
                        logging.error("parse_sensor_xml error: %s", e)
                elif msg["type"] == 0x22:
                    res = build_time_sync_xml()
                    writer.write(res.encode())
                    await writer.drain()
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass

async def main():
    setup_logging()
    try:
        from app.db import init_pool
        await init_pool()
    except Exception:
        pass
    server = await asyncio.start_server(handle_client, config.TCP_HOST, config.TCP_PORT)
    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    asyncio.run(main())
