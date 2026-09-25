@echo off
setlocal enabledelayedexpansion
title JARVIS EDGE - Google Workspace Authorization
cd /d "%~dp0"

echo ============================================================
echo      JARVIS EDGE - GOOGLE WORKSPACE OAUTH AUTHORIZATION
echo ============================================================
echo.

:: 1. Ensure Python executable is available
set "PYTHON_EXE="
if exist "%~dp0.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
) else if exist "%~dp0.runtime\python\py312\python.exe" (
    set "PYTHON_EXE=%~dp0.runtime\python\py312\python.exe"
) else (
    for /f "tokens=*" %%i in ('where python 2^>nul') do (
        set "PYTHON_EXE=%%i"
        goto :python_found
    )
)

:python_found
if "%PYTHON_EXE%"=="" (
    echo [ERROR] No Python runtime detected.
    pause
    exit /b 1
)

echo Starting browser authentication loopback for Google Services:
echo   - Gmail (Read, Drafts)
echo   - Calendar (Events)
echo   - Google Drive (Files)
echo.
echo Opening system browser now...
echo Please log in and grant the requested permissions.
echo.

"%PYTHON_EXE%" -m jarvis.integrations.google.cli connect all

echo.
echo ============================================================
echo Verification completed. Current Google integration status:
echo ============================================================
"%PYTHON_EXE%" -m jarvis.integrations.google.cli status
echo.
pause
