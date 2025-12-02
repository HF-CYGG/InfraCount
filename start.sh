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

# Run Launcher
echo -e "\033[0;32m[INFO] Starting InfraCount Services...\033[0m"
exec "$VENV_PYTHON" tools/launcher.py
