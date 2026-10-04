"""
Stat cards component for Quản Lý Tiến Độ with modern Fluent Design and 1-click filter.
"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel
from qfluentwidgets import CardWidget, SubtitleLabel, CaptionLabel, BodyLabel, IconWidget, FluentIcon

class StatCard(CardWidget):
    filterClicked = Signal(str)

    def __init__(self, key: str, title: str, count: int, icon: FluentIcon, color_accent: str, parent=None):
        super().__init__(parent)
        self.key = key
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(84)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(14)

        # Icon wrapper with soft colored background
        self.icon_box = QWidget(self)
        self.icon_box.setFixedSize(48, 48)
        self.icon_box.setStyleSheet(f"""
            QWidget {{
                background-color: {color_accent}1A;
                border-radius: 10px;
            }}
        """)
        icon_layout = QVBoxLayout(self.icon_box)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_layout.setAlignment(Qt.AlignCenter)
        self.icon_widget = IconWidget(icon, self.icon_box)
        self.icon_widget.setFixedSize(24, 24)
        icon_layout.addWidget(self.icon_widget)

        layout.addWidget(self.icon_box)

        # Text labels
        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 2, 0, 2)
        text_layout.setSpacing(2)

        self.title_lbl = CaptionLabel(title, self)
        self.title_lbl.setStyleSheet("color: #64748b; font-size: 12px; font-weight: 500;")

        self.val_lbl = SubtitleLabel(str(count), self)
        self.val_lbl.setStyleSheet(f"color: {color_accent}; font-size: 22px; font-weight: 700;")

        text_layout.addWidget(self.title_lbl)
        text_layout.addWidget(self.val_lbl)
        layout.addLayout(text_layout)
        layout.addStretch()

    def set_count(self, count: int):
        self.val_lbl.setText(str(count))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.filterClicked.emit(self.key)
        super().mousePressEvent(event)


class StatCardsWidget(QWidget):
    filterRequested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self.card_total = StatCard("all", "Tổng số hàng", 0, FluentIcon.TILES, "#6366f1", self)
        self.card_done = StatCard("video_done", "Xong video", 0, FluentIcon.ACCEPT, "#10b981", self)
        self.card_file = StatCard("has_file", "File sẵn sàng", 0, FluentIcon.FOLDER, "#06b6d4", self)
        self.card_post = StatCard("post_done", "Đã hoàn thành", 0, FluentIcon.SEND, "#f59e0b", self)

        self.card_total.filterClicked.connect(self.filterRequested.emit)
        self.card_done.filterClicked.connect(self.filterRequested.emit)
        self.card_file.filterClicked.connect(self.filterRequested.emit)
        self.card_post.filterClicked.connect(self.filterRequested.emit)

        layout.addWidget(self.card_total)
        layout.addWidget(self.card_done)
        layout.addWidget(self.card_file)
        layout.addWidget(self.card_post)

    def update_stats(self, stats: dict):
        self.card_total.set_count(stats.get("total", 0))
        self.card_done.set_count(stats.get("video_done", 0))
        self.card_file.set_count(stats.get("has_file", 0))
        self.card_post.set_count(stats.get("post_done", 0))
