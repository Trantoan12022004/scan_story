"""
Module cào truyện và tự động đăng CMS dành cho giao diện desktop ban_win.
Hỗ trợ callback logging realtime và callback tiến trình.
"""
import os
import sys
import re
import time
from urllib.parse import urlparse
from typing import Dict, Any, Optional, Callable, List

from ban_win.parsers import detect_parser
from ban_win.core.downloader import Downloader
from ban_win.core.translator import Translator
from ban_win.core.publisher import CMSPublisher, split_chapter_by_parts
from ban_win.core.database import get_db

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_OUTPUT_DIR = os.path.join(APP_DIR, "output")

def sanitize_filename(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*]', "-", name)
    return name[:100].strip(". -")

def save_chapter(chapter, output_dir: str) -> str:
    chapter_dir_name = f"chapter_{chapter.chapter_number:02d}"
    chapter_dir = os.path.join(output_dir, chapter_dir_name)
    os.makedirs(chapter_dir, exist_ok=True)

    title_path = os.path.join(chapter_dir, "title.md")
    with open(title_path, "w", encoding="utf-8") as f:
        f.write(chapter.title.strip() + "\n")

    content_path = os.path.join(chapter_dir, "content.md")
    lines = []
    for elem_type, elem_value in chapter.content_elements:
        if elem_type == "text":
            lines.append(elem_value)
            lines.append("")
        elif elem_type == "heading":
            lines.append(f"## {elem_value}")
            lines.append("")
        elif elem_type == "quote":
            lines.append(f"> {elem_value}")
            lines.append("")

    with open(content_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).strip() + "\n")

    return chapter_dir_name

def save_full_story(chapters, story_info, output_dir: str) -> str:
    filepath = os.path.join(output_dir, "full_story.md")
    lines = [
        f"# {story_info.title}",
        "",
        f"**Tổng số chapter:** {story_info.total_chapters}",
        f"**Nguồn:** {story_info.base_url}",
        "",
        "---",
        ""
    ]
    for chapter in chapters:
        lines.append(f"## {chapter.title}")
        lines.append("")
        for elem_type, elem_value in chapter.content_elements:
            if elem_type == "text":
                lines.append(elem_value)
                lines.append("")
            elif elem_type == "heading":
                lines.append(f"### {elem_value}")
                lines.append("")
            elif elem_type == "quote":
                lines.append(f"> {elem_value}")
                lines.append("")
        lines.append("---")
        lines.append("")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).strip() + "\n")
    return filepath


