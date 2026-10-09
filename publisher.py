# publisher.py
# Module tự động đăng truyện lên CMS BlogBio qua REST API

import re
import random
import string
import requests
from urllib.parse import urljoin
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


def format_chapter_title_treeiq(title: str, chapter_idx: int) -> str:
    """Format tiêu đề chương chuẩn TreeIQ: CHAPTER X — TITLE"""
    clean = (title or "").strip()
    m = re.match(r'^(?:CHAPTER|CHƯƠNG|PART)\s*(\d+)\s*[-:—–]?\s*(.*)$', clean, re.IGNORECASE)
    if m:
        num = m.group(1)
        sub = m.group(2).strip()
        return f"CHAPTER {num} — {sub.upper()}" if sub else f"CHAPTER {num}"
    
    m_num = re.match(r'^(\d+)\.?\s*(.*)$', clean)
    if m_num:
        num = m_num.group(1)
        sub = m_num.group(2).strip()
        return f"CHAPTER {num} — {sub.upper()}" if sub else f"CHAPTER {num}"

    return f"CHAPTER {chapter_idx} — {clean.upper()}" if clean else f"CHAPTER {chapter_idx}"


def generate_treeiq_slug(title: str, base_slug: Optional[str] = None) -> str:
    """Tạo slug bài viết TreeIQ chuẩn format: name-of-story-xxxxxx (kèm 6 ký tự ngẫu nhiên)"""
    slug_base = generate_slug(base_slug or title or "story")
    if not slug_base:
        slug_base = "story"
    suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"{slug_base[:100].rstrip('-')}-{suffix}"


def build_treeiq_excerpt(chapters: List[ChapterContent], max_words: int = 90) -> str:
    """Tạo excerpt 90 từ chuẩn TreeIQ từ phần mở đầu câu chuyện"""
    if not chapters:
        return ""
    ch1 = chapters[0]
    first_title = format_chapter_title_treeiq(ch1.title, 1)
    
    texts = [first_title]
    for p in ch1.paragraphs:
        clean_p = re.sub(r'<[^>]+>', '', p).strip()
        if clean_p:
            texts.append(clean_p)
        if sum(len(t.split()) for t in texts) >= max_words:
            break
            
    combined = " ".join(texts)
    words = combined.split()
    if len(words) > max_words:
        return " ".join(words[:max_words])
    return combined


