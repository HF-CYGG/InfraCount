import subprocess
import sys
import time
import os
import signal

def main():
    # Paths
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    data_dir = os.path.join(root_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    
    tcp_out = open(os.path.join(data_dir, "tcp_server.out"), "a")
    tcp_err = open(os.path.join(data_dir, "tcp_server.err"), "a")
    web_out = open(os.path.join(data_dir, "uvicorn.out"), "a")
    web_err = open(os.path.join(data_dir, "uvicorn.err"), "a")

    env = os.environ.copy()
    python_exe = sys.executable

    print(f"Starting services from {root_dir}...")

    # Start TCP Server
    tcp_process = subprocess.Popen(
        [python_exe, "tcp_server.py"],
        cwd=root_dir,
        stdout=tcp_out,
        stderr=tcp_err,
        env=env
    )
    print(f"TCP Server started (PID: {tcp_process.pid})")

    # Start Web Server
    web_process = subprocess.Popen(
        [python_exe, "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"],
        cwd=root_dir,
        stdout=web_out,
        stderr=web_err,
        env=env
    )
    print(f"Web Server started (PID: {web_process.pid})")

    try:
        while True:
            time.sleep(1)
            # Check if processes are alive
            if tcp_process.poll() is not None:
                print("TCP Server exited unexpectedly.")
                web_process.terminate()
                break
            if web_process.poll() is not None:
                print("Web Server exited unexpectedly.")
                tcp_process.terminate()
                break
    except KeyboardInterrupt:
        print("Stopping services...")
        tcp_process.terminate()
        web_process.terminate()
    finally:
        tcp_out.close()
        tcp_err.close()
        web_out.close()
        web_err.close()

if __name__ == "__main__":
    main()
