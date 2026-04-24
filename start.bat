@echo off
chcp 65001 >nul
echo ========================================
echo    DeepinReader - 一键启动
echo ========================================
echo.

REM 启动 API 服务器 (端口8001，与前端配置一致)
start "API Server" cmd /k "cd /d %~dp0 && python -m uvicorn api:app --host 0.0.0.0 --port 8001"

REM 等待 API 服务器启动（最多等待30秒）
echo 等待 API 服务器启动...
set /a count=0
:wait_api
timeout /t 2 /nobreak >nul
set /a count+=1
netstat -ano | findstr :8001 | findstr LISTENING >nul
if not errorlevel 1 goto api_started
if %count% lss 15 goto wait_api

echo [错误] API服务器启动超时（30秒），请检查日志窗口
pause
exit /b 1

:api_started
echo [OK] API 服务器已启动

echo.
echo [2/2] 启动前端开发服务器 (端口3000)...

REM 启动前端开发服务器
start "Frontend Dev" cmd /k "cd /d %~dp0\frontend && npm run dev"

REM 等待前端服务器启动
echo 等待前端服务器启动...
set /a count=0
:wait_frontend
timeout /t 2 /nobreak >nul
set /a count+=1
netstat -ano | findstr :3000 | findstr LISTENING >nul
if not errorlevel 1 goto frontend_started
if %count% lss 15 goto wait_frontend

echo [警告] 前端服务器启动较慢，请稍后手动打开浏览器
goto open_browser

:frontend_started
echo [OK] 前端服务器已启动

:open_browser
echo.
echo ========================================
echo    服务启动成功！
echo ========================================
echo.
echo API 服务器: http://localhost:8001
echo API 文档:   http://localhost:8001/docs
echo 前端界面:   http://localhost:3000
echo.
echo 浏览器即将自动打开...
timeout /t 2 /nobreak >nul

start http://localhost:3000

echo.
echo 按任意键退出此窗口（服务会继续运行）...
pause >nul
