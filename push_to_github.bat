@echo off
chcp 65001 >nul
echo ============================================
echo  GitHub 一键推送脚本
echo ============================================
echo.
echo 前提: 已在 GitHub 添加 SSH 公钥
echo   (打开 https://github.com/settings/keys -> New SSH Key)
echo   粘贴: ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIEWUdlNPIrmkGHH9hC/KXcwbLjzgnnL/CA1Pa6mgspb6
echo.

cd /d "%~dp0"

echo [1/3] 检查 Git 远程仓库...
git remote get-url origin >nul 2>&1
if %errorlevel% neq 0 (
    echo   请先在 GitHub 创建仓库: https://github.com/new
    echo   仓库名: quant-platform
    echo   设为 Public, 不要勾选任何初始化选项
    echo.
    set /p USERNAME="输入你的 GitHub 用户名: "
    git remote add origin git@github.com:%USERNAME%/quant-platform.git
    echo   已添加远程仓库
) else (
    echo   远程仓库已配置
)

echo [2/3] 推送代码到 GitHub...
git push -u origin main 2>&1
if %errorlevel% equ 0 (
    echo.
    echo ============================================
    echo  推送成功!
    echo  你的仓库: https://github.com/你的用户名/quant-platform
    echo ============================================
) else (
    echo.
    echo 推送失败。请确认:
    echo 1. 已在 GitHub 添加 SSH 公钥
    echo 2. 已在 GitHub 创建 quant-platform 仓库
    echo 3. 仓库名和用户名正确
)

echo.
pause
