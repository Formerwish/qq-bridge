@echo off
rem 后台运行：不开窗口，日志写到 ..\state\web-console.log（排障时看文件）。
rem 想"看得见日志"请用 run.bat。
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" exit /b 1
start "" /B /D "%~dp0" ".venv\Scripts\pythonw.exe" app.py
