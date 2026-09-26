@echo off
chcp 65001 >nul
title Build StoryScraper EXE

:: Tự động tắt StoryScraper nếu đang chạy để không bị khóa file
taskkill /F /IM StoryScraper.exe 2>nul

echo ============================================================
echo   ĐANG ĐÓNG GÓI STORY SCRAPER THÀNH FILE EXE (PyInstaller)
echo ============================================================
echo.

python build.py

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ============================================================
    echo   BUILD THÀNH CÔNG!
    echo   File EXE nằm tại: dist\StoryScraper.exe
    echo ============================================================
) else (
    echo.
    echo [!] Đã xảy ra lỗi trong quá trình build!
)

pause
