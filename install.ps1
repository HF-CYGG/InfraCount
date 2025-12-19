# Windows one-click install/update script (Windows Server 2012 R2+)
# Run this script as Administrator

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

# Settings
$PYTHON_VERSION = "3.10.11"
$PYTHON_URL = "https://mirrors.huaweicloud.com/python/$PYTHON_VERSION/python-$PYTHON_VERSION-amd64.exe"
$PIP_MIRROR = "https://pypi.tuna.tsinghua.edu.cn/simple"
$PIP_HOST = "pypi.tuna.tsinghua.edu.cn"

# Helpers
function Write-Info { param($msg); Write-Host "[INFO] $msg" -ForegroundColor Green }
function Write-Warn { param($msg); Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-ErrorMsg { param($msg); Write-Host "[ERROR] $msg" -ForegroundColor Red }

function Pause-Exit {
    param($code)
    Write-Host "`nPress Enter to exit..." -NoNewline -ForegroundColor Cyan
    Read-Host
    exit $code
}

function Kill-Port-Process {
    param([int]$port)
    Write-Host "Checking port $port..." -ForegroundColor Cyan
    $lines = netstat.exe -ano | Select-String -Pattern ":$port" | ForEach-Object { $_.Line }
    if ($lines) {
        foreach ($line in $lines) {
            $parts = $line.Trim() -split "\s+"
            $pidFound = $parts[-1]
            if ($pidFound -match "^\d+$" -and [int]$pidFound -gt 0) {
                Write-Host "Port $port is used by PID: $pidFound"
                Write-Host "Stopping PID $pidFound..."
                try {
                    Stop-Process -Id $pidFound -Force -ErrorAction SilentlyContinue
                    Write-Host "Process stopped." -ForegroundColor Green
                } catch {
                    Write-Host "Warning: failed to stop PID $pidFound. Manual action may be needed." -ForegroundColor Yellow
                }
            }
        }
    }
}

function Install-Python {
    Write-Info "Downloading Python $PYTHON_VERSION from mirror..."
    $installerPath = "$env:TEMP\python_installer.exe"
    try {
        Invoke-WebRequest -Uri $PYTHON_URL -OutFile $installerPath -UseBasicParsing
    } catch {
        Write-ErrorMsg "Download failed. Please check network connectivity."
        Write-ErrorMsg $_
        return $false
    }

    Write-Info "Installing Python (this may take a minute)..."
    try {
        # Install for all users, add to PATH, silent install
        $proc = Start-Process -FilePath $installerPath -ArgumentList "/quiet InstallAllUsers=1 PrependPath=1 Include_test=0" -Wait -PassThru
        if ($proc.ExitCode -eq 0) {
            Write-Info "Python installed successfully."
            # Refresh PATH in current session
            $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
            return $true
        } else {
            Write-ErrorMsg "Installer exited with code: $($proc.ExitCode)."
            return $false
        }
    } catch {
        Write-ErrorMsg "Failed to run installer."
        Write-ErrorMsg $_
        return $false
    } finally {
        if (Test-Path $installerPath) { Remove-Item $installerPath -Force }
    }
}

try {
    # 1. Check Administrator privilege
    $currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        Write-ErrorMsg "Please run this script as Administrator."
        Pause-Exit 1
    }

    $ROOT = Split-Path -Parent $MyInvocation.MyCommand.Definition
    Set-Location $ROOT
    Write-Info "Install directory: $ROOT"

    # 2. Stop existing task/process and cleanup resources
    Write-Info "Stopping existing services and cleaning up..."
    $TaskName = "InfraCountService"
    
    # Stop scheduled task
    cmd /c "schtasks /end /tn `"$TaskName`" /f 2>nul" | Out-Null
    Start-Sleep -Seconds 2
    
    # Free ports
    Kill-Port-Process 8085 # TCP Server
    Kill-Port-Process 8000 # Web Server

    # 3. Check Python runtime
    Write-Info "Checking Python runtime..."
    $pyCmd = Get-Command python -ErrorAction SilentlyContinue | Select-Object -First 1
    
    # If not in PATH, try common locations
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
                Write-Info "Found Python at $path"
                $pyCmd = @{ Source = $path }
                break
            }
        }
    }

    if (-not $pyCmd) {
        Write-Warn "Python not found in PATH or common locations."
        Write-Info "Attempting to download and install Python $PYTHON_VERSION..."
        
        if (Install-Python) {
            $pyCmd = Get-Command python -ErrorAction SilentlyContinue | Select-Object -First 1
            if (-not $pyCmd) {
                 $stdPath = "C:\Program Files\Python310\python.exe"
                 if (Test-Path $stdPath) {
                     $pyCmd = @{ Source = $stdPath }
                 } else {
                     Write-ErrorMsg "Python installed but not found in PATH. Please rerun the script or reboot."
                     Pause-Exit 1
                 }
            }
        } else {
            Write-ErrorMsg "Automatic install failed."
            Pause-Exit 1
        }
    }
    
    try {
        $PY_VER = & $pyCmd.Source --version 2>&1
        Write-Info "Using Python: $PY_VER ($($pyCmd.Source))"
    } catch {
        Write-ErrorMsg "Unable to execute Python. Is it installed correctly?"
        Pause-Exit 1
    }

    # 4. Setup virtual environment
    Write-Info "Setting up virtual environment..."
    if (Test-Path "$ROOT\.venv") {
        Write-Info "Removing existing virtual environment..."
        try {
            Remove-Item -Path "$ROOT\.venv" -Recurse -Force -ErrorAction Stop
        } catch {
            Write-Warn "Failed to remove .venv (locked?). Retrying after stopping python..."
            Stop-Process -Name "python" -Force -ErrorAction SilentlyContinue
            Start-Sleep -Seconds 1
            try {
                Remove-Item -Path "$ROOT\.venv" -Recurse -Force -ErrorAction Stop
            } catch {
                 Write-ErrorMsg "Unable to delete .venv directory. Please close processes using it."
                 Write-ErrorMsg $_
                 Pause-Exit 1
            }
        }
    }
    
    Write-Info "Creating virtual environment..."
    $venvRes = & $pyCmd.Source -m venv "$ROOT\.venv" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-ErrorMsg "Failed to create virtual environment."
        Write-ErrorMsg $venvRes
        Pause-Exit 1
    }

    $VENV_PY = "$ROOT\.venv\Scripts\python.exe"
    
    if (-not (Test-Path $VENV_PY)) {
        Write-ErrorMsg "Virtual environment not created. Missing: $VENV_PY."
        Pause-Exit 1
    }

    # 5. Install dependencies
    Write-Info "Installing dependencies..."
    Write-Info "Using mirror: $PIP_MIRROR"

    function Run-Pip {
        param($PipArgs)
        $proc = Start-Process -FilePath $VENV_PY -ArgumentList $PipArgs -Wait -PassThru -NoNewWindow
        if ($proc.ExitCode -ne 0) {
            Write-ErrorMsg "Pip command failed: $PipArgs"
            Pause-Exit 1
        }
    }

    Run-Pip "-m pip install --upgrade pip -i $PIP_MIRROR"
    Run-Pip "-m pip config set global.index-url $PIP_MIRROR"
    Run-Pip "-m pip config set global.trusted-host $PIP_HOST"

    if (Test-Path "$ROOT\requirements.txt") {
        Run-Pip "-m pip install -r `"$ROOT\requirements.txt`""
    } else {
        Run-Pip "-m pip install fastapi `"uvicorn[standard]`" aiosqlite python-multipart aiomysql rapidfuzz"
    }

    # 6. Create run script (run_service.bat)
    Write-Info "Creating run script..."
    if (-not (Test-Path "$ROOT\data")) { New-Item -ItemType Directory -Path "$ROOT\data" | Out-Null }

    $BAT_CONTENT = @"
@echo off
cd /d "$ROOT"
".venv\Scripts\python.exe" tools\launcher.py
"@

    Set-Content -Path "$ROOT\run_service.bat" -Value $BAT_CONTENT -Encoding OEM

    # 7. Create scheduled task (run at startup)
    Write-Info "Creating scheduled task 'InfraCountService'..."
    $TaskRun = "$ROOT\run_service.bat"
    
    Write-Info "Removing old task..."
    cmd /c "schtasks /delete /tn `"$TaskName`" /f 2>nul" | Out-Null
    
    Write-Info "Registering new task..."
    # Run as SYSTEM at highest privilege on startup
    $createArgs = "/create /tn `"$TaskName`" /tr `"`"$TaskRun`"`" /sc ONSTART /ru SYSTEM /rl HIGHEST /f"
    $proc = Start-Process schtasks -ArgumentList $createArgs -Wait -PassThru
    
    if ($proc.ExitCode -eq 0) {
        Write-Info "Scheduled task created."
        Write-Info "Service will run on next reboot."
        
        Write-Info "Starting service now..."
        schtasks /run /tn "$TaskName"
        Write-Info "Service started."
    } else {
        Write-ErrorMsg "Failed to create task. Exit code: $($proc.ExitCode)"
    }
    
    Write-Info "Install/update completed."
    Write-Info "Logs are in $ROOT\data\"
    Pause-Exit 0

} catch {
    Write-ErrorMsg "Unexpected error:"
    Write-ErrorMsg $_
    Pause-Exit 1
}
