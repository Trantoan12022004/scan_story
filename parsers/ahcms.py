# parsers/ahcms.py
# Parser cho các trang sử dụng AH CMS Script (ví dụ: whisper.fast2tricks.com)

import re
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from parsers.base import BaseParser, StoryInfo, ChapterContent


class AHCMSParser(BaseParser):
    """
    Parser cho AH CMS Script 1.0.
    Hỗ trợ các trang: *.fast2tricks.com
    
    Cấu trúc HTML:
    - Tiêu đề: <h1 class="pst-title">
    - Nội dung: <div class="entry-content"> chứa <p>, <h2>, <img>
    - Hình ảnh: trong <div class="pst-img-wrap"> hoặc trực tiếp <img> trong entry-content
    - Chapter info: biến JS `chapterNum`, `postId`, `slug`
    - Chapter list: <ul class="ql-table"> hoặc mobile TOC items
    - Breadcrumb: <div class="pst-bc">
    """

    def get_story_info(self, html: str, url: str) -> StoryInfo:
        soup = BeautifulSoup(html, "lxml")
        parsed_url = urlparse(url)

        # Lấy title từ og:title
        title = ""
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            # Bỏ phần "| site_name" ở cuối
            raw_title = og_title["content"].strip()
            # Tìm pattern "Chapter Title — Story Title | SiteName"
            # hoặc "Story Title | SiteName"
            parts = raw_title.split("|")
            full_title = parts[0].strip()
            # Nếu có dấu "—", lấy phần sau (tên truyện gốc)
            if "—" in full_title:
                title = full_title.split("—")[-1].strip()
            elif " — " in full_title:
                title = full_title.split(" — ")[-1].strip()
            else:
                title = full_title

        # Nếu chưa có title, thử từ thẻ <title>
        if not title and soup.title and soup.title.string:
            raw = soup.title.string.strip().split("|")[0].strip()
            if "—" in raw:
                title = raw.split("—")[-1].strip()
            else:
                title = raw

        # Tìm slug từ biến JS hoặc URL
        slug = ""
        # Cách 1: Tìm biến JS `slug`
        script_match = re.search(r'const\s+slug\s*=\s*"([^"]+)"', html)
        if not script_match:
            script_match = re.search(r'var\s+slug\s*=\s*"([^"]+)"', html)
        if script_match:
            slug = script_match.group(1)
        else:
            # Cách 2: Parse từ URL
            path = parsed_url.path.strip("/")
            # Bỏ /chapter-X nếu có
            path = re.sub(r"/chapter-\d+$", "", path)
            slug = path.split("/")[-1] if "/" in path else path

        # Tìm base_url
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}/{slug}"

        # Tìm tổng số chapter
        total_chapters = 0

        # Cách 1: Đếm từ quick links table (ql-table)
        ql_table = soup.find("ul", class_="ql-table")
        if ql_table:
            items = ql_table.find_all("li")
            total_chapters = len(items)

        # Cách 2: Đếm từ mobile TOC items
        if total_chapters == 0:
            mobile_items = soup.find_all(attrs={"data-chapter-search": True})
            if mobile_items:
                total_chapters = len(mobile_items)

        # Cách 3: Tìm link chapter có số lớn nhất
        if total_chapters == 0:
            chapter_links = soup.find_all("a", href=re.compile(r"/chapter-(\d+)"))
            for link in chapter_links:
                href = link.get("href", "")
                m = re.search(r"/chapter-(\d+)", href)
                if m:
                    num = int(m.group(1))
                    total_chapters = max(total_chapters, num)

        # Cách 4: Tìm từ text breadcrumb "CHAPTER X OF Y"
        if total_chapters == 0:
            bc_chapter = soup.find("span", class_="pst-bc-chapter")
            if bc_chapter:
                m = re.search(r"CHAPTER\s+\d+\s+OF\s+(\d+)", bc_chapter.get_text(), re.I)
                if m:
                    total_chapters = int(m.group(1))

        # Cách 5: Single-page post nếu có content nhưng không có TOC/chapter links
        is_single_page = False
        if total_chapters == 0:
            content_div = soup.find("div", class_="entry-content") or soup.find("div", class_="pst-main")
            if content_div and content_div.find("p"):
                total_chapters = 1
                is_single_page = True

        # Lấy cover image
        cover_image = None
        og_image = soup.find("meta", property="og:image")
        if og_image and og_image.get("content"):
            cover_image = og_image["content"]

        return StoryInfo(
            title=title,
            slug=slug,
            base_url=base_url.rstrip("/"),
            total_chapters=total_chapters,
            cover_image=cover_image,
            is_single_page=is_single_page,
        )

    def parse_chapter(self, html: str, chapter_number: int) -> ChapterContent:
        soup = BeautifulSoup(html, "lxml")

        # Lấy tiêu đề chapter
        title = ""
        h1 = soup.find("h1", class_="pst-title")
        if h1:
            title = h1.get_text(strip=True)
        else:
            h1 = soup.find("h1")
            if h1:
                title = h1.get_text(strip=True)

        # Tìm container nội dung chính
        content_div = soup.find("div", class_="entry-content")
        if not content_div:
            content_div = soup.find("div", class_="pst-main")

        paragraphs = []
        images = []
        content_elements = []

        if content_div:
            # Loại bỏ các element không cần thiết trước khi parse
            # Xóa ads
            for ad in content_div.find_all("div", class_=re.compile(r"ai-block|ad-|mgid")):
                ad.decompose()
            # Xóa share buttons
            for share in content_div.find_all("div", class_=re.compile(r"pst-share|share-btn")):
                share.decompose()
            # Xóa related posts
            for related in content_div.find_all("div", class_=re.compile(r"pst-related|pst-rel")):
                related.decompose()
            # Xóa author box
            for author in content_div.find_all("div", class_=re.compile(r"pst-author-box")):
                author.decompose()
            # Xóa chapter navigation buttons
            for nav in content_div.find_all("a", class_=re.compile(r"chapter-nav-btn|read-from-start")):
                nav.decompose()
            # Xóa quick links
            for ql in content_div.find_all("div", class_=re.compile(r"ql-container")):
                ql.decompose()
            # Xóa tags
            for tags in content_div.find_all("div", class_=re.compile(r"pst-tags")):
                tags.decompose()

            # Duyệt qua các element con trực tiếp
            for element in content_div.children:
                if not hasattr(element, "name") or element.name is None:
                    continue

                # Xử lý thẻ <p>
                if element.name == "p":
                    text = element.get_text(strip=True)
                    if text:
                        paragraphs.append(text)
                        content_elements.append(("text", text))

                # Xử lý heading (h2, h3, h4...)
                elif element.name in ("h2", "h3", "h4", "h5", "h6"):
                    text = element.get_text(strip=True)
                    if text:
                        paragraphs.append(text)
                        content_elements.append(("heading", text))

                # Xử lý hình ảnh trực tiếp
                elif element.name == "img":
                    src = element.get("src", "") or element.get("data-src", "")
                    if src and not src.startswith("data:"):
                        images.append(src)
                        content_elements.append(("image", src))

                # Xử lý div chứa hình (pst-img-wrap)
                elif element.name == "div":
                    classes = element.get("class", [])
                    class_str = " ".join(classes) if isinstance(classes, list) else str(classes)

                    if "pst-img-wrap" in class_str:
                        img = element.find("img")
                        if img:
                            src = img.get("src", "") or img.get("data-src", "")
                            if src and not src.startswith("data:"):
                                images.append(src)
                                content_elements.append(("image", src))
                    else:
                        # Tìm text và images bên trong div
                        for sub_p in element.find_all("p"):
                            text = sub_p.get_text(strip=True)
                            if text:
                                paragraphs.append(text)
                                content_elements.append(("text", text))
                        for sub_img in element.find_all("img"):
                            src = sub_img.get("src", "") or sub_img.get("data-src", "")
                            if src and not src.startswith("data:"):
                                images.append(src)
                                content_elements.append(("image", src))

                # Xử lý blockquote
                elif element.name == "blockquote":
                    text = element.get_text(strip=True)
                    if text:
                        paragraphs.append(text)
                        content_elements.append(("quote", text))

        return ChapterContent(
            chapter_number=chapter_number,
            title=title,
            paragraphs=paragraphs,
            images=images,
            content_elements=content_elements,
        )

    def build_chapter_url(self, base_url: str, chapter_number: int, is_single_page: bool = False) -> str:
        if is_single_page:
            return base_url
        return f"{base_url}/chapter-{chapter_number}"

    def get_name(self) -> str:
        return "AH CMS Parser"
