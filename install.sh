#!/usr/bin/env bash
# One-click installer for Linux (Ubuntu/Debian/CentOS)

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

info() { echo -e "${GREEN}[INFO] $1${NC}"; }
warn() { echo -e "${YELLOW}[WARN] $1${NC}"; }
error() { echo -e "${RED}[ERROR] $1${NC}"; exit 1; }

# Check Root
if [ "$(id -u)" -ne 0 ]; then
    error "This script must be run as root (sudo)."
fi

ROOT="$(cd "$(dirname "$0")" && pwd)"
USER_NAME=${SUDO_USER:-$(whoami)}
GROUP_NAME=$(id -gn $USER_NAME)

info "Installing Directory: $ROOT"
info "Running User: $USER_NAME"

# 1. Install Python and Dependencies
info "Checking Python environment..."
if command -v apt-get >/dev/null 2>&1; then
    apt-get update
    apt-get install -y python3 python3-venv python3-pip curl
elif command -v yum >/dev/null 2>&1; then
    yum install -y python3 python3-pip curl
elif command -v dnf >/dev/null 2>&1; then
    dnf install -y python3 python3-pip curl
else
    warn "Unsupported package manager. Assuming Python 3 is installed."
fi

if ! command -v python3 >/dev/null 2>&1; then
    error "Python 3 not found. Please install Python 3 manually."
fi

# 2. Setup Virtual Environment
info "Setting up virtual environment..."
if [ ! -d "$ROOT/.venv" ]; then
    python3 -m venv "$ROOT/.venv"
    chown -R $USER_NAME:$GROUP_NAME "$ROOT/.venv"
fi

PY="$ROOT/.venv/bin/python"
PIP="$ROOT/.venv/bin/pip"

# 3. Install Python Packages
info "Installing Python dependencies..."
# Use Tsinghua Mirror for speed in China
export PIP_INDEX_URL='https://pypi.tuna.tsinghua.edu.cn/simple'
"$PIP" install --upgrade pip
"$PIP" config set global.index-url $PIP_INDEX_URL
"$PIP" config set global.trusted-host pypi.tuna.tsinghua.edu.cn

if [ -f "$ROOT/requirements.txt" ]; then
    "$PIP" install -r "$ROOT/requirements.txt"
else
    "$PIP" install fastapi "uvicorn[standard]" aiosqlite python-multipart aiomysql
fi

# 4. Create Runner Script
info "Creating runner script..."
cat > "$ROOT/run_service.sh" <<EOF
#!/bin/bash
cd "$ROOT"
source .venv/bin/activate
exec python tools/launcher.py
EOF

chmod +x "$ROOT/run_service.sh"
chown $USER_NAME:$GROUP_NAME "$ROOT/run_service.sh"
mkdir -p "$ROOT/data"
chown -R $USER_NAME:$GROUP_NAME "$ROOT/data"

# 5. Create Systemd Service
info "Creating Systemd Service..."
SERVICE_FILE="/etc/systemd/system/infraphone.service"

cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Infrared Counter Service
After=network.target

[Service]
Type=simple
User=$USER_NAME
Group=$GROUP_NAME
WorkingDirectory=$ROOT
ExecStart=$ROOT/run_service.sh
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 6. Enable and Start Service
info "Enabling and Starting Service..."
systemctl daemon-reload
systemctl enable infraphone
systemctl restart infraphone

info "Installation Complete!"
info "Check status with: systemctl status infraphone"
info "View logs in: $ROOT/data/"
