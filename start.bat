@echo off
chcp 65001 >nul
title 量化交易平台 v3.0

echo.
echo ╔══════════════════════════════════════════════╗
echo ║     量化交易平台 v3.0  (Python 重写版)      ║
echo ║     多因子Alpha · 组合优化 · 风险归因       ║
echo ╚══════════════════════════════════════════════╝
echo.
echo [1/3] 检查 Python 环境...

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Python, 请先安装 Python 3.9+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [2/3] 安装依赖库...
python -m pip install -r requirements.txt -q 2>nul
echo [2/3] 依赖已就绪

echo [3/3] 启动服务...
echo.
echo     浏览器打开: http://localhost:3000
echo.
echo     按 Ctrl+C 停止服务
echo.

python app.py

pause
