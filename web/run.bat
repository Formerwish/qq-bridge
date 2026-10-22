@echo off
rem 前台运行：日志直接显示在这个窗口里（同时写 state\web.log）。
rem Ctrl+C 退出。
title qq-bridge 控制台
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo [web] 缺少虚拟环境，请先运行: python -m venv .venv ^&^& .venv\Scripts\python -m pip install -r requirements.txt
  pause
  exit /b 1
)
echo ============================================================
echo  qq-bridge 统一控制台
echo  地址：http://127.0.0.1:21001/   （局域网用本机IP）
echo  日志：本窗口 + ..\state\web.log
echo  关闭本窗口 = 停止控制台（桥接不受影响）；进程退出后窗口自动关闭
echo ============================================================
".venv\Scripts\python.exe" app.py
echo.
echo [web] 控制台已退出（code=%errorlevel%）。按任意键关闭窗口。
pause >nul
