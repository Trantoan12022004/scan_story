# parsers/treeiq.py
# Parser cho các trang sử dụng TreeIQ CMS (ví dụ: sad.treeiq.biz)

import re
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from parsers.base import BaseParser, StoryInfo, ChapterContent


class TreeIQParser(BaseParser):
    """
    Parser cho TreeIQ CMS.
    Hỗ trợ các trang: *.treeiq.biz
    
    Cấu trúc HTML:
    - Tiêu đề: <h1 class="v5-title">
    - Nội dung: <div class="v5-prose ..."> chứa <p> và <img>
    - Chapter info: "Chapter X / Y" trong breadcrumb
    - Chapter list: <ol id="chapter-toc-list"> hoặc <ol id="chapter-toc-list-desktop">
    - Hình ảnh: cdn.treeiq.biz
    """

    def get_story_info(self, html: str, url: str) -> StoryInfo:
        soup = BeautifulSoup(html, "lxml")
        parsed_url = urlparse(url)

        # Lấy title từ thẻ <title> hoặc og:title
        title = ""
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            title = og_title["content"].strip()
        elif soup.title:
            # Bỏ phần "| site_name" ở cuối
            title = soup.title.string.strip().split("|")[0].strip()

        # Tìm base_url (URL truyện không có /chapter-X)
        # Tìm từ link "View intro" hoặc breadcrumb
        base_url = ""
        # Cách 1: Tìm link có text "View intro" hoặc link truyện trong breadcrumb
        intro_link = soup.find("a", string=re.compile(r"View intro", re.I))
        if intro_link and intro_link.get("href"):
            base_url = intro_link["href"]
        else:
            # Cách 2: Parse từ URL hiện tại - bỏ /chapter-X
            path = parsed_url.path
            chapter_match = re.search(r"/chapter-\d+", path)
            if chapter_match:
                base_path = path[: chapter_match.start()]
            else:
                base_path = path
            base_url = f"{parsed_url.scheme}://{parsed_url.netloc}{base_path}"

        # Đảm bảo base_url là absolute
        if base_url and not base_url.startswith("http"):
            base_url = f"{parsed_url.scheme}://{parsed_url.netloc}{base_url}"

        # Tìm slug từ base_url
        slug_match = re.search(r"/blog/(.+?)(?:/chapter-\d+)?/?$", base_url)
        slug = slug_match.group(1) if slug_match else urlparse(base_url).path.strip("/").split("/")[-1]

        # Tìm tổng số chapter
        total_chapters = 0

        # Cách 1: Tìm từ text "Chapter X / Y"
        chapter_info = soup.find("span", string=re.compile(r"Chapter\s+\d+\s*/\s*\d+"))
        if chapter_info:
            match = re.search(r"Chapter\s+\d+\s*/\s*(\d+)", chapter_info.get_text())
            if match:
                total_chapters = int(match.group(1))

        # Cách 2: Đếm từ danh sách chapter trong TOC
        if total_chapters == 0:
            toc = soup.find("ol", id="chapter-toc-list-desktop") or soup.find("ol", id="chapter-toc-list")
            if toc:
                total_chapters = len(toc.find_all("li"))

        # Cách 3: Tìm link chapter có số lớn nhất
        if total_chapters == 0:
            chapter_links = soup.find_all("a", href=re.compile(r"/chapter-(\d+)"))
            for link in chapter_links:
                href = link.get("href", "")
                m = re.search(r"/chapter-(\d+)", href)
                if m:
                    num = int(m.group(1))
                    total_chapters = max(total_chapters, num)

        # Cách 4: Single-page story (truyện 1 trang không có danh sách chapter)
        is_single_page = False
        if total_chapters == 0:
            content_div = soup.find("div", class_=re.compile(r"v5-prose|v4-prose")) or soup.find("section", class_="relative")
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
        h1 = soup.find("h1", class_=re.compile(r"v5-title|v4-title"))
        if h1:
            title = h1.get_text(strip=True)
        else:
            h1 = soup.find("h1")
            if h1:
                title = h1.get_text(strip=True)

        # Tìm container nội dung chính
        content_div = soup.find("div", class_=re.compile(r"v5-prose|v4-prose"))
        if not content_div:
            # Fallback: tìm section chứa nội dung
            content_div = soup.find("section", class_="relative")

        paragraphs = []
        images = []
        content_elements = []

        if content_div:
            # Duyệt qua tất cả children trực tiếp và nested
            for element in content_div.descendants:
                # Bỏ qua ads, recommended stories
                if hasattr(element, "get"):
                    classes = element.get("class", [])
                    if isinstance(classes, list):
                        class_str = " ".join(classes)
                    else:
                        class_str = str(classes)
                    
                    # Bỏ qua ads và related content
                    if any(skip in class_str for skip in [
                        "ad-container", "ad-", "in-article-ad", "not-prose",
                        "ads-parallax", "xad-outstream"
                    ]):
                        continue

                # Kiểm tra parent có phải là div/section not-prose không
                parent_classes = []
                for parent in element.parents:
                    if hasattr(parent, "get"):
                        pc = parent.get("class", [])
                        if isinstance(pc, list):
                            parent_classes.extend(pc)
                        else:
                            parent_classes.append(str(pc))
                
                if any("not-prose" in c for c in parent_classes):
                    continue

                # Xử lý thẻ heading (h2, h3, h4, h5, h6)
                if element.name in ("h2", "h3", "h4", "h5", "h6"):
                    text = element.get_text(strip=True)
                    if text:
                        paragraphs.append(text)
                        content_elements.append(("heading", text))

                # Xử lý thẻ <p>
                elif element.name == "p":
                    text = element.get_text(strip=True)
                    if text:
                        # Kiểm tra nếu text trong <p> bắt đầu bằng ký tự markdown heading như "## PARTE 1"
                        heading_match = re.match(r"^#{1,6}\s+(.+)$", text)
                        if heading_match:
                            clean_heading = heading_match.group(1).strip()
                            paragraphs.append(clean_heading)
                            content_elements.append(("heading", clean_heading))
                        else:
                            paragraphs.append(text)
                            content_elements.append(("text", text))

                # Xử lý thẻ blockquote
                elif element.name == "blockquote":
                    text = element.get_text(strip=True)
                    if text:
                        paragraphs.append(text)
                        content_elements.append(("quote", text))

                # Xử lý thẻ <img>
                elif element.name == "img":
                    src = element.get("src", "") or element.get("data-src", "")
                    if src and not src.startswith("data:"):
                        images.append(src)
                        content_elements.append(("image", src))

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
        return "TreeIQ CMS Parser"
