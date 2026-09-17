# publisher.py
# Module tự động đăng truyện lên CMS BlogBio qua REST API

import re
import requests
from bs4 import BeautifulSoup
from typing import List, Optional
from parsers.base import StoryInfo, ChapterContent


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
            if elem_type == "heading":
                html_parts.append(f'<h2>{elem_val}</h2>')
            elif elem_type == "quote":
                html_parts.append(f'<blockquote><p>{elem_val}</p></blockquote>')
            elif elem_type == "text":
                html_parts.append(f'<p>{elem_val}</p>')

        return "".join(html_parts)

    def publish_story(self, story_info: StoryInfo, chapters: List[ChapterContent], skip_intro: bool = True) -> Optional[list]:
        """
        Đăng bài viết với Content mode = Chapter qua API /admin/api/v1/posts/chapter-batch.
        """
        if not self.csrf_token:
            if not self.login():
                return None

        # Nếu chỉ có 1 chapter nhưng bên trong có nhiều PART, tự động tách thành nhiều chapter
        resolved_chapters = []
        for ch in chapters:
            resolved_chapters.extend(split_chapter_by_parts(ch))

        api_url = f"{self.base_url}/admin/api/v1/posts/chapter-batch"
        api_headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Requested-With": "XMLHttpRequest",
            "X-CSRF-TOKEN": self.csrf_token
        }

        cover_url = story_info.cover_image or ""

        # Chuẩn bị danh sách chapters
        chapters_payload = []
        for ch in resolved_chapters:
            ch_desc = self.build_chapter_description(cover_url, ch)
            chapters_payload.append({
                "title": ch.title,
                "image": cover_url,
                "description": ch_desc
            })

        payload = {
            "title": story_info.title,
            "image": cover_url,
            "skip_intro": skip_intro,
            "is_active": True,
            "is_home": True,
            "is_top": True,
            "chapters": chapters_payload
        }

        try:
            r = self.session.post(api_url, json=payload, headers=api_headers, timeout=60)
            res_data = r.json()
            if r.status_code in (200, 201) and res_data.get("ok"):
                created_posts = res_data.get("data", [])
                return created_posts
            else:
                print(f"  ❌ Lỗi tạo bài viết ({r.status_code}): {res_data.get('message')}")
                if "errors" in res_data:
                    print(f"     Chi tiết lỗi: {res_data.get('errors')}")
                return None
        except Exception as e:
            print(f"  ❌ Lỗi kết nối API CMS: {e}")
            return None
