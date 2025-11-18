$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
if (-not (Get-Command py -ErrorAction SilentlyContinue) -and -not (Get-Command python -ErrorAction SilentlyContinue)) {
  if (Get-Command winget -ErrorAction SilentlyContinue) { winget install --silent --exact Python.Python.3 | Out-Null }
  elseif (Get-Command choco -ErrorAction SilentlyContinue) { choco install python -y | Out-Null }
  else { Write-Host "Python 3 not found. Please install from https://www.python.org/downloads/"; exit 1 }
}
Write-Host "Setting up Python virtual environment..."
if (Get-Command py -ErrorAction SilentlyContinue) { & py -3 -m venv .venv } else { python -m venv .venv }
$py = Join-Path $root ".venv\Scripts\python.exe"
& $py -m ensurepip --upgrade
Write-Host "Upgrading pip..."
$mirror = if ($env:PIP_INDEX_URL -and $env:PIP_INDEX_URL -ne "") { $env:PIP_INDEX_URL } else { "https://pypi.tuna.tsinghua.edu.cn/simple" }
& $py -m pip install --upgrade pip -i $mirror
Write-Host "Installing dependencies..."
& $py -m pip install fastapi "uvicorn[standard]" aiosqlite -i $mirror
if ($env:DB_DRIVER -and $env:DB_DRIVER.ToLower() -eq "mysql") { & $py -m pip install aiomysql -i $mirror }
if (-not $env:DB_SQLITE_PATH -or $env:DB_SQLITE_PATH -eq "") { $env:DB_SQLITE_PATH = (Join-Path $root "data\infrared.db") }
New-Item -ItemType Directory -Force -Path (Join-Path $root "data") | Out-Null
Write-Host "Starting TCP server..."
Start-Process -FilePath $py -ArgumentList "tcp_server.py" -WorkingDirectory $root
Write-Host "Starting API and Web server..."
Start-Process -FilePath $py -ArgumentList "-m","uvicorn","api.main:app","--reload","--host","127.0.0.1","--port","8000" -WorkingDirectory $root
Write-Host "Services started. TCP on $(if ($env:TCP_PORT) { $env:TCP_PORT } else { "8085" }), Web/API on 127.0.0.1:8000"
Write-Host "Please open http://127.0.0.1:8000/dashboard in your browser"