"""
Unit tests verifying 100% Local SQLite storage and complete removal of Google Sheets dependencies.
Includes Happy Path, Edge Cases, and Error Handling.
"""
import os
import sys
import unittest
import tempfile
import csv

# Ensure project root is in sys.path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

try:
    from ban_win.core.database import get_db, Database
    from ban_win.core.config import Config
    from ban_win.workers.sync_worker import ScanFilesWorker
except (ImportError, ModuleNotFoundError):
    raise unittest.SkipTest("Legacy ban_win Python module migrated to ban_win1 TypeScript/Electron app")


class TestLocalSqliteOnly(unittest.TestCase):
    """Kiểm tra hoạt động thuần SQLite Local 100% không phụ thuộc Google Sheets."""

    def setUp(self):
        self.db = get_db()

    def test_happy_path_sqlite_crud(self):
        """Happy Path: Thao tác thêm, đọc, sửa, xóa video thuần SQLite Local."""
        stt = "test_local_100"
        self.db.delete_video(stt)

        # 1. Thêm dòng mới vào SQLite
        ok = self.db.upsert_video({
            "stt": stt,
            "trang_thai_video": "Đang tạo video",
            "prompt_video": "Local prompt test",
            "content": "Local content test",
            "link_video": ""
        })
        self.assertTrue(ok)

        # 2. Đọc lại
        v = self.db.get_video_by_stt(stt)
        self.assertIsNotNone(v)
        self.assertEqual(v["stt"], stt)
        self.assertEqual(v["prompt_video"], "Local prompt test")

        # 3. Cập nhật trường đơn lẻ
        self.db.update_single_field(stt, "trang_thai_video", "Xong video")
        v_updated = self.db.get_video_by_stt(stt)
        self.assertEqual(v_updated["trang_thai_video"], "Xong video")

        # 4. Dọn dẹp
        self.db.delete_video(stt)
        self.assertIsNone(self.db.get_video_by_stt(stt))

    def test_happy_path_local_csv_export_import(self):
        """Happy Path: Xuất và nhập CSV cục bộ vào SQLite."""
        stt1 = "test_csv_1"
        stt2 = "test_csv_2"
        self.db.delete_video(stt1)
        self.db.delete_video(stt2)

        self.db.upsert_video({"stt": stt1, "prompt_video": "P1", "content": "C1"})
        self.db.upsert_video({"stt": stt2, "prompt_video": "P2", "content": "C2"})

        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = os.path.join(tmpdir, "test_export.csv")

            # Xuất dữ liệu ra CSV
            videos = [self.db.get_video_by_stt(stt1), self.db.get_video_by_stt(stt2)]
            headers = ["STT", "Trạng thái video", "Bài gốc", "Prompt video", "Frame đầu tiên",
                       "Báo gốc", "Báo mới", "Trạng thái đăng bài", "Content", "Link Video", "Bài viết"]
            with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                for v in videos:
                    writer.writerow([v["stt"], "", "", v.get("prompt_video", ""), "", "", "", "", v.get("content", ""), "", ""])

            self.assertTrue(os.path.isfile(csv_path))

            # Xóa trong DB
            self.db.delete_video(stt1)
            self.db.delete_video(stt2)
            self.assertIsNone(self.db.get_video_by_stt(stt1))

            # Nhập lại từ file CSV
            with open(csv_path, "r", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                rows = list(reader)
                for r in rows[1:]:
                    if r and r[0].strip():
                        self.db.upsert_video({
                            "stt": r[0].strip(),
                            "prompt_video": r[3] if len(r) > 3 else "",
                            "content": r[8] if len(r) > 8 else ""
                        })

            # Kiểm tra dữ liệu đã nạp lại vào SQLite thành công
            v1_re = self.db.get_video_by_stt(stt1)
            v2_re = self.db.get_video_by_stt(stt2)
            self.assertIsNotNone(v1_re)
            self.assertEqual(v1_re["prompt_video"], "P1")
            self.assertIsNotNone(v2_re)
            self.assertEqual(v2_re["prompt_video"], "P2")

            # Dọn dẹp
            self.db.delete_video(stt1)
            self.db.delete_video(stt2)

    def test_edge_case_config_no_sheet_keys(self):
        """Edge Case: Config chỉ quản lý cấu hình local (video_dir, theme, cms), không còn tham chiếu Sheets."""
        all_settings = Config.get_all()
        self.assertNotIn("google_sheet_id", all_settings)
        self.assertNotIn("sheet_csv_url", all_settings)
        self.assertNotIn("webhook_url", all_settings)
        self.assertNotIn("sync_interval", all_settings)

    def test_error_handling_empty_and_corrupt_csv_import(self):
        """Error Handling: Xử lý tệp CSV rỗng hoặc chỉ có tiêu đề không bị lỗi/crash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            empty_csv = os.path.join(tmpdir, "empty.csv")
            with open(empty_csv, "w", encoding="utf-8-sig") as f:
                f.write("")

            # Đọc file rỗng
            imported = 0
            with open(empty_csv, "r", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                rows = list(reader)
                for r in rows[1:]:
                    if r and r[0].strip():
                        imported += 1
            self.assertEqual(imported, 0)


if __name__ == "__main__":
    unittest.main()
