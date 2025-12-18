$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Ensure UTF-8 output when possible (PowerShell 5.1 may still read scripts as ANSI without BOM)
if ($PSVersionTable.PSVersion.Major -ge 6) {
    $null = [System.Console]::OutputEncoding = [System.Text.Encoding]::UTF8
}

function Kill-Port-Process {
    param([int]$port)
    Write-Host "Checking port $port..." -ForegroundColor Cyan
    
    # Find PIDs using the port
    $pidsFound = @()
    
    # Use netstat
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
            Write-Host "Stopping PID $procId..."
            try {
                Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
                Write-Host "PID $procId stopped." -ForegroundColor Green
            } catch {
                Write-Host "Warning: failed to stop PID $procId (permission?)" -ForegroundColor Yellow
            }
        }
    } else {
        Write-Host "Port $port is free." -ForegroundColor DarkGray
    }
}

function Cleanup-Resources {
    Write-Host "`nCleaning up..." -ForegroundColor Yellow
    
    # Known ports
    Kill-Port-Process 8085
    Kill-Port-Process 8000
    
    Write-Host "Cleanup done." -ForegroundColor Green
}

$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $ROOT

$VENV_PYTHON = "$ROOT\.venv\Scripts\python.exe"

if (-not (Test-Path $VENV_PYTHON)) {
    Write-Host "Error: virtual environment not found." -ForegroundColor Red
    Write-Host "Run install.ps1 first to install dependencies." -ForegroundColor Yellow
    Write-Host "Press Enter to exit..."
    Read-Host
    exit
}

# --- Optional: stop scheduled task if running ---
$TaskName = "InfraCountService"
try {
    $taskStatus = schtasks.exe /query /tn "$TaskName" /fo CSV 2>$null | ConvertFrom-Csv
    if ($taskStatus.Status -eq "Running") {
        Write-Host "Warning: scheduled task '$TaskName' is running, stopping..." -ForegroundColor Yellow
        schtasks.exe /end /tn "$TaskName" 2>$null | Out-Null
        Start-Sleep -Seconds 2
    }
} catch {}

# Initial port check
Kill-Port-Process 8085
Kill-Port-Process 8000

# --- Start services ---
Write-Host "Starting InfraCount..." -ForegroundColor Green
Write-Host "Logs: data/ directory." -ForegroundColor Gray
Write-Host "To stop: press Ctrl+C or close this window." -ForegroundColor Cyan

try {
    & $VENV_PYTHON "$ROOT\tools\launcher.py"
} catch {
    Write-Host "`nError: launcher exited unexpectedly:" -ForegroundColor Red
    Write-Host $_ -ForegroundColor Red
} finally {
    Cleanup-Resources
}

Write-Host "`nPress Enter to exit..." -NoNewline -ForegroundColor Cyan
Read-Host
