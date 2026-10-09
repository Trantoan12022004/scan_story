"""
Verification test suite for UI Highlights, UX Optimizations, and In-App Browser Integration.
Covers Happy Path, Edge Cases, and Error Handling.
"""
import unittest
import os
import sys
try:
    from PySide6.QtWidgets import QApplication
    # Khởi tạo QApplication headless cho testing
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)

    from ban_win.ui.widgets.browser_dialog import InAppBrowserDialog, open_in_app_browser
    from ban_win.ui.widgets.segmented_bar import CapsuleSegmentedBar
    from ban_win.ui.quan_ly.stat_cards import StatCard, StatCardsWidget
    from qfluentwidgets import FluentIcon
except (ImportError, ModuleNotFoundError):
    raise unittest.SkipTest("Legacy ban_win Python module migrated to ban_win1 TypeScript/Electron app")


class TestCapsuleSegmentedBar(unittest.TestCase):
    """Kiểm tra thanh chọn bộ lọc CapsuleSegmentedBar với highlight rõ nét."""

    def setUp(self):
        self.bar = CapsuleSegmentedBar()
        self.bar.addItem("all", "Tất cả")
        self.bar.addItem("tao_video", "Đang tạo video")
        self.bar.addItem("dang_bai", "Cần đăng bài")

    # --- 1. Happy Path ---
    def test_initial_state_and_selection(self):
        self.bar.setCurrentItem("all")
        self.assertEqual(self.bar.currentItem(), "all")

        # Kiểm tra phát tín hiệu khi chuyển mục
        received_keys = []
        self.bar.currentItemChanged.connect(received_keys.append)
        
        self.bar.setCurrentItem("tao_video")
        self.assertEqual(self.bar.currentItem(), "tao_video")
        self.assertIn("tao_video", received_keys)

    def test_button_active_visual_state(self):
        self.bar.setCurrentItem("dang_bai")
        active_btn = self.bar.buttons["dang_bai"]
        inactive_btn = self.bar.buttons["all"]
        
        self.assertTrue(active_btn.property("active"))
        self.assertFalse(inactive_btn.property("active"))

    # --- 2. Edge Cases ---
    def test_set_non_existent_key(self):
        # Đặt key không tồn tại -> không crash, giữ nguyên trạng thái cũ
        self.bar.setCurrentItem("all")
        self.bar.setCurrentItem("non_existent_key")
        self.assertEqual(self.bar.currentItem(), "all")

    def test_add_duplicate_key(self):
        # Thêm key trùng -> cập nhật nhãn, không tạo nút thừa
        initial_count = len(self.bar.buttons)
        self.bar.addItem("all", "Toàn bộ")
        self.assertEqual(len(self.bar.buttons), initial_count)
        self.assertEqual(self.bar.buttons["all"].text(), "Toàn bộ")

    # --- 3. Error Handling ---
    def test_empty_items(self):
        empty_bar = CapsuleSegmentedBar()
        self.assertIsNone(empty_bar.currentItem())
        empty_bar.setCurrentItem("test")
        self.assertIsNone(empty_bar.currentItem())


class TestStatCardsHighlight(unittest.TestCase):
    """Kiểm tra tính năng highlight thẻ thống kê khi người dùng bấm lọc."""

    def setUp(self):
        self.cards = StatCardsWidget()

    # --- 1. Happy Path ---
    def test_stat_cards_active_toggle(self):
        # Đặt active filter cho card Xong video
        self.cards.set_active_filter("video_done")
        self.assertTrue(self.cards.card_done.is_active)
        self.assertFalse(self.cards.card_total.is_active)
        self.assertFalse(self.cards.card_file.is_active)
        self.assertFalse(self.cards.card_post.is_active)

        # Chuyển sang card Đã hoàn thành
        self.cards.set_active_filter("post_done")
        self.assertTrue(self.cards.card_post.is_active)
        self.assertFalse(self.cards.card_done.is_active)

    def test_stat_card_click_signal(self):
        received = []
        self.cards.filterRequested.connect(received.append)
        self.cards.card_done.filterClicked.emit("video_done")
        self.assertEqual(received, ["video_done"])

    # --- 2. Edge Cases ---
    def test_set_all_active_filter(self):
        # Khi chọn "all", card tổng số được highlight làm mốc chuẩn
        self.cards.set_active_filter("all")
        self.assertTrue(self.cards.card_total.is_active)
        self.assertFalse(self.cards.card_done.is_active)

    def test_set_unknown_filter_key(self):
        # Key không tồn tại -> bỏ chọn tất cả các thẻ filter con
        self.cards.set_active_filter("unknown_mode")
        self.assertFalse(self.cards.card_done.is_active)
        self.assertFalse(self.cards.card_file.is_active)
        self.assertFalse(self.cards.card_post.is_active)

    # --- 3. Error Handling ---
    def test_empty_stats_update(self):
        self.cards.update_stats({})
        self.assertEqual(self.cards.card_total.val_lbl.text(), "0")


