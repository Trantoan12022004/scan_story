"""
Trang Tải Video Facebook Reels & Videos với Fluent Design.
Hỗ trợ probe thông tin, chọn chất lượng HD/SD/Audio, báo tiến trình realtime, và chuyển tiếp sang Gemini AI.
"""
import os
import subprocess
import requests
from PySide6.QtCore import Qt, QUrl
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFileDialog,
    QFormLayout, QFrame
)
from PySide6.QtGui import QPixmap, QDesktopServices
from qfluentwidgets import (
    LineEdit, ComboBox, PrimaryPushButton, PushButton,
    ProgressBar, SubtitleLabel, CaptionLabel, BodyLabel,
    FluentIcon, CardWidget
)

from ban_win.core.config import Config
from ban_win.core.fb_downloader import probe_facebook_video
from ban_win.workers.download_worker import DownloadWorker
from ban_win.ui.widgets.toast import Toast
from .download_history import DownloadHistoryWidget
from .video_player import VideoPlayerDialog

class DownloaderPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DownloaderPage")
        self.probed_data = None
        self.last_downloaded_file = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # Header
        top_box = QVBoxLayout()
        title_lbl = SubtitleLabel("Tải Video Facebook Reels & Videos", self)
        title_lbl.setStyleSheet("font-size: 20px; font-weight: 700; color: #1e293b;")
        sub_lbl = CaptionLabel("Tải video Full HD / HD / SD / Tách nhạc MP3 và chuyển sang Gemini AI phân tích kịch bản", self)
        sub_lbl.setStyleSheet("color: #64748b; font-size: 12px;")
        top_box.addWidget(title_lbl)
        top_box.addWidget(sub_lbl)
        layout.addLayout(top_box)

        # 1. Input Box Card
        input_card = CardWidget(self)
        input_layout = QVBoxLayout(input_card)
        input_layout.setContentsMargins(16, 14, 16, 14)
        input_layout.setSpacing(10)

        url_row = QHBoxLayout()
        self.in_url = LineEdit(input_card)
        self.in_url.setPlaceholderText("Dán link video hoặc Facebook Reel vào đây (ví dụ: https://www.facebook.com/reel/...)...")
        self.in_url.setClearButtonEnabled(True)
        url_row.addWidget(self.in_url, 1)

        self.btn_probe = PrimaryPushButton(FluentIcon.SEARCH, "Phân Tích Video", input_card)
        self.btn_probe.clicked.connect(self._probe_video)
        url_row.addWidget(self.btn_probe)
        input_layout.addLayout(url_row)

        layout.addWidget(input_card)

        # 2. Video Preview & Options Card (ẩn khi chưa probe)
        self.info_card = CardWidget(self)
        self.info_card.setVisible(False)
        info_layout = QHBoxLayout(self.info_card)
        info_layout.setContentsMargins(16, 14, 16, 14)
        info_layout.setSpacing(16)

        # Thumbnail
        self.thumb_lbl = QLabel(self.info_card)
        self.thumb_lbl.setFixedSize(140, 140)
        self.thumb_lbl.setAlignment(Qt.AlignCenter)
        self.thumb_lbl.setStyleSheet("background-color: #0f172a; border-radius: 8px;")
        info_layout.addWidget(self.thumb_lbl)

        # Details & Form
        details_layout = QVBoxLayout()
        self.lbl_video_title = SubtitleLabel("Tiêu đề video", self.info_card)
        self.lbl_video_title.setStyleSheet("font-size: 15px; font-weight: 600; color: #1e293b;")
        details_layout.addWidget(self.lbl_video_title)

        self.lbl_video_meta = CaptionLabel("Tác giả: Facebook | Thời lượng: --:--", self.info_card)
        self.lbl_video_meta.setStyleSheet("color: #64748b;")
        details_layout.addWidget(self.lbl_video_meta)

        form = QFormLayout()
        form.setSpacing(8)

        # ComboBox chọn chất lượng
        self.cb_quality = ComboBox(self.info_card)
        form.addRow("Chất lượng:", self.cb_quality)

        # Thư mục lưu
        dir_box = QHBoxLayout()
        self.in_save_dir = LineEdit(self.info_card)
        self.in_save_dir.setText(Config.video_dir())
        dir_box.addWidget(self.in_save_dir, 1)
        self.btn_browse = PushButton(FluentIcon.FOLDER, "Chọn...", self.info_card)
        self.btn_browse.clicked.connect(self._browse_dir)
        dir_box.addWidget(self.btn_browse)
        form.addRow("Lưu vào:", dir_box)

        # Tên file tùy chỉnh
        self.in_custom_name = LineEdit(self.info_card)
        self.in_custom_name.setPlaceholderText("Để trống nếu muốn tự đặt tên theo tiêu đề...")
        form.addRow("Tên file (tùy chọn):", self.in_custom_name)

        details_layout.addLayout(form)

        # Nút tải
        dl_row = QHBoxLayout()
        self.btn_start_dl = PrimaryPushButton(FluentIcon.DOWNLOAD, "Bắt Đầu Tải Video", self.info_card)
        self.btn_start_dl.clicked.connect(self._start_download)
        dl_row.addWidget(self.btn_start_dl)

        self.btn_open_folder = PushButton(FluentIcon.FOLDER, "Mở Thư Mục", self.info_card)
        self.btn_open_folder.clicked.connect(self._open_output_folder)
        dl_row.addWidget(self.btn_open_folder)

        self.btn_preview_last = PushButton(FluentIcon.PLAY, "Xem Trước", self.info_card)
        self.btn_preview_last.setVisible(False)
        self.btn_preview_last.clicked.connect(self._preview_downloaded)
        dl_row.addWidget(self.btn_preview_last)

        self.btn_jump_gemini = PrimaryPushButton(FluentIcon.CHAT, "✨ Sang Tab Gemini Phân Tích", self.info_card)
        self.btn_jump_gemini.setVisible(False)
        self.btn_jump_gemini.clicked.connect(self._jump_to_gemini)
        dl_row.addWidget(self.btn_jump_gemini)

        dl_row.addStretch()
        details_layout.addLayout(dl_row)

        info_layout.addLayout(details_layout, 1)
        layout.addWidget(self.info_card)

        # Progress bar
        self.progress_bar = ProgressBar(self)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.lbl_dl_status = CaptionLabel("", self)
        self.lbl_dl_status.setStyleSheet("color: #6366f1; font-weight: 500;")
        self.lbl_dl_status.setVisible(False)
        layout.addWidget(self.lbl_dl_status)

        # 3. Lịch sử tải xuống
        self.history_widget = DownloadHistoryWidget(self)
        layout.addWidget(self.history_widget, 1)

    def _browse_dir(self):
        folder = QFileDialog.getExistingDirectory(self, "Chọn thư mục lưu video", self.in_save_dir.text())
        if folder:
            self.in_save_dir.setText(folder)

    def _probe_video(self):
        url = self.in_url.text().strip()
        if not url:
            Toast.warning(self, "Chưa nhập link", "Vui lòng nhập đường link video Facebook.")
            return

        self.btn_probe.setEnabled(False)
        self.btn_probe.setText("Đang phân tích...")
        Toast.info(self, "Đang phân tích", "Đang bóc tách thông tin video từ Facebook...")

        # Chạy probe
        try:
            res = probe_facebook_video(url)
            self.btn_probe.setEnabled(True)
            self.btn_probe.setText("Phân Tích Video")

            if "error" in res:
                Toast.error(self, "Lỗi phân tích", res["error"])
                return

            self.probed_data = res
            self.lbl_video_title.setText(res.get("title", "Facebook Reel"))
            self.lbl_video_meta.setText(f"Tác giả: {res.get('author', 'Facebook')} | Thời lượng: {res.get('duration', '--:--')}")

            # Nạp danh sách chất lượng vào ComboBox
            self.cb_quality.clear()
            for q in res.get("qualities", []):
                txt = f"{q.get('label')} [{q.get('size')}]"
                self.cb_quality.addItem(txt, userData=q.get("id"))

            # Load thumbnail nếu có
            thumb_url = res.get("thumbnail")
            if thumb_url:
                try:
                    resp = requests.get(thumb_url, timeout=5)
                    if resp.status_code == 200:
                        pix = QPixmap()
                        pix.loadFromData(resp.content)
                        self.thumb_lbl.setPixmap(pix.scaled(140, 140, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))
                except Exception:
                    self.thumb_lbl.setText("🖼️ Thumbnail")
            else:
                self.thumb_lbl.setText("🖼️ Thumbnail")

            self.info_card.setVisible(True)
            Toast.success(self, "Phân tích thành công", f"Tìm thấy {len(res.get('qualities', []))} tùy chọn tải.")
        except Exception as e:
            self.btn_probe.setEnabled(True)
            self.btn_probe.setText("Phân Tích Video")
            Toast.error(self, "Lỗi", str(e))

    def _start_download(self):
        if not self.probed_data:
            return

        url = self.in_url.text().strip()
        out_dir = self.in_save_dir.text().strip() or Config.video_dir()
        fmt_id = self.cb_quality.currentData()
        custom_name = self.in_custom_name.text().strip() or None

        self.btn_start_dl.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(5)
        self.lbl_dl_status.setVisible(True)
        self.lbl_dl_status.setText("Bắt đầu tải...")

        self.dl_worker = DownloadWorker(
            url=url,
            output_dir=out_dir,
            format_id=fmt_id,
            custom_filename=custom_name,
            parent=self
        )
        self.dl_worker.progressUpdated.connect(self._on_dl_progress)
        self.dl_worker.downloadFinished.connect(self._on_dl_finished)
        self.dl_worker.start()

    def _on_dl_progress(self, pct: float, text: str):
        self.progress_bar.setValue(int(pct))
        self.lbl_dl_status.setText(text)

    def _on_dl_finished(self, res: dict):
        self.btn_start_dl.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.lbl_dl_status.setVisible(False)

        if res.get("ok"):
            self.last_downloaded_file = res.get("file_path", "")
            self.btn_preview_last.setVisible(bool(self.last_downloaded_file))
            self.btn_jump_gemini.setVisible(bool(self.last_downloaded_file))
            Toast.success(self, "Tải thành công!", f"Đã lưu: {res.get('filename')}")
            self.history_widget.load_history()
        else:
            Toast.error(self, "Tải thất bại", res.get("message", ""))

    def _open_output_folder(self):
        out_dir = self.in_save_dir.text().strip() or Config.video_dir()
        if os.path.isdir(out_dir):
            subprocess.Popen(f'explorer "{out_dir}"')

    def _preview_downloaded(self):
        if self.last_downloaded_file and os.path.isfile(self.last_downloaded_file):
            dlg = VideoPlayerDialog(self.last_downloaded_file, parent=self)
            dlg.exec()

    def _jump_to_gemini(self):
        if not self.last_downloaded_file:
            return
        main_win = self.window()
        if hasattr(main_win, "switch_to_gemini"):
            main_win.switch_to_gemini(self.last_downloaded_file, self.lbl_video_title.text())