def build_treeiq_body_html(chapters: List[ChapterContent]) -> str:
    """
    Ghép toàn bộ các chương thành nội dung HTML cho bài viết TreeIQ duy nhất.
    ĐẢM BẢO: Mỗi chương CHỈ chèn tối đa đúng 1 ảnh đại diện (tránh lặp 2 ảnh).
    """
    html_parts = []
    for idx, ch in enumerate(chapters, 1):
        heading = format_chapter_title_treeiq(ch.title, idx)
        html_parts.append(f"<h2>{heading}</h2>")
        
        # 1. Tìm đúng 1 ảnh đại diện duy nhất cho chương này
        chapter_image = ""
        if ch.images:
            for img in ch.images:
                if img and (img.startswith("http://") or img.startswith("https://")):
                    chapter_image = img.strip()
                    break

        if not chapter_image and ch.content_elements:
            for elem_type, elem_val in ch.content_elements:
                val = (elem_val or "").strip()
                if elem_type == "image" and (val.startswith("http://") or val.startswith("https://")):
                    chapter_image = val
                    break
                m_img = re.search(r'!\[.*?\]\((https?://[^\s)]+)\)', val)
                if m_img:
                    chapter_image = m_img.group(1)
                    break

        # 2. Chèn duy nhất 1 ảnh đại diện ngay sau tiêu đề chương
        has_inserted_image = False
        if chapter_image:
            html_parts.append(f'<p><img src="{chapter_image}" alt="" loading="lazy" decoding="async" /></p>')
            has_inserted_image = True

        # 3. Duyệt nội dung chương, bỏ qua mọi thẻ ảnh khác để đảm bảo không bị chèn thêm ảnh thứ 2
        if ch.content_elements:
            for elem_type, elem_val in ch.content_elements:
                val = (elem_val or "").strip()
                if not val:
                    continue

                if elem_type == "image":
                    # Nếu ở trên chưa có ảnh, thì lấy ảnh đầu tiên này làm ảnh duy nhất
                    if not has_inserted_image and (val.startswith("http://") or val.startswith("https://")):
                        html_parts.append(f'<p><img src="{val}" alt="" loading="lazy" decoding="async" /></p>')
                        has_inserted_image = True
                    # Nếu đã chèn rồi thì bỏ qua hoàn toàn
                    continue

                if elem_type == "heading":
                    formatted = markdown_to_html_formatting(val)
                    html_parts.append(f"<h3>{formatted}</h3>")
                elif elem_type == "quote":
                    formatted = markdown_to_html_formatting(val)
                    html_parts.append(f"<blockquote><p>{formatted}</p></blockquote>")
                elif elem_type == "text":
                    clean_text = val
                    if has_inserted_image:
                        clean_text = re.sub(r'!\[.*?\]\(https?://[^\s)]+\)', '', clean_text).strip()
                    elif re.search(r'!\[.*?\]\((https?://[^\s)]+)\)', clean_text):
                        m_img = re.search(r'!\[.*?\]\((https?://[^\s)]+)\)', clean_text)
                        if m_img:
                            html_parts.append(f'<p><img src="{m_img.group(1)}" alt="" loading="lazy" decoding="async" /></p>')
                            has_inserted_image = True
                            clean_text = re.sub(r'!\[.*?\]\(https?://[^\s)]+\)', '', clean_text).strip()

                    if clean_text:
                        formatted = markdown_to_html_formatting(clean_text)
                        html_parts.append(f"<p>{formatted}</p>")
        else:
            for p in ch.paragraphs:
                clean_p = (p or "").strip()
                if not clean_p:
                    continue
                if has_inserted_image:
                    clean_p = re.sub(r'!\[.*?\]\(https?://[^\s)]+\)', '', clean_p).strip()
                elif re.search(r'!\[.*?\]\((https?://[^\s)]+)\)', clean_p):
                    m_img = re.search(r'!\[.*?\]\((https?://[^\s)]+)\)', clean_p)
                    if m_img:
                        html_parts.append(f'<p><img src="{m_img.group(1)}" alt="" loading="lazy" decoding="async" /></p>')
                        has_inserted_image = True
                        clean_p = re.sub(r'!\[.*?\]\(https?://[^\s)]+\)', '', clean_p).strip()

                if clean_p:
                    formatted = markdown_to_html_formatting(clean_p)
                    html_parts.append(f"<p>{formatted}</p>")
                    
    return "\n".join(html_parts)


def build_treeiq_body_text(chapters: List[ChapterContent]) -> str:
    """Ghép toàn bộ các chương thành văn bản thuần cho TreeIQ"""
    text_blocks = []
    for idx, ch in enumerate(chapters, 1):
        heading = format_chapter_title_treeiq(ch.title, idx)
        paras = [p.strip() for p in ch.paragraphs if p.strip()]
        ch_text = f"{heading}\n\n" + "\n\n".join(paras)
        text_blocks.append(ch_text)
    return "\n\n\n".join(text_blocks)


