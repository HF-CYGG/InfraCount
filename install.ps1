# Windows 一键安装/更新脚本 (支持 Windows Server 2012 R2+)
# 请以管理员身份运行

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

# 配置信息
$PYTHON_VERSION = "3.10.11"
$PYTHON_URL = "https://mirrors.huaweicloud.com/python/$PYTHON_VERSION/python-$PYTHON_VERSION-amd64.exe"
$PIP_MIRROR = "https://pypi.tuna.tsinghua.edu.cn/simple"
$PIP_HOST = "pypi.tuna.tsinghua.edu.cn"

# 辅助函数
function Write-Info { param($msg); Write-Host "[信息] $msg" -ForegroundColor Green }
function Write-Warn { param($msg); Write-Host "[警告] $msg" -ForegroundColor Yellow }
function Write-ErrorMsg { param($msg); Write-Host "[错误] $msg" -ForegroundColor Red }

function Pause-Exit {
    param($code)
    Write-Host "`n按回车键退出..." -NoNewline -ForegroundColor Cyan
    Read-Host
    exit $code
}

function Kill-Port-Process {
    param([int]$port)
    Write-Host "正在检查端口 $port..." -ForegroundColor Cyan
    $lines = netstat.exe -ano | Select-String -Pattern ":$port" | ForEach-Object { $_.Line }
    if ($lines) {
        foreach ($line in $lines) {
            $parts = $line.Trim() -split "\s+"
            $pidFound = $parts[-1]
            if ($pidFound -match "^\d+$" -and [int]$pidFound -gt 0) {
                Write-Host "端口 $port 被进程 PID: $pidFound 占用"
                Write-Host "尝试终止进程 $pidFound..."
                try {
                    Stop-Process -Id $pidFound -Force -ErrorAction SilentlyContinue
                    Write-Host "进程已终止。" -ForegroundColor Green
                } catch {
                    Write-Host "警告: 无法终止 PID $pidFound。可能需要手动处理。" -ForegroundColor Yellow
                }
            }
        }
    }
}

function Install-Python {
    Write-Info "正在从华为云镜像下载 Python $PYTHON_VERSION ..."
    $installerPath = "$env:TEMP\python_installer.exe"
    try {
        Invoke-WebRequest -Uri $PYTHON_URL -OutFile $installerPath -UseBasicParsing
    } catch {
        Write-ErrorMsg "下载失败，请检查网络连接。"
        Write-ErrorMsg $_
        return $false
    }

    Write-Info "正在安装 Python (这可能需要一分钟)..."
    try {
        # 为所有用户安装，添加到 PATH，禁用 UI
        $proc = Start-Process -FilePath $installerPath -ArgumentList "/quiet InstallAllUsers=1 PrependPath=1 Include_test=0" -Wait -PassThru
        if ($proc.ExitCode -eq 0) {
            Write-Info "Python 安装成功。"
            # 刷新当前会话的环境变量
            $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
            return $true
        } else {
            Write-ErrorMsg "安装程序退出，代码: $($proc.ExitCode)。"
            return $false
        }
    } catch {
        Write-ErrorMsg "无法运行安装程序。"
        Write-ErrorMsg $_
        return $false
    } finally {
        if (Test-Path $installerPath) { Remove-Item $installerPath -Force }
    }
}

