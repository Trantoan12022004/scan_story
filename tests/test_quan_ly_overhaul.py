"""
Bộ kiểm thử tự động xác minh toàn diện tính năng Nâng cấp Quản Lý Tiến Độ:
1. Gộp trạng thái video & đăng thành cột Status duy nhất với 5 trạng thái tiếng Anh.
2. Màu sắc riêng biệt cho Badge và màu nền nhạt (row tint) cho toàn bộ dòng.
3. Bỏ 2 cột Frame đầu tiên và Báo gốc -> tinh gọn còn 8 cột chuẩn.
4. Tính năng thêm hàng loạt bài gốc kèm tự động đánh số STT liên tục.
5. Kiểm tra đầy đủ 3 nhóm kịch bản: Happy Path, Edge Cases, Error Handling.
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
    from ban_win.core.database import get_db
    from ban_win.core.status_engine import (
        determine_video_status,
        STATUS_FETCH_VIDEO,
        STATUS_VIDEO_READY,
        STATUS_CONTENT_DONE,
        STATUS_POSTED,
        STATUS_FAILED,
        VALID_STATUSES,
        STATUS_COLORS,
        STATUS_ROW_TINTS,
    )
except (ImportError, ModuleNotFoundError):
    raise unittest.SkipTest("Legacy ban_win Python module migrated to ban_win1 TypeScript/Electron app")


class TestQuanLyOverhaul(unittest.TestCase):
    """Bộ kiểm thử nâng cấp Quản Lý Tiến Độ."""

    def setUp(self):
        self.db = get_db()
        self.test_stts = []

    def tearDown(self):
        # Dọn dẹp dữ liệu test
        for stt in self.test_stts:
            self.db.delete_video(str(stt))

    # =========================================================================
    # NHÓM 1: HAPPY PATH (Luồng xử lý chuẩn)
    # =========================================================================

    def test_happy_path_status_lifecycle_transitions(self):
        """Happy Path: Vòng đời chuyển trạng thái chuẩn từ Reel -> Video -> Content -> Posted."""
        # 1. Có link bài gốc -> FETCH VIDEO
        row = {"bai_goc": "https://www.facebook.com/reel/111222333"}
        self.assertEqual(determine_video_status(row), STATUS_FETCH_VIDEO)

        # 2. Có video MP4 cục bộ / link video -> VIDEO READY
        row["link_video"] = "test_video.mp4"
        self.assertEqual(determine_video_status(row), STATUS_VIDEO_READY)

        # 3. Có cả video MP4 và nội dung Content -> CONTENT DONE
        row["content"] = "Tiêu đề bài viết và nội dung tóm tắt chi tiết."
        self.assertEqual(determine_video_status(row), STATUS_CONTENT_DONE)

        # 4. Có link bài viết đã đăng hoàn chỉnh -> POSTED
        row["bai_viet_da_dang"] = "https://www.facebook.com/fanpage/posts/999888"
        self.assertEqual(determine_video_status(row), STATUS_POSTED)

    def test_auto_status_rules_and_video_exists_flag(self):
        """Kiểm tra chính xác 3 quy tắc tự động cập nhật status theo yêu cầu:
        1. Cột content có nội dung + cột Link video (có sẵn) -> CONTENT DONE
        2. Cột video (có sẵn) -> VIDEO READY
        3. Cột bài viết đã đăng: có link -> POSTED
        """
        # Quy tắc 1: Content có nội dung + Link video (có sẵn) -> CONTENT DONE
        row1 = {"stt": "1", "content": "Nội dung bài viết mới", "link_video": ""}
        self.assertEqual(determine_video_status(row1, video_exists=True), STATUS_CONTENT_DONE)

        # Quy tắc 2: Video (có sẵn) + Content rỗng -> VIDEO READY
        row2 = {"stt": "2", "content": "   ", "link_video": ""}
        self.assertEqual(determine_video_status(row2, video_exists=True), STATUS_VIDEO_READY)

        # Quy tắc 3: Bài viết đã đăng có link -> POSTED
        row3 = {
            "stt": "3",
            "content": "Nội dung",
            "link_video": "vid.mp4",
            "bai_viet_da_dang": "https://www.facebook.com/reel/12345"
        }
        self.assertEqual(determine_video_status(row3, video_exists=True), STATUS_POSTED)

        # Quy tắc 3b: Dù chưa có file video nhưng có link bài đã đăng -> POSTED
        row3b = {"stt": "3b", "bai_viet_da_dang": "https://facebook.com/post/999"}
        self.assertEqual(determine_video_status(row3b, video_exists=False), STATUS_POSTED)

    def test_distinct_vibrant_colors_and_richer_tints(self):
        """Kiểm tra 5 màu trạng thái hoàn toàn khác biệt và màu tint dòng đậm nét rõ ràng."""
        all_bg_colors = set()
        all_text_colors = set()
        all_row_tints = set()

        for status in VALID_STATUSES:
            c = STATUS_COLORS[status]
            self.assertNotIn(c["bg"], all_bg_colors, f"Màu nền {c['bg']} bị trùng cho trạng thái {status}")
            self.assertNotIn(c["text"], all_text_colors, f"Màu chữ {c['text']} bị trùng cho trạng thái {status}")
            all_bg_colors.add(c["bg"])
            all_text_colors.add(c["text"])

            tint = STATUS_ROW_TINTS[status]
            self.assertNotIn(tint, all_row_tints, f"Màu tint dòng {tint} bị trùng cho trạng thái {status}")
            all_row_tints.add(tint)

        # Kiểm tra POSTED dùng màu Cam/Hổ phách nhận diện tức thì
        posted_c = STATUS_COLORS[STATUS_POSTED]
        self.assertEqual(posted_c["bg"], "#fed7aa")
        self.assertEqual(posted_c["text"], "#c2410c")
        self.assertEqual(STATUS_ROW_TINTS[STATUS_POSTED], "#fff3e6")

    def test_happy_path_bulk_add_reels_sequential_stt(self):
        """Happy Path: Thêm hàng loạt link Reel, tự động tính STT tiếp theo liên tục."""
        initial_next = self.db.get_next_stt()
        self.assertGreaterEqual(initial_next, 1)

        urls = [
            "https://www.facebook.com/reel/10001",
            "https://www.facebook.com/reel/10002",
            "https://www.facebook.com/reel/10003"
        ]

        inserted = self.db.bulk_insert_reels(urls)
        self.assertEqual(len(inserted), 3)

        for idx, item in enumerate(inserted):
            expected_stt = str(initial_next + idx)
            self.assertEqual(str(item["stt"]), expected_stt)
            self.assertEqual(item["bai_goc"], urls[idx])
            self.assertEqual(item["status"], STATUS_FETCH_VIDEO)
            self.test_stts.append(expected_stt)

        # Kiểm tra STT tiếp theo trong DB đã được cập nhật tăng lên
        new_next = self.db.get_next_stt()
        self.assertEqual(new_next, initial_next + 3)

    def test_happy_path_database_status_filtering_and_stats(self):
        """Happy Path: Thống kê và lọc danh sách video theo status mới."""
        stt_f = f"test_stat_{initial_next if (initial_next := self.db.get_next_stt()) else 9000}"
        self.test_stts.append(stt_f)

        self.db.upsert_video({
            "stt": stt_f,
            "bai_goc": "https://fb.com/reel/test_stat",
            "link_video": "vid.mp4",
            "content": "Done content",
            "status": STATUS_CONTENT_DONE
        })

        row = self.db.get_video_by_stt(stt_f)
        self.assertIsNotNone(row)
        self.assertEqual(row.get("status"), STATUS_CONTENT_DONE)

        # Lọc danh sách theo status
        filtered = self.db.get_all_videos(status=STATUS_CONTENT_DONE)
        matching = [r for r in filtered if str(r["stt"]) == str(stt_f)]
        self.assertEqual(len(matching), 1)

        # Kiểm tra thống kê stat_counts có chứa các trường mới
        stats = self.db.get_stat_counts()
        self.assertIn("content_done", stats)
        self.assertIn("video_ready", stats)
        self.assertIn("posted", stats)
        self.assertIn("fetch_video", stats)

    # =========================================================================
    # NHÓM 2: EDGE CASES (Dữ liệu biên, rỗng, định dạng đặc biệt)
    # =========================================================================

    def test_edge_case_bulk_add_with_empty_and_whitespace_lines(self):
        """Edge Case: Dán danh sách có dòng trống, khoảng trắng đầu/cuối, link trùng."""
        urls = [
            "   ",
            "https://www.facebook.com/reel/20001\n",
            "\n\n",
            "  https://www.facebook.com/reel/20002   ",
            "   ",
            "https://www.facebook.com/reel/20001",  # Trùng lặp
            ""
        ]

        inserted = self.db.bulk_insert_reels(urls, deduplicate=True)
        # Chỉ có 2 link duy nhất hợp lệ
        self.assertEqual(len(inserted), 2)
        for r in inserted:
            self.test_stts.append(str(r["stt"]))

        self.assertEqual(inserted[0]["bai_goc"], "https://www.facebook.com/reel/20001")
        self.assertEqual(inserted[1]["bai_goc"], "https://www.facebook.com/reel/20002")

    def test_edge_case_next_stt_with_non_numeric_and_gaps(self):
        """Edge Case: Tính STT tiếp theo khi có STT phi số hoặc ngắt quãng."""
        stt_txt = "custom_code_abc"
        self.test_stts.append(stt_txt)
        self.db.upsert_video({
            "stt": stt_txt,
            "bai_goc": "https://fb.com/reel/custom",
            "status": STATUS_FETCH_VIDEO
        })

        # get_next_stt phải bỏ qua STT không thuần số một cách an toàn
        next_val = self.db.get_next_stt()
        self.assertIsInstance(next_val, int)
        self.assertGreater(next_val, 0)

    def test_edge_case_status_determination_with_blank_fields(self):
        """Edge Case: Hàng dữ liệu hoàn toàn rỗng hoặc chỉ có khoảng trắng."""
        empty_row = {
            "bai_goc": "   ",
            "link_video": "",
            "content": "  \n  ",
            "bai_viet_da_dang": ""
        }
        # Mặc định an toàn là FETCH VIDEO
        self.assertEqual(determine_video_status(empty_row), STATUS_FETCH_VIDEO)

    def test_happy_path_columns_and_csv_8_col_workflow(self):
        """Happy Path: Cấu trúc 9 cột chuẩn và quy trình xuất/nhập CSV."""
        from ban_win.ui.quan_ly.table_widget import VideoTableWidget
        expected_cols = [
            "STT", "Status", "Bài gốc", "Video mẫu", "Prompt video",
            "Báo mới", "Content", "Video mới", "Bài viết đã đăng"
        ]
        self.assertEqual(VideoTableWidget.COLUMNS, expected_cols)

        # Test dữ liệu xuất CSV
        stt = "test_csv_9col"
        self.test_stts.append(stt)
        self.db.upsert_video({
            "stt": stt,
            "status": STATUS_VIDEO_READY,
            "bai_goc": "https://fb.com/reel/csv9",
            "video_mau": r"C:\Users\Trant\Videos\short_drama\test_csv_9col.mp4",
            "prompt_video": "Prompt CSV 9",
            "bao_moi": "https://baomoi.com/123",
            "content": "Content CSV 9",
            "link_video": "test.mp4",
            "bai_viet_da_dang": ""
        })

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="", encoding="utf-8-sig") as tmp:
            tmp_path = tmp.name
            writer = csv.writer(tmp)
            writer.writerow(VideoTableWidget.COLUMNS)
            writer.writerow([
                stt, STATUS_VIDEO_READY, "https://fb.com/reel/csv9",
                r"C:\Users\Trant\Videos\short_drama\test_csv_9col.mp4",
                "Prompt CSV 9", "https://baomoi.com/123", "Content CSV 9",
                "test.mp4", ""
            ])

        try:
            # Đọc lại và kiểm tra header đúng 9 cột
            with open(tmp_path, "r", newline="", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                rows = [r for r in reader if r]
                self.assertEqual(rows[0], expected_cols)
                self.assertEqual(len(rows[1]), 9)
                self.assertEqual(rows[1][1], STATUS_VIDEO_READY)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_edge_case_csv_import_backward_compatibility(self):
        """Edge Case: Hỗ trợ nạp cả file CSV 11 cột cũ và CSV 8 cột mới."""
        from ban_win.ui.quan_ly.table_widget import VideoTableWidget

        # Giả lập file CSV cũ 11 cột
        legacy_row = [
            "9901", "Xong video", "https://fb.com/reel/old",
            "Prompt Old", "frame.jpg", "bao_goc.html", "bao_moi.html",
            "hoàn thành", "Old content", "old_vid.mp4", "https://fb.com/post/old"
        ]
        self.test_stts.append("9901")

        # Nạp theo định dạng cũ
        self.db.upsert_video({
            "stt": legacy_row[0],
            "trang_thai_video": legacy_row[1],
            "bai_goc": legacy_row[2],
            "prompt_video": legacy_row[3],
            "frame_dau_tien": legacy_row[4],
            "bao_goc": legacy_row[5],
            "bao_moi": legacy_row[6],
            "trang_thai_dang_bai": legacy_row[7],
            "content": legacy_row[8],
            "link_video": legacy_row[9],
            "bai_viet_da_dang": legacy_row[10]
        })

        saved = self.db.get_video_by_stt("9901")
        self.assertIsNotNone(saved)
        # Vì có link bài viết đã đăng, status tự động là POSTED
        self.assertEqual(saved.get("status"), STATUS_POSTED)

    # =========================================================================
    # NHÓM 3: ERROR HANDLING (Xử lý lỗi & Ghi đè trạng thái)
    # =========================================================================

    def test_error_handling_manual_failed_status_override(self):
        """Error Handling: Khi người dùng đổi sang FAILED, giữ nguyên FAILED kể cả khi có file/link."""
        row_failed = {
            "status": STATUS_FAILED,
            "bai_goc": "https://fb.com/reel/error_one",
            "link_video": "has_file.mp4",
            "content": "Has text",
            "bai_viet_da_dang": "https://fb.com/fanpage/posts/123"
        }
        # Người dùng tự đổi FAILED -> phải tôn trọng lựa chọn của người dùng
        self.assertEqual(determine_video_status(row_failed), STATUS_FAILED)

        # Hỗ trợ cả text tiếng Việt "không tạo được" cũ nếu có
        row_vn_failed = {
            "status": "không tạo được",
            "link_video": "abc.mp4"
        }
        self.assertEqual(determine_video_status(row_vn_failed), STATUS_FAILED)

    def test_error_handling_bulk_add_empty_list(self):
        """Error Handling: Nạp danh sách hoàn toàn rỗng."""
        inserted = self.db.bulk_insert_reels([])
        self.assertEqual(inserted, [])

        inserted_whitespace = self.db.bulk_insert_reels(["   ", "\n", "\t"])
        self.assertEqual(inserted_whitespace, [])


if __name__ == "__main__":
    unittest.main()

