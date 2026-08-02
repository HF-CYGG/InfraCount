"""Container health check for the HTTP API, database, and TCP listener."""

import json
import os
import socket
import sys
import time
from http.client import HTTPConnection, HTTPException


HEALTHCHECK_TIMEOUT_SECONDS = 4
MAX_HEALTH_RESPONSE_BYTES = 16 * 1024
HEALTH_RESPONSE_CHUNK_BYTES = 4096


def _port_from_environment(name: str, default: int) -> int:
    try:
        port = int(os.getenv(name, str(default)))
    except ValueError as exc:
        raise RuntimeError(f"invalid {name}") from exc
    if not 1 <= port <= 65535:
        raise RuntimeError(f"invalid {name}")
    return port


def _remaining_timeout(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise RuntimeError("healthcheck timed out")
    return remaining


def _set_socket_timeout(sock: socket.socket | None, deadline: float) -> None:
    if sock is None:
        raise RuntimeError("HTTP health request failed")
    sock.settimeout(_remaining_timeout(deadline))


def _read_health_response(response, response_socket: socket.socket, deadline: float) -> bytes:
    content_length = response.getheader("Content-Length")
    expected_payload_size = None
    if content_length is not None:
        try:
            expected_payload_size = int(content_length)
            if expected_payload_size < 0:
                raise ValueError
            if expected_payload_size > MAX_HEALTH_RESPONSE_BYTES:
                raise RuntimeError("HTTP health response is too large")
        except ValueError as exc:
            raise RuntimeError("invalid HTTP health response") from exc

    chunks = []
    payload_size = 0
    while True:
        _set_socket_timeout(response_socket, deadline)
        chunk = response.read(min(HEALTH_RESPONSE_CHUNK_BYTES, MAX_HEALTH_RESPONSE_BYTES + 1 - payload_size))
        if not chunk:
            break
        payload_size += len(chunk)
        if payload_size > MAX_HEALTH_RESPONSE_BYTES:
            raise RuntimeError("HTTP health response is too large")
        chunks.append(chunk)
        if payload_size == expected_payload_size:
            return b"".join(chunks)
    return b"".join(chunks)


def _fetch_health(web_port: int, deadline: float) -> dict:
    connection = HTTPConnection("127.0.0.1", web_port, timeout=_remaining_timeout(deadline))
    try:
        connection.connect()
        _set_socket_timeout(connection.sock, deadline)
        connection.request("GET", "/api/v1/health")
        _set_socket_timeout(connection.sock, deadline)
        response_socket = connection.sock
        response = connection.getresponse()
        if not 200 <= response.status < 300:
            raise RuntimeError("HTTP health response was unsuccessful")
        payload = _read_health_response(response, response_socket, deadline)
    except (HTTPException, OSError) as exc:
        raise RuntimeError("HTTP health request failed") from exc
    finally:
        connection.close()

    try:
        result = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("invalid HTTP health response") from exc
    if not isinstance(result, dict):
        raise RuntimeError("invalid HTTP health response")
    return result


def _verify_health_payload(payload: dict) -> None:
    db = payload.get("db")
    if payload.get("status") != "ok" or not isinstance(db, dict) or db.get("ok") is not True:
        raise RuntimeError("application health is not ready")


def _verify_tcp_listener(tcp_port: int, deadline: float) -> None:
    try:
        with socket.create_connection(("127.0.0.1", tcp_port), timeout=_remaining_timeout(deadline)):
            pass
    except OSError as exc:
        raise RuntimeError("TCP listener is unavailable") from exc


def main() -> int:
    try:
        web_port = _port_from_environment("WEB_PORT", 8000)
        tcp_port = _port_from_environment("TCP_PORT", 8085)
        deadline = time.monotonic() + HEALTHCHECK_TIMEOUT_SECONDS
        _verify_health_payload(_fetch_health(web_port, deadline))
        _verify_tcp_listener(tcp_port, deadline)
    except RuntimeError as exc:
        print(f"healthcheck failed: {exc}", file=sys.stderr)
        return 1
    except Exception:
        print("healthcheck failed: unexpected error", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
