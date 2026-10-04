"""
Widget danh sách lịch sử các video Facebook đã tải về máy tính từ SQLite.
"""
import os
import subprocess
from PySide6.QtCore import Qt, Signal, QUrl
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget,
    QTableWidgetItem, QHeaderView, QApplication
)
from PySide6.QtGui import QDesktopServices, QColor
from qfluentwidgets import (
    TableWidget, PushButton, PrimaryPushButton, SubtitleLabel,
    CaptionLabel, FluentIcon, RoundMenu, Action
)
from ban_win.core.database import get_db

class DownloadHistoryWidget(QWidget):
    historyUpdated = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 10, 0, 0)
        layout.setSpacing(10)

        header = QHBoxLayout()
        title = SubtitleLabel("Lịch Sử Video Đã Tải", self)
        title.setStyleSheet("font-size: 16px; font-weight: 600;")
        header.addWidget(title)
        header.addStretch()

        self.btn_refresh = PushButton(FluentIcon.SYNC, "Làm mới", self)
        self.btn_refresh.clicked.connect(self.load_history)
        header.addWidget(self.btn_refresh)
        layout.addLayout(header)

        self.table = TableWidget(self)
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "ID", "Tiêu đề video", "Tác giả", "Thời lượng", "Dung lượng", "Đường dẫn file"
        ])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setAlternatingRowColors(True)

        self.table.setColumnWidth(0, 45)
        self.table.setColumnWidth(1, 220)
        self.table.setColumnWidth(2, 130)
        self.table.setColumnWidth(3, 85)
        self.table.setColumnWidth(4, 90)
        self.table.horizontalHeader().setStretchLastSection(True)

        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self.table.cellDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self.table, 1)

        self.load_history()

    def _show_context_menu(self, pos):
        item = self.table.itemAt(pos)
        if not item:
            return
        row = item.row()
        if row >= len(getattr(self, "items_cache", [])):
            return
        it = self.items_cache[row]
        fp = it.get("file_path", "")
        title = it.get("title", "Video")

        menu = RoundMenu(parent=self)

        act_gemini = Action(FluentIcon.CHAT, "✨ Phân tích video với Gemini AI", menu)
        act_gemini.triggered.connect(lambda: self._analyze_gemini(fp, title))
        menu.addAction(act_gemini)

        if fp and os.path.isfile(fp):
            act_folder = Action(FluentIcon.FOLDER, "Mở vị trí file video", menu)
            act_folder.triggered.connect(lambda: subprocess.Popen(f'explorer /select,"{fp}"'))
            menu.addAction(act_folder)

        act_copy_path = Action(FluentIcon.COPY, "Sao chép đường dẫn file", menu)
        act_copy_path.triggered.connect(lambda: QApplication.clipboard().setText(fp))
        menu.addAction(act_copy_path)

        if it.get("url"):
            act_url = Action(FluentIcon.SHARE, "Mở link Facebook gốc", menu)
            act_url.triggered.connect(lambda: QDesktopServices.openUrl(QUrl(it.get("url"))))
            menu.addAction(act_url)

        menu.addSeparator()

        act_del = Action(FluentIcon.DELETE, "Xóa khỏi lịch sử", menu)
        act_del.triggered.connect(lambda: (get_db().delete_downloaded_video(it.get("id")), self.load_history()))
        menu.addAction(act_del)

        menu.exec(QCursor.pos())

    def _analyze_gemini(self, file_path: str, title: str):
        main_win = self.window()
        if hasattr(main_win, "switch_to_gemini"):
            main_win.switch_to_gemini(file_path, title)

    def load_history(self):
        items = get_db().get_downloaded_videos(limit=100)
        self.table.setRowCount(len(items))
        self.items_cache = items

        for row_idx, item in enumerate(items):
            # ID
            id_item = QTableWidgetItem(str(item.get("id", "")))
            id_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, 0, id_item)

            # Title
            t_item = QTableWidgetItem(item.get("title", ""))
            t_item.setToolTip(item.get("title", ""))
            self.table.setItem(row_idx, 1, t_item)

            # Author
            a_item = QTableWidgetItem(item.get("author", ""))
            self.table.setItem(row_idx, 2, a_item)

            # Duration
            d_item = QTableWidgetItem(item.get("duration", ""))
            d_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, 3, d_item)

            # Size
            s_item = QTableWidgetItem(item.get("file_size", ""))
            s_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, 4, s_item)

            # File path
            fp = item.get("file_path", "")
            fp_item = QTableWidgetItem(fp)
            fp_item.setToolTip(fp)
            fp_item.setForeground(QColor("#15803d") if os.path.isfile(fp) else QColor("#ef4444"))
            self.table.setItem(row_idx, 5, fp_item)

    def _on_double_click(self, row: int, col: int):
        if row >= len(getattr(self, "items_cache", [])):
            return
        it = self.items_cache[row]
        fp = it.get("file_path", "")
        if fp and os.path.isfile(fp):
            subprocess.Popen(f'explorer /select,"{fp}"')
        elif it.get("url"):
            QDesktopServices.openUrl(QUrl(it.get("url")))