try {
    # 1. 检查管理员权限
    $currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        Write-ErrorMsg "请以管理员身份运行此脚本！"
        Pause-Exit 1
    }

    $ROOT = Split-Path -Parent $MyInvocation.MyCommand.Definition
    Set-Location $ROOT
    Write-Info "安装目录: $ROOT"

    # 2. 检查并清理旧进程/服务 (释放文件锁)
    Write-Info "正在停止现有服务并清理资源..."
    $TaskName = "InfraCountService"
    
    # 停止计划任务
    cmd /c "schtasks /end /tn `"$TaskName`" /f 2>nul" | Out-Null
    Start-Sleep -Seconds 2
    
    # 清理端口占用
    Kill-Port-Process 8085 # TCP Server
    Kill-Port-Process 8000 # Web Server

    # 3. 检查 Python 环境
    Write-Info "正在检查 Python 环境..."
    $pyCmd = Get-Command python -ErrorAction SilentlyContinue | Select-Object -First 1
    
    # 如果 PATH 中没有，尝试查找常用路径
    if (-not $pyCmd) {
        $commonPaths = @(
            "C:\Python310\python.exe",
            "C:\Program Files\Python310\python.exe",
            "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe",
            "C:\Python39\python.exe",
            "C:\Program Files\Python39\python.exe"
        )
        foreach ($path in $commonPaths) {
            if (Test-Path $path) {
                Write-Info "在 $path 发现 Python"
                $pyCmd = @{ Source = $path }
                break
            }
        }
    }

    if (-not $pyCmd) {
        Write-Warn "未在 PATH 或常用位置找到 Python。"
        Write-Info "正在自动下载并安装 Python $PYTHON_VERSION..."
        
        if (Install-Python) {
            $pyCmd = Get-Command python -ErrorAction SilentlyContinue | Select-Object -First 1
            if (-not $pyCmd) {
                 $stdPath = "C:\Program Files\Python310\python.exe"
                 if (Test-Path $stdPath) {
                     $pyCmd = @{ Source = $stdPath }
                 } else {
                     Write-ErrorMsg "Python 已安装但在 PATH 中未找到。请重启脚本或电脑。"
                     Pause-Exit 1
                 }
            }
        } else {
            Write-ErrorMsg "自动安装失败。"
            Pause-Exit 1
        }
    }
    
    try {
        $PY_VER = & $pyCmd.Source --version 2>&1
        Write-Info "使用 Python 版本: $PY_VER ($($pyCmd.Source))"
    } catch {
        Write-ErrorMsg "无法执行 Python。是否安装正确？"
        Pause-Exit 1
    }

    # 4. 设置虚拟环境 (venv)
    Write-Info "正在设置虚拟环境 (Virtual Environment)..."
    if (Test-Path "$ROOT\.venv") {
        Write-Info "移除旧的虚拟环境以确保干净安装..."
        try {
            Remove-Item -Path "$ROOT\.venv" -Recurse -Force -ErrorAction Stop
        } catch {
            Write-Warn "移除 .venv 失败 (文件被锁定?)。再次尝试清理进程..."
            Stop-Process -Name "python" -Force -ErrorAction SilentlyContinue
            Start-Sleep -Seconds 1
            try {
                Remove-Item -Path "$ROOT\.venv" -Recurse -Force -ErrorAction Stop
            } catch {
                 Write-ErrorMsg "无法删除 .venv 目录。请手动关闭占用该目录的程序。"
                 Write-ErrorMsg $_
                 Pause-Exit 1
            }
        }
    }
    
    Write-Info "正在创建虚拟环境..."
    $venvRes = & $pyCmd.Source -m venv "$ROOT\.venv" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-ErrorMsg "创建虚拟环境失败。"
        Write-ErrorMsg $venvRes
        Pause-Exit 1
    }

    $VENV_PY = "$ROOT\.venv\Scripts\python.exe"
    
    if (-not (Test-Path $VENV_PY)) {
        Write-ErrorMsg "虚拟环境创建失败。未找到 $VENV_PY。"
        Pause-Exit 1
    }

    # 5. 安装依赖
    Write-Info "正在安装依赖包..."
    Write-Info "使用镜像源: $PIP_MIRROR"

    function Run-Pip {
        param($PipArgs)
        $proc = Start-Process -FilePath $VENV_PY -ArgumentList $PipArgs -Wait -PassThru -NoNewWindow
        if ($proc.ExitCode -ne 0) {
            Write-ErrorMsg "Pip 命令执行失败: $PipArgs"
            Pause-Exit 1
        }
    }

    Run-Pip "-m pip install --upgrade pip -i $PIP_MIRROR"
    Run-Pip "-m pip config set global.index-url $PIP_MIRROR"
    Run-Pip "-m pip config set global.trusted-host $PIP_HOST"

    if (Test-Path "$ROOT\requirements.txt") {
        Run-Pip "-m pip install -r `"$ROOT\requirements.txt`""
    } else {
        Run-Pip "-m pip install fastapi `"uvicorn[standard]`" aiosqlite python-multipart aiomysql"
    }

    # 6. 创建启动脚本 (run_service.bat)
    Write-Info "正在创建启动脚本..."
    if (-not (Test-Path "$ROOT\data")) { New-Item -ItemType Directory -Path "$ROOT\data" | Out-Null }

    $BAT_CONTENT = @"
@echo off
cd /d "$ROOT"
call .venv\Scripts\activate.bat
python tools\launcher.py
"@

    Set-Content -Path "$ROOT\run_service.bat" -Value $BAT_CONTENT -Encoding ASCII

    # 7. 创建计划任务 (持久化运行)
    Write-Info "正在创建计划任务 'InfraCountService'..."
    $TaskRun = "$ROOT\run_service.bat"

    Write-Info "清理旧任务..."
    cmd /c "schtasks /delete /tn `"$TaskName`" /f 2>nul" | Out-Null

    Write-Info "注册新任务..."
    # 使用 /ru SYSTEM 以最高权限运行，且开机自启
    $createArgs = "/create /tn `"$TaskName`" /tr `"`"$TaskRun`"`" /sc ONSTART /ru SYSTEM /rl HIGHEST /f"
    $proc = Start-Process schtasks -ArgumentList $createArgs -Wait -PassThru

    if ($proc.ExitCode -eq 0) {
        Write-Info "计划任务创建成功。"
        Write-Info "服务将在下次重启时自动运行。"
        
        Write-Info "正在立即启动服务..."
        schtasks /run /tn "$TaskName"
        Write-Info "服务已启动。"
    } else {
        Write-ErrorMsg "创建计划任务失败。退出代码: $($proc.ExitCode)"
    }

    Write-Info "安装/更新完成！"
    Write-Info "日志文件位于 $ROOT\data\"
    Pause-Exit 0

} catch {
    Write-ErrorMsg "发生未预期的错误:"
    Write-ErrorMsg $_
    Pause-Exit 1
}
