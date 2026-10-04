"""
Module cào truyện và tự động đăng CMS dành cho giao diện desktop ban_win.
Được đồng bộ 100% chuẩn xác theo logic gốc của bản web (app.py:process_story_thread).
"""
import os
import sys
import re
import time
from urllib.parse import urlparse, urljoin
from typing import Dict, Any, Optional, Callable, List

# Fix UTF-8 encoding
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from parsers import detect_parser
from ban_win.core.downloader import Downloader
from ban_win.core.translator import Translator
from ban_win.core.publisher import CMSPublisher
from ban_win.core.database import get_db

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT_DIR = os.path.dirname(APP_DIR)
DEFAULT_OUTPUT_DIR = os.path.join(ROOT_DIR, "output")

def sanitize_filename(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*]', "-", str(name or ""))
    return name[:100].strip(". -") or "story"

def save_chapter(chapter, output_dir: str) -> str:
    chapter_dir_name = f"chapter_{chapter.chapter_number:02d}"
    chapter_dir = os.path.join(output_dir, chapter_dir_name)
    os.makedirs(chapter_dir, exist_ok=True)

    title_path = os.path.join(chapter_dir, "title.md")
    with open(title_path, "w", encoding="utf-8") as f:
        f.write((chapter.title or f"Chapter {chapter.chapter_number}").strip() + "\n")

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
        f"**Tổng số chapter:** {len(chapters)}",
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
    """Xử lý cào truyện và đăng bài chuẩn xác theo quy trình của bản Web"""

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
            translate_en: bool = True,
            publish_cms: bool = False,
            cms_url: str = "",
            cms_user: str = "",
            cms_pass: str = "",
            start_ch: Optional[int] = 1,
            end_ch: Optional[int] = 0,
            delay: float = 1.2) -> Dict[str, Any]:

        if self.is_cancelled():
            return {"ok": False, "message": "Đã hủy thao tác"}

        url = (url or "").strip()
        if not url:
            err = "❌ Chưa nhập URL trang truyện."
            self.log(err)
            return {"ok": False, "message": err}

        self.progress(5.0, "Đang phân tích cấu trúc trang web...")
        self.log(f"🔍 Phân tích URL: {url}")

        try:
            parser = detect_parser(url)
            self.log(f"✅ Đã nhận diện: {parser.get_name()}")
        except Exception as e:
            err = f"❌ Lỗi nhận diện website: {e}"
            self.log(err)
            return {"ok": False, "message": err}

        self.progress(10.0, "Đang tải trang để lấy thông tin truyện...")
        self.log("📥 Đang tải trang để lấy thông tin truyện...")
        downloader = Downloader(delay=delay)
        html = downloader.fetch_html(url)
        if not html:
            err = "❌ Không thể tải trang. Vui lòng kiểm tra lại URL hoặc kết nối mạng."
            self.log(err)
            return {"ok": False, "message": err}

        try:
            story_info = parser.get_story_info(html, url)
        except Exception as e:
            err = f"❌ Lỗi khi phân tích thông tin truyện: {e}"
            self.log(err)
            return {"ok": False, "message": err}

        translator = Translator(target_lang="en") if translate_en else None

        # Dịch tên truyện nếu bật dịch
        if translator and story_info.title:
            self.log("🌐 Đang dịch tên truyện sang tiếng Anh...")
            orig_title = story_info.title
            try:
                story_info.title = translator.translate_text(story_info.title)
                if story_info.title != orig_title:
                    self.log(f"🌐 Tên truyện tiếng Anh: {story_info.title}")
            except Exception as e:
                self.log(f"⚠️ Dịch tên truyện cảnh báo: {e}")

        self.log(f"📚 Tên truyện: {story_info.title}")
        self.log(f"🔗 Nguồn: {story_info.base_url}")

        # Xử lý tổng số chapter nếu ban đầu = 0
        if story_info.total_chapters == 0:
            self.log("⚠️ Không thấy số chapter, thử tải chapter-1...")
            ch1_url = parser.build_chapter_url(story_info.base_url, 1, story_info.is_single_page)
            ch1_html = downloader.fetch_html(ch1_url)
            if ch1_html:
                story_info = parser.get_story_info(ch1_html, ch1_url)
                self.log(f"📄 Tổng số chapter xác định: {story_info.total_chapters}")

        total_chapters = story_info.total_chapters or 1
        from_ch = int(start_ch or 1)
        to_ch = int(end_ch or 0)

        s_ch = max(1, min(from_ch, total_chapters))
        e_ch = max(s_ch, min(to_ch, total_chapters)) if to_ch > 0 else total_chapters
        total_to_download = e_ch - s_ch + 1

        self.log(f"📋 Sẽ xử lý chapter {s_ch} → {e_ch} ({total_to_download} chapters)")

        # Tạo thư mục output
        base_out = output_dir or DEFAULT_OUTPUT_DIR
        story_dir_name = sanitize_filename(story_info.slug or story_info.title)
        out_story_dir = os.path.join(base_out, story_dir_name)
        images_dir = os.path.join(out_story_dir, "images")
        os.makedirs(out_story_dir, exist_ok=True)
        if download_images:
            os.makedirs(images_dir, exist_ok=True)

        chapters = []
        failed_chapters = []

        for idx, ch_num in enumerate(range(s_ch, e_ch + 1), 1):
            if self.is_cancelled():
                self.log("⚠️ Quá trình bị người dùng hủy bỏ.")
                break

            pct = 15.0 + (idx / total_to_download) * 70.0
            self.progress(pct, f"[{idx}/{total_to_download}] Đang tải Chapter {ch_num}...")
            self.log(f"📄 [{idx}/{total_to_download}] Đang tải Chapter {ch_num}...")

            ch_url = parser.build_chapter_url(story_info.base_url, ch_num, story_info.is_single_page)

            # Kiểm tra cache
            ch_html = getattr(parser, "get_cached_html", lambda u: None)(ch_url)
            if ch_html:
                self.log("   ♻ Sử dụng cache từ lần quét cấu trúc")
            else:
                clean_ch_url = ch_url.split("?")[0].split("#")[0].rstrip("/")
                clean_init_url = url.split("?")[0].split("#")[0].rstrip("/")
                current_chapter_match = urlparse(url).path
                is_cached = (story_info.is_single_page and ch_num == 1) or (clean_ch_url == clean_init_url) or (f"/chapter-{ch_num}" in current_chapter_match)

                if is_cached and html:
                    ch_html = html
                    self.log("   ♻ Sử dụng cache từ lần tải đầu")
                else:
                    ch_html = downloader.fetch_html(ch_url)
                    if ch_num < e_ch:
                        downloader.wait()

            if not ch_html:
                self.log(f"   ❌ Thất bại khi tải Chapter {ch_num}")
                failed_chapters.append(ch_num)
                continue

            try:
                chapter = parser.parse_chapter(ch_html, ch_num)
            except Exception as e:
                self.log(f"   ❌ Lỗi phân tích Chapter {ch_num}: {e}")
                failed_chapters.append(ch_num)
                continue

            self.log(f"   📝 Chapter {ch_num}: {len(chapter.paragraphs)} đoạn văn, {len(chapter.images)} ảnh")

            # Chuẩn hóa link ảnh
            for i_idx, img_u in enumerate(chapter.images):
                if not img_u.startswith("http"):
                    chapter.images[i_idx] = urljoin(ch_url, img_u)
            for i, (etype, evalue) in enumerate(chapter.content_elements):
                if etype == "image" and not evalue.startswith("http"):
                    chapter.content_elements[i] = ("image", urljoin(ch_url, evalue))

            # Tải ảnh nếu bật
            if download_images and chapter.images:
                for i_idx, img_u in enumerate(chapter.images, 1):
                    img_name = Downloader.get_image_filename(img_u, ch_num, i_idx)
                    img_path = os.path.join(images_dir, img_name)
                    downloader.download_image(img_u, img_path)

            # Dịch sang tiếng Anh
            if translator:
                self.log(f"   🌐 Đang dịch Chapter {ch_num} sang tiếng Anh...")
                try:
                    chapter = translator.translate_chapter(chapter)
                    self.log(f"   ✅ Tiêu đề EN: {chapter.title[:60]}...")
                except Exception as e:
                    self.log(f"   ⚠️ Lỗi dịch: {e}")

            # Lưu file chapter
            ch_dir_name = save_chapter(chapter, out_story_dir)
            chapters.append(chapter)
            self.log(f"   💾 Đã lưu local: {ch_dir_name}/ (title.md, content.md)")

        # Lưu file tổng hợp
        if chapters:
            save_full_story(chapters, story_info, out_story_dir)
            self.log("📝 Đã tạo file tổng hợp full_story.md")

        # Tải ảnh cover
        if download_images and story_info.cover_image:
            cover_url = story_info.cover_image
            if not cover_url.startswith("http"):
                cover_url = urljoin(story_info.base_url, cover_url)
            cover_ext = os.path.splitext(urlparse(cover_url).path)[1] or ".webp"
            cover_path = os.path.join(out_story_dir, f"cover{cover_ext}")
            if downloader.download_image(cover_url, cover_path):
                self.log(f"🖼️ Đã lưu ảnh cover: cover{cover_ext}")

        # Đăng bài lên CMS nếu bật
        cms_posts = []
        if publish_cms and chapters:
            c_url = cms_url or "https://vmnewstoryus.cfx.bz"
            c_user = cms_user or "admin"
            c_pass = cms_pass or ""
            self.log(f"🚀 Bắt đầu đăng lên CMS ({c_url}) với user '{c_user}'...")

            def cms_log_callback(event_type, msg, data=None):
                self.log(f"[{event_type.upper()}] {msg}")

            publisher = CMSPublisher(
                base_url=c_url,
                username=c_user,
                password=c_pass,
                on_log=cms_log_callback
            )

            if publisher.login():
                self.log(f"🔑 Đăng nhập CMS thành công (User: {c_user})!")
                created = publisher.publish_story(story_info, chapters)
                if created:
                    cms_posts = created
                    self.log(f"🎉 Đăng bài thành công ({len(created)}/{len(chapters)} posts đã tạo trên CMS)!")
                else:
                    self.log(f"❌ Lỗi đăng bài lên CMS: {publisher.last_error or 'Kiểm tra log lỗi ở trên'}")
            else:
                self.log(f"❌ Đăng nhập CMS thất bại: {publisher.last_error or 'Sai URL hoặc mật khẩu'}")

        # Ghi nhận vào SQLite
        try:
            get_db().add_scraped_story({
                "url": url,
                "title": story_info.title,
                "slug": sanitize_filename(story_info.slug or story_info.title),
                "chapters_count": len(chapters),
                "output_dir": out_story_dir,
                "translated": 1 if translate_en else 0,
                "published": 1 if (publish_cms and len(cms_posts) > 0) else 0,
                "cms_url": cms_url
            })
        except Exception as e:
            print(f"[story_scraper] DB error: {e}")

        self.progress(100.0, "Hoàn tất!")
        self.log(f"🎉 ĐÃ HOÀN TẤT! Đã lưu {len(chapters)} chapter vào: {out_story_dir}")

        return {
            "ok": True,
            "title": story_info.title,
            "chapters_scraped": len(chapters),
            "output_dir": out_story_dir,
            "cms_posts": cms_posts
        }
