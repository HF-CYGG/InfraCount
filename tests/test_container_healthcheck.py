import importlib.util
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import socket
import subprocess
import sys
import threading
import unittest
from types import SimpleNamespace
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
HEALTHCHECK_SCRIPT = ROOT / "tools" / "container_healthcheck.py"


def _load_healthcheck_module():
    spec = importlib.util.spec_from_file_location("container_healthcheck", HEALTHCHECK_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/api/v1/health":
            self.send_response(404)
            self.end_headers()
            return

        payload = self.server.payload
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(self.server.status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format, *args):
        pass


class _TcpListener:
    def __init__(self):
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind(("127.0.0.1", 0))
        self._socket.listen(1)
        self.port = self._socket.getsockname()[1]
        self.connected = threading.Event()
        self._thread = threading.Thread(target=self._accept_once, daemon=True)

    def start(self):
        self._thread.start()

    def close(self):
        self._socket.close()
        self._thread.join(timeout=1)

    def _accept_once(self):
        try:
            connection, _ = self._socket.accept()
            with connection:
                self.connected.set()
        except OSError:
            pass


class ContainerHealthcheckTests(unittest.TestCase):
    def setUp(self):
        self.http_server = ThreadingHTTPServer(("127.0.0.1", 0), _HealthHandler)
        self.http_server.status_code = 200
        self.http_server.payload = {"status": "ok", "db": {"ok": True}}
        self.http_thread = threading.Thread(target=self.http_server.serve_forever, daemon=True)
        self.http_thread.start()

    def tearDown(self):
        self.http_server.shutdown()
        self.http_server.server_close()
        self.http_thread.join(timeout=1)

    def _run_healthcheck(self, tcp_port):
        environment = os.environ.copy()
        environment.update(
            {
                "WEB_PORT": str(self.http_server.server_port),
                "TCP_PORT": str(tcp_port),
            }
        )
        return subprocess.run(
            [sys.executable, str(HEALTHCHECK_SCRIPT)],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            timeout=5,
        )

    @staticmethod
    def _unused_tcp_port():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return sock.getsockname()[1]

    def test_exits_zero_when_http_health_and_tcp_listener_are_ready(self):
        listener = _TcpListener()
        listener.start()
        try:
            result = self._run_healthcheck(listener.port)
        finally:
            listener.close()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertTrue(listener.connected.is_set())

    def test_exits_one_without_echoing_sensitive_health_response_content(self):
        self.http_server.status_code = 503
        self.http_server.payload = {"status": "degraded", "db": {"ok": False}, "detail": "super-secret"}

        result = self._run_healthcheck(self._unused_tcp_port())

        self.assertEqual(result.returncode, 1)
        self.assertTrue(result.stderr.startswith("healthcheck failed:"), result.stderr)
        self.assertNotIn("super-secret", result.stderr)

    def test_exits_one_when_health_payload_is_not_database_ready(self):
        self.http_server.payload = {"status": "ok", "db": {"ok": False}}

        result = self._run_healthcheck(self._unused_tcp_port())

        self.assertEqual(result.returncode, 1)
        self.assertTrue(result.stderr.startswith("healthcheck failed:"), result.stderr)

    def test_exits_one_when_tcp_listener_is_unavailable(self):
        result = self._run_healthcheck(self._unused_tcp_port())

        self.assertEqual(result.returncode, 1)
        self.assertTrue(result.stderr.startswith("healthcheck failed:"), result.stderr)

    def test_main_uses_one_total_deadline_for_http_and_tcp_checks(self):
        module = _load_healthcheck_module()
        clock = SimpleNamespace(value=100.0)
        deadlines = []

        def fetch_health(web_port, deadline):
            self.assertEqual(web_port, 8000)
            deadlines.append(deadline)
            clock.value = 102.5
            return {"status": "ok", "db": {"ok": True}}

        def verify_tcp_listener(tcp_port, deadline):
            self.assertEqual(tcp_port, 8085)
            deadlines.append(deadline)

        module.time = SimpleNamespace(monotonic=lambda: clock.value)
        with (
            mock.patch.object(module, "_fetch_health", side_effect=fetch_health),
            mock.patch.object(module, "_verify_tcp_listener", side_effect=verify_tcp_listener),
            mock.patch.dict(module.os.environ, {"WEB_PORT": "8000", "TCP_PORT": "8085"}, clear=True),
        ):
            result = module.main()

        self.assertEqual(result, 0)
        self.assertEqual(deadlines, [104.0, 104.0])
        self.assertEqual(deadlines[1] - clock.value, 1.5)

    def test_fetch_health_rejects_oversized_payload_before_reading_it(self):
        module = _load_healthcheck_module()
        response = mock.Mock(status=200)
        response.getheader.return_value = str(module.MAX_HEALTH_RESPONSE_BYTES + 1)
        connection = mock.Mock()
        connection.sock = mock.Mock()
        connection.getresponse.return_value = response

        with mock.patch.object(module, "HTTPConnection", return_value=connection):
            with self.assertRaisesRegex(RuntimeError, "response is too large"):
                module._fetch_health(8000, module.time.monotonic() + 1)

        response.read.assert_not_called()


if __name__ == "__main__":
    unittest.main()
