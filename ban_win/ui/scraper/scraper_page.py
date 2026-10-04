"""
Trang Cào Truyện & Đăng CMS BlogBio hoàn chỉnh với Fluent Design và Console Log Realtime.
"""
import os
import subprocess
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPlainTextEdit,
    QFormLayout, QFileDialog
)
from qfluentwidgets import (
    LineEdit, CheckBox, SpinBox, DoubleSpinBox, PrimaryPushButton,
    PushButton, ProgressBar, SubtitleLabel, CaptionLabel,
    FluentIcon, CardWidget, InfoBar
)

from ban_win.core.config import Config
from ban_win.workers.scraper_worker import ScraperWorker
from ban_win.ui.widgets.toast import Toast
from .cms_config import CMSConfigWidget
from .history_widget import ScrapedHistoryWidget

class ScraperPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ScraperPage")
        self.worker = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # Header
        top_box = QVBoxLayout()
        title_lbl = SubtitleLabel("Cào Truyện & Tự Động Đăng CMS BlogBio", self)
        title_lbl.setStyleSheet("font-size: 20px; font-weight: 700; color: #1e293b;")
        sub_lbl = CaptionLabel("Cào nội dung chương, dịch thuật sang tiếng Anh, đăng bài trực tiếp lên CMS", self)
        sub_lbl.setStyleSheet("color: #64748b; font-size: 12px;")
        top_box.addWidget(title_lbl)
        top_box.addWidget(sub_lbl)
        layout.addLayout(top_box)

        # 1. Config Card
        config_card = CardWidget(self)
        c_layout = QVBoxLayout(config_card)
        c_layout.setContentsMargins(16, 14, 16, 14)
        c_layout.setSpacing(10)

        # URL Input
        url_row = QHBoxLayout()
        self.in_url = LineEdit(config_card)
        self.in_url.setPlaceholderText("Nhập URL trang truyện (ví dụ: https://...)...")
        self.in_url.setClearButtonEnabled(True)
        url_row.addWidget(self.in_url, 1)
        c_layout.addLayout(url_row)

        # Checkboxes & Options
        opt_row = QHBoxLayout()
        self.chk_images = CheckBox("Tải hình ảnh", config_card)
        self.chk_images.setChecked(True)

        self.chk_translate = CheckBox("Dịch sang tiếng Anh", config_card)
        self.chk_translate.setChecked(True)

        self.chk_publish = CheckBox("Tự động đăng CMS BlogBio", config_card)
        self.chk_publish.setChecked(True)
        self.chk_publish.stateChanged.connect(self._toggle_cms_card)

        opt_row.addWidget(self.chk_images)
        opt_row.addWidget(self.chk_translate)
        opt_row.addWidget(self.chk_publish)
        opt_row.addStretch()
        c_layout.addLayout(opt_row)

        # Range & Delay row
        range_row = QHBoxLayout()
        range_row.addWidget(CaptionLabel("Từ Chapter:", config_card))
        self.spin_start = SpinBox(config_card)
        self.spin_start.setRange(1, 9999)
        self.spin_start.setValue(1)
        range_row.addWidget(self.spin_start)

        range_row.addWidget(CaptionLabel("Đến Chapter (0 = hết):", config_card))
        self.spin_end = SpinBox(config_card)
        self.spin_end.setRange(0, 9999)
        self.spin_end.setValue(0)
        range_row.addWidget(self.spin_end)

        range_row.addWidget(CaptionLabel("Nghỉ (giây):", config_card))
        self.spin_delay = DoubleSpinBox(config_card)
        self.spin_delay.setRange(0.1, 30.0)
        self.spin_delay.setValue(1.0)
        range_row.addWidget(self.spin_delay)

        range_row.addStretch()

        self.btn_start = PrimaryPushButton(FluentIcon.PLAY, "Bắt Đầu Cào Truyện", config_card)
        self.btn_start.clicked.connect(self._start_scraping)
        range_row.addWidget(self.btn_start)

        self.btn_cancel = PushButton(FluentIcon.CANCEL, "Dừng lại", config_card)
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self._cancel_scraping)
        range_row.addWidget(self.btn_cancel)

        c_layout.addLayout(range_row)
        layout.addWidget(config_card)

        # CMS Config Box (hiển thị khi bật đăng CMS)
        self.cms_box = CMSConfigWidget(self)
        self.cms_box.setVisible(True)
        layout.addWidget(self.cms_box)

        # Progress bar
        self.progress_bar = ProgressBar(self)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # 2. Realtime Console Log Terminal
        log_box = QVBoxLayout()
        lbl_console = CaptionLabel("Nhật ký thực thi (Real-time Log):", self)
        lbl_console.setStyleSheet("color: #475569; font-weight: 600;")
        log_box.addWidget(lbl_console)

        self.console_log = QPlainTextEdit(self)
        self.console_log.setReadOnly(True)
        self.console_log.setMaximumHeight(180)
        self.console_log.setStyleSheet("""
            QPlainTextEdit {
                background-color: #0f172a;
                color: #38bdf8;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 12px;
                border-radius: 8px;
                padding: 10px;
                border: 1px solid #1e293b;
            }
        """)
        log_box.addWidget(self.console_log)
        layout.addLayout(log_box)

        # 3. Lịch sử truyện đã cào
        self.history = ScrapedHistoryWidget(self)
        layout.addWidget(self.history, 1)

    def _toggle_cms_card(self, state):
        self.cms_box.setVisible(bool(state))

    def _log(self, text: str):
        self.console_log.appendPlainText(text)
        self.console_log.verticalScrollBar().setValue(
            self.console_log.verticalScrollBar().maximum()
        )

    def _start_scraping(self):
        url = self.in_url.text().strip()
        if not url:
            Toast.warning(self, "Chưa nhập link", "Vui lòng nhập đường link truyện cần cào.")
            return

        self.btn_start.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(5)
        self.console_log.clear()

        start_c = self.spin_start.value()
        end_c = self.spin_end.value()
        end_param = end_c if end_c > 0 else None

        self.worker = ScraperWorker(
            url=url,
            download_images=self.chk_images.isChecked(),
            translate_en=self.chk_translate.isChecked(),
            publish_cms=self.chk_publish.isChecked(),
            cms_url=Config.cms_url(),
            cms_user=Config.cms_user(),
            cms_pass=Config.cms_pass(),
            start_ch=start_c,
            end_ch=end_param,
            delay=self.spin_delay.value(),
            parent=self
        )

        self.worker.logEmitted.connect(self._log)
        self.worker.progressUpdated.connect(lambda pct, st: self.progress_bar.setValue(int(pct)))
        self.worker.scrapeFinished.connect(self._on_scrape_finished)
        self.worker.start()

    def _cancel_scraping(self):
        if self.worker:
            self.worker.cancel()
            self._log("[!] Đang gửi lệnh dừng...")
            self.btn_cancel.setEnabled(False)

    def _on_scrape_finished(self, res: dict):
        self.btn_start.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.progress_bar.setVisible(False)

        if res.get("ok"):
            Toast.success(self, "Hoàn tất!", f"Đã cào {res.get('chapters_scraped', 0)} chapter.")
            self.history.load_history()
        else:
            Toast.error(self, "Lỗi cào truyện", res.get("message", ""))
