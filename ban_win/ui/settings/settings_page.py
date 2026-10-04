"""
Trang Cài Đặt Ứng Dụng, Quản Lý Cấu Hình & Prompt AI Mẫu.
"""
import os
import subprocess
from PySide6.QtCore import Qt, QUrl
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFormLayout,
    QFileDialog, QTableWidget, QTableWidgetItem, QHeaderView,
    QDialog, QPlainTextEdit, QApplication
)
from PySide6.QtGui import QDesktopServices
from qfluentwidgets import (
    LineEdit, SpinBox, SwitchButton, PrimaryPushButton,
    PushButton, TableWidget, SubtitleLabel, CaptionLabel,
    BodyLabel, FluentIcon, CardWidget, setTheme, Theme
)

from ban_win.core.config import Config
from ban_win.core.database import get_db
from ban_win.core.updater import check_for_updates, get_current_version
from ban_win.workers.update_worker import UpdateWorker
from ban_win.ui.widgets.toast import Toast

class PromptEditDialog(QDialog):
    def __init__(self, name: str = "", content: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Chỉnh sửa Prompt AI" if name else "Thêm Prompt AI mới")
        self.resize(540, 400)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        form = QFormLayout()
        self.in_name = LineEdit(self)
        self.in_name.setText(name)
        form.addRow("Tên Prompt:", self.in_name)
        layout.addLayout(form)

        layout.addWidget(CaptionLabel("Nội dung Prompt template:", self))
        self.in_content = QPlainTextEdit(self)
        self.in_content.setPlainText(content)
        self.in_content.setStyleSheet("""
            QPlainTextEdit {
                font-family: 'Segoe UI', Inter, sans-serif;
                font-size: 13px;
                padding: 8px;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
            }
        """)
        layout.addWidget(self.in_content, 1)

        btn_box = QHBoxLayout()
        btn_box.addStretch()
        btn_cancel = PushButton("Hủy", self)
        btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(btn_cancel)

        btn_save = PrimaryPushButton("Lưu", self)
        btn_save.clicked.connect(self._on_save)
        btn_box.addWidget(btn_save)
        layout.addLayout(btn_box)

    def _on_save(self):
        if not self.in_name.text().strip():
            return
        self.accept()

    def get_data(self):
        return {
            "name": self.in_name.text().strip(),
            "content": self.in_content.toPlainText().strip()
        }


class SettingsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SettingsPage")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # Header
        top_box = QVBoxLayout()
        title_lbl = SubtitleLabel("Cài Đặt Hệ Thống", self)
        title_lbl.setStyleSheet("font-size: 20px; font-weight: 700; color: #1e293b;")
        sub_lbl = CaptionLabel("Quản lý đường dẫn lưu trữ, kết nối Google Sheets, Prompt AI và cập nhật", self)
        sub_lbl.setStyleSheet("color: #64748b; font-size: 12px;")
        top_box.addWidget(title_lbl)
        top_box.addWidget(sub_lbl)
        layout.addLayout(top_box)

        # 1. Card Đường dẫn & Google Sheets
        sync_card = CardWidget(self)
        s_layout = QVBoxLayout(sync_card)
        s_layout.setContentsMargins(18, 16, 18, 16)
        s_layout.setSpacing(12)

        lbl_s_title = SubtitleLabel("Thư Mục & Đồng Bộ Google Sheets", sync_card)
        lbl_s_title.setStyleSheet("font-size: 16px; font-weight: 600;")
        s_layout.addWidget(lbl_s_title)

        form = QFormLayout()
        form.setSpacing(10)

        # Video dir
        vdir_box = QHBoxLayout()
        self.in_vdir = LineEdit(sync_card)
        self.in_vdir.setText(Config.video_dir())
        vdir_box.addWidget(self.in_vdir, 1)
        self.btn_vdir = PushButton(FluentIcon.FOLDER, "Chọn...", sync_card)
        self.btn_vdir.clicked.connect(self._browse_vdir)
        vdir_box.addWidget(self.btn_vdir)
        form.addRow("Thư mục video mặc định:", vdir_box)

        # Sheet ID
        self.in_sheet_id = LineEdit(sync_card)
        self.in_sheet_id.setText(Config.google_sheet_id())
        form.addRow("Google Sheet ID:", self.in_sheet_id)

        # Webhook URL
        self.in_webhook = LineEdit(sync_card)
        self.in_webhook.setText(Config.webhook_url())
        self.in_webhook.setPlaceholderText("https://script.google.com/macros/s/.../exec")
        form.addRow("Apps Script Webhook URL:", self.in_webhook)

        # Interval
        int_box = QHBoxLayout()
        self.spin_interval = SpinBox(sync_card)
        self.spin_interval.setRange(2, 60)
        self.spin_interval.setValue(Config.sync_interval())
        int_box.addWidget(self.spin_interval)
        int_box.addWidget(CaptionLabel("giây (chu kỳ tự động kéo dữ liệu từ Google Sheets)", sync_card))
        int_box.addStretch()
        form.addRow("Chu kỳ đồng bộ:", int_box)

        s_layout.addLayout(form)

        btn_save_sync = PrimaryPushButton(FluentIcon.SAVE, "Lưu Cài Đặt", sync_card)
        btn_save_sync.clicked.connect(self._save_sync_settings)
        s_layout.addWidget(btn_save_sync, alignment=Qt.AlignLeft)

        layout.addWidget(sync_card)

        # 2. Card Quản Lý Prompt AI
        prompt_card = CardWidget(self)
        p_layout = QVBoxLayout(prompt_card)
        p_layout.setContentsMargins(18, 16, 18, 16)
        p_layout.setSpacing(10)

        p_header = QHBoxLayout()
        lbl_p_title = SubtitleLabel("Quản Lý Mẫu Prompt Video AI", prompt_card)
        lbl_p_title.setStyleSheet("font-size: 16px; font-weight: 600;")
        p_header.addWidget(lbl_p_title)
        p_header.addStretch()

        self.btn_add_prompt = PushButton(FluentIcon.ADD, "Thêm Prompt Mới", prompt_card)
        self.btn_add_prompt.clicked.connect(self._add_prompt)
        p_header.addWidget(self.btn_add_prompt)
        p_layout.addLayout(p_header)

        self.prompt_table = TableWidget(prompt_card)
        self.prompt_table.setColumnCount(3)
        self.prompt_table.setHorizontalHeaderLabels(["ID", "Tên Prompt", "Nội dung"])
        self.prompt_table.setColumnWidth(0, 45)
        self.prompt_table.setColumnWidth(1, 160)
        self.prompt_table.horizontalHeader().setStretchLastSection(True)
        self.prompt_table.verticalHeader().setVisible(False)
        self.prompt_table.setMaximumHeight(140)
        self.prompt_table.cellDoubleClicked.connect(self._edit_prompt_row)
        p_layout.addWidget(self.prompt_table)

        layout.addWidget(prompt_card)

        # 3. Card Phiên Bản & Cập Nhật
        ver_card = CardWidget(self)
        v_layout = QHBoxLayout(ver_card)
        v_layout.setContentsMargins(18, 14, 18, 14)
        v_layout.setSpacing(14)

        ver_info = QVBoxLayout()
        self.lbl_ver = SubtitleLabel(f"Phiên bản ứng dụng: v{get_current_version()}", ver_card)
        self.lbl_ver.setStyleSheet("font-size: 15px; font-weight: 600;")
        self.lbl_ver_sub = CaptionLabel("Nền tảng Windows Desktop Fluent Design 64-bit", ver_card)
        self.lbl_ver_sub.setStyleSheet("color: #64748b;")
        ver_info.addWidget(self.lbl_ver)
        ver_info.addWidget(self.lbl_ver_sub)
        v_layout.addLayout(ver_info, 1)

        self.btn_check_update = PushButton(FluentIcon.SYNC, "Kiểm Tra Bản Mới", ver_card)
        self.btn_check_update.clicked.connect(self._check_update)
        v_layout.addWidget(self.btn_check_update)

        layout.addWidget(ver_card)
        layout.addStretch()

        self._load_prompts()

    def _browse_vdir(self):
        folder = QFileDialog.getExistingDirectory(self, "Chọn thư mục video mặc định", self.in_vdir.text())
        if folder:
            self.in_vdir.setText(folder)

    def _save_sync_settings(self):
        Config.set_video_dir(self.in_vdir.text().strip())
        Config.set_google_sheet_id(self.in_sheet_id.text().strip())
        Config.set_webhook_url(self.in_webhook.text().strip())
        Config.set_sync_interval(self.spin_interval.value())
        Toast.success(self, "Đã lưu cài đặt", "Cấu hình hệ thống và đồng bộ đã được cập nhật thành công!")

    def _load_prompts(self):
        prompts = get_db().get_all_prompts()
        self.prompt_table.setRowCount(len(prompts))
        self.prompt_cache = prompts

        for r_idx, p in enumerate(prompts):
            id_item = QTableWidgetItem(str(p.get("id", "")))
            id_item.setTextAlignment(Qt.AlignCenter)
            self.prompt_table.setItem(r_idx, 0, id_item)

            name_item = QTableWidgetItem(p.get("name", ""))
            self.prompt_table.setItem(r_idx, 1, name_item)

            cnt_item = QTableWidgetItem(p.get("content", "").replace("\n", " "))
            self.prompt_table.setItem(r_idx, 2, cnt_item)

    def _add_prompt(self):
        dlg = PromptEditDialog(parent=self)
        if dlg.exec():
            data = dlg.get_data()
            get_db().save_prompt(data["name"], data["content"])
            Toast.success(self, "Thành công", f"Đã thêm Prompt '{data['name']}'")
            self._load_prompts()

    def _edit_prompt_row(self, row: int, col: int):
        if row >= len(getattr(self, "prompt_cache", [])):
            return
        p = self.prompt_cache[row]
        dlg = PromptEditDialog(p.get("name", ""), p.get("content", ""), parent=self)
        if dlg.exec():
            data = dlg.get_data()
            get_db().save_prompt(data["name"], data["content"], prompt_id=p.get("id"))
            Toast.success(self, "Thành công", f"Đã cập nhật Prompt '{data['name']}'")
            self._load_prompts()

    def _check_update(self):
        self.btn_check_update.setEnabled(False)
        Toast.info(self, "Kiểm tra", "Đang kết nối GitHub kiểm tra phiên bản mới...")

        self.up_worker = UpdateWorker(parent=self)
        self.up_worker.updateChecked.connect(self._on_update_result)
        self.up_worker.start()

    def _on_update_result(self, res: dict):
        self.btn_check_update.setEnabled(True)
        if res.get("has_update"):
            Toast.success(
                self,
                "Có bản mới!",
                f"Phiên bản mới v{res.get('latest_version')} đã sẵn sàng tải về!\n{res.get('changelog')}",
                duration=6000
            )
            if res.get("download_url"):
                QDesktopServices.openUrl(QUrl(res.get("download_url")))
        else:
            Toast.info(
                self,
                "Phiên bản mới nhất",
                f"Bạn đang sử dụng phiên bản v{res.get('current_version')} mới nhất!"
            )
