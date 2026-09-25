# JARVIS EDGE v1.0 - PowerShell Launcher
$ErrorActionPreference = 'Stop'
$Host.UI.RawUI.WindowTitle = 'JARVIS EDGE v1.0'

Write-Host ''
Write-Host '  ============================================' -ForegroundColor Cyan
Write-Host '    JARVIS EDGE v1.0 - Starting...' -ForegroundColor White
Write-Host '  ============================================' -ForegroundColor Cyan
Write-Host ''

Set-Location -LiteralPath $PSScriptRoot

if (Test-Path '.runtime\python\py312') {
    $env:PATH = "$PSScriptRoot\.runtime\python\py312;$PSScriptRoot\.venv\Scripts;$env:PATH"
    if ((Test-Path '.venv\Scripts') -and -not (Test-Path '.venv\Scripts\python312.dll')) {
        Copy-Item (Join-Path $PSScriptRoot '.runtime\python\py312\*.dll') (Join-Path $PSScriptRoot '.venv\Scripts\') -ErrorAction SilentlyContinue
    }
}

$jarvisPython = $null
if (Test-Path '.venv\Scripts\python.exe') {
    $jarvisPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
} elseif (Test-Path '.runtime\python\py312\python.exe') {
    $jarvisPython = Join-Path $PSScriptRoot '.runtime\python\py312\python.exe'
} elseif (Test-Path '.venv\Scripts\python312.exe') {
    $jarvisPython = Join-Path $PSScriptRoot '.venv\Scripts\python312.exe'
}

if ($jarvisPython) {
    & $jarvisPython -c 'from jarvis.config import load; import fastapi, uvicorn, httpx, numpy, yaml, rapidfuzz; load()'
    if ($LASTEXITCODE -ne 0) { throw 'Startup checks failed. Run setup_jarvis.ps1 or diagnose_jarvis.ps1.' }
    
    # Launch UI process in background if not already open
    Start-Process -FilePath $jarvisPython -ArgumentList '-m', 'jarvis.ui' -WindowStyle Hidden
    
    # Reuse the backend that owns the reserved local port.
    try {
        $jarvisHealth = Invoke-RestMethod -Uri 'http://127.0.0.1:8765/health' -TimeoutSec 2
        if ($jarvisHealth.status -eq 'ready') {
            Write-Host 'JARVIS backend is already running.'
            exit 0
        }
    } catch { }

    # Run primary JARVIS backend in console
    & $jarvisPython -m jarvis
    exit $LASTEXITCODE
} else {
    throw 'Virtual environment missing. Run setup_jarvis.ps1 first.'
}
