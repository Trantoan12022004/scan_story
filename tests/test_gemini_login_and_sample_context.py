"""
Test Suite: Gemini AI Login Security & Sample Video Context Integration
1. Happy Path:
   - Gemini profile có Firefox User-Agent chuẩn và stealth script.
   - analyze_gemini nạp video_mau (Video mẫu) thay vì link_video (Video mới).
   - Cờ Chromium --disable-blink-features=AutomationControlled được cấu hình.
2. Edge Cases:
   - video_mau trong DB rỗng -> Fallback sang build_default_sample_video_path(stt).
   - STT dạng float/chuỗi có khoảng trắng -> Chuẩn hóa đường dẫn chính xác.
   - Thao tác xóa cache dọn dẹp cookie an toàn.
3. Error Handling:
   - STT không tồn tại trong DB -> Xử lý an toàn không crash.
   - Gọi clear cache khi webview chưa load -> Không gây AttributeError.
"""
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

try:
    from PySide6.QtWidgets import QApplication
    # Đảm bảo có QApplication cho QtWebEngine tests
    _APP = QApplication.instance() or QApplication(sys.argv)
    from ban_win.core.database import get_db
    from ban_win.core.video_checker import (
        build_default_sample_video_path,
        build_default_video_link
    )
    from ban_win.ui.gemini.gemini_page import get_gemini_profile, GeminiPage
    from ban_win.ui.quan_ly.quan_ly_page import QuanLyPage
except (ImportError, ModuleNotFoundError):
    raise unittest.SkipTest("Legacy ban_win Python module migrated to ban_win1 TypeScript/Electron app")


