#!/usr/bin/env bash
set -e

# Get script directory
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

# Virtual Environment Python path
VENV_PYTHON="$ROOT/.venv/bin/python"

# Check if installed
if [ ! -f "$VENV_PYTHON" ]; then
    echo -e "\033[0;31m[ERROR] Environment not found!\033[0m"
    echo "Please run './install.sh' first to install dependencies."
    exit 1
fi

# Conflict Resolution
SERVICE_NAME="infraphone"
if command -v systemctl >/dev/null 2>&1; then
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        echo -e "\033[1;33m[WARN] Background service '$SERVICE_NAME' is running.\033[0m"
        echo "Stopping background service..."
        if sudo systemctl stop "$SERVICE_NAME"; then
            echo -e "\033[0;32mBackground service stopped.\033[0m"
        else
             echo -e "\033[0;31m[ERROR] Failed to stop service. You might need sudo.\033[0m"
             exit 1
        fi
    fi
fi

# Check Port 8085
if command -v lsof >/dev/null 2>&1; then
    PID=$(lsof -t -i:8085)
    if [ -n "$PID" ]; then
        echo -e "\033[1;33m[WARN] Port 8085 is in use by PID $PID.\033[0m"
        echo "Attempting to kill process..."
        kill -9 $PID || sudo kill -9 $PID
    fi
fi

# Run Launcher
echo -e "\033[0;32m[INFO] Starting InfraCount Services...\033[0m"
exec "$VENV_PYTHON" tools/launcher.py
