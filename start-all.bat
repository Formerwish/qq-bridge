@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ============================================================
echo  qq-bridge 一键启动：桥接 + Flask 控制台
echo  - 已在运行的组件会自动跳过
echo  - 桥接与控制台各开一个窗口，关闭窗口即停止对应组件（控制台退出会自动重启）
echo ============================================================
echo.

netstat -ano | findstr "LISTENING" | findstr ":3100 " >nul
if errorlevel 1 (
  echo [start-all] 启动桥接...
  start "qq-bridge 桥接" /D "%~dp0" cmd /k "start.bat"
) else (
  echo [start-all] 桥接已在运行（3100），跳过。
)

netstat -ano | findstr "LISTENING" | findstr ":21001 " >nul
if errorlevel 1 (
  echo [start-all] 启动控制台...
  start "qq-bridge 控制台" /D "%~dp0web" cmd /k "run.bat"
) else (
  echo [start-all] 控制台已在运行（21001），跳过。
)

echo.
echo [start-all] 完成。浏览器打开：http://127.0.0.1:21001/
echo [start-all] 日志：桥接 state\bridge.log；控制台窗口内 + state\web-console.log
echo.
ping -n 5 127.0.0.1 >nul
endlocal
