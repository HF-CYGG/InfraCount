$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

function Pause-Exit {
    Write-Host "`nPress Enter to exit..." -NoNewline -ForegroundColor Cyan
    Read-Host
    exit
}

$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $ROOT

$VENV_PYTHON = "$ROOT\.venv\Scripts\python.exe"

if (-not (Test-Path $VENV_PYTHON)) {
    Write-Host "[ERROR] Environment not found!" -ForegroundColor Red
    Write-Host "Please run 'install.ps1' first (as Administrator) to install dependencies." -ForegroundColor Yellow
    Pause-Exit
}

# --- Conflict Resolution Start ---
$TaskName = "InfraCountService"
Write-Host "Checking for background service '$TaskName'..." -ForegroundColor Cyan

# Check if task exists and is running
# Using cmd /c to be compatible with older PS versions and avoid exceptions
$taskRunning = $false
$query = cmd /c "schtasks /query /tn `"$TaskName`" /fo LIST 2>nul"
if ($query -match "Status:\s+Running") {
    $taskRunning = $true
}

if ($taskRunning) {
    Write-Host "[WARN] Background service '$TaskName' is running." -ForegroundColor Yellow
    Write-Host "Stopping background service to avoid conflicts..." -ForegroundColor Yellow
    
    # Try to stop it
    cmd /c "schtasks /end /tn `"$TaskName`" 2>nul" | Out-Null
    
    # Wait a bit
    Start-Sleep -Seconds 2
    
    # Check again
    $queryAfter = cmd /c "schtasks /query /tn `"$TaskName`" /fo LIST 2>nul"
    if ($queryAfter -match "Status:\s+Running") {
         Write-Host "[ERROR] Failed to stop background service." -ForegroundColor Red
         Write-Host "Please run this script as Administrator or manually stop the task." -ForegroundColor Red
         Pause-Exit
    } else {
         Write-Host "Background service stopped." -ForegroundColor Green
    }
}

# Check Port 8085 (TCP Server)
$port = 8085
Write-Host "Checking Port $port..." -ForegroundColor Cyan
$netstat = cmd /c "netstat -ano | findstr :$port"
if ($netstat) {
    Write-Host "[WARN] Port $port seems to be in use." -ForegroundColor Yellow
    # Try to parse PID from netstat output (last token)
    # TCP    0.0.0.0:8085           0.0.0.0:0              LISTENING       1234
    $lines = $netstat -split "`r`n"
    foreach ($line in $lines) {
        if ($line -match ":$port\s") {
             $parts = $line.Trim() -split "\s+"
             $pidFound = $parts[-1]
             if ($pidFound -match "^\d+$") {
                 Write-Host "Found process with PID: $pidFound"
                 Write-Host "Attempting to kill PID $pidFound..."
                 try {
                     Stop-Process -Id $pidFound -Force -ErrorAction Stop
                     Write-Host "Process killed." -ForegroundColor Green
                 } catch {
                     Write-Host "[ERROR] Failed to kill process $pidFound. Access Denied?" -ForegroundColor Red
                 }
             }
        }
    }
}
# --- Conflict Resolution End ---

Write-Host "[INFO] Starting InfraCount Services..." -ForegroundColor Green
Write-Host "Logs are being written to data/ directory." -ForegroundColor Gray

try {
    & $VENV_PYTHON "$ROOT\tools\launcher.py"
} catch {
    Write-Host "[ERROR] Launcher exited with error:" -ForegroundColor Red
    Write-Host $_ -ForegroundColor Red
} finally {
    Pause-Exit
}
