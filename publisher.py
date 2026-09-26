# publisher.py
# Module tự động đăng truyện lên CMS BlogBio qua REST API

import re
import requests
from bs4 import BeautifulSoup
from typing import List, Optional
from parsers.base import StoryInfo, ChapterContent, markdown_to_html_formatting


def generate_slug(text: str) -> str:
    """Tạo slug chuẩn SEO từ tiêu đề văn bản"""
    import unicodedata
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('utf-8')
    text = re.sub(r'[^\w\s-]', '', text).strip().lower()
    slug = re.sub(r'[-\s]+', '-', text)
    return slug[:120].strip('-')


def split_chapter_by_parts(chapter: ChapterContent) -> List[ChapterContent]:
    """
    Nếu một chapter chứa nhiều phần (ví dụ: 'PART 1: ...', 'PART 2: ...'),
    tự động tách thành các chapter riêng biệt để đăng lên CMS.
    """
    elements = chapter.content_elements
    part_indices = []

    for idx, (elem_type, elem_val) in enumerate(elements):
        if elem_type == "heading" and re.search(r"^(PART|PARTE|CHAPTER|CAP[IÍ]TULO)\s*\d+", elem_val.strip(), re.I):
            part_indices.append((idx, elem_val.strip()))

    # Nếu tìm thấy từ 2 part trở lên, tiến hành tách
    if len(part_indices) >= 2:
        sub_chapters = []
        for i, (start_idx, part_title) in enumerate(part_indices):
            end_idx = part_indices[i + 1][0] if i + 1 < len(part_indices) else len(elements)
            # Lấy các element từ sau heading của part này đến trước heading của part tiếp theo
            sub_elements = elements[start_idx + 1:end_idx]
            sub_paragraphs = [val for etype, val in sub_elements if etype in ("text", "heading", "quote")]
            
            sub_chapters.append(ChapterContent(
                chapter_number=i + 1,
                title=part_title,
                paragraphs=sub_paragraphs,
                images=chapter.images,
                content_elements=sub_elements
            ))
        return sub_chapters

    return [chapter]


