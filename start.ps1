param(
    [int]$WebPort = 8000,
    [int]$TcpPort = 8085,
    [switch]$ForceKillPorts,
    [switch]$ResetLogs,
    [switch]$NoBrowser
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

if ($PSVersionTable.PSVersion.Major -ge 6) {
    $null = [System.Console]::OutputEncoding = [System.Text.Encoding]::UTF8
}

function Pause-Exit {
    param([int]$code)
    $canPause = $false
    try {
        $null = $Host.UI.RawUI
        $canPause = [Environment]::UserInteractive
    } catch {}
    if ($Host -and $Host.Name -eq "ConsoleHost") { $canPause = $true }
    if (($env:INFRACOUNT_NO_PAUSE -as [string]).Trim() -eq "1") { $canPause = $false }
    if ($canPause) {
        Write-Host "`nPress Enter to exit..." -NoNewline -ForegroundColor Cyan
        Read-Host
    }
    exit $code
}

function Get-PortPids {
    param([int]$Port)
    $pidsFound = @()
    $netstatLines = netstat.exe -ano | Select-String -Pattern ":$Port\s"
    foreach ($line in $netstatLines) {
        $parts = $line.ToString().Trim() -split "\s+"
        $pidVal = $parts[-1]
        if ($pidVal -match "^\d+$" -and [int]$pidVal -gt 0) {
            $pidsFound += [int]$pidVal
        }
    }
    return ($pidsFound | Select-Object -Unique)
}

function Get-ProcessDetails {
    param([int]$ProcessId)
    try {
        $p = Get-CimInstance Win32_Process -Filter "ProcessId=$ProcessId" -ErrorAction Stop
        return @{
            Name = $p.Name
            ExecutablePath = $p.ExecutablePath
            CommandLine = $p.CommandLine
        }
    } catch {
        try {
            $p2 = Get-Process -Id $ProcessId -ErrorAction Stop
            return @{
                Name = $p2.ProcessName
                ExecutablePath = $null
                CommandLine = $null
            }
        } catch {
            return @{
                Name = $null
                ExecutablePath = $null
                CommandLine = $null
            }
        }
    }
}

function Stop-PortOwnerIfSafe {
    param(
        [int]$Port,
        [string]$RootDir,
        [string]$VenvPython,
        [switch]$Force
    )
    Write-Host "Checking port $Port..." -ForegroundColor Cyan
    $pids = Get-PortPids $Port
    if (-not $pids -or $pids.Count -eq 0) {
        Write-Host "Port $Port is free." -ForegroundColor DarkGray
        return $true
    }

    $blocked = $false
    foreach ($portPid in $pids) {
        $d = Get-ProcessDetails $portPid
        $exe = [string]($d.ExecutablePath)
        $cmd = [string]($d.CommandLine)
        $isInfraCount = $false
        if ($exe -and $VenvPython -and ($exe -ieq $VenvPython)) { $isInfraCount = $true }
        if (-not $isInfraCount -and $cmd -and $RootDir -and ($cmd -like "*$RootDir*")) { $isInfraCount = $true }
        if (-not $isInfraCount -and $cmd) {
            if ($cmd -like "*tcp_server.py*") { $isInfraCount = $true }
            if ($cmd -like "*-m uvicorn*" -and $cmd -like "*api.main:app*") { $isInfraCount = $true }
            if ($cmd -like "*tools\\launcher.py*") { $isInfraCount = $true }
        }
        if ($Force -or $isInfraCount) {
            Write-Host "Port $Port is used by PID: $portPid ($($d.Name))"
            Write-Host "Stopping PID $portPid..."
            try {
                Stop-Process -Id $portPid -Force -ErrorAction SilentlyContinue
                Write-Host "PID $portPid stopped." -ForegroundColor Green
            } catch {
                Write-Host "Warning: failed to stop PID $portPid (permission?)" -ForegroundColor Yellow
                $blocked = $true
            }
        } else {
            Write-Host "Port $Port is occupied by PID: $portPid ($($d.Name))" -ForegroundColor Yellow
            if ($exe) { Write-Host "Executable: $exe" -ForegroundColor Yellow }
            if ($cmd) { Write-Host "CommandLine: $cmd" -ForegroundColor Yellow }
            $blocked = $true
        }
    }

    if ($blocked) { return $false }
    Start-Sleep -Milliseconds 600
    $pids2 = Get-PortPids $Port
    return (-not $pids2 -or $pids2.Count -eq 0)
}

function Find-FreePort {
    param([int]$StartPort, [int]$MaxTries = 50)
    for ($i = 0; $i -lt $MaxTries; $i++) {
        $p = $StartPort + $i
        $pids = Get-PortPids $p
        if (-not $pids -or $pids.Count -eq 0) { return $p }
    }
    return $null
}

function Cleanup-Resources {
    Write-Host "`nCleaning up..." -ForegroundColor Yellow
    
    # Known ports
    $null = Stop-PortOwnerIfSafe -Port $TcpPort -RootDir $ROOT -VenvPython $VENV_PYTHON -Force:$ForceKillPorts
    $null = Stop-PortOwnerIfSafe -Port $WebPort -RootDir $ROOT -VenvPython $VENV_PYTHON -Force:$ForceKillPorts
    
    Write-Host "Cleanup done." -ForegroundColor Green
}

$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $ROOT

$VENV_PYTHON = "$ROOT\.venv\Scripts\python.exe"

function Resolve-SystemPython {
    $pyCmd = Get-Command python -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($pyCmd -and $pyCmd.Source) { return $pyCmd.Source }

    $commonPaths = @(
        "C:\Python310\python.exe",
        "C:\Program Files\Python310\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe",
        "C:\Python39\python.exe",
        "C:\Program Files\Python39\python.exe"
    )
    foreach ($p in $commonPaths) {
        if (Test-Path $p) { return $p }
    }
    return $null
}

function Test-PythonRunnable {
    param([string]$PythonPath)
    if (-not $PythonPath) { return $false }
    if (-not (Test-Path $PythonPath)) { return $false }
    $cmd = "`"$PythonPath`" -c `"import sys;print(sys.executable)`" >nul 2>nul"
    cmd /c $cmd | Out-Null
    return ($LASTEXITCODE -eq 0)
}

function Ensure-VenvPython {
    if (Test-PythonRunnable $VENV_PYTHON) { return $true }

    $sysPy = Resolve-SystemPython
    if (-not (Test-PythonRunnable $sysPy)) { return $false }

    if (Test-Path "$ROOT\.venv") {
        try {
            Remove-Item -Path "$ROOT\.venv" -Recurse -Force -ErrorAction Stop
        } catch {
            Stop-Process -Name "python" -Force -ErrorAction SilentlyContinue
            Start-Sleep -Milliseconds 800
            Remove-Item -Path "$ROOT\.venv" -Recurse -Force -ErrorAction Stop
        }
    }

    & $sysPy -m venv "$ROOT\.venv" *> $null
    if (-not (Test-PythonRunnable $VENV_PYTHON)) { return $false }
    return $true
}

function Ensure-VenvDeps {
    $checkCmd = "`"$VENV_PYTHON`" -c `"import fastapi,uvicorn,aiosqlite,aiomysql,multipart,rapidfuzz;print('ok')`" >nul 2>nul"
    cmd /c $checkCmd | Out-Null
    if ($LASTEXITCODE -eq 0) { return $true }

    Write-Host "Virtual environment packages missing, installing..." -ForegroundColor Yellow
    $pipMirror = "https://pypi.tuna.tsinghua.edu.cn/simple"
    $pipHost = "pypi.tuna.tsinghua.edu.cn"
    try {
        & $VENV_PYTHON -m pip install --upgrade pip -i $pipMirror --trusted-host $pipHost *> $null
    } catch {}

    if (Test-Path "$ROOT\requirements.txt") {
        & $VENV_PYTHON -m pip install -r "$ROOT\requirements.txt" -i $pipMirror --trusted-host $pipHost
    } else {
        & $VENV_PYTHON -m pip install fastapi "uvicorn[standard]" aiosqlite aiomysql python-multipart rapidfuzz -i $pipMirror --trusted-host $pipHost
    }

    cmd /c $checkCmd | Out-Null
    return ($LASTEXITCODE -eq 0)
}

try {
    if (-not (Ensure-VenvPython)) {
        Write-Host "Error: virtual environment python is missing or not runnable." -ForegroundColor Red
        Write-Host "Please install Python on this machine and run install.ps1 to create .venv." -ForegroundColor Yellow
        Pause-Exit 1
    }

    if (-not (Ensure-VenvDeps)) {
        Write-Host "Error: failed to prepare required python packages in .venv." -ForegroundColor Red
        Pause-Exit 1
    }

    $TaskName = "InfraCountService"
    try {
        $taskStatus = schtasks.exe /query /tn "$TaskName" /fo CSV 2>$null | ConvertFrom-Csv
        if ($taskStatus.Status -eq "Running") {
            Write-Host "Warning: scheduled task '$TaskName' is running, stopping..." -ForegroundColor Yellow
            schtasks.exe /end /tn "$TaskName" 2>$null | Out-Null
            if ($LASTEXITCODE -ne 0) {
                Write-Host "Warning: failed to stop scheduled task '$TaskName'. Try running PowerShell as Administrator." -ForegroundColor Yellow
            }
            Start-Sleep -Seconds 2
        }
    } catch {}

    $env:TCP_PORT = "$TcpPort"
    $env:WEB_PORT = "$WebPort"
    if ($NoBrowser) { $env:INFRACOUNT_NO_BROWSER = "1" } else { $env:INFRACOUNT_NO_BROWSER = "0" }
    if ($ResetLogs) { $env:INFRACOUNT_RESET_LOGS = "1" } else { $env:INFRACOUNT_RESET_LOGS = "0" }

    $tcpOk = Stop-PortOwnerIfSafe -Port $TcpPort -RootDir $ROOT -VenvPython $VENV_PYTHON -Force:$ForceKillPorts
    if (-not $tcpOk) {
        Write-Host "Error: port $TcpPort is in use by another process." -ForegroundColor Red
        Write-Host "Tip: run with -ForceKillPorts to forcibly free ports." -ForegroundColor Yellow
        Pause-Exit 1
    }

    $webOk = Stop-PortOwnerIfSafe -Port $WebPort -RootDir $ROOT -VenvPython $VENV_PYTHON -Force:$ForceKillPorts
    if (-not $webOk) {
        $free = Find-FreePort -StartPort ($WebPort + 1)
        if ($free) {
            Write-Host "Port $WebPort is busy, switching to $free." -ForegroundColor Yellow
            $WebPort = $free
            $env:WEB_PORT = "$WebPort"
        } else {
            Write-Host "Error: no free web port found near $WebPort." -ForegroundColor Red
            Pause-Exit 1
        }
    }

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

    Pause-Exit 0
} catch {
    Write-Host "`nError: start.ps1 crashed:" -ForegroundColor Red
    Write-Host $_ -ForegroundColor Red
    try { Cleanup-Resources } catch {}
    Pause-Exit 1
}
