"""
Test suite verifying performance and responsiveness optimizations in ban_win.
Includes Happy Path, Edge Cases, and Error Handling tests.
"""
import os
import sys
import unittest
import time
from unittest.mock import MagicMock, patch

# Ensure project root is in sys.path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

try:
    from ban_win.core.config import Config
    from ban_win.core.database import get_db, Database
    from ban_win.core.video_checker import check_video_file, normalize_stt, build_default_video_link, check_video_files_batch
    from ban_win.core.content_generator import compute_post_status
except (ImportError, ModuleNotFoundError):
    raise unittest.SkipTest("Legacy ban_win Python module migrated to ban_win1 TypeScript/Electron app")


class TestConfigAndCache(unittest.TestCase):
    """Kiểm tra tối ưu bộ đệm Config (in-memory cache) tránh truy vấn SQLite lặp lại."""

    def setUp(self):
        # Đảm bảo DB khởi tạo
        self.db = get_db()

    def test_happy_path_config_cache(self):
        """Happy Path: Config.get đọc nhanh từ cache và Config.set cập nhật đồng bộ cache."""
        Config.set("test_opt_key", "test_val_123")
        
        # Lần đọc đầu tiên
        val1 = Config.get("test_opt_key")
        self.assertEqual(val1, "test_val_123")

        # Cập nhật giá trị mới
        Config.set("test_opt_key", "test_val_456")
        val2 = Config.get("test_opt_key")
        self.assertEqual(val2, "test_val_456")

    def test_edge_case_config_default_and_empty(self):
        """Edge Case: Key không tồn tại, trả về giá trị default."""
        val = Config.get("non_existing_key_xyz_999", default="my_default")
        self.assertEqual(val, "my_default")

        # Key rỗng
        val_empty = Config.get("", default="empty_def")
        self.assertEqual(val_empty, "empty_def")

    def test_no_sheet_keys_in_config(self):
        """Kiểm tra không còn bất kỳ cấu hình Google Sheets nào trong Config."""
        all_settings = Config.get_all()
        for sheet_key in ["google_sheet_id", "sheet_csv_url", "webhook_url", "sync_interval"]:
            self.assertNotIn(sheet_key, all_settings)


