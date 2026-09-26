@echo off
chcp 65001 >nul
title Build StoryScraper - Admin ^& User Version
cls

echo ============================================================
echo      STORY SCRAPER - ĐÓNG GÓI 2 PHIÊN BẢN EXE
echo ============================================================
echo   [1] Build CẢ 2 PHIÊN BẢN (StoryScraper_User ^& StoryScraper_Admin)
echo   [2] Chỉ Build bản USER (Dành cho khách hàng)
echo   [3] Chỉ Build bản ADMIN (Dành cho Quản trị viên)
echo ============================================================
set /p opt="Vui lòng nhập lựa chọn (1/2/3) [Mặc định 1]: "

if "%opt%"=="2" (
    echo.
    echo Đang build bản User...
    python build.py --target user
) else if "%opt%"=="3" (
    echo.
    echo Đang build bản Admin...
    python build.py --target admin
) else (
    echo.
    echo Đang build cả 2 phiên bản...
    python build.py --target all
)

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ============================================================
    echo   🎉 QUÁ TRÌNH BUILD HOÀN TẤT THÀNH CÔNG!
    echo   Thư mục chứa file EXE: dist\
    echo ============================================================
) else (
    echo.
    echo [!] Đã xảy ra lỗi trong quá trình build!
)

pause
