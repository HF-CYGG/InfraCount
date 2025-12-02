#!/usr/bin/env bash
# One-click installer for Linux (Ubuntu/Debian/CentOS)

set -e

# Configuration
PIP_MIRROR="https://pypi.tuna.tsinghua.edu.cn/simple"
PIP_HOST="pypi.tuna.tsinghua.edu.cn"
CONDA_MIRROR_X86="https://mirrors.tuna.tsinghua.edu.cn/anaconda/miniconda/Miniconda3-latest-Linux-x86_64.sh"
CONDA_MIRROR_ARM="https://mirrors.tuna.tsinghua.edu.cn/anaconda/miniconda/Miniconda3-latest-Linux-aarch64.sh"

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

info "Installation Directory: $ROOT"
info "Running User: $USER_NAME"

# 1. Install Python and Dependencies
info "Checking Python environment..."

install_system_python() {
    if command -v apt-get >/dev/null 2>&1; then
        apt-get update
        apt-get install -y python3 python3-venv python3-pip curl
    elif command -v yum >/dev/null 2>&1; then
        yum install -y python3 python3-pip curl
    elif command -v dnf >/dev/null 2>&1; then
        dnf install -y python3 python3-pip curl
    else
        return 1
    fi
}

install_miniconda() {
    info "Attempting to install Miniconda (Python 3) from Tsinghua Mirror..."
    ARCH="$(uname -m)"
    URL=""
    if [ "$ARCH" = "x86_64" ]; then
        URL="$CONDA_MIRROR_X86"
    elif [ "$ARCH" = "aarch64" ]; then
        URL="$CONDA_MIRROR_ARM"
    fi

    if [ -z "$URL" ]; then
        error "Unsupported architecture for Miniconda auto-install: $ARCH"
    fi

    if ! command -v curl >/dev/null 2>&1; then
        # Try to install curl if missing, though unlikely if we got here
        if command -v apt-get >/dev/null 2>&1; then apt-get install -y curl; fi
        if command -v yum >/dev/null 2>&1; then yum install -y curl; fi
    fi

    TMP_SCRIPT="/tmp/miniconda.sh"
    INSTALL_DIR="/opt/miniconda"
    
    curl -fsSL "$URL" -o "$TMP_SCRIPT"
    bash "$TMP_SCRIPT" -b -p "$INSTALL_DIR" -u
    rm "$TMP_SCRIPT"
    
    # Link to /usr/local/bin for easy access
    ln -sf "$INSTALL_DIR/bin/python3" /usr/local/bin/python3
    ln -sf "$INSTALL_DIR/bin/pip3" /usr/local/bin/pip3
    
    info "Miniconda installed to $INSTALL_DIR"
}

if ! command -v python3 >/dev/null 2>&1; then
    info "Python 3 not found. Attempting to install via system package manager..."
    if ! install_system_python; then
        warn "System package manager failed or not found."
        install_miniconda
    fi
fi

if ! command -v python3 >/dev/null 2>&1; then
    error "Failed to install Python 3. Please install it manually."
fi

PY_VER=$(python3 --version)
info "Using $PY_VER"

# 2. Setup Virtual Environment
info "Setting up virtual environment..."
# Check if python3 supports venv module (some distros separate it)
if ! python3 -c "import venv" 2>/dev/null; then
    if command -v apt-get >/dev/null 2>&1; then
        apt-get install -y python3-venv
    fi
fi

if [ ! -d "$ROOT/.venv" ]; then
    python3 -m venv "$ROOT/.venv"
    chown -R $USER_NAME:$GROUP_NAME "$ROOT/.venv"
fi

PY="$ROOT/.venv/bin/python"
PIP="$ROOT/.venv/bin/pip"

if [ ! -f "$PY" ]; then
    error "Virtual environment creation failed. $PY not found."
fi

# 3. Install Python Packages
info "Installing Python dependencies..."
info "Using Mirror: $PIP_MIRROR"

# Install
"$PY" -m pip install --upgrade pip -i "$PIP_MIRROR" --trusted-host "$PIP_HOST"

# Set pip config (after upgrade to ensure 'config' command exists)
"$PY" -m pip config set global.index-url "$PIP_MIRROR"
"$PY" -m pip config set global.trusted-host "$PIP_HOST"

if [ -f "$ROOT/requirements.txt" ]; then
    "$PY" -m pip install -r "$ROOT/requirements.txt"
else
    "$PY" -m pip install fastapi "uvicorn[standard]" aiosqlite python-multipart aiomysql
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