class CMSPublisher:
    """Quản lý đăng nhập và đăng bài viết lên CMS BlogBio (Laravel REST API)"""

    def __init__(self, base_url: str = "https://vmnewstoryus.cfx.bz", username: str = "admin", password: str = "Vnpt@123"):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })
        self.csrf_token: Optional[str] = None

    def login(self) -> bool:
        """Đăng nhập vào hệ thống CMS và lấy CSRF Token cho API"""
        login_url = f"{self.base_url}/login"
        try:
            # 1. Lấy _token từ trang login
            r1 = self.session.get(login_url, timeout=15)
            soup1 = BeautifulSoup(r1.text, "lxml")
            token_input = soup1.find("input", {"name": "_token"})
            if not token_input:
                print("  ❌ Không tìm thấy _token trong trang login.")
                return False

            login_data = {
                "_token": token_input["value"],
                "email": self.username,
                "password": self.password,
                "remember": "1"
            }

            # 2. Gửi request đăng nhập
            r2 = self.session.post(login_url, data=login_data, timeout=15)
            if r2.status_code != 200:
                print(f"  ❌ Đăng nhập thất bại (HTTP {r2.status_code})")
                return False

            # 3. Lấy CSRF token cho API từ trang admin
            admin_url = f"{self.base_url}/admin/posts/new"
            r3 = self.session.get(admin_url, timeout=15)
            soup3 = BeautifulSoup(r3.text, "lxml")
            csrf_meta = soup3.find("meta", {"name": "csrf-token"})
            if csrf_meta and csrf_meta.get("content"):
                self.csrf_token = csrf_meta["content"]
                return True
            else:
                print("  ❌ Không tìm thấy csrf-token trong admin.")
                return False

        except Exception as e:
            print(f"  ❌ Lỗi khi đăng nhập CMS: {e}")
            return False

    def build_chapter_description(self, cover_url: str, chapter: ChapterContent) -> str:
        """
        Tạo HTML description cho chapter:
        Bắt đầu bằng ảnh cover chung, theo sau là các đoạn văn bản trong thẻ <p>.
        """
        html_parts = []
        if cover_url:
            html_parts.append(f'<p><img src="{cover_url}" alt=""></p>')

        for elem_type, elem_val in chapter.content_elements:
            elem_val = elem_val.strip()
            if not elem_val:
                continue
            formatted_val = markdown_to_html_formatting(elem_val)
            if elem_type == "heading":
                html_parts.append(f'<h2>{formatted_val}</h2>')
            elif elem_type == "quote":
                html_parts.append(f'<blockquote><p>{formatted_val}</p></blockquote>')
            elif elem_type == "text":
                html_parts.append(f'<p>{formatted_val}</p>')

        return "".join(html_parts)

    def publish_story(self, story_info: StoryInfo, chapters: List[ChapterContent], skip_intro: bool = True) -> Optional[list]:
        """
        Đăng các chapter theo dạng Standalone Posts và liên kết chuỗi next_chapter & prev_chapter.
        Giúp mỗi chapter hiển thị đúng tiêu đề riêng của nó, không bị dính tiêu đề chương 1.
        """
        if not self.csrf_token:
            if not self.login():
                return None

        # Nếu chỉ có 1 chapter nhưng bên trong có nhiều PART, tự động tách thành nhiều chapter
        resolved_chapters = []
        for ch in chapters:
            resolved_chapters.extend(split_chapter_by_parts(ch))

        if not resolved_chapters:
            return None

        # 1. Dự tính trước slug duy nhất cho từng chapter để liên kết Next/Prev
        chapter_slugs = []
        seen_slugs = set()
        for idx, ch in enumerate(resolved_chapters, 1):
            base_slug = generate_slug(ch.title)
            # Nếu slug quá ngắn hoặc chỉ là chapter-X, thêm story slug để tránh trùng
            if len(base_slug.split('-')) <= 2 and story_info.slug:
                base_slug = f"{story_info.slug}-{base_slug}"
            if not base_slug:
                base_slug = f"chapter-{idx}"

            slug_candidate = base_slug
            counter = 1
            while slug_candidate in seen_slugs:
                slug_candidate = f"{base_slug}-{counter}"
                counter += 1

            seen_slugs.add(slug_candidate)
            chapter_slugs.append(slug_candidate)

        api_url = f"{self.base_url}/admin/api/v1/posts"
        api_headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Requested-With": "XMLHttpRequest",
            "X-CSRF-TOKEN": self.csrf_token
        }

        cover_url = story_info.cover_image or ""
        created_posts = []

        # 2. Đăng lần lượt từng chapter với liên kết prev_chapter và next_chapter
        total = len(resolved_chapters)
        for idx, ch in enumerate(resolved_chapters):
            current_slug = chapter_slugs[idx]
            prev_slug = chapter_slugs[idx - 1] if idx > 0 else None
            next_slug = chapter_slugs[idx + 1] if idx < total - 1 else None

            ch_desc = self.build_chapter_description(cover_url, ch)

            payload = {
                "title": ch.title,
                "slug": current_slug,
                "image": cover_url,
                "description": ch_desc,
                "series_id": None,          # Không đưa vào Series để tránh bị theme đè tiêu đề Series lên H1
                "prev_chapter": prev_slug,   # Nối chương trước
                "next_chapter": next_slug,   # Nối chương tiếp theo
                "is_active": True,
                "is_home": True,
                "is_top": (idx == 0)         # Chỉ đưa chapter đầu lên top
            }

            try:
                r = self.session.post(api_url, json=payload, headers=api_headers, timeout=30)
                res_data = r.json()
                if r.status_code in (200, 201) and res_data.get("ok"):
                    post_data = res_data.get("data", {})
                    created_posts.append(post_data)
                    print(f"  ✅ Đã tạo [{idx+1}/{total}]: {ch.title[:50]} (Next: {next_slug or 'Hết'})")
                else:
                    print(f"  ❌ Lỗi tạo chapter {ch.title[:30]}: {res_data.get('message')}")
                    if "errors" in res_data:
                        print(f"     Chi tiết lỗi: {res_data.get('errors')}")
            except Exception as e:
                print(f"  ❌ Lỗi khi gửi request: {e}")

        return created_posts if created_posts else None

