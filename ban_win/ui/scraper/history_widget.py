"""
Widget lịch sử truyện đã cào lưu trong SQLite.
"""
import os
import subprocess
from PySide6.QtCore import Qt, Signal, QUrl
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget,
    QTableWidgetItem, QHeaderView
)
from PySide6.QtGui import QDesktopServices, QColor
from qfluentwidgets import (
    TableWidget, PushButton, SubtitleLabel, FluentIcon
)
from ban_win.core.database import get_db

class ScrapedHistoryWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 10, 0, 0)
        layout.setSpacing(10)

        header = QHBoxLayout()
        title = SubtitleLabel("Lịch Sử Truyện Đã Cào", self)
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
            "ID", "Tên truyện", "Số chapter", "Dịch EN", "Đăng CMS", "Thư mục lưu"
        ])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setAlternatingRowColors(True)

        self.table.setColumnWidth(0, 45)
        self.table.setColumnWidth(1, 240)
        self.table.setColumnWidth(2, 90)
        self.table.setColumnWidth(3, 85)
        self.table.setColumnWidth(4, 95)
        self.table.horizontalHeader().setStretchLastSection(True)

        self.table.cellDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self.table, 1)

        self.load_history()

    def load_history(self):
        items = get_db().get_scraped_stories(limit=100)
        self.table.setRowCount(len(items))
        self.items_cache = items

        for row_idx, item in enumerate(items):
            # ID
            id_item = QTableWidgetItem(str(item.get("id", "")))
            id_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, 0, id_item)

            # Title
            t_item = QTableWidgetItem(item.get("title", ""))
            t_item.setToolTip(item.get("url", ""))
            self.table.setItem(row_idx, 1, t_item)

            # Chapters count
            c_item = QTableWidgetItem(str(item.get("chapters_count", 0)))
            c_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, 2, c_item)

            # Translated
            tr_item = QTableWidgetItem("✅ Có" if item.get("translated") else "❌ Không")
            tr_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, 3, tr_item)

            # Published
            pub_item = QTableWidgetItem("✅ Có" if item.get("published") else "❌ Không")
            pub_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, 4, pub_item)

            # Output dir
            out_dir = item.get("output_dir", "")
            out_item = QTableWidgetItem(out_dir)
            out_item.setToolTip(out_dir)
            out_item.setForeground(QColor("#15803d") if os.path.isdir(out_dir) else QColor("#ef4444"))
            self.table.setItem(row_idx, 5, out_item)

    def _on_double_click(self, row: int, col: int):
        if row >= len(getattr(self, "items_cache", [])):
            return
        it = self.items_cache[row]
        out_dir = it.get("output_dir", "")
        if out_dir and os.path.isdir(out_dir):
            subprocess.Popen(f'explorer "{out_dir}"')
        elif it.get("url"):
            QDesktopServices.openUrl(QUrl(it.get("url")))
