"""
Unit tests for the Donate Notification feature on the Web version:
"Tools hoàn toàn miễn phí bạn có thể donate ủng hộ tác giả qua stk, mã qr như ảnh, cứ 20 bài báo 1 lần"
Follows TDD rules: Happy Path, Edge Cases, Error Handling.
"""
import os
import sys
import unittest

# Ensure project root is in sys.path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

from app import app


def check_donate_trigger(current_count: int, last_prompted: int) -> bool:
    """Helper mô phỏng logic kích hoạt thông báo cứ mỗi 20 bài báo 1 lần."""
    if current_count < 20:
        return False
    return (current_count // 20) > (last_prompted // 20)


def check_startup_donate_trigger(session_shown: bool, last_boot: str, current_boot: str) -> bool:
    """Helper mô phỏng logic kích hoạt khi tắt khởi động lại (mới mở tab hoặc server khởi động lại)."""
    if not session_shown:
        return True
    if current_boot and last_boot != current_boot:
        return True
    return False


class TestDonateModal(unittest.TestCase):
    """Kiểm tra tính năng popup donate cứ mỗi 20 bài báo ở bản web."""

    def setUp(self):
        self.client = app.test_client()
        self.templates_dir = os.path.join(PARENT_DIR, "templates")
        self.static_img = os.path.join(PARENT_DIR, "static", "img", "donate_qr.png")

    # ==========================================
    # 1. HAPPY PATH
    # ==========================================
    def test_donate_qr_image_exists_and_served(self):
        """Happy Path: Ảnh QR donate tồn tại trên đĩa và được phục vụ đúng qua static route."""
        self.assertTrue(os.path.exists(self.static_img), "File donate_qr.png phải tồn tại trong static/img/")
        with self.client.get("/static/img/donate_qr.png") as res:
            self.assertEqual(res.status_code, 200)
            self.assertGreater(len(res.data), 10000, "Dữ liệu ảnh QR phải hợp lệ")

    def test_donate_modal_elements_in_web_templates(self):
        """Happy Path: Các template web chứa cấu trúc modal donate và đầy đủ thông tin thanh toán."""
        for filename in ["index_user.html", "index_admin.html", "index.html"]:
            file_path = os.path.join(self.templates_dir, filename)
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            self.assertIn('id="donateModal"', content, f"{filename} phải có modal id='donateModal'")
            self.assertIn("9363870102", content, f"{filename} phải chứa STK 9363870102")
            self.assertIn("TRAN VAN TOAN", content, f"{filename} phải chứa tên chủ tài khoản TRAN VAN TOAN")
            self.assertIn("Vietcombank", content, f"{filename} phải chứa tên ngân hàng Vietcombank")
            self.assertIn("Tools hoàn toàn miễn phí", content, f"{filename} phải chứa thông điệp Tools hoàn toàn miễn phí")
            self.assertIn("donate_qr.png", content, f"{filename} phải nhúng ảnh QR donate")

    def test_donate_trigger_at_multiples_of_20(self):
        """Happy Path: Kích hoạt chính xác tại các mốc 20, 40, 60 bài báo."""
        # Tại 20 bài: kích hoạt
        self.assertTrue(check_donate_trigger(20, 0))
        # Tại 40 bài: kích hoạt (lần trước ở 20)
        self.assertTrue(check_donate_trigger(40, 20))
        # Tại 60 bài: kích hoạt (lần trước ở 40)
        self.assertTrue(check_donate_trigger(60, 40))

    def test_startup_donate_trigger_on_restart(self):
        """Happy Path: Kích hoạt thông báo khi mở phiên mới hoặc khi server khởi động lại."""
        # Khi mới mở app/trình duyệt lại (sessionStorage trống) -> Luôn hiện!
        self.assertTrue(check_startup_donate_trigger(session_shown=False, last_boot="b1", current_boot="b1"))
        # Khi server tắt rồi bật lại (boot_id mới) -> Luôn hiện!
        self.assertTrue(check_startup_donate_trigger(session_shown=True, last_boot="b1", current_boot="b2"))
        # Khi chỉ là F5 trong cùng 1 phiên và server không khởi động lại -> Không spam lặp
        self.assertFalse(check_startup_donate_trigger(session_shown=True, last_boot="b1", current_boot="b1"))

    def test_templates_contain_startup_check(self):
        """Happy Path: Cả 3 template đều gọi kiểm tra checkStartupDonate khi khởi tạo."""
        for filename in ["index_user.html", "index_admin.html", "index.html"]:
            file_path = os.path.join(self.templates_dir, filename)
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("checkStartupDonate", content, f"{filename} phải gọi checkStartupDonate")

    def test_api_license_info_returns_boot_id(self):
        """Happy Path: Endpoint /api/license-info trả về boot_id để client nhận diện server khởi động lại."""
        res = self.client.get("/api/license-info")
        self.assertEqual(res.status_code, 200)
        self.assertIn("boot_id", res.json, "Response phải chứa boot_id")
        self.assertTrue(bool(res.json.get("boot_id")), "boot_id không được rỗng")

    # ==========================================
    # 2. EDGE CASES
    # ==========================================
    def test_donate_not_triggered_before_20_or_between_multiples(self):
        """Edge Case: Không kích hoạt trước 20 bài hoặc giữa các mốc."""
        # Dưới 20 bài
        self.assertFalse(check_donate_trigger(0, 0))
        self.assertFalse(check_donate_trigger(1, 0))
        self.assertFalse(check_donate_trigger(19, 0))

        # Đã nhắc ở 20 bài, các bài 21 -> 39 không được nhắc lại
        for c in range(21, 40):
            self.assertFalse(check_donate_trigger(c, 20), f"Không được nhắc lại ở bài thứ {c}")

        # Đã nhắc ở 40 bài, các bài 41 -> 59 không được nhắc lại
        for c in range(41, 60):
            self.assertFalse(check_donate_trigger(c, 40), f"Không được nhắc lại ở bài thứ {c}")

    def test_donate_trigger_large_batch(self):
        """Edge Case: Nếu một lần tạo số lượng lớn vượt mốc 20 (ví dụ từ 0 nhảy lên 25 bài), vẫn kích hoạt đúng."""
        self.assertTrue(check_donate_trigger(25, 0))
        self.assertTrue(check_donate_trigger(45, 25))

    # ==========================================
    # 3. ERROR HANDLING
    # ==========================================
    def test_negative_or_corrupt_count_graceful(self):
        """Error Handling: Giá trị âm hoặc không hợp lệ không gây lỗi."""
        self.assertFalse(check_donate_trigger(-5, 0))
        self.assertFalse(check_donate_trigger(0, -10))


if __name__ == "__main__":
    unittest.main()
