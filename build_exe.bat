@echo off
chcp 65001 >nul
title Build StoryScraper EXE
echo ============================================================
echo   ĐANG ĐÓNG GÓI STORY SCRAPER THÀNH FILE EXE (PyInstaller)
echo ============================================================
echo.

pyinstaller --noconfirm --onefile --console ^
  --name "StoryScraper" ^
  --add-data "templates;templates" ^
  --hidden-import "parsers" ^
  --hidden-import "parsers.base" ^
  --hidden-import "parsers.treeiq" ^
  --hidden-import "parsers.ahcms" ^
  --hidden-import "downloader" ^
  --hidden-import "translator" ^
  --hidden-import "publisher" ^
  --hidden-import "license_manager" ^
  --hidden-import "bs4" ^
  --hidden-import "lxml" ^
  app.py

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
