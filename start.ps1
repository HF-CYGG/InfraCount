$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

function Kill-Port-Process {
    param([int]$port)
    Write-Host "正在检查端口 $port..." -ForegroundColor Cyan
    $netstat = cmd /c "netstat -ano | findstr :$port"
    if ($netstat) {
        $lines = $netstat -split "`r`n"
        foreach ($line in $lines) {
            if ($line -match ":$port\s") {
                $parts = $line.Trim() -split "\s+"
                $pidFound = $parts[-1]
                if ($pidFound -match "^\d+$") {
                    Write-Host "发现端口 $port 被进程 PID: $pidFound 占用"
                    Write-Host "尝试结束进程 $pidFound..."
                    try {
                        Stop-Process -Id $pidFound -Force -ErrorAction SilentlyContinue
                        Write-Host "进程已结束。" -ForegroundColor Green
                    } catch {
                        Write-Host "[警告] 无法结束进程 $pidFound。拒绝访问或进程已不存在。" -ForegroundColor Yellow
                    }
                }
            }
        }
    }
}

function Cleanup-Resources {
    Write-Host "`n[信息] 正在清理资源..." -ForegroundColor Yellow
    
    # Kill known ports
    Kill-Port-Process 8085 # TCP Server
    Kill-Port-Process 8000 # Web Server (if running on 8000)
    
    Write-Host "[信息] 清理完成。" -ForegroundColor Green
}

function Pause-Exit {
    Cleanup-Resources
    Write-Host "`n按回车键退出..." -NoNewline -ForegroundColor Cyan
    Read-Host
    exit
}

$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $ROOT

$VENV_PYTHON = "$ROOT\.venv\Scripts\python.exe"

if (-not (Test-Path $VENV_PYTHON)) {
    Write-Host "[错误] 未找到运行环境！" -ForegroundColor Red
    Write-Host "请先以管理员身份运行 'install.ps1' 安装依赖。" -ForegroundColor Yellow
    Pause-Exit
}

# --- Conflict Resolution Start ---
$TaskName = "InfraCountService"
Write-Host "正在检查后台服务 '$TaskName'..." -ForegroundColor Cyan

# Check if task exists and is running
$taskRunning = $false
$query = cmd /c "schtasks /query /tn `"$TaskName`" /fo LIST 2>nul"
if ($query -match "Status:\s+Running") {
    $taskRunning = $true
}

if ($taskRunning) {
    Write-Host "[警告] 后台服务 '$TaskName' 正在运行。" -ForegroundColor Yellow
    Write-Host "正在停止后台服务以避免冲突..." -ForegroundColor Yellow
    
    # Try to stop it
    cmd /c "schtasks /end /tn `"$TaskName`" 2>nul" | Out-Null
    
    # Wait a bit
    Start-Sleep -Seconds 2
    
    # Check again
    $queryAfter = cmd /c "schtasks /query /tn `"$TaskName`" /fo LIST 2>nul"
    if ($queryAfter -match "Status:\s+Running") {
         Write-Host "[错误] 停止后台服务失败。" -ForegroundColor Red
         Write-Host "请以管理员身份运行此脚本或手动停止任务。" -ForegroundColor Red
         Pause-Exit
    } else {
         Write-Host "后台服务已停止。" -ForegroundColor Green
    }
}

# Initial Port Check using helper
Kill-Port-Process 8085

# --- Conflict Resolution End ---

Write-Host "[信息] 正在启动 InfraCount 服务..." -ForegroundColor Green
Write-Host "日志将写入 data/ 目录。" -ForegroundColor Gray

try {
    & $VENV_PYTHON "$ROOT\tools\launcher.py"
} catch {
    Write-Host "[错误] 启动器异常退出：" -ForegroundColor Red
    Write-Host $_ -ForegroundColor Red
} finally {
    Pause-Exit
}
