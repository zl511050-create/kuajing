@echo off
title FastMoss Agent Hub

:: 检查 Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ============================================================
    echo [ERROR] Python is not installed or not in system PATH!
    echo [错误] 未检测到 Python，请先安装 Python 3.9 以上版本。
    echo.
    echo IMPORTANT / 关键提示:
    echo When installing Python, MUST CHECK: "Add python.exe to PATH"
    echo 安装 Python 时，必须勾选: "Add python.exe to PATH"
    echo.
    echo Download link / 官网下载: https://www.python.org/downloads/
    echo ============================================================
    echo.
    pause
    exit /b 1
)

echo Starting FastMoss Server on port 8688...
echo Please open your browser: http://127.0.0.1:8688
echo ============================================================
python server.py 8688

pause
