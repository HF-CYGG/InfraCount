import asyncio
import logging
import os
import xml.etree.ElementTree as ET
from app import config
from app.protocol import HEAD, TAIL, parse_packet, parse_sensor_xml, build_ack_xml, build_time_sync_xml, build_frame
from app.logging import setup as setup_logging

async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    buffer = b""
    try:
        peer = writer.get_extra_info("peername")
        raw_lg = logging.getLogger("device.raw")
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
                    try:
                        raw_lg.info(f"peer={peer} invalid_frame={frame.hex()}")
                    except Exception:
                        pass
                    continue
                try:
                    raw_lg.info(f"peer={peer} seq={msg['seq']} type={msg['type']} xml={msg['xml']}")
                except Exception:
                    pass
                if msg["type"] == 0x21:
                    try:
                        d = parse_sensor_xml(msg["xml"])
                        if d and d.get("uuid"):
                            ret = 0
                            try:
                                from app.db import save_device_data
                                await save_device_data(d)
                            except Exception as e:
                                logging.error("save_device_data error: %s", e)
                                ret = 1
                            ack = build_ack_xml(d["uuid"], ret)
                            writer.write(ack.encode())
                            await writer.drain()
                            try:
                                os.makedirs(os.path.join("data", "sync"), exist_ok=True)
                                flag = os.path.join("data", "sync", f"{d['uuid']}.flag")
                                if os.path.exists(flag):
                                    res = build_time_sync_xml(d["uuid"]) 
                                    writer.write(build_frame(0x22, res, msg["seq"]))
                                    await writer.drain()
                                    try:
                                        raw_lg.info(f"peer={peer} time_sync_sent xml={res}")
                                    except Exception:
                                        pass
                                    try:
                                        os.remove(flag)
                                    except Exception:
                                        pass
                            except Exception:
                                pass
                    except Exception as e:
                        logging.error("parse_sensor_xml error: %s", e)
                        try:
                            root = ET.fromstring(msg.get("xml") or "")
                            uuid_el = root.find("uuid") if root is not None else None
                            uuid = (uuid_el.text.strip() if (uuid_el is not None and uuid_el.text) else "")
                            if uuid:
                                ack = build_ack_xml(uuid, 1)
                                writer.write(ack.encode())
                                await writer.drain()
                        except Exception:
                            pass
                elif msg["type"] == 0x22:
                    try:
                        root = ET.fromstring(msg["xml"]) if msg.get("xml") else None
                        uuid_el = root.find("uuid") if root is not None else None
                        uuid = (uuid_el.text.strip() if (uuid_el is not None and uuid_el.text) else "")
                        os.makedirs(os.path.join("data", "sync"), exist_ok=True)
                        flag = os.path.join("data", "sync", f"{uuid}.flag") if uuid else None
                        if flag and os.path.exists(flag):
                            res = build_time_sync_xml(uuid)
                            writer.write(build_frame(0x22, res, msg["seq"]))
                            await writer.drain()
                            try:
                                raw_lg.info(f"peer={peer} time_sync_sent xml={res}")
                            except Exception:
                                pass
                            try:
                                os.remove(flag)
                            except Exception:
                                pass
                    except Exception:
                        pass
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
