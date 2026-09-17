#!/usr/bin/env python3
# main.py
# Script chính - CLI tool lấy nội dung truyện từ nhiều trang web

import os
import sys
import re
import argparse
import time
from urllib.parse import urlparse

# Fix encoding cho Windows console (hỗ trợ emoji/unicode)
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from parsers import detect_parser
from downloader import Downloader
from translator import Translator


def sanitize_filename(name: str) -> str:
    """Loại bỏ ký tự không hợp lệ trong tên file/thư mục"""
    # Thay thế ký tự đặc biệt bằng dấu gạch ngang
    name = re.sub(r'[<>:"/\\|?*]', "-", name)
    # Giới hạn độ dài
    return name[:100].strip(". -")


def save_chapter(chapter, output_dir: str) -> str:
    """
    Lưu một chapter thành thư mục riêng với title.md và content.md (không có ảnh).
    
    Cấu trúc:
        output_dir/
            chapter_01/
                title.md
                content.md
    
    Args:
        chapter: ChapterContent object
        output_dir: Thư mục output của truyện
        
    Returns:
        Tên thư mục chapter (ví dụ: chapter_01)
    """
    chapter_dir_name = f"chapter_{chapter.chapter_number:02d}"
    chapter_dir = os.path.join(output_dir, chapter_dir_name)
    os.makedirs(chapter_dir, exist_ok=True)

    # 1. Lưu title.md (tiêu đề thuần, không có ký tự markdown '#')
    title_path = os.path.join(chapter_dir, "title.md")
    with open(title_path, "w", encoding="utf-8") as f:
        f.write(chapter.title.strip() + "\n")

    # 2. Lưu content.md (chỉ lấy text, heading, quote; loại bỏ hoàn toàn thẻ ảnh)
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
        # elem_type == "image" được bỏ qua, không ghi vào content.md

    with open(content_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).strip() + "\n")

    return chapter_dir_name


def save_full_story(chapters, story_info, output_dir: str) -> str:
    """Lưu toàn bộ truyện thành 1 file markdown duy nhất (không có ảnh)"""
    filepath = os.path.join(output_dir, "full_story.md")

    lines = []
    lines.append(f"# {story_info.title}")
    lines.append("")
    lines.append(f"**Tổng số chapter:** {story_info.total_chapters}")
    lines.append(f"**Nguồn:** {story_info.base_url}")
    lines.append("")
    lines.append("---")
    lines.append("")

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
            # Bỏ qua elem_type == "image"

        lines.append("")
        lines.append("---")
        lines.append("")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return filepath


