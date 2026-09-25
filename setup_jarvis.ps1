param([switch]$Browser, [switch]$SkipModels, [switch]$CoreOnly)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (Test-Path '.runtime\python\py312') {
    $env:PATH = "$PSScriptRoot\.runtime\python\py312;$PSScriptRoot\.venv\Scripts;$env:PATH"
    if ((Test-Path '.venv\Scripts') -and -not (Test-Path '.venv\Scripts\python312.dll')) {
        Copy-Item (Join-Path $PSScriptRoot '.runtime\python\py312\*.dll') (Join-Path $PSScriptRoot '.venv\Scripts\') -ErrorAction SilentlyContinue
    }
}
$jarvisPython = if (Test-Path ".venv\Scripts\python.exe") { Join-Path $PSScriptRoot '.venv\Scripts\python.exe' } elseif (Test-Path ".runtime\python\py312\python.exe") { Join-Path $PSScriptRoot '.runtime\python\py312\python.exe' } elseif (Test-Path ".venv\Scripts\python312.exe") { Join-Path $PSScriptRoot '.venv\Scripts\python312.exe' } else { $null }
if (-not $jarvisPython) {
    if (Test-Path '.runtime\python\py312\python.exe') {
        & "$PSScriptRoot\.runtime\python\py312\python.exe" -m venv .venv
    } else {
        & py -3.12 -m venv .venv
    }
    if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.12, then run setup again.' }
    $jarvisPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
}
& $jarvisPython -c 'import sys; sys.exit(0 if sys.version_info[:2] == (3, 12) else 1)'
if ($LASTEXITCODE -ne 0) { throw 'This repository requires Python 3.12. Existing environment was preserved.' }

# Core + voice (wake word, speech recognition, VAD, TTS, hotkey) + Windows automation.
# Without the voice extras the wake word can never start, so they are installed by default.
$extras = if ($CoreOnly) { '.' } else { '.[voice,windows]' }
& $jarvisPython -m pip install -e $extras
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed ($extras)." }

if ($Browser) {
    & $jarvisPython -m pip install 'playwright>=1.50,<2' 'Pillow>=11,<13'
    if ($LASTEXITCODE -ne 0) { throw 'Browser dependency installation failed.' }
    & $jarvisPython -m playwright install chromium
    if ($LASTEXITCODE -ne 0) { throw 'Chromium installation failed.' }
}

if (-not $SkipModels -and -not $CoreOnly) {
    # Whisper model.bin, Piper voice, wake word and the configured Ollama models (git ignores the binaries).
    & $jarvisPython scripts\setup_models.py
    if ($LASTEXITCODE -ne 0) { Write-Warning 'Some models could not be prepared; see the messages above (JARVIS falls back where it can).' }
}

& $jarvisPython -m jarvis.diagnostics
if ($LASTEXITCODE -ne 0) { throw 'Diagnostics found a critical failure.' }
Write-Host 'Setup complete. Run start.bat, then say "Hey Jarvis" or press Ctrl+Shift+J.'
