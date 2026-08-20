@echo off
echo ========================================
echo    DeepinReader - Quick Start
echo ========================================
echo.

REM Start API server (port 8001)
start "API Server" cmd /k "cd /d %~dp0 && python -m uvicorn api:app --host 0.0.0.0 --port 8001"

REM Wait for API server to start (max 30s)
echo Waiting for API server to start...
set /a count=0
:wait_api
timeout /t 2 /nobreak >nul
set /a count+=1
netstat -ano | findstr :8001 | findstr LISTENING >nul
if not errorlevel 1 goto api_started
if %count% lss 15 goto wait_api

echo [ERROR] API server start timeout (30s), please check the log window
pause
exit /b 1

:api_started
echo [OK] API server started

echo.
echo [2/2] Starting frontend dev server (port 3000)...

REM Start frontend dev server
start "Frontend Dev" cmd /k "cd /d %~dp0\frontend && npm run dev"

REM Wait for frontend server to start
echo Waiting for frontend server to start...
set /a count=0
:wait_frontend
timeout /t 2 /nobreak >nul
set /a count+=1
netstat -ano | findstr :3000 | findstr LISTENING >nul
if not errorlevel 1 goto frontend_started
if %count% lss 15 goto wait_frontend

echo [WARN] Frontend server is slow to start, please open browser manually later
goto open_browser

:frontend_started
echo [OK] Frontend server started

:open_browser
echo.
echo ========================================
echo    All services started!
echo ========================================
echo.
echo API Server : http://localhost:8001
echo API Docs   : http://localhost:8001/docs
echo Frontend   : http://localhost:3000
echo.
echo Opening browser...
timeout /t 2 /nobreak >nul

start http://localhost:3000

echo.
echo Press any key to close this window (services will keep running)...
pause >nul
