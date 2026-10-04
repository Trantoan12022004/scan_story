"""
Cửa sổ chính của ứng dụng Windows ban_win sử dụng SplitFluentWindow (Fluent Design).
"""
import os
import sys
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon
from qfluentwidgets import (
    SplitFluentWindow, FluentIcon, NavigationItemPosition,
    setTheme, Theme, setThemeColor
)

from ban_win.ui.quan_ly import QuanLyPage
from ban_win.ui.downloader import DownloaderPage
from ban_win.ui.gemini import GeminiPage
from ban_win.ui.scraper import ScraperPage
from ban_win.ui.license import LicensePage
from ban_win.ui.settings import SettingsPage

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class MainWindow(SplitFluentWindow):
    def __init__(self):
        super().__init__()
        self.init_window()

        # Tạo các trang giao diện con
        self.quan_ly_page = QuanLyPage(self)
        self.downloader_page = DownloaderPage(self)
        self.gemini_page = GeminiPage(self)
        self.scraper_page = ScraperPage(self)
        self.license_page = LicensePage(self)
        self.settings_page = SettingsPage(self)

        self.init_navigation()

    def init_window(self):
        self.setWindowTitle("Scan Story & Video Studio Pro - Windows Edition")
        self.resize(1280, 820)
        self.setMinimumSize(1040, 680)

        # Cài đặt màu chủ đạo & giao diện Sáng mặc định
        setTheme(Theme.LIGHT)
        setThemeColor("#6366f1")

        # Cài đặt icon nếu có
        icon_path = os.path.join(APP_DIR, "assets", "app_icon.ico")
        if os.path.isfile(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # Canh giữa màn hình
        desktop = self.screen().availableGeometry()
        w, h = desktop.width(), desktop.height()
        self.move(int((w - self.width()) / 2), int((h - self.height()) / 2))

    def init_navigation(self):
        # 1. Quản Lý Tiến Độ
        self.addSubInterface(
            self.quan_ly_page,
            FluentIcon.TILES,
            "Quản Lý Video",
            position=NavigationItemPosition.TOP
        )

        # 2. Tải Video Facebook
        self.addSubInterface(
            self.downloader_page,
            FluentIcon.DOWNLOAD,
            "Tải Video FB",
            position=NavigationItemPosition.TOP
        )

        # 3. Gemini AI Phân Tích Video
        self.addSubInterface(
            self.gemini_page,
            FluentIcon.CHAT,
            "Gemini AI Video",
            position=NavigationItemPosition.TOP
        )

        # 4. Cào Truyện & CMS
        self.addSubInterface(
            self.scraper_page,
            FluentIcon.BOOK_SHELF,
            "Cào Truyện & CMS",
            position=NavigationItemPosition.TOP
        )

        # 5. Bản Quyền HWID (ở góc dưới)
        self.addSubInterface(
            self.license_page,
            FluentIcon.CERTIFICATE,
            "Bản Quyền",
            position=NavigationItemPosition.BOTTOM
        )

        # 6. Cài Đặt (ở góc dưới)
        self.addSubInterface(
            self.settings_page,
            FluentIcon.SETTING,
            "Cài Đặt",
            position=NavigationItemPosition.BOTTOM
        )

    def switch_to_gemini(self, video_path: str = "", video_title: str = ""):
        """Chuyển sang Tab Gemini và nạp context video"""
        if video_path:
            self.gemini_page.set_active_video(video_path, video_title)
        self.switchTo(self.gemini_page)

    def closeEvent(self, event):
        # Dừng luồng đồng bộ ngầm khi đóng cửa sổ
        if hasattr(self, "quan_ly_page"):
            self.quan_ly_page.closeEvent(event)
        super().closeEvent(event)
