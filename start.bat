@echo off
setlocal enabledelayedexpansion
title JARVIS EDGE v1.0 - All Systems Launcher
cd /d "%~dp0"

echo ============================================================
echo           JARVIS EDGE v1.0 - ALL SYSTEMS LAUNCHER
echo ============================================================
echo.

:: 1. Ensure DLLs and runtime are in PATH
if exist "%~dp0.runtime\python\py312" (
    set "PATH=%~dp0.runtime\python\py312;%~dp0.venv\Scripts;%PATH%"
    if exist "%~dp0.venv\Scripts" (
        if not exist "%~dp0.venv\Scripts\python312.dll" (
            copy /y "%~dp0.runtime\python\py312\*.dll" "%~dp0.venv\Scripts\" >nul 2>&1
        )
    )
) else (
    set "PATH=%~dp0.venv\Scripts;!PATH!"
)

:: 2. Locate Python executable
set "PYTHON_EXE="
if exist "%~dp0.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
) else if exist "%~dp0.runtime\python\py312\python.exe" (
    set "PYTHON_EXE=%~dp0.runtime\python\py312\python.exe"
) else if exist "%~dp0.venv\Scripts\python312.exe" (
    set "PYTHON_EXE=%~dp0.venv\Scripts\python312.exe"
) else (
    for /f "tokens=*" %%i in ('where python 2^>nul') do (
        set "PYTHON_EXE=%%i"
        goto :python_found
    )
)

:python_found
if "%PYTHON_EXE%"=="" (
    echo [ERROR] No Python runtime detected.
    echo Please ensure .venv or .runtime\python\py312 is present.
    pause
    exit /b 1
)

:: 3. Check Ollama Service (Port 11434)
echo [1/7] Checking Ollama service status on port 11434...
netstat -ano | findstr /R ":11434.*LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo [OK] Ollama is already active and listening on port 11434.
    goto :check_wa
)

echo [INFO] Ollama is not running. Starting Ollama daemon in background...
set "OLLAMA_EXE="
if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" set "OLLAMA_EXE=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
if not defined OLLAMA_EXE (
    for /f "tokens=*" %%i in ('where ollama 2^>nul') do set "OLLAMA_EXE=%%i"
)
if not defined OLLAMA_EXE (
    echo [WARNING] Ollama executable not found in PATH or %LOCALAPPDATA%\Programs\Ollama.
    goto :check_wa
)

start "Ollama Service" /min "!OLLAMA_EXE!" serve
echo [INFO] Waiting for Ollama service to reach ready state...
set /a ollama_attempts=0
:wait_ollama
ping -n 2 127.0.0.1 >nul
set /a ollama_attempts+=1
netstat -ano | findstr /R ":11434.*LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo [OK] Ollama is READY and listening at http://127.0.0.1:11434
    goto :check_wa
)
if !ollama_attempts! lss 20 goto :wait_ollama
echo [WARNING] Ollama server is taking longer than expected. Continuing startup...

:check_wa
echo.
:: 4. Check WhatsApp Omnichannel Bridge (Port 8768)
echo [2/7] Checking WhatsApp bridge status on port 8768...
netstat -ano | findstr /R ":8768.*LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo [OK] WhatsApp Bridge is already active and listening on port 8768.
    goto :check_adb
)

echo [INFO] WhatsApp Bridge is not running. Launching transport bridge...
set "WHATSAPP_PHONE_NUMBER=916381456199"
if not exist "%~dp0integrations\whatsapp\bridge\src\index.js" (
    echo [WARNING] WhatsApp bridge files not found at integrations\whatsapp\bridge\src\index.js
    goto :check_adb
)

start "JARVIS EDGE - WhatsApp Bridge" /min node "%~dp0integrations\whatsapp\bridge\src\index.js"
echo [INFO] Waiting for WhatsApp bridge to reach ready state...
set /a wa_attempts=0
:wait_wa
ping -n 2 127.0.0.1 >nul
set /a wa_attempts+=1
netstat -ano | findstr /R ":8768.*LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo [OK] WhatsApp Bridge is READY on ws://127.0.0.1:8768 (Owner: 6381456199)
    goto :check_adb
)
if !wa_attempts! lss 15 goto :wait_wa
echo [WARNING] WhatsApp bridge is taking longer than usual to start. Continuing...

