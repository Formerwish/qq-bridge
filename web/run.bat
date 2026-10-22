@echo off
chcp 65001 >nul
title qq-bridge 控制台
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo [web] 缺少虚拟环境：先执行 python -m venv .venv 并安装 requirements.txt
  pause
  exit /b 1
)
:loop
echo [%date% %time%] 启动控制台...
".venv\Scripts\python.exe" app.py
set code=%errorlevel%
echo [%date% %time%] 控制台退出（code=%code%），3 秒后自动重启；关闭本窗口可停止。
timeout /t 3 /nobreak >nul
goto loop
