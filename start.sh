#!/usr/bin/env bash
if [ -z "${BASH_VERSION:-}" ]; then if command -v bash >/dev/null 2>&1; then exec bash "$0" "$@"; fi; fi
set -euo pipefail 2>/dev/null || set -eu
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
SUDO=""; if command -v sudo >/dev/null 2>&1 && [ "$(id -u)" -ne 0 ]; then SUDO="sudo"; fi
if ! command -v python3 >/dev/null 2>&1; then
  if command -v apt-get >/dev/null 2>&1; then $SUDO apt-get update && $SUDO apt-get install -y python3 python3-venv python3-pip; elif command -v yum >/dev/null 2>&1; then ${SUDO:-} yum install -y python3 python3-venv python3-pip || ${SUDO:-} yum install -y python3; elif command -v dnf >/dev/null 2>&1; then ${SUDO:-} dnf install -y python3 python3-venv python3-pip || ${SUDO:-} dnf install -y python3; elif command -v pacman >/dev/null 2>&1; then ${SUDO:-} pacman -Sy --noconfirm python; elif command -v brew >/dev/null 2>&1; then brew install python; else
    if [ "$(uname -s)" = "Linux" ]; then
      ARCH="$(uname -m)"; TMP="/tmp/miniconda.sh"; URL=""
      if [ "$ARCH" = "x86_64" ]; then URL="https://mirrors.tuna.tsinghua.edu.cn/anaconda/miniconda/Miniconda3-latest-Linux-x86_64.sh"; elif [ "$ARCH" = "aarch64" ]; then URL="https://mirrors.tuna.tsinghua.edu.cn/anaconda/miniconda/Miniconda3-latest-Linux-aarch64.sh"; fi
      if [ -n "$URL" ]; then
        if command -v curl >/dev/null 2>&1; then curl -fsSL "$URL" -o "$TMP"; elif command -v wget >/dev/null 2>&1; then wget -qO "$TMP" "$URL"; else echo "curl/wget not found."; exit 1; fi
        bash "$TMP" -b -p "$HOME/miniconda" && export PATH="$HOME/miniconda/bin:$PATH"
      else
        echo "Python 3 not found."; exit 1
      fi
    else
      echo "Python 3 not found."; exit 1
    fi
  fi
fi
echo "Setting up Python virtual environment..."
if [ ! -d "$ROOT/.venv" ]; then
  if ! python3 -m venv .venv >/dev/null 2>&1; then
    if command -v apt-get >/dev/null 2>&1; then $SUDO apt-get update && $SUDO apt-get install -y python3-venv; fi
    python3 -m venv .venv || python -m venv .venv
  fi
fi
PY="$ROOT/.venv/bin/python"
"$PY" -m ensurepip --upgrade
echo "Upgrading pip..."
MIRROR="${PIP_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}"
export PIP_INDEX_URL="$MIRROR"
"$PY" -m pip install --upgrade pip -i "$MIRROR"
"$PY" -m pip config set global.index-url "$MIRROR"
"$PY" -m pip config set global.trusted-host pypi.tuna.tsinghua.edu.cn
echo "Installing dependencies..."
if [ -f "$ROOT/requirements.txt" ]; then "$PY" -m pip install -i "$MIRROR" -r "$ROOT/requirements.txt"; else "$PY" -m pip install fastapi "uvicorn[standard]" aiosqlite python-multipart -i "$MIRROR"; fi
if [ "${DB_DRIVER:-sqlite}" = "mysql" ]; then "$PY" -m pip install aiomysql -i "$MIRROR"; fi
mkdir -p "$ROOT/data"
export DB_SQLITE_PATH="$ROOT/data/infrared.db"
echo "Starting TCP server..."
nohup "$PY" "$ROOT/tcp_server.py" > "$ROOT/data/tcp_server.out" 2>&1 &
echo "Starting API and Web server..."
nohup "$PY" -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000 > "$ROOT/data/uvicorn.out" 2>&1 &
echo "Services started. TCP on ${TCP_PORT:-8085}, Web/API on http://127.0.0.1:8000"
echo "Please open http://127.0.0.1:8000/dashboard in your browser"
