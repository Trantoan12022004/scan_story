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

    def __init__(self, base_url: str = "https://vmnewstoryus.cfx.bz", username: str = "admin", password: str = "Vnpt@123", on_log=None):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })
        self.csrf_token: Optional[str] = None
        self.on_log = on_log              # Callback phát log ra UI: on_log(type, message)
        self.last_error: str = ""         # Lưu trữ chi tiết lỗi gần nhất

    def log(self, level: str, message: str):
        """Ghi log nội bộ ra console và phát qua callback ra giao diện UI nếu có"""
        try:
            if level == "error":
                print(f"  ❌ {message}")
            elif level == "success":
                print(f"  ✅ {message}")
            elif level == "warning":
                print(f"  ⚠️ {message}")
            else:
                print(f"  ℹ️ {message}")
        except Exception:
            try:
                print(f"  [{level.upper()}] {message.encode('ascii', 'replace').decode('ascii')}")
            except Exception:
                pass

        if self.on_log:
            try:
                self.on_log(level, message)
            except Exception:
                pass

    def _extract_error_detail(self, response: requests.Response) -> str:
        """Trích xuất chi tiết lỗi từ HTTP Response của CMS"""
        status_code = response.status_code
        try:
            res_data = response.json()
            msg = res_data.get("message") or ""
            # Bóc tách lỗi chi tiết theo từng field validate (ví dụ slug, title, content...)
            errors = res_data.get("errors")
            if errors and isinstance(errors, dict):
                error_list = []
                for field, err in errors.items():
                    if isinstance(err, list):
                        error_list.append(f"{field}: {', '.join(err)}")
                    else:
                        error_list.append(f"{field}: {err}")
                detail_str = "; ".join(error_list)
                return f"HTTP {status_code}: {msg} ({detail_str})" if msg else f"HTTP {status_code}: {detail_str}"
            elif msg:
                return f"HTTP {status_code}: {msg}"
            return f"HTTP {status_code}: {response.text[:200]}"
        except Exception:
            # CMS trả về HTML hoặc lỗi 500 / 502
            clean_text = response.text[:150].replace('\n', ' ').strip()
            return f"HTTP {status_code} ({response.reason}): {clean_text}"

    def login(self, on_log=None) -> bool:
        """Đăng nhập vào hệ thống CMS và lấy CSRF Token cho API"""
        if on_log:
            self.on_log = on_log

        login_url = f"{self.base_url}/login"
        try:
            # 1. Lấy _token từ trang login
            r1 = self.session.get(login_url, timeout=15)
            if r1.status_code != 200:
                self.last_error = f"Không thể tải trang login (HTTP {r1.status_code})"
                self.log("error", f"Đăng nhập thất bại: {self.last_error}")
                return False

            soup1 = BeautifulSoup(r1.text, "lxml")
            token_input = soup1.find("input", {"name": "_token"})
            if not token_input:
                self.last_error = "Không tìm thấy _token trong trang login (kiểm tra lại CMS URL)."
                self.log("error", f"Đăng nhập thất bại: {self.last_error}")
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
                self.last_error = f"Request đăng nhập thất bại (HTTP {r2.status_code})"
                self.log("error", f"Đăng nhập thất bại: {self.last_error}")
                return False

            # Kiểm tra xem có cảnh báo sai tài khoản/mật khẩu trong trang không
            soup2 = BeautifulSoup(r2.text, "lxml")
            error_box = soup2.find(class_=lambda c: c and any(k in c for k in ["alert-danger", "invalid-feedback", "error-msg"]))
            if error_box:
                err_text = error_box.get_text(strip=True)
                if err_text:
                    self.last_error = f"Sai tài khoản hoặc mật khẩu: {err_text}"
                    self.log("error", f"Đăng nhập thất bại: {self.last_error}")
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
                if "/login" in r3.url:
                    self.last_error = "Tài khoản hoặc mật khẩu không chính xác (bị điều hướng lại trang login)."
                else:
                    self.last_error = "Không tìm thấy csrf-token trong admin (kiểm tra quyền hạn của tài khoản CMS)."
                self.log("error", f"Đăng nhập thất bại: {self.last_error}")
                return False

        except Exception as e:
            self.last_error = f"Lỗi kết nối tới CMS: {str(e)}"
            self.log("error", f"Đăng nhập thất bại: {self.last_error}")
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

    def publish_story(self, story_info: StoryInfo, chapters: List[ChapterContent], skip_intro: bool = True, on_log=None) -> Optional[list]:
        """
        Đăng các chapter theo dạng Standalone Posts và liên kết chuỗi next_chapter & prev_chapter.
        Giúp mỗi chapter hiển thị đúng tiêu đề riêng của nó, không bị dính tiêu đề chương 1.
        """
        if on_log:
            self.on_log = on_log

        if not self.csrf_token:
            if not self.login():
                return None

        # Nếu chỉ có 1 chapter nhưng bên trong có nhiều PART, tự động tách thành nhiều chapter
        resolved_chapters = []
        for ch in chapters:
            resolved_chapters.extend(split_chapter_by_parts(ch))

        if not resolved_chapters:
            self.last_error = "Không có nội dung chương nào để đăng."
            self.log("error", self.last_error)
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
                if r.status_code in (200, 201):
                    try:
                        res_data = r.json()
                    except Exception:
                        res_data = {}

                    if res_data.get("ok", True):
                        post_data = res_data.get("data", {})
                        created_posts.append(post_data)
                        post_id = post_data.get("id", "N/A")
                        self.log("success", f"[{idx+1}/{total}] Đã đăng chapter: {ch.title[:45]} (ID: {post_id})")
                    else:
                        err_msg = res_data.get("message") or "CMS phản hồi ok: false"
                        self.last_error = f"Lỗi tạo chapter: {err_msg}"
                        self.log("error", f"[{idx+1}/{total}] '{ch.title[:35]}': {self.last_error}")
                else:
                    detail_error = self._extract_error_detail(r)
                    self.last_error = detail_error
                    self.log("error", f"[{idx+1}/{total}] Lỗi đăng '{ch.title[:35]}': {detail_error}")

            except requests.exceptions.Timeout:
                err_msg = "Request bị quá thời gian (Timeout >30s) khi gửi lên CMS"
                self.last_error = err_msg
                self.log("error", f"[{idx+1}/{total}] '{ch.title[:35]}': {err_msg}")
            except Exception as e:
                err_msg = f"Lỗi kết nối khi gửi request: {str(e)}"
                self.last_error = err_msg
                self.log("error", f"[{idx+1}/{total}] '{ch.title[:35]}': {err_msg}")

        return created_posts if created_posts else None

