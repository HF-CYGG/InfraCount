#!/usr/bin/env bash
# 一键启动脚本 (Linux)

set -e

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

info() { echo -e "${GREEN}[INFO] $1${NC}"; }
warn() { echo -e "${YELLOW}[WARN] $1${NC}"; }
error() { echo -e "${RED}[ERROR] $1${NC}"; exit 1; }

# 获取脚本目录
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

# 虚拟环境 Python 路径
VENV_PYTHON="$ROOT/.venv/bin/python"

# 检查是否安装
if [ ! -f "$VENV_PYTHON" ]; then
    echo -e "${RED}[ERROR] 未找到环境！${NC}"
    echo "请先运行 './install.sh' 安装依赖。"
    exit 1
fi

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

# 冲突解决
SERVICE_NAME="infraphone"
if command -v systemctl >/dev/null 2>&1; then
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        echo -e "${YELLOW}[WARN] 后台服务 '$SERVICE_NAME' 正在运行。${NC}"
        echo "正在停止后台服务..."
        if sudo systemctl stop "$SERVICE_NAME"; then
            echo -e "${GREEN}后台服务已停止。${NC}"
        else
             echo -e "${RED}[ERROR] 无法停止服务。可能需要 sudo 权限。${NC}"
             exit 1
        fi
    fi
fi

# 检查端口
kill_port_process 8085
kill_port_process 8000

# 运行启动器
echo -e "${GREEN}[INFO] 正在启动 InfraCount 服务...${NC}"
exec "$VENV_PYTHON" tools/launcher.py
