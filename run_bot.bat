@echo off
title CoC Bot
cd /d "%~dp0"

echo ===================================================
echo               Iniciando CoC Bot...
echo ===================================================

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" src/main.py %*
) else if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" src/main.py %*
) else (
    python src/main.py %*
)

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] El bot se detuvo con un codigo de error: %ERRORLEVEL%
)

echo.
pause
