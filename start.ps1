$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Ensure script runs as UTF-8
if ($PSVersionTable.PSVersion.Major -ge 6) {
    $null = [System.Console]::OutputEncoding = [System.Text.Encoding]::UTF8
}

function Kill-Port-Process {
    param([int]$port)
    Write-Host "Checking port $port..." -ForegroundColor Cyan
    
    # Get PIDs
    $pidsFound = @()
    
    # Method 1: netstat
    $netstatLines = netstat.exe -ano | Select-String -Pattern ":$port\s"
    foreach ($line in $netstatLines) {
        $parts = $line.ToString().Trim() -split "\s+"
        $pidVal = $parts[-1]
        if ($pidVal -match "^\d+$" -and [int]$pidVal -gt 0) {
            $pidsFound += [int]$pidVal
        }
    }

    # Unique
    $pidsFound = $pidsFound | Select-Object -Unique

    if ($pidsFound) {
        foreach ($procId in $pidsFound) {
            Write-Host "Port $port is used by PID: $procId"
            Write-Host "Attempting to kill process $procId..."
            try {
                Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
                Write-Host "Process $procId killed." -ForegroundColor Green
            } catch {
                Write-Host "Warning: Could not kill PID $procId. Manual intervention may be required." -ForegroundColor Yellow
            }
        }
    } else {
        Write-Host "Port $port is free." -ForegroundColor DarkGray
    }
}

function Cleanup-Resources {
    Write-Host "`nInfo: Cleaning up resources..." -ForegroundColor Yellow
    
    # Kill known ports
    Kill-Port-Process 8085 # TCP Server
    Kill-Port-Process 8000 # Web Server
    
    Write-Host "Info: Cleanup complete." -ForegroundColor Green
}

$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $ROOT

$VENV_PYTHON = "$ROOT\.venv\Scripts\python.exe"

if (-not (Test-Path $VENV_PYTHON)) {
    Write-Host "Error: Virtual environment not found!" -ForegroundColor Red
    Write-Host "Please run 'install.ps1' as Administrator first." -ForegroundColor Yellow
    Write-Host "Press Enter to exit..."
    Read-Host
    exit
}

# --- Conflict Resolution ---
$TaskName = "InfraCountService"
try {
    $taskStatus = schtasks.exe /query /tn "$TaskName" /fo CSV 2>$null | ConvertFrom-Csv
    if ($taskStatus.Status -eq "Running") {
        Write-Host "Warning: Background task '$TaskName' is running. Stopping..." -ForegroundColor Yellow
        schtasks.exe /end /tn "$TaskName" 2>$null | Out-Null
        Start-Sleep -Seconds 2
    }
} catch {}

# Initial port check
Kill-Port-Process 8085
Kill-Port-Process 8000

# --- Start Service ---

Write-Host "Info: Starting InfraCount Service..." -ForegroundColor Green
Write-Host "Logs will be written to 'data/' directory." -ForegroundColor Gray
Write-Host "Tip: Press Ctrl+C to stop the service." -ForegroundColor Cyan

try {
    # Start Python launcher
    & $VENV_PYTHON "$ROOT\tools\launcher.py"
} catch {
    Write-Host "`nError: Launcher exited unexpectedly:" -ForegroundColor Red
    Write-Host $_ -ForegroundColor Red
} finally {
    Cleanup-Resources
}

Write-Host "`nPress Enter to exit..." -NoNewline -ForegroundColor Cyan
Read-Host
