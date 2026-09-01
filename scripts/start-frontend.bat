@echo off
chcp 65001 >nul
echo ========================================
echo   CardLab - Frontend Server
echo ========================================
echo.

cd /d "%~dp0..\web"

echo Checking Node.js installation...
where node >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js not found. Please install Node.js first.
    pause
    exit /b 1
)

echo Checking dependencies...
if not exist "node_modules" (
    echo Installing dependencies...
    npm install
)

echo.
echo Starting frontend server on http://localhost:5173
echo Press Ctrl+C to stop
echo.

npm run dev