def resolve_featured_image_url(cover_image: Optional[str], base_url: Optional[str] = None) -> str:
    """Chỉ chấp nhận URL tuyệt đối bắt đầu bằng http:// hoặc https:// để tránh TreeIQ trả HTTP 400"""
    if not cover_image:
        return ""
    cover = cover_image.strip()
    if cover.startswith("http://") or cover.startswith("https://"):
        return cover
    if cover.startswith("/") and base_url and (base_url.startswith("http://") or base_url.startswith("https://")):
        return urljoin(base_url, cover)
    return ""


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

    def __init__(self, base_url: str = "https://vmnewstoryus.cfx.bz", username: str = "admin", password: str = "Vnpt@123", on_log=None, cms_type: str = "auto", category_id: str = "9"):
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
        self.category_id: str = category_id
        
        lower_url = self.base_url.lower()
        if cms_type != "auto":
            self.cms_type = cms_type
        elif "teasy.live" in lower_url or "treeiq" in lower_url:
            self.cms_type = "treeiq"
        else:
            self.cms_type = "blogbio"

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
        """Trích xuất chi tiết lỗi từ HTTP Response của CMS (hỗ trợ cả JSON REST API và TreeIQ HTML form)"""
        status_code = response.status_code
        try:
            res_data = response.json()
            msg = res_data.get("message") or res_data.get("error") or ""
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
            pass

        try:
            soup = BeautifulSoup(response.text, "lxml")
            err_box = soup.find(class_=lambda c: c and any(k in c.lower() for k in ["alert", "invalid", "error", "danger"]))
            if err_box:
                err_text = err_box.get_text(" ", strip=True)
                if err_text:
                    return f"HTTP {status_code}: {err_text[:200]}"
        except Exception:
            pass

        clean_text = response.text[:150].replace('\n', ' ').strip()
        return f"HTTP {status_code} ({response.reason}): {clean_text}"

    def login(self, on_log=None) -> bool:
        """Đăng nhập vào hệ thống CMS và lấy CSRF Token cho API/Form"""
        if on_log:
            self.on_log = on_log

        login_url = f"{self.base_url}/login"
        try:
            # 1. Tải trang login
            r1 = self.session.get(login_url, timeout=15)
            if r1.status_code != 200:
                self.last_error = f"Không thể tải trang login (HTTP {r1.status_code})"
                self.log("error", f"Đăng nhập thất bại: {self.last_error}")
                return False

            soup1 = BeautifulSoup(r1.text, "lxml")
            token_input = soup1.find("input", {"name": "_token"})

            # Kiểm tra nếu đây là TreeIQ CMS (không dùng _token)
            if not token_input and (self.cms_type == "treeiq" or soup1.find("form", {"action": "/login"}) or "teasy" in self.base_url or "treeiq" in self.base_url):
                self.cms_type = "treeiq"
                return self._login_treeiq()

            if not token_input:
                self.last_error = "Không tìm thấy _token trong trang login (kiểm tra lại CMS URL)."
                self.log("error", f"Đăng nhập thất bại: {self.last_error}")
                return False

            self.cms_type = "blogbio"
            return self._login_blogbio(token_input["value"])

        except Exception as e:
            self.last_error = f"Lỗi kết nối tới CMS: {str(e)}"
            self.log("error", f"Đăng nhập thất bại: {self.last_error}")
            return False

    def _login_blogbio(self, token_val: str) -> bool:
        """Đăng nhập chuẩn Laravel / BlogBio CMS"""
        login_url = f"{self.base_url}/login"
        login_data = {
            "_token": token_val,
            "email": self.username,
            "password": self.password,
            "remember": "1"
        }

        r2 = self.session.post(login_url, data=login_data, timeout=15)
        if r2.status_code != 200:
            self.last_error = f"Request đăng nhập thất bại (HTTP {r2.status_code})"
            self.log("error", f"Đăng nhập thất bại: {self.last_error}")
            return False

        soup2 = BeautifulSoup(r2.text, "lxml")
        error_box = soup2.find(class_=lambda c: c and any(k in c for k in ["alert-danger", "invalid-feedback", "error-msg"]))
        if error_box:
            err_text = error_box.get_text(strip=True)
            if err_text:
                self.last_error = f"Sai tài khoản hoặc mật khẩu: {err_text}"
                self.log("error", f"Đăng nhập thất bại: {self.last_error}")
                return False

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

    def _login_treeiq(self) -> bool:
        """Đăng nhập chuẩn TreeIQ CMS Network"""
        login_url = f"{self.base_url}/login"
        login_data = {
            "email": self.username,
            "password": self.password
        }

        r2 = self.session.post(login_url, data=login_data, timeout=15, allow_redirects=False)
        if r2.status_code == 200:
            soup2 = BeautifulSoup(r2.text, "lxml")
            error_box = soup2.find(class_=lambda c: c and any(k in c for k in ["alert-danger", "invalid-feedback", "error-msg", "text-danger", "error"]))
            if error_box:
                err_text = error_box.get_text(strip=True)
                if err_text:
                    self.last_error = f"Sai tài khoản hoặc mật khẩu: {err_text}"
                    self.log("error", f"Đăng nhập thất bại: {self.last_error}")
                    return False

        admin_url = f"{self.base_url}/admin/posts/new"
        r3 = self.session.get(admin_url, timeout=15)
        soup3 = BeautifulSoup(r3.text, "lxml")

        if "/login" in r3.url or r3.status_code in (401, 403) or soup3.find("form", {"action": "/login"}):
            self.last_error = "Tài khoản hoặc mật khẩu không chính xác (bị điều hướng lại trang login)."
            self.log("error", f"Đăng nhập thất bại: {self.last_error}")
            return False

        csrf_input = soup3.find("input", {"name": "csrf_token"}) or soup3.find("input", {"name": "_token"})
        csrf_meta = soup3.find("meta", {"name": "csrf-token"})
        if csrf_input and csrf_input.get("value"):
            self.csrf_token = csrf_input["value"]
        elif csrf_meta and csrf_meta.get("content"):
            self.csrf_token = csrf_meta["content"]

        # Tìm category mặc định
        cat_select = soup3.find("select", {"name": "category_id"})
        if cat_select:
            options = cat_select.find_all("option")
            for opt in options:
                v = opt.get("value")
                if v and v.strip():
                    self.category_id = v.strip()
                    break

        if self.csrf_token:
            return True

        self.last_error = "Không tìm thấy csrf_token trong trang admin TreeIQ."
        self.log("error", f"Đăng nhập thất bại: {self.last_error}")
        return False

    def build_chapter_description(self, cover_url: str, chapter: ChapterContent) -> str:
        """
        Tạo HTML description cho chapter:
        Bắt đầu bằng ảnh cover chung, theo sau là các đoạn văn bản trong thẻ <p>.
        Mỗi chương CHỈ chèn tối đa đúng 1 ảnh (tránh lặp 2 ảnh).
        """
        html_parts = []
        has_image = False
        if cover_url and (cover_url.startswith("http://") or cover_url.startswith("https://")):
            html_parts.append(f'<p><img src="{cover_url}" alt=""></p>')
            has_image = True

        for elem_type, elem_val in chapter.content_elements:
            elem_val = elem_val.strip()
            if not elem_val:
                continue
            if elem_type == "image":
                if not has_image and (elem_val.startswith("http://") or elem_val.startswith("https://")):
                    html_parts.append(f'<p><img src="{elem_val}" alt=""></p>')
                    has_image = True
                continue

            if elem_type == "heading":
                formatted_val = markdown_to_html_formatting(elem_val)
                html_parts.append(f'<h2>{formatted_val}</h2>')
            elif elem_type == "quote":
                formatted_val = markdown_to_html_formatting(elem_val)
                html_parts.append(f'<blockquote><p>{formatted_val}</p></blockquote>')
            elif elem_type == "text":
                clean_val = elem_val
                if has_image:
                    clean_val = re.sub(r'!\[.*?\]\(https?://[^\s)]+\)', '', clean_val).strip()
                elif re.search(r'!\[.*?\]\((https?://[^\s)]+)\)', clean_val):
                    m_img = re.search(r'!\[.*?\]\((https?://[^\s)]+)\)', clean_val)
                    if m_img:
                        html_parts.append(f'<p><img src="{m_img.group(1)}" alt=""></p>')
                        has_image = True
                        clean_val = re.sub(r'!\[.*?\]\(https?://[^\s)]+\)', '', clean_val).strip()
                if clean_val:
                    formatted_val = markdown_to_html_formatting(clean_val)
                    html_parts.append(f'<p>{formatted_val}</p>')

        return "".join(html_parts)

    def publish_story_treeiq(self, story_info: StoryInfo, chapters: List[ChapterContent], on_log=None) -> Optional[list]:
        """
        Đăng toàn bộ câu truyện thành 1 bài viết duy nhất lên TreeIQ CMS Network.
        Tất cả các chương được gộp lại với tiêu đề <h2>CHAPTER X — [TITLE]</h2>.
        """
        if on_log:
            self.on_log = on_log

        if not self.csrf_token:
            if not self.login():
                return None

        resolved_chapters = []
        for ch in chapters:
            resolved_chapters.extend(split_chapter_by_parts(ch))

        if not resolved_chapters:
            self.last_error = "Không có nội dung chương nào để đăng."
            self.log("error", self.last_error)
            return None

        # Tiêu đề bài viết: Tên của câu chuyện viết hoa chuẩn format bài báo
        story_title = (story_info.title or "").strip().upper()
        if not story_title:
            story_title = format_chapter_title_treeiq(resolved_chapters[0].title, 1)

        # Slug kèm 6 ký tự ngẫu nhiên (ví dụ the-boy-the-kingdom-feared-ause9k)
        slug = generate_treeiq_slug(story_info.title, story_info.slug)

        # Excerpt chuẩn ~90 từ từ phần mở đầu câu chuyện
        excerpt = build_treeiq_excerpt(resolved_chapters, max_words=90)

        # Gộp toàn bộ nội dung các chương lại thành 1 câu chuyện hoàn chỉnh
        body_html = build_treeiq_body_html(resolved_chapters)
        body_text = build_treeiq_body_text(resolved_chapters)

        # Featured image: chỉ gửi URL tuyệt đối hợp lệ (tránh TreeIQ trả HTTP 400 nếu gửi relative URL)
        featured_image = resolve_featured_image_url(story_info.cover_image, self.base_url)
        if not featured_image and resolved_chapters[0].images:
            featured_image = resolve_featured_image_url(resolved_chapters[0].images[0], self.base_url)

        api_url = f"{self.base_url}/admin/posts"
        form_data = {
            "csrf_token": self.csrf_token or "",
            "title": story_title,
            "slug": slug,
            "category_id": self.category_id or "9",
            "category_ids": self.category_id or "9",
            "status": "PUBLISHED",
            "featured_image_url": featured_image,
            "excerpt": excerpt,
            "body_html": body_html,
            "body_text": body_text
        }

        self.log("info", f"🚀 Đang đăng bài tổng hợp ({len(resolved_chapters)} chương) lên TreeIQ: {story_title}...")
        try:
            r = self.session.post(api_url, data=form_data, timeout=45, allow_redirects=False)
            if r.status_code in (200, 201, 302, 303):
                loc = r.headers.get("Location") or ""
                match_id = re.search(r"/posts/(\d+)", loc)
                post_id = match_id.group(1) if match_id else "treeiq-1"
                post_url = f"{self.base_url}/story/{slug}"
                post_data = {
                    "id": post_id,
                    "title": story_title,
                    "slug": slug,
                    "url": post_url
                }
                self.log("success", f"🎉 Đã đăng thành công câu chuyện lên TreeIQ: {story_title} (ID: {post_id})")
                self.log("info", f"   👉 Link bài viết: {post_url}")
                return [post_data]
            else:
                detail_error = self._extract_error_detail(r)
                self.last_error = detail_error
                self.log("error", f"Lỗi đăng câu chuyện lên TreeIQ: {detail_error}")
                return None
        except requests.exceptions.Timeout:
            err_msg = "Request bị quá thời gian (Timeout >45s) khi gửi lên TreeIQ CMS"
            self.last_error = err_msg
            self.log("error", err_msg)
            return None
        except Exception as e:
            err_msg = f"Lỗi gửi request lên TreeIQ: {str(e)}"
            self.last_error = err_msg
            self.log("error", err_msg)
            return None

    def publish_story_blogbio(self, story_info: StoryInfo, chapters: List[ChapterContent], skip_intro: bool = True, on_log=None) -> Optional[list]:
        """
        Đăng các chapter theo dạng Standalone Posts và liên kết chuỗi next_chapter & prev_chapter
        lên BlogBio / Laravel REST API (/admin/api/v1/posts).
        """
        if on_log:
            self.on_log = on_log

        if not self.csrf_token:
            if not self.login():
                return None

        resolved_chapters = []
        for ch in chapters:
            resolved_chapters.extend(split_chapter_by_parts(ch))

        if not resolved_chapters:
            self.last_error = "Không có nội dung chương nào để đăng."
            self.log("error", self.last_error)
            return None

        chapter_slugs = []
        seen_slugs = set()
        for idx, ch in enumerate(resolved_chapters, 1):
            base_slug = generate_slug(ch.title)
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

        cover_url = story_info.cover_image or ""
        created_posts = []
        total = len(resolved_chapters)

        for idx, ch in enumerate(resolved_chapters):
            current_slug = chapter_slugs[idx]
            prev_slug = chapter_slugs[idx - 1] if idx > 0 else None
            next_slug = chapter_slugs[idx + 1] if idx < total - 1 else None

            ch_image = (ch.images[0] if (ch.images and len(ch.images) > 0) else cover_url) or ""
            ch_desc = self.build_chapter_description(ch_image or cover_url, ch)

            api_url = f"{self.base_url}/admin/api/v1/posts"
            api_headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-Requested-With": "XMLHttpRequest",
                "X-CSRF-TOKEN": self.csrf_token
            }
            payload = {
                "title": ch.title,
                "slug": current_slug,
                "image": ch_image or cover_url,
                "description": ch_desc,
                "series_id": None,
                "prev_chapter": prev_slug,
                "next_chapter": next_slug,
                "is_active": True,
                "is_home": True,
                "is_top": (idx == 0)
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

    def publish_story(self, story_info: StoryInfo, chapters: List[ChapterContent], skip_intro: bool = True, on_log=None) -> Optional[list]:
        """
        Đăng truyện lên CMS. Tự động phân nhánh theo nền tảng:
        - TreeIQ CMS: Gộp toàn bộ các chương thành 1 bài viết duy nhất.
        - BlogBio CMS: Đăng từng chương riêng biệt liên kết chuỗi prev/next chapter.
        """
        if on_log:
            self.on_log = on_log

        if self.cms_type == "treeiq":
            return self.publish_story_treeiq(story_info, chapters, on_log=on_log)
        else:
            return self.publish_story_blogbio(story_info, chapters, skip_intro=skip_intro, on_log=on_log)


