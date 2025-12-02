$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $ROOT

$VENV_PYTHON = "$ROOT\.venv\Scripts\python.exe"

if (-not (Test-Path $VENV_PYTHON)) {
    Write-Host "[ERROR] Environment not found!" -ForegroundColor Red
    Write-Host "Please run 'install.ps1' first (as Administrator) to install dependencies." -ForegroundColor Yellow
    exit 1
}

Write-Host "[INFO] Starting InfraCount Services..." -ForegroundColor Green
& $VENV_PYTHON "$ROOT\tools\launcher.py"
