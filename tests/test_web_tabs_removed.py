"""
Tests verifying the removal of unwanted tabs ('Tải video', 'Gemini', 'Quản lý')
from the web version of Story Scraper & Auto CMS Publisher.
Follows TDD rules: Happy Path, Edge Cases, and Error Handling.
"""
import os
import sys
import unittest
import re

# Ensure project root is in sys.path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

from app import app


class TestWebTabsRemoved(unittest.TestCase):
    """Kiểm tra việc loại bỏ các tab 'tải video', 'gemini', 'quản lý' ở phiên bản web."""

    def setUp(self):
        self.client = app.test_client()
        self.templates_dir = os.path.join(PARENT_DIR, "templates")

    # ==========================================
    # 1. HAPPY PATH
    # ==========================================
    def test_story_scraper_core_features_intact(self):
        """Happy Path: Đảm bảo giao diện cốt lõi Cào & Đăng truyện vẫn nguyên vẹn."""
        for filename in ["index_user.html", "index_admin.html", "index.html"]:
            file_path = os.path.join(self.templates_dir, filename)
            self.assertTrue(os.path.exists(file_path), f"File {filename} phải tồn tại")
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Các phần tử trọng yếu của Story Scraper
            self.assertIn('id="storyUrl"', content, f"{filename} phải có ô nhập URL truyện")
            self.assertIn('id="btnStart"', content, f"{filename} phải có nút Bắt đầu")
            self.assertIn('id="cmsUrl"', content, f"{filename} phải có cấu hình CMS")
            self.assertIn('live_terminal.log', content, f"{filename} phải có console live log")
            self.assertIn('id="licenseAlertBanner"', content, f"{filename} phải có banner bản quyền")
            self.assertIn('id="previewCard"', content, f"{filename} phải có preview card")

    def test_web_route_get_index_success(self):
        """Happy Path: GET / trả về 200 OK và chứa giao diện cào truyện."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn("Story Scraper & Auto CMS Publisher", html)
        self.assertIn('id="storyUrl"', html)
        self.assertIn('id="btnStart"', html)

    # ==========================================
    # 2. EDGE CASES
    # ==========================================
    def test_unwanted_tabs_removed_from_user_and_admin_templates(self):
        """Edge Case: Đảm bảo cả index_user, index_admin và index.html đều không còn 3 tab và các section tương ứng."""
        for filename in ["index_user.html", "index_admin.html", "index.html"]:
            file_path = os.path.join(self.templates_dir, filename)
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # 1. Tab Tải video Facebook
            self.assertNotIn('id="tabFbBtn"', content, f"{filename} không được chứa tab tải video id=tabFbBtn")
            self.assertNotIn('id="fbTabSection"', content, f"{filename} không được chứa section id=fbTabSection")

            # 2. Tab Gemini AI
            self.assertNotIn('id="tabGeminiBtn"', content, f"{filename} không được chứa tab gemini id=tabGeminiBtn")
            self.assertNotIn('id="geminiTabSection"', content, f"{filename} không được chứa section id=geminiTabSection")

            # 3. Tab Quản lý tiến độ
            self.assertNotIn('href="/quan-ly"', content, f"{filename} không được chứa tab điều hướng href=/quan-ly")

    def test_admin_mode_response_has_no_unwanted_tabs(self):
        """Edge Case: Khi chạy ở chế độ Admin, trang trả về cũng không chứa 3 tab."""
        # Giả lập chế độ admin qua env
        os.environ["STORY_APP_MODE"] = "admin"
        try:
            res = self.client.get("/")
            self.assertEqual(res.status_code, 200)
            html = res.get_data(as_text=True)
            self.assertNotIn('id="tabFbBtn"', html)
            self.assertNotIn('id="tabGeminiBtn"', html)
            self.assertNotIn('href="/quan-ly"', html)
            self.assertNotIn('id="fbTabSection"', html)
            self.assertNotIn('id="geminiTabSection"', html)
        finally:
            os.environ.pop("STORY_APP_MODE", None)

    def test_no_empty_nav_tabs_wrapper(self):
        """Edge Case: Thanh điều hướng nav-tabs-wrapper không được để sót các tab đã loại bỏ."""
        for filename in ["index_user.html", "index_admin.html", "index.html"]:
            file_path = os.path.join(self.templates_dir, filename)
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Không được có tabFbBtn, tabGeminiBtn, hay href="/quan-ly"
            self.assertNotIn('switchMainTab(\'fb\')', content)
            self.assertNotIn('switchMainTab(\'gemini\')', content)

    # ==========================================
    # 3. ERROR HANDLING
    # ==========================================
    def test_switch_main_tab_js_safe_execution(self):
        """Error Handling: Hàm switchMainTab (nếu còn tồn tại) không được throw TypeError khi không tìm thấy tab cũ."""
        for filename in ["index_user.html", "index_admin.html", "index.html"]:
            file_path = os.path.join(self.templates_dir, filename)
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Kiểm tra xem switchMainTab có còn tham chiếu cứng tới tabFbBtn hoặc tabGeminiBtn không
            # Nếu còn function switchMainTab, nó không được cố truy cập .style của fbTabSection hay geminiTabSection mà không kiểm tra
            pattern = re.compile(r'function\s+switchMainTab\s*\([^)]*\)\s*\{([^}]+)\}', re.DOTALL)
            matches = pattern.findall(content)
            for body in matches:
                self.assertNotIn('fbTabSection', body, f"{filename} switchMainTab không được phụ thuộc fbTabSection")
                self.assertNotIn('geminiTabSection', body, f"{filename} switchMainTab không được phụ thuộc geminiTabSection")


if __name__ == "__main__":
    unittest.main()
