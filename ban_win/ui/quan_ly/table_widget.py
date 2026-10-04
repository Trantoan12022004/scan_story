"""
Bảng quản lý tiến độ 11 cột với thiết kế Fluent 1 dòng cố định, badge màu, và tương tác mở nhanh.
"""
import os
import subprocess
from PySide6.QtCore import Qt, Signal, QUrl
from PySide6.QtWidgets import (
    QTableWidget, QTableWidgetItem, QHeaderView, QWidget,
    QHBoxLayout, QLabel, QMenu, QApplication
)
from PySide6.QtGui import QCursor, QDesktopServices, QColor
from qfluentwidgets import TableWidget, FluentIcon, Action, RoundMenu

from ban_win.core.database import get_db
from ban_win.core.video_checker import check_video_file
from .status_menu import StatusBadge
from .frame_preview import FramePreviewDialog
from .dialogs import TextViewerDialog, RowEditDialog

class VideoTableWidget(TableWidget):
    dataChangedSignal = Signal()
    requestAction = Signal(str, str)  # (action_type, stt)

    COLUMNS = [
        "STT",
        "Trạng thái video",
        "Bài gốc",
        "Prompt video",
        "Frame đầu tiên",
        "Báo gốc",
        "Báo mới",
        "Trạng thái đăng",
        "Content",
        "Link Video",
        "Bài viết đã đăng"
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(len(self.COLUMNS))
        self.setHorizontalHeaderLabels(self.COLUMNS)

        # Style & behavior
        self.verticalHeader().setVisible(False)
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setSelectionMode(QTableWidget.SingleSelection)
        self.setWordWrap(False)  # 1 dòng duy nhất!
        self.setAlternatingRowColors(True)
        self.setShowGrid(True)

        # Column widths
        self.setColumnWidth(0, 55)   # STT
        self.setColumnWidth(1, 130)  # Video Status
        self.setColumnWidth(2, 160)  # Bài gốc
        self.setColumnWidth(3, 200)  # Prompt
        self.setColumnWidth(4, 90)   # Frame
        self.setColumnWidth(5, 140)  # Báo gốc
        self.setColumnWidth(6, 140)  # Báo mới
        self.setColumnWidth(7, 140)  # Post Status
        self.setColumnWidth(8, 220)  # Content
        self.setColumnWidth(9, 150)  # Link Video
        self.setColumnWidth(10, 140) # Bài viết

        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        # Context menu
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        # Double click cell
        self.cellDoubleClicked.connect(self._on_cell_double_clicked)

        self.rows_cache = []

    def populate(self, rows: list):
        self.rows_cache = rows
        self.setRowCount(len(rows))
        self.verticalHeader().setDefaultSectionSize(40)

        for row_idx, r in enumerate(rows):
            stt = str(r.get("stt", ""))

            # Col 0: STT
            stt_item = QTableWidgetItem(stt)
            stt_item.setTextAlignment(Qt.AlignCenter)
            stt_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.setItem(row_idx, 0, stt_item)

            # Col 1: Video Status (Badge)
            v_badge = StatusBadge(stt, "video", r.get("trang_thai_video", ""), self)
            v_badge.statusChanged.connect(self._on_status_changed)
            self.setCellWidget(row_idx, 1, v_badge)

            # Col 2: Bài gốc
            bai_goc = r.get("bai_goc", "")
            bg_item = QTableWidgetItem(bai_goc)
            bg_item.setToolTip(bai_goc)
            bg_item.setForeground(QColor("#2563eb") if bai_goc.startswith("http") else QColor("#334155"))
            bg_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.setItem(row_idx, 2, bg_item)

            # Col 3: Prompt
            prompt = r.get("prompt_video", "")
            pr_item = QTableWidgetItem(prompt.replace("\n", " "))
            pr_item.setToolTip(prompt if len(prompt) > 30 else "Bấm đúp để xem Prompt")
            pr_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.setItem(row_idx, 3, pr_item)

            # Col 4: Frame đầu tiên
            frame_path = r.get("frame_dau_tien", "")
            frame_item = QTableWidgetItem("🖼️ Xem ảnh" if frame_path else "-")
            frame_item.setTextAlignment(Qt.AlignCenter)
            frame_item.setForeground(QColor("#0ea5e9") if frame_path else QColor("#94a3b8"))
            frame_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.setItem(row_idx, 4, frame_item)

            # Col 5: Báo gốc
            bao_goc = r.get("bao_goc", "")
            b_item = QTableWidgetItem(bao_goc)
            b_item.setToolTip(bao_goc)
            b_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.setItem(row_idx, 5, b_item)

            # Col 6: Báo mới
            bao_moi = r.get("bao_moi", "")
            bm_item = QTableWidgetItem(bao_moi)
            bm_item.setToolTip(bao_moi)
            bm_item.setForeground(QColor("#16a34a") if bao_moi.startswith("http") else QColor("#334155"))
            bm_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.setItem(row_idx, 6, bm_item)

            # Col 7: Trạng thái đăng (Badge)
            p_badge = StatusBadge(stt, "post", r.get("trang_thai_dang_bai", ""), self)
            p_badge.statusChanged.connect(self._on_post_status_changed)
            self.setCellWidget(row_idx, 7, p_badge)

            # Col 8: Content
            content = r.get("content", "")
            c_item = QTableWidgetItem(content.replace("\n", " "))
            c_item.setToolTip(content if len(content) > 30 else "Bấm đúp để xem Content")
            c_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.setItem(row_idx, 8, c_item)

            # Col 9: Link video + File checker
            link_v = r.get("link_video", "")
            v_check = check_video_file(link_v, stt)
            if v_check["exists"]:
                v_txt = f"💾 Có sẵn ({v_check['size']})"
                color = QColor("#15803d")
            else:
                v_txt = os.path.basename(link_v) if link_v else "Chưa có file"
                color = QColor("#64748b")
            lv_item = QTableWidgetItem(v_txt)
            lv_item.setToolTip(v_check["path"] or link_v)
            lv_item.setForeground(color)
            lv_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.setItem(row_idx, 9, lv_item)

            # Col 10: Bài viết đã đăng
            bv = r.get("bai_viet_da_dang", "")
            bv_item = QTableWidgetItem(bv)
            bv_item.setToolTip(bv)
            bv_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.setItem(row_idx, 10, bv_item)

    def _on_status_changed(self, stt: str, new_status: str):
        get_db().update_single_field(stt, "trang_thai_video", new_status)
        self.dataChangedSignal.emit()

    def _on_post_status_changed(self, stt: str, new_status: str):
        get_db().update_single_field(stt, "trang_thai_dang_bai", new_status)
        self.dataChangedSignal.emit()

    def _on_cell_double_clicked(self, row: int, col: int):
        if row >= len(self.rows_cache):
            return
        r = self.rows_cache[row]
        stt = str(r.get("stt", ""))

        if col == 2:  # Bài gốc -> Mở trình duyệt
            url = r.get("bai_goc", "").strip()
            if url.startswith("http"):
                QDesktopServices.openUrl(QUrl(url))
        elif col == 3:  # Prompt -> Mở xem text
            dlg = TextViewerDialog(f"Prompt Video (STT {stt})", r.get("prompt_video", ""), editable=True, parent=self)
            if dlg.exec():
                new_txt = dlg.get_text()
                get_db().update_single_field(stt, "prompt_video", new_txt)
                self.dataChangedSignal.emit()
        elif col == 4:  # Frame -> Phóng to
            dlg = FramePreviewDialog(r.get("frame_dau_tien", ""), stt=stt, parent=self)
            dlg.exec()
        elif col == 6:  # Báo mới -> Mở trình duyệt nếu là link
            url = r.get("bao_moi", "").strip()
            if url.startswith("http"):
                QDesktopServices.openUrl(QUrl(url))
        elif col == 8:  # Content -> Mở xem text
            dlg = TextViewerDialog(f"Nội dung Content (STT {stt})", r.get("content", ""), editable=True, parent=self)
            if dlg.exec():
                new_txt = dlg.get_text()
                get_db().update_single_field(stt, "content", new_txt)
                self.dataChangedSignal.emit()
        elif col == 9:  # Video file -> Mở thư mục hoặc file
            v_check = check_video_file(r.get("link_video", ""), stt)
            if v_check["exists"]:
                subprocess.Popen(f'explorer /select,"{v_check["path"]}"')
        elif col == 10:  # Bài viết đã đăng -> Mở link
            url = r.get("bai_viet_da_dang", "").strip()
            if url.startswith("http"):
                QDesktopServices.openUrl(QUrl(url))
        else:
            # Mở sửa dòng
            dlg = RowEditDialog(r, parent=self)
            if dlg.exec():
                new_data = dlg.get_data()
                get_db().upsert_video(new_data)
                self.dataChangedSignal.emit()

    def _show_context_menu(self, pos):
        item = self.itemAt(pos)
        if not item:
            return
        row = item.row()
        if row >= len(self.rows_cache):
            return
        r = self.rows_cache[row]
        stt = str(r.get("stt", ""))

        menu = RoundMenu(parent=self)

        act_edit = Action(FluentIcon.EDIT, f"Sửa dòng STT {stt}", menu)
        act_edit.triggered.connect(lambda: self._edit_row(r))
        menu.addAction(act_edit)

        menu.addSeparator()

        act_gen_content = Action(FluentIcon.DOCUMENT, "Ghép Báo Mới (Tạo Content)", menu)
        act_gen_content.triggered.connect(lambda: self.requestAction.emit("gen_content", stt))
        menu.addAction(act_gen_content)

        act_extract_frame = Action(FluentIcon.CAMERA, "Trích xuất Frame đầu tiên", menu)
        act_extract_frame.triggered.connect(lambda: self.requestAction.emit("extract_frame", stt))
        menu.addAction(act_extract_frame)

        act_gemini = Action(FluentIcon.CHAT, "✨ Phân tích video bằng Gemini AI", menu)
        act_gemini.triggered.connect(lambda: self.requestAction.emit("analyze_gemini", stt))
        menu.addAction(act_gemini)

        if r.get("bai_goc", "").startswith("http"):
            act_open_reel = Action(FluentIcon.SHARE, "Mở link Facebook Reel", menu)
            act_open_reel.triggered.connect(lambda: QDesktopServices.openUrl(QUrl(r.get("bai_goc"))))
            menu.addAction(act_open_reel)

        v_check = check_video_file(r.get("link_video", ""), stt)
        if v_check["exists"]:
            act_open_folder = Action(FluentIcon.FOLDER, "Mở vị trí file video", menu)
            act_open_folder.triggered.connect(lambda: subprocess.Popen(f'explorer /select,"{v_check["path"]}"'))
            menu.addAction(act_open_folder)

        menu.addSeparator()

        act_copy_prompt = Action(FluentIcon.COPY, "Sao chép Prompt", menu)
        act_copy_prompt.triggered.connect(lambda: QApplication.clipboard().setText(r.get("prompt_video", "")))
        menu.addAction(act_copy_prompt)

        act_copy_content = Action(FluentIcon.COPY, "Sao chép Content", menu)
        act_copy_content.triggered.connect(lambda: QApplication.clipboard().setText(r.get("content", "")))
        menu.addAction(act_copy_content)

        menu.addSeparator()

        act_del = Action(FluentIcon.DELETE, f"Xóa dòng STT {stt}", menu)
        act_del.triggered.connect(lambda: self._delete_row(stt))
        menu.addAction(act_del)

        menu.exec(QCursor.pos())

    def _edit_row(self, r: dict):
        dlg = RowEditDialog(r, parent=self)
        if dlg.exec():
            new_data = dlg.get_data()
            get_db().upsert_video(new_data)
            self.dataChangedSignal.emit()

    def _delete_row(self, stt: str):
        get_db().delete_video(stt)
        self.dataChangedSignal.emit()
