"""
Trang Gemini AI Phân Tích Video & Quản Lý Prompt Mẫu (Chuẩn theo bản Web).
Tích hợp Webview Google Gemini nhúng (QWebEngineView) và hộp thoại soạn thảo Prompt.
"""
import os
import subprocess
from PySide6.QtCore import Qt, QUrl
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPlainTextEdit,
    QApplication, QInputDialog, QMessageBox, QFrame, QSplitter
)
from PySide6.QtGui import QDesktopServices
from qfluentwidgets import (
    ComboBox, PrimaryPushButton, PushButton,
    SubtitleLabel, CaptionLabel, BodyLabel,
    FluentIcon, CardWidget, LineEdit
)

from ban_win.core.database import get_db
from ban_win.ui.widgets.toast import Toast

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
    WEBENGINE_AVAILABLE = True
except ImportError:
    WEBENGINE_AVAILABLE = False


DEFAULT_GEMINI_PROMPT_CONTENT = """từ video tôi gửi sau đây hãy phân tích cho tôi theo format này nhé 
Create a 15-second cinematic realistic video.
Keep the same characters, faces, clothing, location, lighting, and key objects consistent in every shot.   
Use subtle natural acting, realistic facial micro-expressions, slow eye movement, small pauses before speaking, natural breathing, restrained emotions, and cinematic realism.
Avoid repeated generic dialogue. Avoid exaggerated crying, avoid sudden screaming, avoid cartoon-like reactions, avoid unnatural mouth movement, avoid fast body movements, avoid overacting.
Character consistency:
Sarah: Caucasian woman in her early 30s, shoulder-length brown hair, bruised left cheek with soup stains dripping down her chin, neck, and stained ivory cable-knit sweater, wearing a delicate gold necklace.   
Husband: Mid-30s Caucasian man, short neat dark hair, clean-shaven, dark green textured knit sweater, tense and evasive expression.   
Mother-in-law (Mrs. Harrington): Mid-60s elegant Caucasian woman, styled silver hair, gold chain necklace, wearing a sophisticated fitted red long-sleeve dress, composed yet condescending demeanor.   
The Father: Imposing older man (around late 60s/70s), weathered tough facial features, gray hair, wearing a heavy black overcoat over a dark turtleneck, accompanied by suited bodyguards.   
Key objects: Bowl of spilled soup on the dining table, modern smartphone, grand Harrington mansion illuminated in winter night.   
Structure the video in shots:
[0s - 3s] Medium shot: Sarah sits at the lavish Christmas dinner table with soup spilled across her front and an injury on her face. She glares at her husband with restrained fury while he avoids taking her side.   
Character dialogue: Sarah firmly: “Say something.”
   
Character dialogue: Husband defensively: “You shouldn’t have provoked her.”
   
[3s - 6s] Close-up to Medium close-up: Sarah wipes her face slightly, pulls out her smartphone, and begins dialing. The mother-in-law smirks smugly with crossed arms.   
Character dialogue: Mother-in-law condescendingly: “Who are you calling?”
   
Character dialogue: Husband panicked: “Sarah, don’t!”
   
[6s - 9s] Close-up: Sarah holds the phone to her ear, her voice trembling but resolute.   
Character dialogue: Sarah into phone: “Dad, they crossed the line.”
   
Character dialogue: Father (over phone): “Are you still inside the Harrington house?”
   
Character dialogue: Sarah: “Yes.”
   
[9s - 12s] Wide exterior shot cut to Interior reaction shot: The exterior of the lavish snow-covered Harrington mansion shudders under a loud impact. Cut quickly to the dining room as the family freezes in sudden dread.   
Character dialogue: Husband in panic: “Mom, what did you do?”
   
[12s - 15s] Low-angle tracking shot to Close-up: The front doors swing wide open as Sarah’s powerful father walks into the foyer with armed bodyguards in dark suits. Cut to the mother-in-law’s face draining of color, completely paralyzed with fear.   
Character dialogue: The Father in a low, menacing voice: “Who touched my daughter?”"""


class GeminiPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("GeminiPage")
        self.active_video_path = ""
        self.active_video_name = ""
        self.prompts_cache = []

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 16, 20, 16)
        main_layout.setSpacing(12)

        # Header
        top_box = QVBoxLayout()
        title_lbl = SubtitleLabel("✨ Gemini AI Phân Tích Video & Quản Lý Prompt", self)
        title_lbl.setStyleSheet("font-size: 20px; font-weight: 700; color: #1e293b;")
        sub_lbl = CaptionLabel("Nhúng trực tiếp Google Gemini AI, tự động ghép đường dẫn video vào prompt mẫu chuẩn Cinematic", self)
        sub_lbl.setStyleSheet("color: #64748b; font-size: 12px;")
        top_box.addWidget(title_lbl)
        top_box.addWidget(sub_lbl)
        main_layout.addLayout(top_box)

        # Splitter 2 cột: Cột trái Prompt (460px) + Cột phải Gemini Webview
        splitter = QSplitter(Qt.Horizontal, self)
        splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #e2e8f0;
                width: 3px;
                border-radius: 1px;
            }
        """)

        # ============================================================
        # CỘT TRÁI: HỘP THOẠI PROMPT MẪU & VIDEO CONTEXT
        # ============================================================
        left_widget = QWidget(splitter)
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 10, 0)
        left_layout.setSpacing(12)

        prompt_card = CardWidget(left_widget)
        p_card_layout = QVBoxLayout(prompt_card)
        p_card_layout.setContentsMargins(16, 14, 16, 14)
        p_card_layout.setSpacing(10)

        # Tiêu đề cột
        col_header = QHBoxLayout()
        p_title = SubtitleLabel("📝 Hộp Thoại Prompt Mẫu", prompt_card)
        p_title.setStyleSheet("font-size: 15px; font-weight: 600; color: #1e293b;")
        col_header.addWidget(p_title)
        col_header.addStretch()

        badge_lbl = QLabel("Gemini Format", prompt_card)
        badge_lbl.setStyleSheet("""
            background: #ede9fe; color: #6d28d9;
            font-size: 11px; font-weight: 600;
            padding: 3px 8px; border-radius: 6px;
            border: 1px solid #ddd6fe;
        """)
        col_header.addWidget(badge_lbl)
        p_card_layout.addLayout(col_header)

        # 1. Video Context Card (Hiển thị video đang được chọn)
        self.video_context_card = QFrame(prompt_card)
        self.video_context_card.setStyleSheet("""
            QFrame {
                background: #f8fafc;
                border: 1px dashed #cbd5e1;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        vc_layout = QVBoxLayout(self.video_context_card)
        vc_layout.setContentsMargins(6, 6, 6, 6)
        vc_layout.setSpacing(6)

        vc_header = QHBoxLayout()
        vc_icon = QLabel("🎬", self.video_context_card)
        vc_icon.setStyleSheet("font-size: 18px;")
        vc_header.addWidget(vc_icon)

        vc_info = QVBoxLayout()
        self.lbl_vname = BodyLabel("Chưa chọn video nào", self.video_context_card)
        self.lbl_vname.setStyleSheet("font-weight: 600; color: #1e293b; font-size: 13px;")
        self.lbl_vpath = CaptionLabel("Tải video ở tab 'Tải Video FB' hoặc chọn từ 'Quản Lý Video'", self.video_context_card)
        self.lbl_vpath.setStyleSheet("color: #64748b; font-size: 11px;")
        vc_info.addWidget(self.lbl_vname)
        vc_info.addWidget(self.lbl_vpath)
        vc_header.addLayout(vc_info, 1)
        vc_layout.addLayout(vc_header)

        # Nút tương tác video
        vc_btns = QHBoxLayout()
        self.btn_copy_vpath = PushButton(FluentIcon.COPY, "Sao chép Path", self.video_context_card)
        self.btn_copy_vpath.clicked.connect(self._copy_video_path)
        vc_btns.addWidget(self.btn_copy_vpath)

        self.btn_insert_path = PushButton(FluentIcon.ADD, "Chèn Path vào Prompt", self.video_context_card)
        self.btn_insert_path.clicked.connect(self._insert_path_to_prompt)
        vc_btns.addWidget(self.btn_insert_path)

        self.btn_open_vfolder = PushButton(FluentIcon.FOLDER, "Thư mục", self.video_context_card)
        self.btn_open_vfolder.clicked.connect(self._open_video_folder)
        vc_btns.addWidget(self.btn_open_vfolder)

        vc_layout.addLayout(vc_btns)
        p_card_layout.addWidget(self.video_context_card)

        # 2. Selector chọn mẫu prompt
        sel_row = QHBoxLayout()
        sel_row.addWidget(CaptionLabel("Chọn mẫu prompt:", prompt_card))
        sel_row.addStretch()

        self.btn_new_prompt = PushButton(FluentIcon.ADD, "Thêm", prompt_card)
        self.btn_new_prompt.clicked.connect(self._create_new_prompt)
        sel_row.addWidget(self.btn_new_prompt)

        self.btn_reset_prompt = PushButton(FluentIcon.SYNC, "Khôi phục", prompt_card)
        self.btn_reset_prompt.clicked.connect(self._reset_default_prompt)
        sel_row.addWidget(self.btn_reset_prompt)

        self.btn_del_prompt = PushButton(FluentIcon.DELETE, "Xóa", prompt_card)
        self.btn_del_prompt.clicked.connect(self._delete_current_prompt)
        sel_row.addWidget(self.btn_del_prompt)

        p_card_layout.addLayout(sel_row)

        self.cb_prompt_select = ComboBox(prompt_card)
        self.cb_prompt_select.currentIndexChanged.connect(self._on_prompt_selected)
        p_card_layout.addWidget(self.cb_prompt_select)

        # 3. Ô soạn thảo Prompt
        editor_header = QHBoxLayout()
        editor_header.addWidget(CaptionLabel("Nội dung Prompt:", prompt_card))
        editor_header.addStretch()
        self.lbl_stats = CaptionLabel("0 ký tự • 0 từ", prompt_card)
        self.lbl_stats.setStyleSheet("color: #64748b; font-size: 11px;")
        editor_header.addWidget(self.lbl_stats)
        p_card_layout.addLayout(editor_header)

        self.txt_prompt = QPlainTextEdit(prompt_card)
        self.txt_prompt.setPlaceholderText("Nhập nội dung Prompt mẫu...")
        self.txt_prompt.setStyleSheet("""
            QPlainTextEdit {
                background: #ffffff;
                color: #1e293b;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                padding: 10px;
                font-family: 'Segoe UI', Inter, sans-serif;
                font-size: 12.5px;
                line-height: 1.5;
            }
            QPlainTextEdit:focus {
                border-color: #6366f1;
            }
        """)
        self.txt_prompt.textChanged.connect(self._update_text_stats)
        p_card_layout.addWidget(self.txt_prompt, 1)

        # 4. Các nút thao tác
        self.btn_copy_prompt = PrimaryPushButton(FluentIcon.COPY, "SAO CHÉP PROMPT NÀY", prompt_card)
        self.btn_copy_prompt.setFixedHeight(40)
        self.btn_copy_prompt.clicked.connect(self._copy_prompt_only)
        p_card_layout.addWidget(self.btn_copy_prompt)

        self.btn_copy_with_path = PushButton(FluentIcon.SHARE, "📎 Sao chép Kèm Path Video", prompt_card)
        self.btn_copy_with_path.clicked.connect(self._copy_prompt_with_video_path)
        p_card_layout.addWidget(self.btn_copy_with_path)

        act_row = QHBoxLayout()
        self.btn_save_changes = PushButton(FluentIcon.SAVE, "💾 Lưu Thay Đổi", prompt_card)
        self.btn_save_changes.clicked.connect(self._save_prompt_changes)
        act_row.addWidget(self.btn_save_changes)

        self.btn_open_external = PushButton(FluentIcon.GLOBE, "🚀 Mở Gemini Ngoài", prompt_card)
        self.btn_open_external.clicked.connect(self._open_gemini_in_browser)
        act_row.addWidget(self.btn_open_external)
        p_card_layout.addLayout(act_row)

        left_layout.addWidget(prompt_card)
        splitter.addWidget(left_widget)

        # ============================================================
        # CỘT PHẢI: TRÌNH DUYỆT WEBVIEW GEMINI NHÚNG
        # ============================================================
        right_widget = QWidget(splitter)
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(10, 0, 0, 0)
        right_layout.setSpacing(8)

        # Browser Toolbar
        browser_bar = CardWidget(right_widget)
        b_bar_layout = QHBoxLayout(browser_bar)
        b_bar_layout.setContentsMargins(12, 8, 12, 8)
        b_bar_layout.setSpacing(10)

        badge_ssl = QLabel("🔒 Bảo mật", browser_bar)
        badge_ssl.setStyleSheet("color: #10b981; font-weight: 600; font-size: 11px;")
        b_bar_layout.addWidget(badge_ssl)

        self.in_gemini_url = LineEdit(browser_bar)
        self.in_gemini_url.setText("https://gemini.google.com/app")
        self.in_gemini_url.setReadOnly(True)
        b_bar_layout.addWidget(self.in_gemini_url, 1)

        self.btn_reload = PushButton(FluentIcon.SYNC, "Tải lại", browser_bar)
        self.btn_reload.clicked.connect(self._reload_webview)
        b_bar_layout.addWidget(self.btn_reload)

        self.btn_open_browser = PushButton(FluentIcon.SHARE, "Mở Trình Duyệt", browser_bar)
        self.btn_open_browser.clicked.connect(self._open_gemini_in_browser)
        b_bar_layout.addWidget(self.btn_open_browser)

        right_layout.addWidget(browser_bar)

        # Khung Webview
        if WEBENGINE_AVAILABLE:
            self.webview = QWebEngineView(right_widget)
            self.webview.setStyleSheet("border-radius: 8px; border: 1px solid #e2e8f0; background: #ffffff;")
            self.webview.setUrl(QUrl("https://gemini.google.com/app"))
            right_layout.addWidget(self.webview, 1)
        else:
            fallback_box = QFrame(right_widget)
            fallback_box.setStyleSheet("background: #0f172a; border-radius: 8px; border: 1px solid #1e293b;")
            f_layout = QVBoxLayout(fallback_box)
            f_layout.setAlignment(Qt.AlignCenter)

            f_lbl = QLabel("Khung Webview Gemini AI", fallback_box)
            f_lbl.setStyleSheet("color: #f8fafc; font-size: 18px; font-weight: 700; margin-bottom: 8px;")
            f_sub = QLabel("Bấm nút bên dưới để mở Google Gemini trên trình duyệt mặc định máy tính.", fallback_box)
            f_sub.setStyleSheet("color: #94a3b8; font-size: 13px; margin-bottom: 16px;")
            f_layout.addWidget(f_lbl)
            f_layout.addWidget(f_sub)

            btn_open_web = PrimaryPushButton(FluentIcon.GLOBE, "Mở https://gemini.google.com/app", fallback_box)
            btn_open_web.clicked.connect(self._open_gemini_in_browser)
            f_layout.addWidget(btn_open_web, alignment=Qt.AlignCenter)

            right_layout.addWidget(fallback_box, 1)

        splitter.addWidget(right_widget)
        splitter.setSizes([460, 780])

        main_layout.addWidget(splitter, 1)

        # Nạp dữ liệu prompt từ SQLite
        self._load_prompts_from_db()

    def set_active_video(self, file_path: str, title: str = ""):
        """Đặt video hiện tại để hiển thị trên Video Context Card"""
        self.active_video_path = file_path or ""
        self.active_video_name = title or (os.path.basename(file_path) if file_path else "Video")

        if self.active_video_path:
            self.lbl_vname.setText(self.active_video_name)
            self.lbl_vpath.setText(self.active_video_path)
            self.video_context_card.setStyleSheet("""
                QFrame {
                    background: #f0fdf4;
                    border: 1px solid #86efac;
                    border-radius: 8px;
                    padding: 10px;
                }
            """)
        else:
            self.lbl_vname.setText("Chưa chọn video nào")
            self.lbl_vpath.setText("Tải video ở tab 'Tải Video FB' hoặc chọn từ 'Quản Lý Video'")
            self.video_context_card.setStyleSheet("""
                QFrame {
                    background: #f8fafc;
                    border: 1px dashed #cbd5e1;
                    border-radius: 8px;
                    padding: 10px;
                }
            """)

    def _load_prompts_from_db(self):
        db = get_db()
        prompts = db.get_all_prompts()
        if not prompts:
            # Seed default if empty
            db.save_prompt("🎬 Kịch bản 15s Cinematic Realism (Mẫu chuẩn)", DEFAULT_GEMINI_PROMPT_CONTENT)
            prompts = db.get_all_prompts()

        self.prompts_cache = prompts
        self.cb_prompt_select.blockSignals(True)
        self.cb_prompt_select.clear()
        for idx, p in enumerate(prompts):
            self.cb_prompt_select.addItem(p["name"], userData=p["id"])
        self.cb_prompt_select.blockSignals(False)

        if prompts:
            self.txt_prompt.setPlainText(prompts[0]["content"])
            self._update_text_stats()

    def _on_prompt_selected(self, index: int):
        if 0 <= index < len(self.prompts_cache):
            p = self.prompts_cache[index]
            self.txt_prompt.setPlainText(p["content"])
            self._update_text_stats()

    def _update_text_stats(self):
        text = self.txt_prompt.toPlainText()
        chars = len(text)
        words = len(text.split()) if text.strip() else 0
        self.lbl_stats.setText(f"{chars} ký tự • {words} từ")

    def _copy_video_path(self):
        if not self.active_video_path:
            Toast.warning(self, "Chưa có video", "Chưa có đường dẫn video nào được chọn.")
            return
        QApplication.clipboard().setText(self.active_video_path)
        Toast.success(self, "Đã sao chép", "Đã sao chép đường dẫn video vào clipboard!")

    def _insert_path_to_prompt(self):
        if not self.active_video_path:
            Toast.warning(self, "Chưa có video", "Chưa có video nào đang được chọn.")
            return
        current_text = self.txt_prompt.toPlainText()
        insert_line = f"Đường dẫn video trên máy tính: {self.active_video_path}\n\n"
        if not current_text.startswith("Đường dẫn video trên máy tính:"):
            self.txt_prompt.setPlainText(insert_line + current_text)
            Toast.success(self, "Đã chèn", "Đã chèn đường dẫn video vào đầu Prompt!")

    def _open_video_folder(self):
        if self.active_video_path and os.path.exists(self.active_video_path):
            subprocess.Popen(f'explorer /select,"{self.active_video_path}"')
        else:
            Toast.info(self, "Thông báo", "File video chưa tải về máy hoặc đường dẫn không tồn tại.")

    def _copy_prompt_only(self):
        content = self.txt_prompt.toPlainText()
        if not content.strip():
            Toast.warning(self, "Prompt trống", "Nội dung prompt đang trống!")
            return
        QApplication.clipboard().setText(content)
        Toast.success(self, "Đã sao chép Prompt!", "Đã chép nội dung prompt vào clipboard để dán vào Gemini.")

    def _copy_prompt_with_video_path(self):
        content = self.txt_prompt.toPlainText()
        if not content.strip():
            Toast.warning(self, "Prompt trống", "Nội dung prompt đang trống!")
            return
        if self.active_video_path:
            text = f"Đường dẫn video trên máy tính: {self.active_video_path}\n\n" + content
            QApplication.clipboard().setText(text)
            Toast.success(self, "Đã sao chép Kèm Path!", "Đã chép prompt kèm đường dẫn video vào clipboard.")
        else:
            QApplication.clipboard().setText(content)
            Toast.info(self, "Đã sao chép Prompt", "Đã chép prompt (chưa có đường dẫn video).")

    def _save_prompt_changes(self):
        idx = self.cb_prompt_select.currentIndex()
        if 0 <= idx < len(self.prompts_cache):
            p = self.prompts_cache[idx]
            new_content = self.txt_prompt.toPlainText()
            get_db().save_prompt(p["name"], new_content, prompt_id=p["id"])
            p["content"] = new_content
            Toast.success(self, "Đã lưu thay đổi", f"Đã cập nhật prompt '{p['name']}' vào cơ sở dữ liệu.")

    def _create_new_prompt(self):
        name, ok = QInputDialog.getText(self, "Tạo Mẫu Prompt Mới", "Nhập tên mẫu Prompt:")
        if ok and name.strip():
            new_id = get_db().save_prompt(name.strip(), DEFAULT_GEMINI_PROMPT_CONTENT)
            self._load_prompts_from_db()
            # Select new
            for i, p in enumerate(self.prompts_cache):
                if p["id"] == new_id:
                    self.cb_prompt_select.setCurrentIndex(i)
                    break
            Toast.success(self, "Thành công", f"Đã tạo mẫu Prompt: '{name.strip()}'")

    def _reset_default_prompt(self):
        reply = QMessageBox.question(
            self, "Khôi phục mặc định",
            "Bạn có chắc muốn khôi phục nội dung mẫu này về định dạng Cinematic 15s chuẩn?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.txt_prompt.setPlainText(DEFAULT_GEMINI_PROMPT_CONTENT)
            self._save_prompt_changes()
            Toast.success(self, "Đã khôi phục", "Đã khôi phục prompt về mẫu chuẩn 15s Cinematic.")

    def _delete_current_prompt(self):
        if len(self.prompts_cache) <= 1:
            Toast.warning(self, "Không thể xóa", "Phải giữ lại ít nhất một mẫu Prompt mặc định.")
            return
        idx = self.cb_prompt_select.currentIndex()
        if 0 <= idx < len(self.prompts_cache):
            p = self.prompts_cache[idx]
            reply = QMessageBox.question(
                self, "Xóa Prompt",
                f"Bạn có chắc muốn xóa mẫu prompt '{p['name']}'?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                get_db().delete_prompt(p["id"])
                self._load_prompts_from_db()
                Toast.info(self, "Đã xóa", f"Đã xóa prompt '{p['name']}'")

    def _reload_webview(self):
        if WEBENGINE_AVAILABLE and hasattr(self, "webview"):
            self.webview.reload()
            Toast.info(self, "Tải lại", "Đang tải lại giao diện Gemini AI...")

    def _open_gemini_in_browser(self):
        QDesktopServices.openUrl(QUrl("https://gemini.google.com/app"))
