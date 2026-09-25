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

echo [1/3] Python Runtime: "%PYTHON_EXE%"
"%PYTHON_EXE%" --version
echo.

:: 3. Start JARVIS Backend Daemon if not already running on port 8765
echo [2/3] Checking JARVIS Backend status on port 8765...
netstat -ano | findstr /R ":8765.*LISTENING" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Starting JARVIS backend daemon in background...
    start "JARVIS EDGE - Backend Daemon" /min "%PYTHON_EXE%" -m jarvis
    
    echo [INFO] Waiting for JARVIS backend to reach ready state...
    set /a attempts=0
    :wait_backend
    ping -n 2 127.0.0.1 >nul
    set /a attempts+=1
    netstat -ano | findstr /R ":8765.*LISTENING" >nul 2>&1
    if errorlevel 1 (
        if !attempts! lss 25 (
            goto wait_backend
        ) else (
            echo [WARNING] Backend is taking longer than usual to report ready. Proceeding to launch UI...
        )
    ) else (
        echo [OK] JARVIS Backend is READY at http://127.0.0.1:8765
    )
) else (
    echo [OK] JARVIS Backend is already active and listening on port 8765.
)
echo.

:: 4. Launch JARVIS Desktop UI & Voice Overlay
echo [3/3] Launching JARVIS Desktop UI and Voice Overlay...
start "JARVIS EDGE - Desktop UI" "%PYTHON_EXE%" -m jarvis.ui

echo.
echo ============================================================
echo   JARVIS EDGE is successfully launched!
echo.
echo   * Voice Wake Word: "Hey Jarvis" (Sensitivity: 0.35)
echo   * Voice Overlay Hotkey: Ctrl + Shift + J
echo   * Voice Switching: "Change your voice to female" / "male"
echo   * Dashboard: Opens automatically on wake word or tray icon
echo   * Backend Gateway: http://127.0.0.1:8765
echo ============================================================
echo.
echo Closing launcher in 5 seconds...
ping -n 6 127.0.0.1 >nul
exit /b 0
