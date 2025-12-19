import subprocess
import sys
import time
import os
import signal
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

def main():
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
    no_browser = env.get("INFRACOUNT_NO_BROWSER", "").strip() == "1"
    reset_logs = env.get("INFRACOUNT_RESET_LOGS", "").strip() == "1"

    tcp_out_path = os.path.join(data_dir, "tcp_server.out")
    tcp_err_path = os.path.join(data_dir, "tcp_server.err")
    web_out_path = os.path.join(data_dir, "uvicorn.out")
    web_err_path = os.path.join(data_dir, "uvicorn.err")

    mode = "wb" if reset_logs else "ab"
    tcp_out = open(tcp_out_path, mode, buffering=0)
    tcp_err = open(tcp_err_path, mode, buffering=0)
    web_out = open(web_out_path, mode, buffering=0)
    web_err = open(web_err_path, mode, buffering=0)

    print(f"Starting services from {root_dir}...")

    # Start TCP Server
    tcp_process = subprocess.Popen(
        [python_exe, "tcp_server.py"],
        cwd=root_dir,
        stdout=tcp_out,
        stderr=tcp_err,
        env={**env, "TCP_HOST": str(tcp_host), "TCP_PORT": str(tcp_port)},
    )
    print(f"TCP Server started (PID: {tcp_process.pid})")

    # Start Web Server
    web_process = subprocess.Popen(
        [python_exe, "-m", "uvicorn", "api.main:app", "--host", str(web_host), "--port", str(web_port)],
        cwd=root_dir,
        stdout=web_out,
        stderr=web_err,
        env=env,
    )
    print(f"Web Server started (PID: {web_process.pid})")

    # Open Dashboard
    try:
        time.sleep(2)
        url = f"http://127.0.0.1:{web_port}/login"
        print(f"Opening {url} ...")
        if not no_browser:
            webbrowser.open(url)
    except Exception:
        pass

    try:
        while True:
            time.sleep(1)
            # Check if processes are alive
            if tcp_process.poll() is not None:
                print(f"TCP Server exited unexpectedly with code {tcp_process.returncode}.")
                print(f"Log: {tcp_err_path}")
                print("Tail of tcp_server.err:")
                tail = _tail_file_bytes(tcp_err_path)
                if tail:
                    print(tail)
                _terminate_process(web_process)
                break
            if web_process.poll() is not None:
                print(f"Web Server exited unexpectedly with code {web_process.returncode}.")
                print(f"Log: {web_err_path}")
                print("Tail of uvicorn.err:")
                tail = _tail_file_bytes(web_err_path)
                if tail:
                    print(tail)
                _terminate_process(tcp_process)
                break
    except KeyboardInterrupt:
        print("Stopping services...")
        _terminate_process(tcp_process)
        _terminate_process(web_process)
    finally:
        tcp_out.close()
        tcp_err.close()
        web_out.close()
        web_err.close()

if __name__ == "__main__":
    main()