class StoryScraperEngine:
    """Xử lý cào truyện và đăng bài với tín hiệu realtime"""

    def __init__(self,
                 on_log: Optional[Callable[[str], None]] = None,
                 on_progress: Optional[Callable[[float, str], None]] = None,
                 is_cancelled: Optional[Callable[[], bool]] = None):
        self.on_log = on_log or (lambda msg: print(msg))
        self.on_progress = on_progress or (lambda pct, status: None)
        self.is_cancelled = is_cancelled or (lambda: False)

    def log(self, msg: str):
        if self.on_log:
            self.on_log(msg)

    def progress(self, pct: float, status: str):
        if self.on_progress:
            self.on_progress(pct, status)

    def run(self,
            url: str,
            output_dir: Optional[str] = None,
            download_images: bool = False,
            translate_en: bool = False,
            publish_cms: bool = False,
            cms_url: str = "",
            cms_user: str = "",
            cms_pass: str = "",
            start_ch: Optional[int] = None,
            end_ch: Optional[int] = None,
            delay: float = 1.0) -> Dict[str, Any]:

        if self.is_cancelled():
            return {"ok": False, "message": "Đã hủy thao tác"}

        self.progress(5.0, "Đang phân tích cấu trúc trang web...")
        self.log(f"[*] Bắt đầu cào truyện từ: {url}")

        parser_class = detect_parser(url)
        if not parser_class:
            err = f"[-] Chưa hỗ trợ cào từ trang web này: {url}"
            self.log(err)
            return {"ok": False, "message": err}

        parser = parser_class()
        self.log(f"[+] Sử dụng parser: {parser.NAME}")

        try:
            story_info = parser.get_story_info(url)
        except Exception as e:
            err = f"[-] Lỗi khi lấy thông tin truyện: {e}"
            self.log(err)
            return {"ok": False, "message": err}

        if not story_info:
            err = "[-] Không tìm thấy thông tin truyện tại đường dẫn này."
            self.log(err)
            return {"ok": False, "message": err}

        self.log(f"[+] Tên truyện: {story_info.title}")
        self.log(f"[+] Tác giả: {story_info.author or 'Chưa rõ'}")
        self.log(f"[+] Tìm thấy: {story_info.total_chapters} chapter")

        base_out = output_dir or DEFAULT_OUTPUT_DIR
        story_folder = sanitize_filename(story_info.title)
        out_story_dir = os.path.join(base_out, story_folder)
        os.makedirs(out_story_dir, exist_ok=True)

        # Lọc danh sách chapters
        ch_list = story_info.chapters
        if start_ch is not None or end_ch is not None:
            s_idx = (start_ch - 1) if (start_ch and start_ch > 0) else 0
            e_idx = end_ch if (end_ch and end_ch > 0) else len(ch_list)
            ch_list = ch_list[s_idx:e_idx]

        total_to_scrape = len(ch_list)
        if total_to_scrape == 0:
            err = "[-] Không có chapter nào được chọn để cào."
            self.log(err)
            return {"ok": False, "message": err}

        self.log(f"[*] Tiến hành cào {total_to_scrape} chapter...")

        downloader = Downloader(on_log=self.on_log) if download_images else None
        translator = Translator(on_log=self.on_log) if translate_en else None

        publisher = None
        if publish_cms:
            publisher = CMSPublisher(
                base_url=cms_url or "https://vmnewstoryus.cfx.bz",
                username=cms_user or "admin",
                password=cms_pass or "",
                on_log=self.on_log
            )
            self.log("[*] Đang đăng nhập vào CMS BlogBio...")
            if not publisher.login():
                self.log("[-] Đăng nhập CMS thất bại! Vui lòng kiểm tra lại tài khoản/mật khẩu.")
                publish_cms = False
            else:
                self.log("[+] Đăng nhập CMS thành công!")

        scraped_chapters = []
        for idx, ch_meta in enumerate(ch_list):
            if self.is_cancelled():
                self.log("[!] Quá trình bị người dùng hủy bỏ.")
                break

            pct = 10.0 + (idx / total_to_scrape) * 75.0
            self.progress(pct, f"Đang cào Chapter {ch_meta.chapter_number} ({idx+1}/{total_to_scrape})")
            self.log(f"--> Đang cào Chapter {ch_meta.chapter_number}: {ch_meta.title}")

            try:
                ch_content = parser.get_chapter_content(ch_meta.url, ch_meta.chapter_number)
            except Exception as e:
                self.log(f"[-] Lỗi cào chapter {ch_meta.chapter_number}: {e}")
                continue

            if not ch_content:
                self.log(f"[!] Chapter {ch_meta.chapter_number} rỗng, bỏ qua.")
                continue

            # Dịch thuật
            if translator:
                self.log(f"[*] Dịch Chapter {ch_content.chapter_number} sang tiếng Anh...")
                ch_content = translator.translate_chapter(ch_content)

            # Lưu file local
            save_chapter(ch_content, out_story_dir)
            scraped_chapters.append(ch_content)

            # Đăng CMS
            if publish_cms and publisher:
                parts = split_chapter_by_parts(ch_content)
                for p in parts:
                    self.log(f"[*] Đang đăng '{p.title}' lên CMS...")
                    pub_res = publisher.publish_chapter(p, story_info.title)
                    if pub_res.get("ok"):
                        self.log(f"[+] Đăng thành công: {pub_res.get('url')}")
                    else:
                        self.log(f"[-] Đăng thất bại: {pub_res.get('message')}")

            if delay > 0 and idx < total_to_scrape - 1:
                time.sleep(delay)

        # Lưu full_story.md
        if scraped_chapters:
            save_full_story(scraped_chapters, story_info, out_story_dir)

        # Ghi nhận vào SQLite
        try:
            get_db().add_scraped_story({
                "url": url,
                "title": story_info.title,
                "slug": sanitize_filename(story_info.title),
                "chapters_count": len(scraped_chapters),
                "output_dir": out_story_dir,
                "translated": 1 if translate_en else 0,
                "published": 1 if publish_cms else 0,
                "cms_url": cms_url
            })
        except Exception as e:
            print(f"[story_scraper] DB save error: {e}")

        self.progress(100.0, "Hoàn tất cào truyện!")
        self.log(f"[🎉] Hoàn tất! Đã lưu {len(scraped_chapters)} chapter vào thư mục: {out_story_dir}")

        return {
            "ok": True,
            "title": story_info.title,
            "chapters_scraped": len(scraped_chapters),
            "output_dir": out_story_dir
        }
