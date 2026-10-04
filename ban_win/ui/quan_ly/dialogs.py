"""
Hộp thoại thêm/sửa dòng, xem Prompt chi tiết, xem Content chi tiết, và đẩy dữ liệu lên Google Sheets.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QFormLayout,
    QPlainTextEdit, QWidget, QApplication
)
from qfluentwidgets import (
    LineEdit, ComboBox, PrimaryPushButton, PushButton,
    SubtitleLabel, CaptionLabel, BodyLabel, FluentIcon
)
from .status_menu import VALID_VIDEO_STATUSES, VALID_POST_STATUSES

class TextViewerDialog(QDialog):
    """Hộp thoại xem và chỉnh sửa văn bản dài (Prompt AI hoặc Content ghép)"""
    def __init__(self, title: str, text: str, editable: bool = True, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(600, 450)
        self.text_result = text

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        header = QHBoxLayout()
        lbl_title = SubtitleLabel(title, self)
        header.addWidget(lbl_title)
        header.addStretch()
        layout.addLayout(header)

        self.edit = QPlainTextEdit(self)
        self.edit.setPlainText(text)
        self.edit.setReadOnly(not editable)
        self.edit.setStyleSheet("""
            QPlainTextEdit {
                font-family: 'Segoe UI', Inter, sans-serif;
                font-size: 13px;
                padding: 10px;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                background-color: #ffffff;
                color: #1e293b;
            }
        """)
        self.edit.textChanged.connect(self._update_counter)
        layout.addWidget(self.edit, 1)

        # Footer
        footer = QHBoxLayout()
        self.lbl_count = CaptionLabel("", self)
        self.lbl_count.setStyleSheet("color: #64748b;")
        footer.addWidget(self.lbl_count)
        self._update_counter()

        footer.addStretch()

        self.btn_copy = PushButton(FluentIcon.COPY, "Sao chép", self)
        self.btn_copy.clicked.connect(self._copy_to_clipboard)
        footer.addWidget(self.btn_copy)

        if editable:
            self.btn_save = PrimaryPushButton("Lưu thay đổi", self)
            self.btn_save.clicked.connect(self._on_save)
            footer.addWidget(self.btn_save)

        self.btn_close = PushButton("Đóng", self)
        self.btn_close.clicked.connect(self.reject)
        footer.addWidget(self.btn_close)

        layout.addLayout(footer)

    def _update_counter(self):
        txt = self.edit.toPlainText()
        chars = len(txt)
        words = len(txt.split()) if txt else 0
        self.lbl_count.setText(f"Số từ: {words} | Ký tự: {chars}")

    def _copy_to_clipboard(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.edit.toPlainText())
        self.btn_copy.setText("Đã chép!")

    def _on_save(self):
        self.text_result = self.edit.toPlainText()
        self.accept()

    def get_text(self) -> str:
        return self.text_result


class RowEditDialog(QDialog):
    """Hộp thoại thêm hoặc sửa dữ liệu một dòng (11 cột chuẩn)"""
    def __init__(self, data: dict = None, parent=None):
        super().__init__(parent)
        is_edit = bool(data and data.get("stt"))
        self.setWindowTitle("Sửa dòng dữ liệu" if is_edit else "Thêm dòng mới")
        self.resize(580, 520)
        self.data = data or {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        header = SubtitleLabel("Thông Tin Chi Tiết Hàng Dữ Liệu", self)
        layout.addWidget(header)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignRight)

        self.in_stt = LineEdit(self)
        self.in_stt.setText(str(self.data.get("stt", "")))
        if is_edit:
            self.in_stt.setReadOnly(True)
        form.addRow("STT (*):", self.in_stt)

        self.cb_v_status = ComboBox(self)
        self.cb_v_status.addItems(VALID_VIDEO_STATUSES)
        v_cur = self.data.get("trang_thai_video", "Lấy video")
        if v_cur in VALID_VIDEO_STATUSES:
            self.cb_v_status.setCurrentText(v_cur)
        form.addRow("Trạng thái video:", self.cb_v_status)

        self.in_bai_goc = LineEdit(self)
        self.in_bai_goc.setText(self.data.get("bai_goc", ""))
        self.in_bai_goc.setPlaceholderText("https://www.facebook.com/reel/...")
        form.addRow("Bài gốc (FB Reel):", self.in_bai_goc)

        self.in_prompt = LineEdit(self)
        self.in_prompt.setText(self.data.get("prompt_video", ""))
        form.addRow("Prompt video:", self.in_prompt)

        self.in_frame = LineEdit(self)
        self.in_frame.setText(self.data.get("frame_dau_tien", ""))
        form.addRow("Frame đầu tiên:", self.in_frame)

        self.in_bao_goc = LineEdit(self)
        self.in_bao_goc.setText(self.data.get("bao_goc", ""))
        form.addRow("Báo gốc:", self.in_bao_goc)

        self.in_bao_moi = LineEdit(self)
        self.in_bao_moi.setText(self.data.get("bao_moi", ""))
        form.addRow("Báo mới:", self.in_bao_moi)

        self.cb_p_status = ComboBox(self)
        self.cb_p_status.addItems(VALID_POST_STATUSES)
        p_cur = self.data.get("trang_thai_dang_bai", "chưa hoàn thành")
        if p_cur in VALID_POST_STATUSES:
            self.cb_p_status.setCurrentText(p_cur)
        form.addRow("Trạng thái đăng:", self.cb_p_status)

        self.in_content = LineEdit(self)
        self.in_content.setText(self.data.get("content", ""))
        form.addRow("Content:", self.in_content)

        self.in_link_video = LineEdit(self)
        self.in_link_video.setText(self.data.get("link_video", ""))
        form.addRow("Link Video:", self.in_link_video)

        self.in_bai_viet = LineEdit(self)
        self.in_bai_viet.setText(self.data.get("bai_viet_da_dang", ""))
        form.addRow("Bài viết đã đăng:", self.in_bai_viet)

        layout.addLayout(form)

        # Footer buttons
        footer = QHBoxLayout()
        footer.addStretch()

        self.btn_cancel = PushButton("Hủy", self)
        self.btn_cancel.clicked.connect(self.reject)
        footer.addWidget(self.btn_cancel)

        self.btn_ok = PrimaryPushButton("Lưu Dữ Liệu", self)
        self.btn_ok.clicked.connect(self._on_submit)
        footer.addWidget(self.btn_ok)

        layout.addLayout(footer)

    def _on_submit(self):
        stt = self.in_stt.text().strip()
        if not stt:
            return
        self.result_data = {
            "stt": stt,
            "trang_thai_video": self.cb_v_status.currentText(),
            "bai_goc": self.in_bai_goc.text().strip(),
            "prompt_video": self.in_prompt.text().strip(),
            "frame_dau_tien": self.in_frame.text().strip(),
            "bao_goc": self.in_bao_goc.text().strip(),
            "bao_moi": self.in_bao_moi.text().strip(),
            "trang_thai_dang_bai": self.cb_p_status.currentText(),
            "content": self.in_content.text().strip(),
            "link_video": self.in_link_video.text().strip(),
            "bai_viet_da_dang": self.in_bai_viet.text().strip(),
        }
        self.accept()

    def get_data(self) -> dict:
        return getattr(self, "result_data", {})
