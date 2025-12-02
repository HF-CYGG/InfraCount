# One-click installer for Windows (Server 2012 R2+)
# Run as Administrator

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

# Configuration
$PYTHON_VERSION = "3.10.11"
$PYTHON_URL = "https://mirrors.huaweicloud.com/python/$PYTHON_VERSION/python-$PYTHON_VERSION-amd64.exe"
$PIP_MIRROR = "https://pypi.tuna.tsinghua.edu.cn/simple"
$PIP_HOST = "pypi.tuna.tsinghua.edu.cn"

function Pause-Exit {
    param($code)
    Write-Host "`nPress Enter to exit..." -NoNewline -ForegroundColor Cyan
    Read-Host
    exit $code
}

function Write-Info { param($msg); Write-Host "[INFO] $msg" -ForegroundColor Green }
function Write-Warn { param($msg); Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-ErrorMsg { param($msg); Write-Host "[ERROR] $msg" -ForegroundColor Red }

function Install-Python {
    Write-Info "Downloading Python $PYTHON_VERSION from Huawei Cloud Mirror..."
    $installerPath = "$env:TEMP\python_installer.exe"
    try {
        Invoke-WebRequest -Uri $PYTHON_URL -OutFile $installerPath -UseBasicParsing
    } catch {
        Write-ErrorMsg "Download failed. Please check your network connection."
        Write-ErrorMsg $_
        return $false
    }

    Write-Info "Installing Python (this may take a minute)..."
    try {
        # Install for all users, add to PATH, disable UI
        $proc = Start-Process -FilePath $installerPath -ArgumentList "/quiet InstallAllUsers=1 PrependPath=1 Include_test=0" -Wait -PassThru
        if ($proc.ExitCode -eq 0) {
            Write-Info "Python installed successfully."
            # Refresh environment variables for the current session
            $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
            return $true
        } else {
            Write-ErrorMsg "Installer exited with code $($proc.ExitCode)."
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
    # 1. Check Admin
    $currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        Write-ErrorMsg "Please run this script as Administrator!"
        Pause-Exit 1
    }

    $ROOT = Split-Path -Parent $MyInvocation.MyCommand.Definition
    Set-Location $ROOT
    Write-Info "Installation Directory: $ROOT"

    # 2. Check Python
    Write-Info "Checking Python..."
    $pyCmd = Get-Command python -ErrorAction SilentlyContinue | Select-Object -First 1
    
    # Attempt to find in common paths if not in PATH
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
        Write-Info "Automatically downloading and installing Python $PYTHON_VERSION..."
        
        if (Install-Python) {
            $pyCmd = Get-Command python -ErrorAction SilentlyContinue | Select-Object -First 1
            if (-not $pyCmd) {
                 # Try to find where it installed (usually C:\Program Files\Python310)
                 $stdPath = "C:\Program Files\Python310\python.exe"
                 if (Test-Path $stdPath) {
                     $pyCmd = @{ Source = $stdPath }
                 } else {
                     Write-ErrorMsg "Python installed but not found in PATH. Please restart the script."
                     Pause-Exit 1
                 }
            }
        } else {
            Write-ErrorMsg "Automatic installation failed."
            Pause-Exit 1
        }
    }
    
    try {
        $PY_VER = & $pyCmd.Source --version 2>&1
        Write-Info "Using $PY_VER ($($pyCmd.Source))"
    } catch {
        Write-ErrorMsg "Failed to execute Python. Is it installed correctly?"
        Pause-Exit 1
    }

    # 2.5 Stop Existing Service to Release File Locks
    Write-Info "Ensuring existing services are stopped..."
    $TaskName = "InfraCountService"
    
    # Stop the scheduled task if it's running
    cmd /c "schtasks /end /tn `"$TaskName`" /f 2>nul" | Out-Null
    
    # Wait for graceful shutdown
    Start-Sleep -Seconds 2
    
    # Force kill any lingering Python processes associated with this project
    # Since identifying exact process is hard in PS2.0 compatible way, we try to delete.
    # If delete fails, we will prompt or force kill all python.
    
    # 3. Setup Virtual Environment
    Write-Info "Setting up Virtual Environment..."
    if (Test-Path "$ROOT\.venv") {
        Write-Info "Removing existing venv to ensure clean state..."
        try {
            Remove-Item -Path "$ROOT\.venv" -Recurse -Force -ErrorAction Stop
        } catch {
            Write-Warn "Failed to remove venv (Files locked?). Attempting to kill Python processes..."
            Stop-Process -Name "python" -Force -ErrorAction SilentlyContinue
            Start-Sleep -Seconds 1
            try {
                Remove-Item -Path "$ROOT\.venv" -Recurse -Force -ErrorAction Stop
            } catch {
                 Write-ErrorMsg "Could not delete .venv directory. Please manually close any programs using it."
                 Write-ErrorMsg $_
                 Pause-Exit 1
            }
        }
    }
    
    Write-Info "Creating venv..."
    $venvRes = & $pyCmd.Source -m venv "$ROOT\.venv" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-ErrorMsg "Failed to create venv."
        Write-ErrorMsg $venvRes
        Pause-Exit 1
    }

    $VENV_PY = "$ROOT\.venv\Scripts\python.exe"
    
    if (-not (Test-Path $VENV_PY)) {
        Write-ErrorMsg "Virtual environment creation failed. $VENV_PY not found."
        Pause-Exit 1
    }

    # 4. Install Dependencies
    Write-Info "Installing Dependencies..."
    Write-Info "Using Mirror: $PIP_MIRROR"

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
        Run-Pip "-m pip install fastapi `"uvicorn[standard]`" aiosqlite python-multipart aiomysql"
    }

    # 5. Create Runner Script (run_service.bat)
    Write-Info "Creating Runner Script..."
    if (-not (Test-Path "$ROOT\data")) { New-Item -ItemType Directory -Path "$ROOT\data" | Out-Null }

    $BAT_CONTENT = @"
@echo off
cd /d "$ROOT"
call .venv\Scripts\activate.bat
python tools\launcher.py
"@

    Set-Content -Path "$ROOT\run_service.bat" -Value $BAT_CONTENT -Encoding ASCII

    # 6. Create Scheduled Task for Persistence
    Write-Info "Creating Scheduled Task 'InfraCountService'..."
    $TaskName = "InfraCountService"
    $TaskRun = "$ROOT\run_service.bat"

    # Use cmd /c to suppress stderr/error from schtasks delete if task doesn't exist
    Write-Info "Cleaning up old tasks..."
    cmd /c "schtasks /delete /tn `"$TaskName`" /f 2>nul" | Out-Null

    Write-Info "Registering new task..."
    # Quote the path to ensure spaces are handled
    $createArgs = "/create /tn `"$TaskName`" /tr `"`"$TaskRun`"`" /sc ONSTART /ru SYSTEM /rl HIGHEST /f"
    $proc = Start-Process schtasks -ArgumentList $createArgs -Wait -PassThru

    if ($proc.ExitCode -eq 0) {
        Write-Info "Scheduled Task created successfully."
        Write-Info "It will run automatically on next reboot."
        
        Write-Info "Starting service now..."
        schtasks /run /tn "$TaskName"
        Write-Info "Service started."
    } else {
        Write-ErrorMsg "Failed to create Scheduled Task. Exit Code: $($proc.ExitCode)"
    }

    Write-Info "Installation Complete."
    Write-Info "Logs are in $ROOT\data\"
    Pause-Exit 0

} catch {
    Write-ErrorMsg "An unexpected error occurred:"
    Write-ErrorMsg $_
    Pause-Exit 1
}
