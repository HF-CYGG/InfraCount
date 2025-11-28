#!/usr/bin/env bash
# update.sh - One-click update script
# Usage: bash update.sh [remote_name] [branch_tag]
# Default: bash update.sh origin main

set -euo pipefail

# 1. Compatibility Check & Directory Setup
if [ -z "${BASH_VERSION:-}" ]; then if command -v bash >/dev/null 2>&1; then exec bash "$0" "$@"; fi; fi
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

REMOTE="${1:-origin}"
TARGET="${2:-main}"
BACKUP_DIR="$ROOT/backup_$(date +%Y%m%d_%H%M%S)"

echo "=== InfraCount Auto Update Script ==="
echo "Working Directory: $ROOT"
echo "Target Remote: $REMOTE"
echo "Target Branch/Tag: $TARGET"

# 2. Stop Services
echo ">>> Stopping services..."
pkill -f "tcp_server.py" || true
pkill -f "uvicorn api.main:app" || true
sleep 2

# 3. Backup Data
echo ">>> Backing up critical data..."
mkdir -p "$BACKUP_DIR/data"
if [ -d "$ROOT/data" ]; then
    # Backup database and log only
    cp -r "$ROOT/data/infrared.db" "$BACKUP_DIR/data/" 2>/dev/null || true
    cp -r "$ROOT/data/device_raw.log" "$BACKUP_DIR/data/" 2>/dev/null || true
fi
echo "Backup saved to: $BACKUP_DIR"

# 4. Git Pull
echo ">>> Pulling code updates..."
# Stash local changes to prevent conflicts
if [ -n "$(git status --porcelain)" ]; then
    echo "Local changes detected, stashing..."
    git stash
fi

# Try pull
if ! git pull --tags "$REMOTE" "$TARGET"; then
    echo "Error: Git pull failed! Restoring backup and exiting."
    echo "Please check network connection or remote repository config."
    exit 1
fi

# 5. Restore Data (Safety check)
if [ ! -d "$ROOT/data" ] || [ ! -f "$ROOT/data/infrared.db" ]; then
    echo "Warning: Data directory seems missing/corrupted. Restoring from backup..."
    mkdir -p "$ROOT/data"
    cp -r "$BACKUP_DIR/data/"* "$ROOT/data/"
fi

# 6. Update Dependencies
echo ">>> Updating dependencies..."
if [ -f "$ROOT/start.sh" ]; then
    # Reuse venv logic
    PY="$ROOT/.venv/bin/python"
    if [ ! -f "$PY" ]; then
        echo "Virtual environment not found, initializing via start.sh..."
        bash "$ROOT/start.sh" &
        echo "Please wait for start.sh to finish initialization."
        exit 0
    else
        "$PY" -m pip install --upgrade pip
        if [ -f "$ROOT/requirements.txt" ]; then
            "$PY" -m pip install -r "$ROOT/requirements.txt"
        else
            "$PY" -m pip install fastapi "uvicorn[standard]" aiosqlite python-multipart
        fi
    fi
fi

# 7. Restart Services
echo ">>> Restarting services..."
bash "$ROOT/start.sh"

echo "=== Update Completed! ==="
