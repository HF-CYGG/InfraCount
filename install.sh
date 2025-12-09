#!/usr/bin/env bash
# Linux 一键安装脚本 (Ubuntu/Debian/CentOS)

set -e

# 配置
PIP_MIRROR="https://pypi.tuna.tsinghua.edu.cn/simple"
PIP_HOST="pypi.tuna.tsinghua.edu.cn"
CONDA_MIRROR_X86="https://mirrors.tuna.tsinghua.edu.cn/anaconda/miniconda/Miniconda3-latest-Linux-x86_64.sh"
CONDA_MIRROR_ARM="https://mirrors.tuna.tsinghua.edu.cn/anaconda/miniconda/Miniconda3-latest-Linux-aarch64.sh"

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

info() { echo -e "${GREEN}[INFO] $1${NC}"; }
warn() { echo -e "${YELLOW}[WARN] $1${NC}"; }
error() { echo -e "${RED}[ERROR] $1${NC}"; exit 1; }
step() { echo -e "${CYAN}[STEP] $1${NC}"; }

# 检查 Root 权限
if [ "$(id -u)" -ne 0 ]; then
    error "请使用 root 权限运行此脚本 (sudo ./install.sh)"
fi

ROOT="$(cd "$(dirname "$0")" && pwd)"
USER_NAME=${SUDO_USER:-$(whoami)}
GROUP_NAME=$(id -gn $USER_NAME)

info "安装目录: $ROOT"
info "运行用户: $USER_NAME"

# --- 辅助函数：清理端口占用 ---
kill_port_process() {
    local port=$1
    echo -e "${CYAN}正在检查端口 $port...${NC}"
    
    local pids=""
    
    # 尝试使用 lsof
    if command -v lsof >/dev/null 2>&1; then
        pids=$(lsof -t -i:$port)
    # 尝试使用 netstat
    elif command -v netstat >/dev/null 2>&1; then
        pids=$(netstat -nlp | grep ":$port " | awk '{print $7}' | cut -d'/' -f1)
    # 尝试使用 ss
    elif command -v ss >/dev/null 2>&1; then
        pids=$(ss -lptn "sport = :$port" | grep -v State | awk '{print $6}' | cut -d',' -f2 | cut -d'=' -f2)
    fi

    if [ -n "$pids" ]; then
        for pid in $pids; do
            if [ -n "$pid" ] && [ "$pid" -gt 0 ]; then
                echo -e "${YELLOW}端口 $port 被进程 PID: $pid 占用${NC}"
                echo -e "尝试终止进程 $pid..."
                kill -9 $pid 2>/dev/null || true
                echo -e "${GREEN}进程已终止${NC}"
            fi
        done
    else
        echo "端口 $port 未被占用"
    fi
}

# 清理端口
kill_port_process 8085
kill_port_process 8000

# 1. 安装 Python 和依赖
step "1. 检查 Python 环境..."

install_system_python() {
    if command -v apt-get >/dev/null 2>&1; then
        apt-get update
        apt-get install -y python3 python3-venv python3-pip curl net-tools
    elif command -v yum >/dev/null 2>&1; then
        yum install -y python3 python3-pip curl net-tools
    elif command -v dnf >/dev/null 2>&1; then
        dnf install -y python3 python3-pip curl net-tools
    else
        return 1
    fi
}

install_miniconda() {
    info "尝试从清华镜像安装 Miniconda (Python 3)..."
    ARCH="$(uname -m)"
    URL=""
    if [ "$ARCH" = "x86_64" ]; then
        URL="$CONDA_MIRROR_X86"
    elif [ "$ARCH" = "aarch64" ]; then
        URL="$CONDA_MIRROR_ARM"
    fi

    if [ -z "$URL" ]; then
        error "不支持的架构: $ARCH"
    fi

    if ! command -v curl >/dev/null 2>&1; then
        if command -v apt-get >/dev/null 2>&1; then apt-get install -y curl; fi
        if command -v yum >/dev/null 2>&1; then yum install -y curl; fi
    fi

    TMP_SCRIPT="/tmp/miniconda.sh"
    INSTALL_DIR="/opt/miniconda"
    
    curl -fsSL "$URL" -o "$TMP_SCRIPT"
    bash "$TMP_SCRIPT" -b -p "$INSTALL_DIR" -u
    rm "$TMP_SCRIPT"
    
    ln -sf "$INSTALL_DIR/bin/python3" /usr/local/bin/python3
    ln -sf "$INSTALL_DIR/bin/pip3" /usr/local/bin/pip3
    
    info "Miniconda 已安装到 $INSTALL_DIR"
}

if ! command -v python3 >/dev/null 2>&1; then
    info "未找到 Python 3，尝试使用系统包管理器安装..."
    if ! install_system_python; then
        warn "系统包管理器失败或未找到。"
        install_miniconda
    fi
fi

if ! command -v python3 >/dev/null 2>&1; then
    error "无法安装 Python 3，请手动安装。"
fi

PY_VER=$(python3 --version)
info "使用版本: $PY_VER"

# 2. 设置虚拟环境
step "2. 设置虚拟环境..."
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
    error "虚拟环境创建失败，$PY 未找到。"
fi

# 3. 安装 Python 包
step "3. 安装 Python 依赖..."
info "使用镜像源: $PIP_MIRROR"

"$PY" -m pip install --upgrade pip -i "$PIP_MIRROR" --trusted-host "$PIP_HOST"
"$PY" -m pip config set global.index-url "$PIP_MIRROR"
"$PY" -m pip config set global.trusted-host "$PIP_HOST"

if [ -f "$ROOT/requirements.txt" ]; then
    "$PY" -m pip install -r "$ROOT/requirements.txt"
else
    "$PY" -m pip install fastapi "uvicorn[standard]" aiosqlite python-multipart aiomysql rapidfuzz jinja2
fi

# 4. 创建启动脚本
step "4. 创建启动脚本..."
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

# 5. 创建 Systemd 服务
step "5. 配置 Systemd 服务..."
SERVICE_FILE="/etc/systemd/system/infraphone.service"

cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=InfraCount Service
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

# 6. 启用并启动服务
step "6. 启用并启动服务..."
systemctl daemon-reload
systemctl enable infraphone
systemctl restart infraphone

info "安装完成！"
info "查看状态: systemctl status infraphone"
info "查看日志: $ROOT/data/"
