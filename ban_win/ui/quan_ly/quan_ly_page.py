"""
Trang Quản Lý Tiến Độ Tạo Video & Đăng Bài hoàn chỉnh với Fluent Design.
"""
import os
import csv
import time
from PySide6.QtCore import Qt, QUrl
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFileDialog
)
from PySide6.QtGui import QDesktopServices
from qfluentwidgets import (
    SearchLineEdit, SegmentedWidget, PrimaryPushButton,
    PushButton, SubtitleLabel, CaptionLabel, BodyLabel,
    FluentIcon, InfoBar, InfoBarPosition, ProgressBar
)

from ban_win.core.database import get_db
from ban_win.core.config import Config
from ban_win.core.sheets_sync import push_to_google_sheet, push_to_google_sheet_async
from ban_win.core.frame_extractor import ensure_local_frames_db
from ban_win.core.content_generator import ensure_auto_content_db
from ban_win.workers.sync_worker import SyncWorker
from ban_win.workers.frame_worker import FrameWorker
from ban_win.workers.content_worker import ContentWorker
from ban_win.ui.widgets.toast import Toast
from .stat_cards import StatCardsWidget
from .table_widget import VideoTableWidget
from .dialogs import RowEditDialog

class QuanLyPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("QuanLyPage")

        self.current_search = ""
        self.current_filter_mode = "all"  # "all", "video_done", "has_file", "post_done"
        self.current_segmented = "all"    # "all", "tao_video", "dang_bai"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # 1. Top Bar: Header + Search + Segmented
        top_bar = QHBoxLayout()
        title_box = QVBoxLayout()
        self.title_lbl = SubtitleLabel("Quản Lý Tiến Độ Video & Đăng Bài", self)
        self.title_lbl.setStyleSheet("font-size: 20px; font-weight: 700; color: #1e293b;")
        self.subtitle_lbl = CaptionLabel("Đồng bộ Google Sheets Realtime | Lưu trữ SQLite Local", self)
        self.subtitle_lbl.setStyleSheet("color: #64748b; font-size: 12px;")
        title_box.addWidget(self.title_lbl)
        title_box.addWidget(self.subtitle_lbl)
        top_bar.addLayout(title_box)

        top_bar.addStretch()

        # Segmented Filter (Tất cả / Cần tạo video / Cần đăng bài)
        self.seg_widget = SegmentedWidget(self)
        self.seg_widget.addItem("all", "Tất cả")
        self.seg_widget.addItem("tao_video", "Đang tạo video")
        self.seg_widget.addItem("dang_bai", "Cần đăng bài")
        self.seg_widget.setCurrentItem("all")
        self.seg_widget.currentItemChanged.connect(self._on_segment_changed)
        top_bar.addWidget(self.seg_widget)

        # Search Bar
        self.search_bar = SearchLineEdit(self)
        self.search_bar.setPlaceholderText("Tìm kiếm STT, prompt, content...")
        self.search_bar.setFixedWidth(240)
        self.search_bar.textChanged.connect(self._on_search_changed)
        top_bar.addWidget(self.search_bar)

        layout.addLayout(top_bar)

        # 2. Stat Cards (4 thẻ thống kê tương tác)
        self.stat_cards = StatCardsWidget(self)
        self.stat_cards.filterRequested.connect(self._on_stat_card_clicked)
        layout.addWidget(self.stat_cards)

        # 3. Action Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self.btn_sync = PrimaryPushButton(FluentIcon.SYNC, "Đồng bộ Sheet", self)
        self.btn_sync.clicked.connect(self._trigger_sheet_sync)
        toolbar.addWidget(self.btn_sync)

        self.btn_gen_content = PushButton(FluentIcon.DOCUMENT, "✨ Ghép Báo Mới", self)
        self.btn_gen_content.clicked.connect(self._batch_gen_content)
        toolbar.addWidget(self.btn_gen_content)

        self.btn_get_frames = PushButton(FluentIcon.CAMERA, "📸 Lấy Frame", self)
        self.btn_get_frames.clicked.connect(self._batch_extract_frames)
        toolbar.addWidget(self.btn_get_frames)

        self.btn_scan_files = PushButton(FluentIcon.FOLDER, "📁 Quét File Video", self)
        self.btn_scan_files.clicked.connect(self._scan_video_files)
        toolbar.addWidget(self.btn_scan_files)

        self.btn_push = PushButton(FluentIcon.SEND, "📤 Đẩy Lên Sheet", self)
        self.btn_push.clicked.connect(self._push_to_sheet)
        toolbar.addWidget(self.btn_push)

        self.btn_add_row = PushButton(FluentIcon.ADD, "Thêm Dòng", self)
        self.btn_add_row.clicked.connect(self._add_row)
        toolbar.addWidget(self.btn_add_row)

        self.btn_export = PushButton(FluentIcon.DOWNLOAD, "Xuất CSV", self)
        self.btn_export.clicked.connect(self._export_csv)
        toolbar.addWidget(self.btn_export)

        toolbar.addStretch()

        # Link mở Google Sheets trực tiếp trên web
        self.btn_open_sheet = PushButton(FluentIcon.SHARE, "Mở Sheet Online", self)
        self.btn_open_sheet.clicked.connect(self._open_sheet_in_browser)
        toolbar.addWidget(self.btn_open_sheet)

        layout.addLayout(toolbar)

        # Progress bar (ẩn khi không có tác vụ nền)
        self.progress_bar = ProgressBar(self)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # 4. Table Widget
        self.table = VideoTableWidget(self)
        self.table.dataChangedSignal.connect(self.refresh_data)
        self.table.requestAction.connect(self._handle_table_action)
        layout.addWidget(self.table, 1)

        # 5. Footer info
        footer = QHBoxLayout()
        self.lbl_footer_info = CaptionLabel("Sẵn sàng.", self)
        self.lbl_footer_info.setStyleSheet("color: #64748b;")
        footer.addWidget(self.lbl_footer_info)
        footer.addStretch()
        self.lbl_sync_status = CaptionLabel("Tự động đồng bộ: Bật", self)
        self.lbl_sync_status.setStyleSheet("color: #10b981; font-weight: 500;")
        footer.addWidget(self.lbl_sync_status)
        layout.addLayout(footer)

        # Khởi tạo dữ liệu
        self.refresh_data()

        # Khởi động worker đồng bộ ngầm định kỳ 3s
        self.bg_sync_worker = SyncWorker(continuous=True, parent=self)
        self.bg_sync_worker.syncCompleted.connect(self._on_bg_sync_completed)
        self.bg_sync_worker.start()

    def refresh_data(self):
        """Tải dữ liệu từ SQLite theo bộ lọc và cập nhật bảng + stat cards"""
        db = get_db()
        v_status = None
        p_status = None

        if self.current_filter_mode == "video_done":
            v_status = "Xong video"
        elif self.current_filter_mode == "post_done":
            p_status = "hoàn thành"

        if self.current_segmented == "tao_video":
            v_status = "Đang tạo video"
        elif self.current_segmented == "dang_bai":
            p_status = "đăng bài"

        rows = db.get_all_videos(
            search=self.current_search,
            trang_thai_video=v_status,
            trang_thai_dang_bai=p_status
        )

        if self.current_filter_mode == "has_file":
            rows = [r for r in rows if r.get("link_video")]

        self.table.populate(rows)

        # Cập nhật stat cards
        stats = db.get_stat_counts()
        self.stat_cards.update_stats(stats)

        self.lbl_footer_info.setText(
            f"Hiển thị {len(rows)} / {stats.get('total', 0)} dòng | Video xong: {stats.get('video_done', 0)} | Có file: {stats.get('has_file', 0)} | Đã hoàn thành: {stats.get('post_done', 0)}"
        )

    def _on_search_changed(self, text: str):
        self.current_search = text.strip()
        self.refresh_data()

    def _on_segment_changed(self, key: str):
        self.current_segmented = key
        self.refresh_data()

    def _on_stat_card_clicked(self, key: str):
        if self.current_filter_mode == key:
            self.current_filter_mode = "all"
        else:
            self.current_filter_mode = key
        self.refresh_data()

    def _trigger_sheet_sync(self):
        self.btn_sync.setEnabled(False)
        self.lbl_sync_status.setText("Đang đồng bộ Google Sheets...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(30)

        self.manual_sync_worker = SyncWorker(continuous=False, force=True, parent=self)
        self.manual_sync_worker.syncCompleted.connect(self._on_manual_sync_done)
        self.manual_sync_worker.start()

    def _on_manual_sync_done(self, res: dict):
        self.btn_sync.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.lbl_sync_status.setText("Tự động đồng bộ: Bật")
        if res.get("ok"):
            Toast.success(self, "Đồng bộ thành công", res.get("message", ""))
            self.refresh_data()
        else:
            Toast.error(self, "Lỗi đồng bộ", res.get("message", ""))

    def _on_bg_sync_completed(self, res: dict):
        if res.get("changed"):
            self.refresh_data()

    def _batch_gen_content(self):
        self.btn_gen_content.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(10)

        self.content_worker = ContentWorker(parent=self)
        self.content_worker.contentProgress.connect(lambda cur, tot, msg: self.lbl_footer_info.setText(msg))
        self.content_worker.contentFinished.connect(self._on_content_batch_done)
        self.content_worker.start()

    def _on_content_batch_done(self, res: dict):
        self.btn_gen_content.setEnabled(True)
        self.progress_bar.setVisible(False)
        Toast.success(self, "Tạo Content Tự Động", res.get("message", ""))
        self.refresh_data()

    def _batch_extract_frames(self):
        self.btn_get_frames.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(10)

        self.frame_worker = FrameWorker(parent=self)
        self.frame_worker.frameProgress.connect(lambda cur, tot, msg: self.lbl_footer_info.setText(msg))
        self.frame_worker.frameFinished.connect(self._on_frame_batch_done)
        self.frame_worker.start()

    def _on_frame_batch_done(self, res: dict):
        self.btn_get_frames.setEnabled(True)
        self.progress_bar.setVisible(False)
        Toast.success(self, "Trích Xuất Frame", res.get("message", ""))
        self.refresh_data()

    def _scan_video_files(self):
        """Quét và đối chiếu file trong thư mục video local"""
        count = ensure_local_frames_db()
        Toast.info(self, "Quét file hoàn tất", f"Đã cập nhật đối chiếu {count} file trên máy tính.")
        self.refresh_data()

    def _push_to_sheet(self):
        webhook = Config.webhook_url()
        if not webhook:
            Toast.warning(self, "Chưa cài Webhook", "Vui lòng vào tab Cài Đặt để cấu hình Apps Script Webhook URL.")
            return

        self.btn_push.setEnabled(False)
        Toast.info(self, "Đang đẩy dữ liệu", "Đang gửi dữ liệu lên Google Sheets...")

        res = push_to_google_sheet(webhook)
        self.btn_push.setEnabled(True)
        if res.get("ok"):
            Toast.success(self, "Thành công", res.get("message", ""))
        else:
            Toast.error(self, "Lỗi đẩy Sheet", res.get("message", ""))

    def _add_row(self):
        dlg = RowEditDialog(parent=self)
        if dlg.exec():
            data = dlg.get_data()
            get_db().upsert_video(data)
            Toast.success(self, "Đã thêm dòng", f"Đã tạo mới STT {data.get('stt')}")
            self.refresh_data()

    def _export_csv(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Xuất dữ liệu CSV", "quan_ly_video.csv", "CSV Files (*.csv)"
        )
        if not file_path:
            return

        rows = get_db().get_all_videos()
        try:
            with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(VideoTableWidget.COLUMNS)
                for r in rows:
                    writer.writerow([
                        r.get("stt", ""),
                        r.get("trang_thai_video", ""),
                        r.get("bai_goc", ""),
                        r.get("prompt_video", ""),
                        r.get("frame_dau_tien", ""),
                        r.get("bao_goc", ""),
                        r.get("bao_moi", ""),
                        r.get("trang_thai_dang_bai", ""),
                        r.get("content", ""),
                        r.get("link_video", ""),
                        r.get("bai_viet_da_dang", "")
                    ])
            Toast.success(self, "Xuất thành công", f"Đã xuất {len(rows)} dòng ra file {os.path.basename(file_path)}")
        except Exception as e:
            Toast.error(self, "Lỗi xuất file", str(e))

    def _open_sheet_in_browser(self):
        url = f"https://docs.google.com/spreadsheets/d/{Config.google_sheet_id()}/edit"
        QDesktopServices.openUrl(QUrl(url))

    def _handle_table_action(self, action_type: str, stt: str):
        if action_type == "gen_content":
            worker = ContentWorker(single_stt=stt, parent=self)
            worker.contentFinished.connect(lambda res: (
                Toast.success(self, f"STT {stt}", res.get("message", "")) if res.get("ok")
                else Toast.error(self, f"STT {stt}", res.get("message", "")),
                self.refresh_data()
            ))
            worker.start()
        elif action_type == "extract_frame":
            worker = FrameWorker(single_stt=stt, parent=self)
            worker.frameFinished.connect(lambda res: (
                Toast.success(self, f"STT {stt}", res.get("message", "")) if res.get("ok")
                else Toast.error(self, f"STT {stt}", res.get("message", "")),
                self.refresh_data()
            ))
            worker.start()

    def closeEvent(self, event):
        if hasattr(self, "bg_sync_worker"):
            self.bg_sync_worker.stop()
        super().closeEvent(event)
