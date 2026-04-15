@echo off
setlocal

set BACKEND_PORT=8000
set FRONTEND_PORT=5173
set PROJECT_ROOT=%~dp0
set BACKEND_DIR=%PROJECT_ROOT%dashboard\backend
set FRONTEND_DIR=%PROJECT_ROOT%dashboard\frontend

echo === LGA Dashboard Launcher ===
echo.

:: --- Kill backend port if occupied ---
echo [1/4] Checking port %BACKEND_PORT%...
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":%BACKEND_PORT% "') do (
    echo       Port %BACKEND_PORT% occupied by PID %%a, killing...
    taskkill /F /PID %%a >nul 2>&1
)
echo       Port %BACKEND_PORT% free.

:: --- Kill frontend port if occupied ---
echo [2/4] Checking port %FRONTEND_PORT%...
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":%FRONTEND_PORT% "') do (
    echo       Port %FRONTEND_PORT% occupied by PID %%a, killing...
    taskkill /F /PID %%a >nul 2>&1
)
echo       Port %FRONTEND_PORT% free.

:: --- Start backend in new window ---
echo [3/4] Starting backend (port %BACKEND_PORT%)...
start "LGA Backend" cmd /k "cd /d %BACKEND_DIR% && python -m uvicorn main:app --port %BACKEND_PORT%"

:: --- Start frontend in new window ---
echo [4/4] Starting frontend (port %FRONTEND_PORT%)...
start "LGA Frontend" cmd /k "cd /d %FRONTEND_DIR% && npm run dev"

echo.
echo Both services starting in separate windows.
echo   Backend:  http://localhost:%BACKEND_PORT%
echo   Frontend: http://localhost:%FRONTEND_PORT%
echo.
echo Backend takes ~2 minutes to load (293K flights + ML inference).
echo.
pause
