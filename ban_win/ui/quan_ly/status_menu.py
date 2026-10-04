"""
Menu chọn trạng thái và widget badge hiển thị màu trạng thái cho bảng Quản Lý.
"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PySide6.QtGui import QCursor
from qfluentwidgets import RoundMenu, Action, FluentIcon

VIDEO_STATUS_COLORS = {
    "Xong video": {"bg": "#dcfce7", "text": "#15803d", "border": "#86efac"},
    "Đang tạo video": {"bg": "#fef3c7", "text": "#b45309", "border": "#fde68a"},
    "Xong báo": {"bg": "#cffafe", "text": "#0e7490", "border": "#a5f3fc"},
    "Lấy video": {"bg": "#dbeafe", "text": "#1d4ed8", "border": "#bfdbfe"},
    "không tạo được": {"bg": "#fee2e2", "text": "#b91c1c", "border": "#fca5a5"},
    "bị từ chối": {"bg": "#f3e8ff", "text": "#7e22ce", "border": "#e9d5ff"},
}

POST_STATUS_COLORS = {
    "chưa hoàn thành": {"bg": "#f1f5f9", "text": "#475569", "border": "#cbd5e1"},
    "hoàn thành": {"bg": "#dcfce7", "text": "#15803d", "border": "#86efac"},
    "đăng bài": {"bg": "#e0e7ff", "text": "#4338ca", "border": "#c7d2fe"},
}

VALID_VIDEO_STATUSES = [
    "Xong video",
    "Đang tạo video",
    "Xong báo",
    "Lấy video",
    "không tạo được",
    "bị từ chối"
]

VALID_POST_STATUSES = [
    "chưa hoàn thành",
    "hoàn thành",
    "đăng bài"
]


class StatusBadge(QWidget):
    statusChanged = Signal(str, str)  # (stt, new_status)

    def __init__(self, stt: str, status_type: str, initial_status: str, parent=None):
        super().__init__(parent)
        self.stt = stt
        self.status_type = status_type  # "video" or "post"
        self.current_status = initial_status or ("Lấy video" if status_type == "video" else "chưa hoàn thành")

        self.setCursor(Qt.PointingHandCursor)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 3, 6, 3)
        layout.setAlignment(Qt.AlignCenter)

        self.label = QLabel(self.current_status, self)
        self.label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.label)

        self.update_style()

    def set_status(self, new_status: str):
        self.current_status = new_status
        self.label.setText(new_status)
        self.update_style()

    def update_style(self):
        palette = VIDEO_STATUS_COLORS if self.status_type == "video" else POST_STATUS_COLORS
        color = palette.get(self.current_status, {"bg": "#f8fafc", "text": "#334155", "border": "#e2e8f0"})
        self.setStyleSheet(f"""
            StatusBadge {{
                background-color: {color['bg']};
                border: 1px solid {color['border']};
                border-radius: 6px;
            }}
            QLabel {{
                color: {color['text']};
                font-size: 11px;
                font-weight: 600;
                background: transparent;
            }}
        """)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.show_menu()
        super().mousePressEvent(event)

    def show_menu(self):
        menu = RoundMenu(parent=self)
        options = VALID_VIDEO_STATUSES if self.status_type == "video" else VALID_POST_STATUSES
        for opt in options:
            action = Action(opt, menu)
            if opt == self.current_status:
                action.setIcon(FluentIcon.ACCEPT)
            action.triggered.connect(lambda checked=False, val=opt: self._on_select(val))
            menu.addAction(action)

        menu.exec(QCursor.pos())

    def _on_select(self, val: str):
        if val != self.current_status:
            self.set_status(val)
            self.statusChanged.emit(self.stt, val)