class TestInAppBrowser(unittest.TestCase):
    """Kiểm tra trình duyệt nhúng InAppBrowserDialog và hàm tiện ích mở link."""

    def setUp(self):
        self.dialogs = []

    def track(self, dlg):
        if dlg:
            self.dialogs.append(dlg)
        return dlg

    def tearDown(self):
        for dlg in self.dialogs:
            try:
                dlg.close()
                dlg.deleteLater()
            except Exception:
                pass
        self.dialogs.clear()
        import gc
        gc.collect()

    # --- 1. Happy Path ---
    def test_browser_dialog_creation_with_valid_url(self):
        url = "https://www.facebook.com/reel/123456789"
        dlg = self.track(InAppBrowserDialog(url, title="Facebook Reel", auto_probe_video=False))
        self.assertEqual(dlg.raw_url, url)
        self.assertIn("Facebook Reel", dlg.windowTitle())
        self.assertEqual(dlg.in_url.text(), url)

    def test_open_in_app_browser_returns_dialog(self):
        # Kiểm tra mở link hợp lệ
        dlg = self.track(open_in_app_browser("https://baomoi.com/bai-viet/1.epi", title="Báo Mới", test_mode=True))
        self.assertIsNotNone(dlg)
        self.assertIsInstance(dlg, InAppBrowserDialog)

    # --- 2. Edge Cases ---
    def test_auto_prefix_http_scheme(self):
        # Tự động thêm https:// nếu người dùng truyền url trần
        dlg = self.track(InAppBrowserDialog("facebook.com/reel/999", title="Test", auto_probe_video=False))
        self.assertTrue(dlg.in_url.text().startswith("https://facebook.com/reel/999"))
        # Khi điều hướng từ input
        dlg.in_url.setText("vnexpress.net")
        dlg._navigate_from_input()
        if hasattr(dlg, "webview"):
            self.assertTrue(dlg.webview.url().toString().startswith("https://"))

    def test_empty_or_whitespace_url(self):
        dlg1 = open_in_app_browser("", title="Empty", test_mode=True)
        self.assertIsNone(dlg1)
        dlg2 = open_in_app_browser("   ", title="Whitespace", test_mode=True)
        self.assertIsNone(dlg2)
        dlg3 = open_in_app_browser(None, title="None", test_mode=True)
        self.assertIsNone(dlg3)

    # --- 3. Error Handling ---
    def test_copy_url_when_empty(self):
        dlg = self.track(InAppBrowserDialog("", title="Empty Test", auto_probe_video=False))
        dlg.in_url.setText("")
        # Không gây lỗi exception khi copy url rỗng
        dlg._copy_url()

    def test_navigate_empty_input(self):
        dlg = self.track(InAppBrowserDialog("https://example.com", title="Test", auto_probe_video=False))
        dlg.in_url.setText("")
        # Không crash khi nhấn Enter với ô nhập rỗng
        dlg._navigate_from_input()

    def test_is_video_url_detection(self):
        from ban_win.ui.widgets.browser_dialog import is_video_url
        self.assertTrue(is_video_url("https://www.facebook.com/reel/1123266030131230"))
        self.assertTrue(is_video_url("https://facebook.com/watch/?v=987654"))
        self.assertTrue(is_video_url("https://fb.watch/abcxyz"))
        self.assertFalse(is_video_url("https://baomoi.com/bai-viet.epi"))
        self.assertFalse(is_video_url("https://vnexpress.net/thoi-su"))
        self.assertFalse(is_video_url(""))
        self.assertFalse(is_video_url(None))

    def test_custom_page_create_window_returns_self(self):
        # Đảm bảo target="_blank" tự động mở trong chính browser dialog
        dlg = self.track(InAppBrowserDialog("https://example.com", title="Test", auto_probe_video=False))
        if hasattr(dlg, "custom_page"):
            new_page = dlg.custom_page.createWindow(0)
            self.assertEqual(new_page, dlg.custom_page)

    def test_webview_runner_module_exists(self):
        # Kiểm tra module webview_runner độc lập tồn tại và import được
        from ban_win.ui.widgets.webview_runner import run_browser
        self.assertTrue(callable(run_browser))

    def test_open_in_app_browser_production_subprocess(self):
        # Kiểm tra launch subprocess với webview_runner độc lập trong môi trường thực
        from unittest.mock import patch
        with patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value = "mock_proc"
            res = open_in_app_browser("https://facebook.com/reel/123", title="Reel Test", test_mode=False)
            self.assertEqual(res, "mock_proc")
            mock_popen.assert_called_once()
            args = mock_popen.call_args[0][0]
            self.assertTrue(args[1].endswith("webview_runner.py"))
            self.assertEqual(args[2], "https://facebook.com/reel/123")
            self.assertEqual(args[3], "Reel Test")


