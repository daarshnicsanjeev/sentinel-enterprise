# start_backend.ps1 — Start the Project Sentinel FastAPI backend
# Run this from the project root: .\scripts\start_backend.ps1
#
# NOTE: Uses the Python venv at C:\sanjeev\job-search\.python312
# All backend packages (fastapi, langchain-ollama, faiss-cpu, etc.) are installed there.

param(
    [int]$Port = 8000,
    [switch]$NoReload
)

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $ProjectRoot "backend"

Write-Host ""
Write-Host "=== Project Sentinel — Backend ===" -ForegroundColor Cyan
Write-Host "Directory : $BackendDir"
Write-Host "Port      : $Port"
Write-Host ""

# Check Python
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "Python not found on PATH. Install Python 3.10+ and retry."
    exit 1
}

# Check Ollama is reachable
try {
    $null = Invoke-WebRequest "http://localhost:11434" -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop
    Write-Host "[OK] Ollama is reachable at http://localhost:11434" -ForegroundColor Green
} catch {
    Write-Warning "[WARN] Ollama is not responding at http://localhost:11434."
    Write-Warning "       Start Ollama with: ollama serve"
    Write-Warning "       Then ensure gemma4:e2b is pulled: ollama pull gemma4:e2b"
    Write-Warning "       Continuing anyway — agent calls will fail until Ollama is up."
}

# Check fastapi is installed
$FastapiCheck = python -c "import fastapi; print('ok')" 2>&1
if ($FastapiCheck -ne "ok") {
    Write-Host "Installing backend dependencies..." -ForegroundColor Yellow
    pip install -r "$BackendDir\requirements.txt"
}

Set-Location $BackendDir

$ReloadFlag = if ($NoReload) { "" } else { "--reload" }

Write-Host ""
Write-Host "Starting uvicorn on port $Port ..." -ForegroundColor Green
Write-Host "Health check: http://localhost:$Port/api/health"
Write-Host "API docs    : http://localhost:$Port/docs"
Write-Host "Press Ctrl+C to stop."
Write-Host ""

python -m uvicorn main:app $ReloadFlag --port $Port --host 0.0.0.0
