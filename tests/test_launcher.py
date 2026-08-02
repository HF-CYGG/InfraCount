import signal
import threading
import unittest
from unittest.mock import Mock, patch

from tools import launcher


class LauncherTests(unittest.TestCase):
    def test_stdio_mode_is_explicit(self):
        self.assertTrue(launcher._is_stdio_mode("stdio"))
        self.assertTrue(launcher._is_stdio_mode("STDIO"))
        self.assertFalse(launcher._is_stdio_mode("files"))

    def test_wait_for_web_ready_stops_if_process_exits(self):
        process = Mock()
        process.poll.return_value = 3

        self.assertFalse(
            launcher._wait_for_web_ready(
                process,
                8000,
                timeout_sec=1,
                poll_interval_sec=0,
            )
        )

    def test_wait_for_web_ready_accepts_healthy_response(self):
        process = Mock()
        process.poll.return_value = None
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)

        with patch("tools.launcher.urllib.request.urlopen", return_value=response):
            ready = launcher._wait_for_web_ready(
                process,
                8000,
                timeout_sec=1,
                poll_interval_sec=0,
            )

        self.assertTrue(ready)

    def test_install_signal_handlers_requests_shutdown(self):
        stop_event = threading.Event()
        handlers = {}

        def capture_handler(signum, handler):
            handlers[signum] = handler

        with patch("tools.launcher.signal.signal", side_effect=capture_handler):
            launcher._install_signal_handlers(stop_event)

        handlers[signal.SIGTERM](signal.SIGTERM, None)
        self.assertTrue(stop_event.is_set())
        self.assertIn(signal.SIGINT, handlers)

    def test_main_waits_for_web_before_starting_tcp_and_stops_children(self):
        events = []
        web_process = Mock(pid=101, returncode=None)
        tcp_process = Mock(pid=102, returncode=None)
        web_process.poll.return_value = None
        tcp_process.poll.return_value = None

        def start_process(command, **_kwargs):
            service = "web" if "uvicorn" in command else "tcp"
            events.append(service)
            return web_process if service == "web" else tcp_process

        def wait_for_web(process, _port):
            self.assertIs(process, web_process)
            events.append("web-ready")
            return True

        stop_event = Mock()
        stop_event.wait.return_value = True

        with (
            patch.dict(
                launcher.os.environ,
                {
                    "INFRACOUNT_LOG_MODE": "stdio",
                    "INFRACOUNT_NO_BROWSER": "1",
                },
                clear=False,
            ),
            patch("tools.launcher.subprocess.Popen", side_effect=start_process) as popen,
            patch("tools.launcher._wait_for_web_ready", side_effect=wait_for_web),
            patch("tools.launcher.threading.Event", return_value=stop_event),
            patch("tools.launcher._install_signal_handlers"),
            patch("tools.launcher._terminate_process") as terminate,
            patch("builtins.print"),
        ):
            exit_code = launcher.main()

        self.assertEqual(exit_code, 0)
        self.assertEqual(events, ["web", "web-ready", "tcp"])
        self.assertIsNone(popen.call_args_list[0].kwargs["stdout"])
        self.assertIsNone(popen.call_args_list[1].kwargs["stdout"])
        self.assertEqual(
            terminate.call_args_list,
            [unittest.mock.call(tcp_process), unittest.mock.call(web_process)],
        )


if __name__ == "__main__":
    unittest.main()