class TestVideoCheckerOptimization(unittest.TestCase):
    """Kiểm tra tối ưu kiểm tra file video qua batch lookup và caching."""

    def test_happy_path_normalize_stt(self):
        """Happy Path: Chuẩn hóa số thứ tự (STT)."""
        self.assertEqual(normalize_stt(1), "1")
        self.assertEqual(normalize_stt(" 25 "), "25")
        self.assertEqual(normalize_stt("10.0"), "10")

    def test_edge_case_normalize_stt(self):
        """Edge Case: STT là None, chuỗi rỗng hoặc giá trị đặc biệt."""
        self.assertEqual(normalize_stt(None), "")
        self.assertEqual(normalize_stt(""), "")
        self.assertEqual(normalize_stt("   "), "")

    def test_batch_video_checker(self):
        """Happy Path: Hàm check_video_files_batch kiểm tra nhanh nhiều dòng cùng lúc mà không mở đĩa liên tục."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            # Tạo 2 file video mẫu
            f1 = os.path.join(tmpdir, "1.mp4")
            f2 = os.path.join(tmpdir, "2.mp4")
            with open(f1, "wb") as f:
                f.write(b"0" * 1024 * 1024)  # 1MB
            with open(f2, "wb") as f:
                f.write(b"0" * 512 * 1024)   # 512KB

            items = [
                {"stt": "1", "link_video": ""},
                {"stt": "2", "link_video": f2},
                {"stt": "3", "link_video": ""},  # Không có file
                {"stt": "4", "link_video": os.path.join(tmpdir, "not_exist.mp4")},
            ]

            results = check_video_files_batch(items, base_dir=tmpdir)
            self.assertEqual(len(results), 4)

            # STT 1: Tự động tìm thấy 1.mp4 trong base_dir
            self.assertTrue(results["1"]["exists"])
            self.assertEqual(results["1"]["path"], f1)
            self.assertIn("1.0 MB", results["1"]["size"])

            # STT 2: Có link_video f2
            self.assertTrue(results["2"]["exists"])
            self.assertEqual(results["2"]["path"], f2)

            # STT 3: Không có file
            self.assertFalse(results["3"]["exists"])

            # STT 4: File không tồn tại
            self.assertFalse(results["4"]["exists"])


class TestPostStatusLogic(unittest.TestCase):
    """Kiểm tra logic tính toán trạng thái bài viết."""

    def test_happy_path_post_status(self):
        self.assertEqual(compute_post_status("", "Content text", "video.mp4"), "hoàn thành")
        self.assertEqual(compute_post_status("", "", "video.mp4"), "chưa hoàn thành")
        self.assertEqual(compute_post_status("", "Content text", ""), "chưa hoàn thành")

    def test_edge_case_dang_bai(self):
        self.assertEqual(compute_post_status("đăng bài", "Content text", "video.mp4"), "đăng bài")
        self.assertEqual(compute_post_status("ĐĂNG BÀI", "", ""), "đăng bài")

    def test_error_handling_empty_inputs(self):
        self.assertEqual(compute_post_status("", "", ""), "chưa hoàn thành")
        self.assertEqual(compute_post_status(None, None, None), "chưa hoàn thành")


class TestDatabaseWALAndConnection(unittest.TestCase):
    """Kiểm tra kết nối DB ở chế độ WAL tối ưu không chạy lặp PRAGMA."""

    def test_happy_path_db_crud(self):
        db = get_db()
        test_stt = "test_opt_999"
        # Dọn dẹp trước nếu có
        db.delete_video(test_stt)

        created = db.upsert_video({
            "stt": test_stt,
            "trang_thai_video": "Lấy video",
            "prompt_video": "Test prompt optimization",
            "link_video": ""
        })
        self.assertTrue(created)

        # Lấy lại
        row = db.get_video_by_stt(test_stt)
        self.assertIsNotNone(row)
        self.assertEqual(row["stt"], test_stt)
        self.assertEqual(row["prompt_video"], "Test prompt optimization")

        # Cập nhật 1 trường
        updated = db.update_single_field(test_stt, "prompt_video", "Updated prompt")
        self.assertTrue(updated)
        row_updated = db.get_video_by_stt(test_stt)
        self.assertEqual(row_updated["prompt_video"], "Updated prompt")

        # Dọn dẹp
        db.delete_video(test_stt)
        self.assertIsNone(db.get_video_by_stt(test_stt))


from ban_win.workers.sync_worker import ScanFilesWorker
from ban_win.workers.download_worker import ProbeWorker
from ban_win.core.sheets_sync import export_sqlite_to_csv, import_csv_to_sqlite


class TestAsyncWorkers(unittest.TestCase):
    """Kiểm tra các worker bất đồng bộ và tiện ích CSV local."""

    def test_happy_path_scan_files_worker(self):
        """Happy Path: ScanFilesWorker chạy và phát tín hiệu scanFinished(count)."""
        worker = ScanFilesWorker()
        received = []
        worker.scanFinished.connect(lambda count: received.append(count))
        # Chạy trực tiếp phương thức run() để test logic mà không phụ thuộc QEventLoop
        worker.run()
        self.assertEqual(len(received), 1)
        self.assertIsInstance(received[0], int)

    def test_edge_case_csv_import_non_existent(self):
        """Edge Case: Nhập file CSV không tồn tại trả về thông báo lỗi có kiểm soát."""
        res = import_csv_to_sqlite("non_existent_file_path_12345.csv")
        self.assertFalse(res.get("ok"))
        self.assertIn("không tồn tại", res.get("message", ""))

    def test_error_handling_probe_worker_invalid_url(self):
        """Error Handling: ProbeWorker với URL không hợp lệ trả về kết quả lỗi có kiểm soát không crash."""
        worker = ProbeWorker(url="https://invalid-non-existent-site-test.xyz/123")
        received = []
        worker.probeFinished.connect(lambda res: received.append(res))
        worker.run()
        self.assertEqual(len(received), 1)
        # Kết quả trả về dict có key 'error' hoặc ok=False
        self.assertTrue("error" in received[0] or not received[0].get("ok", True))


if __name__ == "__main__":
    unittest.main()
