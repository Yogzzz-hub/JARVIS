$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$jarvisPython = $null
if (Test-Path '.venv\Scripts\python.exe') {
    $jarvisPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
} elseif (Test-Path '.venv\Scripts\python312.exe') {
    $jarvisPython = Join-Path $PSScriptRoot '.venv\Scripts\python312.exe'
}

if (-not $jarvisPython) {
    throw 'Virtual environment missing. Run setup_jarvis.ps1.'
}
& $jarvisPython -m jarvis.diagnostics @args
$diagExit = $LASTEXITCODE

Write-Host "`n--- Checking Local Connectors ---" -ForegroundColor Cyan
& $jarvisPython -m jarvis.connectors.status

exit $diagExit

