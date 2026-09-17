# downloader.py
# Module xử lý tải nội dung HTML và hình ảnh

import os
import re
import time
import requests
from urllib.parse import urlparse, urljoin
from typing import Optional


# Headers giả lập trình duyệt để tránh bị block
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


class Downloader:
    """Xử lý tải HTML và hình ảnh với retry và rate limiting"""

    def __init__(self, delay: float = 1.5, max_retries: int = 3):
        """
        Args:
            delay: Thời gian chờ giữa các request (giây) để tránh bị block
            max_retries: Số lần thử lại tối đa khi request thất bại
        """
        self.delay = delay
        self.max_retries = max_retries
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)

    def fetch_html(self, url: str) -> Optional[str]:
        """
        Tải HTML từ URL.
        Trả về nội dung HTML dạng string, hoặc None nếu thất bại.
        """
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                response.encoding = response.apparent_encoding or "utf-8"
                return response.text
            except requests.RequestException as e:
                print(f"  ⚠ Lỗi tải {url} (lần {attempt}/{self.max_retries}): {e}")
                if attempt < self.max_retries:
                    wait_time = self.delay * attempt
                    print(f"  ⏳ Chờ {wait_time}s rồi thử lại...")
                    time.sleep(wait_time)
                else:
                    print(f"  ❌ Không thể tải: {url}")
                    return None

    def download_image(self, url: str, save_path: str) -> bool:
        """
        Tải hình ảnh và lưu vào file.
        Trả về True nếu thành công, False nếu thất bại.
        """
        # Tạo thư mục nếu chưa có
        os.makedirs(os.path.dirname(save_path), exist_ok=True)

        # Kiểm tra nếu file đã tồn tại thì bỏ qua
        if os.path.exists(save_path):
            return True

        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.session.get(url, timeout=30, stream=True)
                response.raise_for_status()

                with open(save_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                return True

            except requests.RequestException as e:
                if attempt < self.max_retries:
                    time.sleep(self.delay)
                else:
                    print(f"  ⚠ Không thể tải ảnh: {url} - {e}")
                    return False

    def wait(self):
        """Chờ giữa các request để tránh bị rate limit"""
        time.sleep(self.delay)

    @staticmethod
    def get_image_filename(url: str, chapter_num: int, img_index: int) -> str:
        """
        Tạo tên file cho hình ảnh dựa trên URL.
        Ví dụ: chapter-01-img-01.webp
        """
        # Lấy extension từ URL
        parsed = urlparse(url)
        path = parsed.path
        ext = os.path.splitext(path)[1] or ".webp"
        
        # Giới hạn extension hợp lệ
        valid_exts = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg", ".bmp"}
        if ext.lower() not in valid_exts:
            ext = ".webp"

        return f"chapter-{chapter_num:02d}-img-{img_index:02d}{ext}"
