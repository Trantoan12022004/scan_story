"""
Bộ kiểm thử tính năng Cột Video Mẫu & Quét Tải Tự Động Chất Lượng Cao:
1. Happy Path:
   - Cấu hình thư mục mặc định Video mẫu: C:\\Users\\Trant\\Videos\\short_drama
   - Mẫu lưu mặc định: C:\\Users\\Trant\\Videos\\short_drama\\37.mp4
   - Bảng hiển thị 9 cột chuẩn với 2 cột phân định rõ ràng:
     + Video mẫu: Phân tích AI tạo prompt
     + Video mới: Dùng để đăng bài
   - Cơ sở dữ liệu SQLite lưu trữ và cập nhật trường video_mau
2. Edge Cases:
   - STT rỗng hoặc không chuẩn dạng chuỗi/số
   - Link bài gốc rỗng hoặc không phải URL
   - Tương thích ngược dữ liệu cũ và các định dạng CSV
3. Error Handling:
   - Xử lý link lỗi/mất mạng khi quét tải ngầm mà không gây sập app
   - Bảo toàn dữ liệu an toàn trong SQLite transaction
"""
import os
import sys
import unittest
import tempfile
import csv

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

try:
    from ban_win.core.config import Config
    from ban_win.core.database import get_db
    from ban_win.core.models import VideoRow
    from ban_win.core.video_checker import (
        build_default_sample_video_path,
        build_default_video_link,
        check_sample_video_file,
        check_sample_videos_batch
    )
    from ban_win.ui.quan_ly.table_widget import VideoTableWidget
except (ImportError, ModuleNotFoundError):
    raise unittest.SkipTest("Legacy ban_win Python module migrated to ban_win1 TypeScript/Electron app")


