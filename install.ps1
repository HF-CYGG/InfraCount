# One-click installer for Windows (Server 2012 R2+)
# Run as Administrator

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

function Write-Info { param($msg); Write-Host "[INFO] $msg" -ForegroundColor Green }
function Write-ErrorMsg { param($msg); Write-Host "[ERROR] $msg" -ForegroundColor Red }

# 1. Check Admin
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-ErrorMsg "Please run this script as Administrator!"
    exit 1
}

$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $ROOT
Write-Info "Installation Directory: $ROOT"

# 2. Check Python
Write-Info "Checking Python..."
$pyCmd = Get-Command python -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $pyCmd) {
    Write-ErrorMsg "Python not found. Please install Python 3.9+ (x64) and add it to PATH."
    Write-Host "Download: https://www.python.org/downloads/"
    exit 1
}
$PY_VER = & $pyCmd.Source --version
Write-Info "Found $PY_VER"

# 3. Setup Virtual Environment
Write-Info "Setting up Virtual Environment..."
if (-not (Test-Path "$ROOT\.venv")) {
    & $pyCmd.Source -m venv "$ROOT\.venv"
}

$VENV_PY = "$ROOT\.venv\Scripts\python.exe"
$VENV_PIP = "$ROOT\.venv\Scripts\pip.exe"

# 4. Install Dependencies
Write-Info "Installing Dependencies..."
$env:PIP_INDEX_URL = 'https://pypi.tuna.tsinghua.edu.cn/simple'
& $VENV_PY -m pip install --upgrade pip -i $env:PIP_INDEX_URL
& $VENV_PY -m pip config set global.index-url $env:PIP_INDEX_URL
& $VENV_PY -m pip config set global.trusted-host pypi.tuna.tsinghua.edu.cn

if (Test-Path "$ROOT\requirements.txt") {
    & $VENV_PY -m pip install -r "$ROOT\requirements.txt"
} else {
    & $VENV_PY -m pip install fastapi "uvicorn[standard]" aiosqlite python-multipart aiomysql
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

# Delete existing task if any
schtasks /delete /tn "$TaskName" /f 2>$null

# Create new task (Runs at system startup, as SYSTEM user)
# ONSTART trigger is robust for servers
schtasks /create /tn "$TaskName" /tr "$TaskRun" /sc ONSTART /ru SYSTEM /rl HIGHEST /f

if ($LASTEXITCODE -eq 0) {
    Write-Info "Scheduled Task created successfully."
    Write-Info "It will run automatically on next reboot."
    
    # Ask to start now
    $resp = Read-Host "Do you want to start the service now? (Y/N)"
    if ($resp -eq 'Y' -or $resp -eq 'y') {
        schtasks /run /tn "$TaskName"
        Write-Info "Service started."
    }
} else {
    Write-ErrorMsg "Failed to create Scheduled Task."
}

Write-Info "Installation Complete."
Write-Info "Logs are in $ROOT\data\"
