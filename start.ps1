[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = 'Stop'
$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $ROOT
if (-not (Test-Path "$ROOT\data")) { New-Item -ItemType Directory -Path "$ROOT\data" | Out-Null }
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$pyCmd = (Get-Command python -ErrorAction SilentlyContinue | Select-Object -First 1)
if (-not $pyCmd) { $pyCmd = (Get-Command python3 -ErrorAction SilentlyContinue | Select-Object -First 1) }
if (-not $pyCmd) { Write-Host "Python not found. Please install Python 3.9+ (x64) and add to PATH." -ForegroundColor Red; exit 1 }
$PY = "$ROOT\.venv\Scripts\python.exe"
if (-not (Test-Path "$ROOT\.venv")) { & $pyCmd.Source -m venv "$ROOT\.venv" }
& $PY -m ensurepip --upgrade
$env:PIP_INDEX_URL = $env:PIP_INDEX_URL; if ([string]::IsNullOrEmpty($env:PIP_INDEX_URL)) { $env:PIP_INDEX_URL = 'https://pypi.tuna.tsinghua.edu.cn/simple' }
& $PY -m pip install --upgrade pip -i $env:PIP_INDEX_URL
& $PY -m pip config set global.index-url $env:PIP_INDEX_URL
& $PY -m pip config set global.trusted-host pypi.tuna.tsinghua.edu.cn
if (Test-Path "$ROOT\requirements.txt") { & $PY -m pip install -i $env:PIP_INDEX_URL -r "$ROOT\requirements.txt" } else { & $PY -m pip install fastapi "uvicorn[standard]" aiosqlite python-multipart -i $env:PIP_INDEX_URL }
if ($env:DB_DRIVER -eq 'mysql') { & $PY -m pip install aiomysql -i $env:PIP_INDEX_URL }
Start-Process -FilePath $PY -ArgumentList "$ROOT\tcp_server.py" -NoNewWindow -RedirectStandardOutput "$ROOT\data\tcp_server.out" -RedirectStandardError "$ROOT\data\tcp_server.err"
Start-Process -FilePath $PY -ArgumentList "-m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000" -NoNewWindow -RedirectStandardOutput "$ROOT\data\uvicorn.out" -RedirectStandardError "$ROOT\data\uvicorn.err"
Write-Host "Services started. TCP on ${env:TCP_PORT}:8085 (default), Web/API on http://127.0.0.1:8000" -ForegroundColor Green
Write-Host "Please open http://127.0.0.1:8000/dashboard in your browser" -ForegroundColor Yellow
