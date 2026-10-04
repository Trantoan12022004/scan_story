"""
Widget xem trước và phóng to ảnh Frame đầu tiên của video.
"""
import os
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QWidget
from PySide6.QtGui import QPixmap, QDesktopServices
from PySide6.QtCore import QUrl
from qfluentwidgets import PrimaryPushButton, PushButton, SubtitleLabel, CaptionLabel, FluentIcon

class FramePreviewDialog(QDialog):
    def __init__(self, image_path: str, stt: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Xem ảnh Frame - STT {stt}" if stt else "Xem ảnh Frame")
        self.resize(650, 480)
        self.image_path = image_path

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Header
        header = QHBoxLayout()
        title = SubtitleLabel(f"Ảnh Frame Đầu Tiên (STT: {stt})", self)
        header.addWidget(title)
        header.addStretch()
        layout.addLayout(header)

        # Image display container
        self.img_label = QLabel(self)
        self.img_label.setAlignment(Qt.AlignCenter)
        self.img_label.setStyleSheet("""
            QLabel {
                background-color: #0f172a;
                border-radius: 8px;
                border: 1px solid #e2e8f0;
            }
        """)
        self.img_label.setMinimumSize(600, 360)

        self._load_image()
        layout.addWidget(self.img_label, 1)

        # Footer actions
        footer = QHBoxLayout()
        self.path_lbl = CaptionLabel(image_path or "Không có đường dẫn ảnh", self)
        self.path_lbl.setStyleSheet("color: #64748b;")
        footer.addWidget(self.path_lbl, 1)

        if os.path.isfile(image_path):
            self.btn_open = PushButton(FluentIcon.FOLDER, "Mở file", self)
            self.btn_open.clicked.connect(self._open_file)
            footer.addWidget(self.btn_open)

        self.btn_close = PrimaryPushButton("Đóng", self)
        self.btn_close.clicked.connect(self.accept)
        footer.addWidget(self.btn_close)

        layout.addLayout(footer)

    def _load_image(self):
        if self.image_path and os.path.isfile(self.image_path):
            pixmap = QPixmap(self.image_path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(580, 340, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.img_label.setPixmap(scaled)
                return
        self.img_label.setText("Không thể hiển thị ảnh hoặc file không tồn tại.")
        self.img_label.setStyleSheet("color: #94a3b8; font-size: 14px; background-color: #1e293b; border-radius: 8px;")

    def _open_file(self):
        if os.path.isfile(self.image_path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.image_path))
