@echo off
chcp 65001 >nul
title Scan Story & Video Studio Pro - Windows Edition
cd /d "%~dp0.."

echo ========================================================
echo   SCAN STORY & VIDEO STUDIO PRO - WINDOWS EDITION
echo ========================================================
echo.
echo [*] Đang khởi động ứng dụng Desktop...
echo.

python -m ban_win.main

if %errorlevel% neq 0 (
    echo.
    echo [!] Ứng dụng đã thoát hoặc gặp sự cố!
    echo Vui lòng kiểm tra lại môi trường Python và dependencies:
    echo   pip install -r ban_win\requirements.txt
    echo.
    pause
)