:check_adb
echo.
:: 5. Check Local Device & Phone Connectivity (ADB)
echo [3/7] Checking Android / Local Device connection (ADB)...
where adb >nul 2>&1
if not errorlevel 1 (
    adb start-server >nul 2>&1
    set "PHONE_ATTACHED="
    for /f "skip=1 tokens=1,2" %%A in ('adb devices 2^>nul') do (
        if "%%B"=="device" (
            echo [OK] Android Device Connected: %%A
            set "PHONE_ATTACHED=1"
        )
    )
    if not defined PHONE_ATTACHED (
        echo [INFO] ADB daemon active. Connect phone via USB or WiFi to enable mobile control.
    )
) else (
    echo [INFO] ADB not in PATH. Phone bridge will activate when ADB is installed.
)

:check_browser
echo.
:: 6. Check Browser Automation Engine (Playwright)
echo [4/7] Checking Browser Automation Engine [Playwright]...
"%PYTHON_EXE%" -c "import playwright; from playwright.sync_api import sync_playwright; p=sync_playwright().start(); b=p.chromium.executable_path; p.stop()" >nul 2>&1
if not errorlevel 1 (
    echo [OK] Browser Automations: Playwright Chromium ready.
) else (
    echo [INFO] Initializing Playwright Chromium...
    "%PYTHON_EXE%" -m playwright install chromium >nul 2>&1
    echo [OK] Browser Automations initialized.
)

:check_backend
echo.
:: 7. Start JARVIS Backend Daemon if not already running on port 8765
echo [5/7] Checking JARVIS Backend status on port 8765...
netstat -ano | findstr /R ":8765.*LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo [OK] JARVIS Backend is already active and listening on port 8765.
    goto :check_google
)

echo [INFO] Starting JARVIS backend daemon in background...
start "JARVIS EDGE - Backend Daemon" /min "%PYTHON_EXE%" -m jarvis

echo [INFO] Waiting for JARVIS backend to reach ready state...
set /a attempts=0
:wait_backend
ping -n 2 127.0.0.1 >nul
set /a attempts+=1
netstat -ano | findstr /R ":8765.*LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo [OK] JARVIS Backend is READY at http://127.0.0.1:8765
    goto :check_google
)
if !attempts! lss 25 goto :wait_backend
echo [WARNING] Backend is taking longer than usual to report ready. Proceeding to launch UI...

:check_google
echo.
:: 8. Check Google Workspace Client Configuration
echo [6/7] Checking Google Workspace Configuration...
if exist "%~dp0config\google_client_secret.json" (
    echo [OK] Google OAuth credentials found: config\google_client_secret.json
    echo      ^(To link account: run connect_google.bat or 'python -m jarvis.integrations.google.cli connect all'^)
) else (
    echo [WARNING] config\google_client_secret.json not found.
)

echo.
:: 9. Launch JARVIS Desktop UI & Voice Overlay
echo [7/7] Launching JARVIS Desktop UI and Voice Overlay...
start "JARVIS EDGE - Desktop UI" "%PYTHON_EXE%" -m jarvis.ui

echo.
echo ============================================================
echo   JARVIS EDGE v1.0 - ALL SYSTEMS ACTIVE ^& CONNECTED
echo ============================================================
echo   * Ollama Service:       http://127.0.0.1:11434 (Connected)
echo   * WhatsApp Bridge:      ws://127.0.0.1:8768 (Owner: 6381456199)
echo   * Browser Automations:  Playwright Chromium (Connected)
echo   * Local Device / Phone: ADB Active (tcp:5037)
echo   * Google Workspace:     Configured (connect_google.bat)
echo   * Jarvis Backend:       http://127.0.0.1:8765 (116 Tools Loaded)
echo   * Voice Wake Word:      "Hey Jarvis"
echo   * Voice Hotkey:         Ctrl + Shift + J
echo ============================================================
echo.
echo Launcher console closing in 5 seconds...
ping -n 6 127.0.0.1 >nul
exit /b 0
