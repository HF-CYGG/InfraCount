import subprocess
import sys
import time
import os
import signal
import threading
import urllib.request
import webbrowser

def _tail_file_bytes(path: str, max_bytes: int = 6000) -> str:
    try:
        with open(path, "rb") as f:
            try:
                f.seek(0, os.SEEK_END)
                size = f.tell()
                start = max(0, size - max_bytes)
                f.seek(start, os.SEEK_SET)
            except Exception:
                pass
            data = f.read(max_bytes)
        try:
            return data.decode("utf-8", errors="replace")
        except Exception:
            return data.decode("gbk", errors="replace")
    except Exception:
        return ""

def _terminate_process(proc: subprocess.Popen, timeout_sec: float = 3.0) -> None:
    if not proc:
        return
    try:
        if proc.poll() is None:
            proc.terminate()
        try:
            proc.wait(timeout=timeout_sec)
        except Exception:
            if proc.poll() is None:
                proc.kill()
    except Exception:
        pass


def _is_stdio_mode(value: str) -> bool:
    return str(value or "").strip().lower() == "stdio"


def _wait_for_web_ready(
    process: subprocess.Popen,
    port: int | str,
    timeout_sec: float = 30.0,
    poll_interval_sec: float = 0.25,
) -> bool:
    deadline = time.monotonic() + timeout_sec
    url = f"http://127.0.0.1:{port}/api/v1/health"
    while time.monotonic() < deadline:
        if process.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                response.read(1)
            return True
        except Exception:
            if poll_interval_sec > 0:
                time.sleep(poll_interval_sec)
    return False


def _install_signal_handlers(stop_event: threading.Event) -> None:
    def request_shutdown(_signum, _frame):
        stop_event.set()

    signal.signal(signal.SIGINT, request_shutdown)
    signal.signal(signal.SIGTERM, request_shutdown)


def main() -> int:
    # Paths
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    data_dir = os.path.join(root_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    
    env = os.environ.copy()
    python_exe = sys.executable

    tcp_host = env.get("TCP_HOST", "0.0.0.0")
    tcp_port = env.get("TCP_PORT", "8085")
    web_host = env.get("WEB_HOST", "0.0.0.0")
    web_port = env.get("WEB_PORT", "8000")
    # 浏览器自动打开策略（默认关闭，避免在受限环境触发 webbrowser/桌面能力相关崩溃）：
    # - INFRACOUNT_NO_BROWSER=1：强制禁止打开（优先级最高）
    # - INFRACOUNT_OPEN_BROWSER=1：显式允许打开
    # 只有当「未禁止」且「显式允许」时才会尝试打开浏览器
    no_browser = env.get("INFRACOUNT_NO_BROWSER", "").strip() == "1"
    open_browser = env.get("INFRACOUNT_OPEN_BROWSER", "").strip() == "1"
    reset_logs = env.get("INFRACOUNT_RESET_LOGS", "").strip() == "1"
    stdio_mode = _is_stdio_mode(env.get("INFRACOUNT_LOG_MODE", "files"))

    tcp_out_path = os.path.join(data_dir, "tcp_server.out")
    tcp_err_path = os.path.join(data_dir, "tcp_server.err")
    web_out_path = os.path.join(data_dir, "uvicorn.out")
    web_err_path = os.path.join(data_dir, "uvicorn.err")

    log_handles = []
    if stdio_mode:
        tcp_out = tcp_err = web_out = web_err = None
    else:
        mode = "wb" if reset_logs else "ab"
        tcp_out = open(tcp_out_path, mode, buffering=0)
        tcp_err = open(tcp_err_path, mode, buffering=0)
        web_out = open(web_out_path, mode, buffering=0)
        web_err = open(web_err_path, mode, buffering=0)
        log_handles.extend((tcp_out, tcp_err, web_out, web_err))

    print(f"Starting services from {root_dir}...")
    stop_event = threading.Event()
    _install_signal_handlers(stop_event)
    web_process = None
    tcp_process = None
    exit_code = 0

    try:
        web_process = subprocess.Popen(
            [
                python_exe,
                "-m",
                "uvicorn",
                "api.main:app",
                "--host",
                str(web_host),
                "--port",
                str(web_port),
            ],
            cwd=root_dir,
            stdout=web_out,
            stderr=web_err,
            env=env,
        )
        print(f"Web Server started (PID: {web_process.pid})")
        if not _wait_for_web_ready(web_process, web_port):
            print("Web Server failed to become healthy.")
            tail = _tail_file_bytes(web_err_path)
            if tail:
                print(tail)
            return 1

        tcp_process = subprocess.Popen(
            [python_exe, "tcp_server.py"],
            cwd=root_dir,
            stdout=tcp_out,
            stderr=tcp_err,
            env={**env, "TCP_HOST": str(tcp_host), "TCP_PORT": str(tcp_port)},
        )
        print(f"TCP Server started (PID: {tcp_process.pid})")

        url = f"http://127.0.0.1:{web_port}/login"
        # 兼容性说明：
        # - 旧版本默认会尝试打开浏览器；新版本默认不再自动打开，避免受限环境（无桌面/无默认浏览器）
        #   因调用 webbrowser.open() 导致启动脚本异常退出或卡死。
        # - 如需自动打开：设置 INFRACOUNT_OPEN_BROWSER=1；如需强制禁止：设置 INFRACOUNT_NO_BROWSER=1。
        if (not no_browser) and open_browser:
            print(f"Opening {url} ...")
            webbrowser.open(url)
        else:
            print(f"Dashboard: {url}")
        while not stop_event.wait(1):
            # Check if processes are alive
            if tcp_process.poll() is not None:
                print(f"TCP Server exited unexpectedly with code {tcp_process.returncode}.")
                print(f"Log: {tcp_err_path}")
                print("Tail of tcp_server.err:")
                tail = _tail_file_bytes(tcp_err_path)
                if tail:
                    print(tail)
                exit_code = 1
                break
            if web_process.poll() is not None:
                print(f"Web Server exited unexpectedly with code {web_process.returncode}.")
                print(f"Log: {web_err_path}")
                print("Tail of uvicorn.err:")
                tail = _tail_file_bytes(web_err_path)
                if tail:
                    print(tail)
                exit_code = 1
                break
    except KeyboardInterrupt:
        stop_event.set()
    except Exception as exc:
        print(f"Launcher failed: {exc}")
        exit_code = 1
    finally:
        print("Stopping services...")
        _terminate_process(tcp_process)
        _terminate_process(web_process)
        for handle in log_handles:
            handle.close()
    return exit_code

if __name__ == "__main__":
    raise SystemExit(main())
