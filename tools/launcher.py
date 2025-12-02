import subprocess
import sys
import time
import os
import signal
import webbrowser

def main():
    # Paths
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    data_dir = os.path.join(root_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    
    # Use buffering=1 for line buffering to ensure logs are written immediately
    tcp_out = open(os.path.join(data_dir, "tcp_server.out"), "a", buffering=1, encoding='utf-8')
    tcp_err = open(os.path.join(data_dir, "tcp_server.err"), "a", buffering=1, encoding='utf-8')
    web_out = open(os.path.join(data_dir, "uvicorn.out"), "a", buffering=1, encoding='utf-8')
    web_err = open(os.path.join(data_dir, "uvicorn.err"), "a", buffering=1, encoding='utf-8')

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

    # Open Dashboard
    try:
        time.sleep(2)
        url = "http://127.0.0.1:8000/dashboard"
        print(f"Opening {url} ...")
        webbrowser.open(url)
    except Exception:
        pass

    try:
        while True:
            time.sleep(1)
            # Check if processes are alive
            if tcp_process.poll() is not None:
                print(f"TCP Server exited unexpectedly with code {tcp_process.returncode}.")
                print("Tail of tcp_server.err:")
                try:
                    with open(os.path.join(data_dir, "tcp_server.err"), "r", encoding='utf-8') as f:
                        print(f.read()[-500:]) # Print last 500 chars
                except:
                    pass
                web_process.terminate()
                break
            if web_process.poll() is not None:
                print(f"Web Server exited unexpectedly with code {web_process.returncode}.")
                print("Tail of uvicorn.err:")
                try:
                    with open(os.path.join(data_dir, "uvicorn.err"), "r", encoding='utf-8') as f:
                        print(f.read()[-500:])
                except:
                    pass
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