def main():
    # Cấu hình CLI arguments
    arg_parser = argparse.ArgumentParser(
        description="📖 Story Scraper - Lấy nội dung truyện từ nhiều trang web",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ví dụ sử dụng:
  python main.py "https://sad.treeiq.biz/blog/story-slug/chapter-1"
  python main.py "https://whisper.fast2tricks.com/story-slug/chapter-1"
  python main.py "https://sad.treeiq.biz/blog/story-slug/chapter-1" --from 3 --to 10
  python main.py "https://sad.treeiq.biz/blog/story-slug/chapter-1" --no-images
  python main.py "https://sad.treeiq.biz/blog/story-slug/chapter-1" --output D:\\truyen

Trang web hỗ trợ:
  - *.treeiq.biz (TreeIQ CMS)
  - *.fast2tricks.com (AH CMS)
        """
    )
    arg_parser.add_argument("url", help="URL bất kỳ chapter nào của truyện")
    arg_parser.add_argument("--output", "-o", default="output",
                           help="Thư mục output (mặc định: output)")
    arg_parser.add_argument("--from", "-f", dest="from_chapter", type=int, default=1,
                           help="Chapter bắt đầu (mặc định: 1)")
    arg_parser.add_argument("--to", "-t", dest="to_chapter", type=int, default=0,
                           help="Chapter kết thúc (mặc định: chapter cuối)")
    arg_parser.add_argument("--delay", "-d", type=float, default=1.5,
                           help="Thời gian chờ giữa các request, tính bằng giây (mặc định: 1.5)")
    arg_parser.add_argument("--no-images", action="store_true",
                           help="Không tải hình ảnh, chỉ lấy text")
    arg_parser.add_argument("--no-full", action="store_true",
                           help="Không tạo file full_story.md tổng hợp")
    arg_parser.add_argument("--no-translate", action="store_true",
                           help="Không dịch nội dung sang tiếng Anh, giữ ngôn ngữ gốc")
    arg_parser.add_argument("--publish", action="store_true",
                           help="Tự động đăng truyện lên CMS (Content mode: chapter)")
    arg_parser.add_argument("--cms-url", type=str, default=os.getenv("CMS_URL", "https://vmnewstoryus.cfx.bz"),
                           help="Base URL của hệ thống CMS (mặc định: https://vmnewstoryus.cfx.bz)")
    arg_parser.add_argument("--cms-user", type=str, default=os.getenv("CMS_USER", "admin"),
                           help="Tài khoản đăng nhập CMS (mặc định: admin)")
    arg_parser.add_argument("--cms-pass", type=str, default=os.getenv("CMS_PASS", "admin123"),
                           help="Mật khẩu đăng nhập CMS (mặc định: admin123)")
    arg_parser.add_argument("--license-key", type=str, default="",
                           help="Kích hoạt License Key bản quyền")

    args = arg_parser.parse_args()

    url = args.url
    print("=" * 60)
    print("📖 STORY SCRAPER - Lấy nội dung truyện")
    print("=" * 60)

    # Bước 0: Kiểm tra bản quyền phần mềm
    from license_manager import LicenseManager
    if args.license_key:
        res = LicenseManager.verify_key(args.license_key)
        if res.get("valid"):
            LicenseManager.save_license(args.license_key)
            print(f"✅ Đã kích hoạt bản quyền thành công cho {res.get('user')} (Hạn: {res.get('expires')})!\n")
        else:
            print(f"❌ Kích hoạt thất bại: {res.get('message')}\n")
            sys.exit(1)

    lic = LicenseManager.check_current_license()
    if not lic.get("valid"):
        print("\n" + "=" * 60)
        print("🔒 BẢN QUYỀN CHƯA KÍCH HOẠT HOẶC ĐÃ HẾT HẠN")
        print("=" * 60)
        print(f"❌ Thông báo   : {lic.get('message')}")
        print(f"💻 Mã máy (HWID): {lic.get('hwid')}")
        print("-" * 60)
        print("👉 Vui lòng gửi Mã máy (HWID) trên cho Admin để nhận License Key.")
        print("👉 Kích hoạt bằng lệnh:")
        print(f'   python main.py "{url}" --license-key "<KEY>"')
        print("=" * 60 + "\n")
        sys.exit(1)
    else:
        print(f"🟢 Bản quyền: {lic.get('user')} | Còn {lic.get('days_left')} ngày (Hết hạn: {lic.get('expires')})\n")

    # Khởi tạo Translator (mặc định dịch sang tiếng Anh)
    translator = None if args.no_translate else Translator(target_lang="en")

    # Bước 1: Detect parser
    print(f"🔍 Phân tích URL: {url}")
    try:
        parser = detect_parser(url)
        print(f"✅ Đã nhận diện: {parser.get_name()}")
    except ValueError as e:
        print(f"❌ {e}")
        sys.exit(1)

    # Bước 2: Tải trang đầu tiên để lấy thông tin truyện
    print(f"\n📥 Đang tải trang để lấy thông tin truyện...")
    downloader = Downloader(delay=args.delay)
    html = downloader.fetch_html(url)
    if not html:
        print("❌ Không thể tải trang. Kiểm tra URL và kết nối mạng.")
        sys.exit(1)

    # Bước 3: Parse thông tin truyện
    story_info = parser.get_story_info(html, url)

    # Dịch tên truyện sang tiếng Anh nếu được bật
    if translator and story_info.title:
        orig_title = story_info.title
        story_info.title = translator.translate_text(story_info.title)
        if story_info.title != orig_title:
            print(f"   🌐 Đã dịch tên truyện sang tiếng Anh: {story_info.title}")

    print(f"\n📚 Thông tin truyện:")
    print(f"   📖 Tên: {story_info.title}")
    print(f"   🔗 Slug: {story_info.slug}")
    print(f"   📄 Tổng số chapter: {story_info.total_chapters}")
    print(f"   🌐 Base URL: {story_info.base_url}")
    if story_info.cover_image:
        print(f"   🖼️  Cover: {story_info.cover_image}")

    if story_info.total_chapters == 0:
        print("\n⚠ Không thể xác định số chapter. Thử tải chapter-1...")
        # Thử tải chapter 1 trực tiếp
        ch1_url = parser.build_chapter_url(story_info.base_url, 1, story_info.is_single_page)
        ch1_html = downloader.fetch_html(ch1_url)
        if ch1_html:
            story_info = parser.get_story_info(ch1_html, ch1_url)
            print(f"   📄 Tổng số chapter: {story_info.total_chapters}")

    if story_info.total_chapters == 0:
        print("\n❌ Không thể xác định tổng số chapter.")
        sys.exit(1)

    # Xác định phạm vi chapter cần tải
    from_ch = args.from_chapter
    to_ch = args.to_chapter if args.to_chapter > 0 else story_info.total_chapters

    # Validate
    from_ch = max(1, min(from_ch, story_info.total_chapters))
    to_ch = max(from_ch, min(to_ch, story_info.total_chapters))

    total_to_download = to_ch - from_ch + 1
    print(f"\n📋 Sẽ tải chapter {from_ch} → {to_ch} ({total_to_download} chapters)")

    # Bước 4: Tạo thư mục output
    story_dir_name = sanitize_filename(story_info.slug)
    output_dir = os.path.join(args.output, story_dir_name)
    images_dir_name = "images"
    images_dir = os.path.join(output_dir, images_dir_name)
    os.makedirs(output_dir, exist_ok=True)
    if not args.no_images:
        os.makedirs(images_dir, exist_ok=True)
    print(f"📁 Output: {os.path.abspath(output_dir)}")

    # Bước 5: Tải và parse từng chapter
    chapters = []
    image_map = {}  # URL -> local filename
    failed_chapters = []

    print(f"\n{'=' * 60}")
    print("🚀 Bắt đầu tải truyện...")
    print(f"{'=' * 60}\n")

    start_time = time.time()

    for ch_num in range(from_ch, to_ch + 1):
        ch_url = parser.build_chapter_url(story_info.base_url, ch_num, story_info.is_single_page)
        progress = f"[{ch_num - from_ch + 1}/{total_to_download}]"
        print(f"📄 {progress} Đang tải Chapter {ch_num}...")

        # Kiểm tra nếu đây là trang đã tải ở bước đầu
        current_chapter_match = re.search(r"/chapter-(\d+)", url)
        current_ch_from_url = int(current_chapter_match.group(1)) if current_chapter_match else -1

        # Sử dụng cache nếu URL ban đầu khớp với chapter hiện tại hoặc nếu là truyện 1 chapter (single page)
        is_cached = (ch_num == current_ch_from_url) or (story_info.is_single_page and ch_num == 1)
        if is_cached and html:
            ch_html = html
            print(f"   ♻ Sử dụng cache từ lần tải đầu")
        else:
            ch_html = downloader.fetch_html(ch_url)
            if ch_num < to_ch:
                downloader.wait()

        if not ch_html:
            print(f"   ❌ Thất bại!")
            failed_chapters.append(ch_num)
            continue

        # Parse chapter
        chapter = parser.parse_chapter(ch_html, ch_num)
        print(f"   ✅ {chapter.title[:60]}...")
        print(f"      📝 {len(chapter.paragraphs)} đoạn văn, 🖼️  {len(chapter.images)} hình ảnh")

        # Chuẩn hóa URLs cho hình ảnh (chuyển relative URL thành absolute URL)
        from urllib.parse import urljoin
        for img_idx, img_url in enumerate(chapter.images):
            if not img_url.startswith("http"):
                chapter.images[img_idx] = urljoin(ch_url, img_url)
        for i, (etype, evalue) in enumerate(chapter.content_elements):
            if etype == "image" and not evalue.startswith("http"):
                chapter.content_elements[i] = ("image", urljoin(ch_url, evalue))

        # Tải hình ảnh
        if not args.no_images and chapter.images:
            for img_idx, img_url in enumerate(chapter.images, 1):
                img_filename = Downloader.get_image_filename(img_url, ch_num, img_idx)
                img_path = os.path.join(images_dir, img_filename)
                
                success = downloader.download_image(img_url, img_path)
                if success:
                    image_map[img_url] = img_filename
                    print(f"      🖼️  Đã tải: {img_filename}")

        # Dịch chapter sang tiếng Anh
        if translator:
            print(f"   🌐 Đang dịch chapter sang tiếng Anh...")
            chapter = translator.translate_chapter(chapter)
            print(f"   ✅ Tiêu đề: {chapter.title[:60]}...")

        # Lưu chapter vào thư mục riêng (title.md & content.md không chứa ảnh)
        ch_dir_name = save_chapter(chapter, output_dir)
        chapters.append(chapter)
        print(f"   💾 Đã lưu: {ch_dir_name}/ (title.md, content.md)")

    # Bước 6: Tạo file tổng hợp
    if not args.no_full and chapters:
        print(f"\n📝 Tạo file tổng hợp full_story.md...")
        full_path = save_full_story(chapters, story_info, output_dir)
        print(f"   💾 Đã lưu: {os.path.basename(full_path)}")

    # Bước 7: Tải cover image
    if not args.no_images and story_info.cover_image:
        cover_url = story_info.cover_image
        if not cover_url.startswith("http"):
            cover_url = urljoin(story_info.base_url, cover_url)
        cover_ext = os.path.splitext(urlparse(cover_url).path)[1] or ".webp"
        cover_path = os.path.join(output_dir, f"cover{cover_ext}")
        if downloader.download_image(cover_url, cover_path):
            print(f"   🖼️  Đã tải cover: cover{cover_ext}")

    # Báo cáo kết quả
    elapsed = time.time() - start_time
    print(f"\n{'=' * 60}")
    print("📊 KẾT QUẢ")
    print(f"{'=' * 60}")
    print(f"   ✅ Thành công: {len(chapters)}/{total_to_download} chapters")
    if failed_chapters:
        print(f"   ❌ Thất bại: {len(failed_chapters)} chapters: {failed_chapters}")
    print(f"   🖼️  Hình ảnh: {len(image_map)} files")
    print(f"   ⏱️  Thời gian: {elapsed:.1f}s")
    print(f"   📁 Output: {os.path.abspath(output_dir)}")
    print()

    # Bước 8: Tự động đăng lên CMS nếu có cờ --publish
    if args.publish and chapters:
        print(f"{'=' * 60}")
        print("🚀 Bắt đầu tự động đăng lên CMS (Content mode: chapter)...")
        print(f"{'=' * 60}")
        from publisher import CMSPublisher
        cms_url = args.cms_url.rstrip("/")
        print(f"🔑 Đang đăng nhập vào CMS ({cms_url}) với user '{args.cms_user}'...")
        publisher = CMSPublisher(base_url=cms_url, username=args.cms_user, password=args.cms_pass)
        if publisher.login():
            print("✅ Đăng nhập CMS thành công!")
            print(f"📤 Đang đăng các chapter lên CMS...")
            created = publisher.publish_story(story_info, chapters)
            if created:
                print(f"\n🎉 Đăng bài thành công ({len(created)} bài viết đã tạo)!")
                for p in created:
                    print(f"   📄 ID: {p.get('id')} | Tiêu đề: {p.get('title')} | Slug: {p.get('slug')}")
            else:
                print("❌ Đăng bài lên CMS thất bại. Vui lòng kiểm tra log lỗi ở trên.")
        else:
            print("❌ Đăng nhập CMS thất bại.")
        print()

    if failed_chapters:
        print(f"💡 Để tải lại chapters thất bại, chạy:")
        for ch in failed_chapters:
            print(f"   python main.py \"{url}\" --from {ch} --to {ch}")


if __name__ == "__main__":
    main()