class TestGeminiLoginAndSampleContext(unittest.TestCase):
    def setUp(self):
        self.db = get_db()
        self.test_stts = ["9901", "9902", "9903"]
        for stt in self.test_stts:
            self.db.delete_video(stt)

    def tearDown(self):
        for stt in self.test_stts:
            self.db.delete_video(stt)

    # =========================================================================
    # NHÓM 1: HAPPY PATH (Luồng chuẩn)
    # =========================================================================

    def test_happy_path_gemini_profile_firefox_ua_and_stealth(self):
        """Happy Path: Profile Gemini sử dụng Firefox UA và stealth script để vượt qua Google Botguard."""
        import tempfile
        import shutil
        tmp_dir = tempfile.mkdtemp(prefix="gemini_test_")
        try:
            profile = get_gemini_profile(storage_dir=tmp_dir)
            self.assertIsNotNone(profile)
            ua = profile.httpUserAgent()
            self.assertIn("Firefox", ua, "User Agent phải là Firefox để tránh Google Botguard kiểm tra Chrome API")
            self.assertNotIn("Chrome/128", ua, "Không dùng Chrome UA cũ vì thiếu API Chrome chuẩn trong QtWebEngine")

            # Kiểm tra stealth script đã được đăng ký
            scripts = profile.scripts().toList()
            script_names = [s.name() for s in scripts]
            self.assertTrue(
                any("stealth" in name.lower() for name in script_names),
                f"Phải có stealth script trong profile, tìm thấy: {script_names}"
            )
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_happy_path_analyze_gemini_loads_sample_video(self):
        """Happy Path: Phân tích AI phải load video_mau (Video mẫu), KHÔNG ĐƯỢC load link_video (Video mới)."""
        stt = "9901"
        sample_path = r"C:\Users\Trant\Videos\short_drama\9901.mp4"
        new_video_path = r"C:\Users\Trant\Videos\new_produced\9901.mp4"

        self.db.upsert_video({
            "stt": stt,
            "bai_goc": "https://www.facebook.com/reel/9901",
            "video_mau": sample_path,
            "link_video": new_video_path,
            "status": "READY"
        })

        # Tạo QuanLyPage với mock MainWindow
        mock_main_win = MagicMock()
        mock_main_win.switch_to_gemini = MagicMock()

        page = QuanLyPage()
        page.window = MagicMock(return_value=mock_main_win)

        # Kích hoạt action analyze_gemini
        page._handle_table_action("analyze_gemini", stt)

        # Xác thực switch_to_gemini được gọi với video_mau, KHÔNG PHẢI new_video_path
        mock_main_win.switch_to_gemini.assert_called_once()
        passed_path, passed_title = mock_main_win.switch_to_gemini.call_args[0]

        self.assertEqual(os.path.normpath(passed_path), os.path.normpath(sample_path))
        self.assertNotEqual(os.path.normpath(passed_path), os.path.normpath(new_video_path))
        self.assertIn("9901", passed_title)

    def test_happy_path_chromium_flags_configured(self):
        """Happy Path: Cờ QTWEBENGINE_CHROMIUM_FLAGS vô hiệu hóa AutomationControlled."""
        import ban_win.main  # nạp module
        flag = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
        self.assertIn("--disable-blink-features=AutomationControlled", flag)

    # =========================================================================
    # NHÓM 2: EDGE CASES (Trường hợp biên)
    # =========================================================================

    def test_edge_case_empty_video_mau_fallback_to_default_sample_path(self):
        """Edge Case: Nếu video_mau rỗng trong DB, fallback về default sample video path short_drama/{stt}.mp4."""
        stt = "9902"
        new_video_path = r"C:\Users\Trant\Videos\new_produced\9902.mp4"

        self.db.upsert_video({
            "stt": stt,
            "bai_goc": "https://www.facebook.com/reel/9902",
            "video_mau": "",  # Chưa có video mẫu tùy chỉnh
            "link_video": new_video_path,
            "status": "PROCESSING"
        })

        mock_main_win = MagicMock()
        mock_main_win.switch_to_gemini = MagicMock()

        page = QuanLyPage()
        page.window = MagicMock(return_value=mock_main_win)

        page._handle_table_action("analyze_gemini", stt)

        mock_main_win.switch_to_gemini.assert_called_once()
        passed_path, _ = mock_main_win.switch_to_gemini.call_args[0]

        expected_fallback = build_default_sample_video_path(stt)
        self.assertEqual(os.path.normpath(passed_path), os.path.normpath(expected_fallback))
        self.assertNotEqual(os.path.normpath(passed_path), os.path.normpath(new_video_path))

    def test_edge_case_gemini_page_set_active_video(self):
        """Edge Case: GeminiPage nhận video context và hiển thị chính xác tên & đường dẫn."""
        gpage = GeminiPage()
        try:
            test_path = r"C:\Users\Trant\Videos\short_drama\37.mp4"
            gpage.set_active_video(test_path, "Video mẫu STT 37")

            self.assertEqual(gpage.active_video_path, test_path)
            self.assertEqual(gpage.lbl_vname.text(), "Video mẫu STT 37")
            self.assertEqual(gpage.lbl_vpath.text(), test_path)
        finally:
            gpage.close()

    # =========================================================================
    # NHÓM 3: ERROR HANDLING (Xử lý ngoại lệ)
    # =========================================================================

    def test_error_handling_non_existent_stt_analyze(self):
        """Error Handling: STT không tồn tại trong DB không gây crash khi bấm phân tích AI."""
        mock_main_win = MagicMock()
        mock_main_win.switch_to_gemini = MagicMock()

        page = QuanLyPage()
        page.window = MagicMock(return_value=mock_main_win)

        # Chạy với STT hoàn toàn không có trong DB
        try:
            page._handle_table_action("analyze_gemini", "999999_non_exist")
            mock_main_win.switch_to_gemini.assert_called_once()
        except Exception as e:
            self.fail(f"analyze_gemini với STT không tồn tại bị crash: {e}")

    def test_error_handling_clear_cache_when_webview_none(self):
        """Error Handling: Gọi xóa cache an toàn ngay cả khi webview chưa khởi tạo."""
        gpage = GeminiPage()
        try:
            self.assertIsNone(gpage.webview)
            # Mock hộp thoại xác nhận đồng ý xóa
            with patch("ban_win.ui.gemini.gemini_page.QMessageBox.question", return_value=16384): # QMessageBox.Yes = 0x4000 = 16384
                try:
                    gpage._clear_cache_and_reload()
                except Exception as e:
                    self.fail(f"Xóa cache bị lỗi: {e}")
        finally:
            gpage.close()


    def test_happy_path_find_chromium_executable(self):
        """Happy Path: Hệ thống tự động tìm thấy Google Chrome hoặc Microsoft Edge trên máy tính."""
        from ban_win.ui.gemini.gemini_page import find_chromium_executable
        res = find_chromium_executable()
        self.assertIsNotNone(res, "Phải tìm thấy Google Chrome hoặc Microsoft Edge trên hệ thống Windows")
        exe_path, browser_name = res
        self.assertTrue(os.path.isfile(exe_path), f"File {exe_path} phải tồn tại trên đĩa")
        self.assertIn(browser_name, ["Google Chrome", "Microsoft Edge", "Chromium", "Brave"])

    def test_happy_path_chromium_embed_widget_init(self):
        """Happy Path: Khởi tạo ChromiumEmbedWidget an toàn, sẵn sàng nhúng."""
        from ban_win.ui.gemini.gemini_page import ChromiumEmbedWidget
        widget = ChromiumEmbedWidget()
        self.assertIsNotNone(widget)
        self.assertIsNone(widget.proc)
        self.assertIsNone(widget.container)
        widget.terminate()  # An toàn khi chưa chạy

    def test_edge_case_chromium_embed_terminate_safe(self):
        """Edge Case: Gọi terminate nhiều lần liên tiếp không gây lỗi."""
        from ban_win.ui.gemini.gemini_page import ChromiumEmbedWidget
        widget = ChromiumEmbedWidget()
        try:
            widget.terminate()
            widget.terminate()
        except Exception as e:
            self.fail(f"terminate() nhiều lần bị lỗi: {e}")


if __name__ == "__main__":
    unittest.main()

