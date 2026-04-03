@echo off
chcp 65001 >nul
echo ========================================
echo   AI Card Game Lab - Backend Server
echo ========================================
echo.

cd /d "%~dp0server"

echo Checking Poetry installation...
where poetry >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Poetry not found. Please install Poetry first.
    echo Run: pip install poetry
    pause
    exit /b 1
)

echo Installing dependencies...
poetry install

echo Creating data directories...
if not exist "%~dp0data\db" mkdir "%~dp0data\db"
if not exist "%~dp0data\games" mkdir "%~dp0data\games"
if not exist "%~dp0data\datasets" mkdir "%~dp0data\datasets"

echo.
echo Starting backend server on http://localhost:8000
echo Press Ctrl+C to stop
echo.

poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
