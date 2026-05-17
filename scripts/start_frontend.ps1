# start_frontend.ps1 — Start the Project Sentinel React/TS frontend
# Run this from the project root: .\scripts\start_frontend.ps1

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$FrontendDir = Join-Path $ProjectRoot "frontend\sentinel-ui"

Write-Host ""
Write-Host "=== Project Sentinel — Frontend ===" -ForegroundColor Cyan
Write-Host "Directory : $FrontendDir"
Write-Host "URL       : http://localhost:5173"
Write-Host ""

# Check Node
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Error "Node.js not found on PATH. Install Node.js 18+ and retry."
    exit 1
}

# Check node_modules
if (-not (Test-Path "$FrontendDir\node_modules")) {
    Write-Host "node_modules not found — running npm install..." -ForegroundColor Yellow
    Set-Location $FrontendDir
    npm install
}

Set-Location $FrontendDir

Write-Host "Starting Vite dev server..." -ForegroundColor Green
Write-Host "Open: http://localhost:5173"
Write-Host "Backend must be running at: http://localhost:8000"
Write-Host "Press Ctrl+C to stop."
Write-Host ""

npm run dev
