@echo off
chcp 65001 >nul
title Đóng gói ScanStoryStudio.exe
cd /d "%~dp0"

echo ========================================================
echo   ĐÓNG GÓI ỨNG DỤNG WINDOWS DESKTOP (PyInstaller)
echo ========================================================
echo.

python build.py

echo.
pause