class TestSessionPersistence(unittest.TestCase):
    """Kiểm tra cơ chế lưu trữ phiên đăng nhập (Cookies & Session) cho Facebook & Gemini."""

    # --- 1. Happy Path ---
    def test_default_browser_storage_dir(self):
        from ban_win.ui.widgets.webview_runner import get_default_browser_storage_dir
        path = get_default_browser_storage_dir()
        self.assertTrue(os.path.isdir(path))
        self.assertTrue(path.endswith("browser_profile"))

    def test_gemini_profile_persistence(self):
        from ban_win.ui.gemini.gemini_page import get_gemini_profile
        from PySide6.QtWebEngineCore import QWebEngineProfile
        profile = get_gemini_profile()
        self.assertIsNotNone(profile)
        # Profile không được ở chế độ ẩn danh (OffTheRecord)
        self.assertFalse(profile.isOffTheRecord())
        # Phải cấu hình bắt buộc lưu cookie vĩnh viễn (ForcePersistentCookies)
        self.assertEqual(
            profile.persistentCookiesPolicy(),
            QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies
        )
        self.assertTrue(len(profile.persistentStoragePath()) > 0)
        self.assertTrue(os.path.isdir(profile.persistentStoragePath()))

    def test_webview_runner_private_mode_disabled(self):
        # Đảm bảo khi khởi chạy webview_runner, private_mode=False và có storage_path
        from unittest.mock import patch
        from ban_win.ui.widgets.webview_runner import run_browser
        with patch("webview.create_window") as mock_create, patch("webview.start") as mock_start:
            run_browser("https://www.facebook.com", "Facebook Login Test")
            mock_create.assert_called_once()
            mock_start.assert_called_once()
            kwargs = mock_start.call_args[1]
            self.assertFalse(kwargs.get("private_mode", True))
            self.assertIsNotNone(kwargs.get("storage_path"))
            self.assertTrue(kwargs.get("storage_path").endswith("browser_profile"))
            self.assertFalse(kwargs.get("debug", True))

    # --- 2. Edge Cases ---
    def test_gemini_profile_singleton(self):
        # Gọi nhiều lần phải trả về cùng 1 profile instance
        from ban_win.ui.gemini.gemini_page import get_gemini_profile
        p1 = get_gemini_profile()
        p2 = get_gemini_profile()
        self.assertIs(p1, p2)

    def test_custom_storage_path(self):
        from unittest.mock import patch
        from ban_win.ui.widgets.webview_runner import run_browser
        import tempfile
        custom_dir = os.path.join(tempfile.gettempdir(), "test_custom_browser_profile")
        with patch("webview.create_window"), patch("webview.start") as mock_start:
            run_browser("https://facebook.com", "Test", storage_path=custom_dir)
            kwargs = mock_start.call_args[1]
            self.assertEqual(kwargs.get("storage_path"), custom_dir)
            self.assertTrue(os.path.isdir(custom_dir))

    # --- 3. Error Handling ---
    def test_empty_storage_path_fallback(self):
        from unittest.mock import patch
        from ban_win.ui.widgets.webview_runner import run_browser, get_default_browser_storage_dir
        with patch("webview.create_window"), patch("webview.start") as mock_start:
            run_browser("https://facebook.com", "Test", storage_path="   ")
            kwargs = mock_start.call_args[1]
            self.assertEqual(kwargs.get("storage_path"), get_default_browser_storage_dir())


if __name__ == "__main__":
    unittest.main()