class TestSampleVideoFeature(unittest.TestCase):
    def setUp(self):
        self.db = get_db()
        self.test_stts = []

    def tearDown(self):
        for stt in self.test_stts:
            self.db.delete_video(str(stt))

    # =========================================================================
    # NHÓM 1: HAPPY PATH (Luồng chuẩn)
    # =========================================================================

    def test_happy_path_sample_video_dir_default(self):
        """Happy Path: Thư mục mẫu mặc định là C:\\Users\\Trant\\Videos\\short_drama."""
        default_dir = Config.sample_video_dir()
        self.assertTrue(default_dir.endswith("short_drama"))
        self.assertIn("short_drama", default_dir.lower())

    def test_happy_path_build_default_sample_video_path(self):
        """Happy Path: Đường dẫn mẫu mặc định cho STT 37 là C:\\Users\\Trant\\Videos\\short_drama\\37.mp4."""
        sample_path = build_default_sample_video_path("37")
        self.assertTrue(sample_path.endswith(r"short_drama\37.mp4") or sample_path.endswith("short_drama/37.mp4"))
        self.assertTrue(sample_path.endswith(".mp4"))

    def test_happy_path_9_columns_specification(self):
        """Happy Path: Bảng quản lý tiến độ có đúng 9 cột chuẩn với Video mẫu & Video mới rõ ràng."""
        expected_cols = [
            "STT",
            "Status",
            "Bài gốc",
            "Video mẫu",
            "Prompt video",
            "Báo mới",
            "Content",
            "Video mới",
            "Bài viết đã đăng"
        ]
        self.assertEqual(VideoTableWidget.COLUMNS, expected_cols)
        self.assertEqual(len(VideoTableWidget.COLUMNS), 9)
        self.assertEqual(VideoTableWidget.COLUMNS[3], "Video mẫu")
        self.assertEqual(VideoTableWidget.COLUMNS[7], "Video mới")

    def test_happy_path_db_video_mau_persistence(self):
        """Happy Path: SQLite lưu và truy xuất chính xác trường video_mau."""
        test_stt = "998811"
        self.test_stts.append(test_stt)

        sample_path = r"C:\Users\Trant\Videos\short_drama\998811.mp4"
        post_video_path = r"C:\Users\Trant\Videos\Seedance\anhtonton\AI_VIDEO\998811.mp4"

        # Tạo bản ghi mới
        self.db.upsert_video({
            "stt": test_stt,
            "bai_goc": "https://www.facebook.com/reel/123456789",
            "video_mau": sample_path,
            "link_video": post_video_path,
            "prompt_video": "Prompt mẫu phân tích từ video 998811.mp4"
        })

        row = self.db.get_video_by_stt(test_stt)
        self.assertIsNotNone(row)
        self.assertEqual(row.get("video_mau"), sample_path)
        self.assertEqual(row.get("link_video"), post_video_path)

        # Cập nhật trường video_mau riêng lẻ
        updated_sample = r"C:\Users\Trant\Videos\short_drama\998811_updated.mp4"
        self.db.update_single_field(test_stt, "video_mau", updated_sample)
        row_after = self.db.get_video_by_stt(test_stt)
        self.assertEqual(row_after.get("video_mau"), updated_sample)

    def test_happy_path_check_sample_video_file_detection(self):
        """Happy Path: Kiểm tra phát hiện file video mẫu khi file thực tế tồn tại trên đĩa."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            test_file = os.path.join(tmp_dir, "37.mp4")
            with open(test_file, "wb") as f:
                f.write(b"SAMPLE_VIDEO_DATA" * 1024)

            # Kiểm tra với đường dẫn trực tiếp
            res = check_sample_video_file(test_file, "37", base_dir=tmp_dir)
            self.assertTrue(res["exists"])
            self.assertEqual(os.path.normpath(res["path"]), os.path.normpath(test_file))
            self.assertGreater(res["bytes"], 0)

            # Kiểm tra với batch scan
            batch_res = check_sample_videos_batch([{"stt": "37", "video_mau": ""}], base_dir=tmp_dir)
            self.assertIn("37", batch_res)
            self.assertTrue(batch_res["37"]["exists"])

    # =========================================================================
    # NHÓM 2: EDGE CASES (Trường hợp biên)
    # =========================================================================

    def test_edge_case_empty_and_numeric_stt(self):
        """Edge Case: STT rỗng, None hoặc định dạng số thực 37.0."""
        self.assertEqual(build_default_sample_video_path(""), "")
        self.assertEqual(build_default_sample_video_path(None), "")
        self.assertTrue(build_default_sample_video_path("37.0").endswith("37.mp4"))

    def test_edge_case_non_existent_sample_file(self):
        """Edge Case: File video mẫu chưa tồn tại trên ổ cứng."""
        res = check_sample_video_file(r"C:\fake_non_existent_dir_xyz\9999.mp4", "9999")
        self.assertFalse(res["exists"])
        self.assertEqual(res["bytes"], 0)

    def test_edge_case_csv_migration_compatibility(self):
        """Edge Case: Nhập file CSV 8 cột cũ vẫn đọc đúng và không làm lỗi trường video_mau."""
        test_stt = "998822"
        self.test_stts.append(test_stt)

        old_8_col_row = {
            "stt": test_stt,
            "status": "FETCH VIDEO",
            "bai_goc": "https://www.facebook.com/reel/999",
            "prompt_video": "Prompt",
            "bao_moi": "https://baomoi.com",
            "content": "Content",
            "link_video": "video_moi.mp4",
            "bai_viet_da_dang": ""
        }
        self.db.upsert_video(old_8_col_row)
        saved = self.db.get_video_by_stt(test_stt)
        self.assertIsNotNone(saved)
        self.assertEqual(saved.get("link_video"), "video_moi.mp4")

    # =========================================================================
    # NHÓM 3: ERROR HANDLING (Xử lý lỗi)
    # =========================================================================

    def test_error_handling_invalid_urls_in_queue(self):
        """Error Handling: URL không hợp lệ không làm crash tiến trình tải ngầm."""
        from ban_win.core.sample_downloader import get_sample_downloader
        downloader = get_sample_downloader()
        self.assertIsNotNone(downloader)
        # Hàng đợi chấp nhận và lọc link an toàn
        downloader.queue_download("99999", "")
        # Không có crash xảy ra

    def test_error_handling_video_row_dataclass(self):
        """Error Handling: VideoRow khởi tạo an toàn với đầy đủ các trường mới."""
        v = VideoRow(stt="37", video_mau=r"C:\Users\Trant\Videos\short_drama\37.mp4")
        d = v.to_dict()
        self.assertIn("video_mau", d)
        self.assertEqual(d["video_mau"], r"C:\Users\Trant\Videos\short_drama\37.mp4")
        v2 = VideoRow.from_dict(d)
        self.assertEqual(v2.video_mau, r"C:\Users\Trant\Videos\short_drama\37.mp4")


if __name__ == "__main__":
    unittest.main()
