"""
Main application entry point for ban_win Desktop Application.
Scan Story & Video Studio Pro - Windows Native Edition.
"""
import os
import sys

# Ensure project root is in sys.path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

# Fix UTF-8 encoding for Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from qfluentwidgets import setTheme, Theme

from ban_win.core.database import get_db
from ban_win.ui.main_window import MainWindow

def main():
    # Kích hoạt High DPI scaling cho màn hình 2K/4K Windows
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("ScanStoryStudio")
    app.setOrganizationName("ScanStory")

    # Đặt theme Sáng (Light) mặc định theo yêu cầu người dùng
    setTheme(Theme.LIGHT)

    # Khởi tạo SQLite database (tự động tạo bảng & migrate dữ liệu nếu có)
    db = get_db()

    # Khởi tạo cửa sổ chính Fluent Design
    window = MainWindow()
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
