# update.ps1 - Windows One-Click Update Script
# Supports Server 2012 R2+ (PowerShell 4.0+)
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = 'Stop'
$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $ROOT

Write-Host "=== InfraCount Auto Update Script ===" -ForegroundColor Cyan
Write-Host "Working Directory: $ROOT"

# 1. Stop Services
Write-Host ">>> Stopping services..." -ForegroundColor Yellow
try {
    # Find python processes running tcp_server.py or uvicorn
    $procs = Get-WmiObject Win32_Process | Where-Object { 
        ($_.Name -eq "python.exe" -or $_.Name -eq "pythonw.exe") -and 
        ($_.CommandLine -like "*tcp_server.py*" -or $_.CommandLine -like "*uvicorn*") 
    }
    if ($procs) {
        foreach ($p in $procs) {
            Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
            Write-Host "Stopped Process ID: $($p.ProcessId)" -ForegroundColor DarkGray
        }
    } else {
        Write-Host "No running service processes found." -ForegroundColor DarkGray
    }
} catch {
    Write-Warning "Minor error while stopping services: $_"
}
Start-Sleep -Seconds 2

# 2. Backup Data
$dateStr = Get-Date -Format "yyyyMMdd_HHmmss"
$backupDir = "$ROOT\backup_$dateStr"
Write-Host ">>> Backing up critical data to $backupDir ..." -ForegroundColor Yellow
try {
    New-Item -ItemType Directory -Path "$backupDir\data" -Force | Out-Null
    if (Test-Path "$ROOT\data") {
        Copy-Item -Path "$ROOT\data\*" -Destination "$backupDir\data" -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host "Backup completed." -ForegroundColor Green
    } else {
        Write-Warning "Data directory not found, skipping backup."
    }
} catch {
    Write-Error "Backup failed: $_"
    exit 1
}

# 3. Git Pull
Write-Host ">>> Pulling code updates..." -ForegroundColor Yellow
$gitSuccess = $false

# Remote priority: origin -> mirrors
$remotes = @('origin', 'mirror_kgithub', 'mirror_gitclone', 'mirror_ghproxy')
$availableRemotes = git remote
if (-not $availableRemotes) {
    Write-Error "No Git remotes found. Cannot update."
    exit 1
}

foreach ($remote in $remotes) {
    if ($availableRemotes -contains $remote) {
        Write-Host "Attempting pull from '$remote'..." -ForegroundColor Cyan
        try {
            # Stash local changes
            git stash | Out-Null
            
            # Pull main branch
            $proc = Start-Process -FilePath "git" -ArgumentList "pull --tags $remote main" -NoNewWindow -PassThru -Wait
            if ($proc.ExitCode -eq 0) {
                $gitSuccess = $true
                Write-Host "Successfully pulled from $remote!" -ForegroundColor Green
                break
            } else {
                Write-Warning "Failed to pull from $remote (ExitCode: $($proc.ExitCode))"
            }
        } catch {
            Write-Warning "Git operation error: $_"
        }
    }
}

if (-not $gitSuccess) {
    Write-Error "Failed to pull from all remotes. Please check network connection."
    Write-Host "Attempting to restart services..."
    & "$ROOT\start.ps1"
    exit 1
}

# 4. Update Dependencies
Write-Host ">>> Checking and updating dependencies..." -ForegroundColor Yellow
$PY = "$ROOT\.venv\Scripts\python.exe"
if (-not (Test-Path $PY)) {
    Write-Warning "Virtual environment python not found, start.ps1 will handle it."
} else {
    try {
        & $PY -m pip install --upgrade pip | Out-Null
        if (Test-Path "$ROOT\requirements.txt") {
            & $PY -m pip install -r "$ROOT\requirements.txt" | Out-Null
        } else {
            & $PY -m pip install fastapi "uvicorn[standard]" aiosqlite python-multipart rapidfuzz | Out-Null
        }
        Write-Host "Dependencies updated." -ForegroundColor Green
    } catch {
        Write-Warning "Dependency update encountered issues, proceeding to start..."
    }
}

# 5. Restart Services
Write-Host ">>> Restarting services..." -ForegroundColor Yellow
& "$ROOT\start.ps1"

Write-Host "=== Update & Restart Completed ===" -ForegroundColor Green
