@echo off
chcp 65001 >nul
echo ========================================
echo   无限AI工作流系统 V2
echo   文字生成像素图片模型
echo ========================================
echo.

set PYTHON_PATH=C:\Users\24141\python-sdk\python3.10.16\python.exe
set WORK_DIR=%~dp0

cd /d %WORK_DIR%

echo Python: %PYTHON_PATH%
echo 工作目录: %WORK_DIR%
echo.

%PYTHON_PATH% scripts\infinite_loop_v2.py

pause
