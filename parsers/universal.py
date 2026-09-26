# parsers/universal.py
# Universal Story Parser - Tự động nhận diện cấu trúc truyện và bóc tách nội dung từ mọi trang web

import re
import requests
from typing import Optional, Dict, List, Tuple
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from parsers.base import BaseParser, StoryInfo, ChapterContent, clean_formatted_text


class UniversalParser(BaseParser):
    """
    Parser đa năng thông minh:
    - Tự động nhận diện mục lục (TOC) / danh sách chapter từ HTML.
    - Tự động dò tìm điều hướng Next / Previous buttons nếu không có TOC.
    - Tự động nhận diện bài viết đơn (single-page story/blog post).
    - Tự động bóc tách tiêu đề, nội dung chính, heading, quote, và hình ảnh.
    - Tự động lọc sạch quảng cáo, popups, social share, author box và bài liên quan.
    """

    def __init__(self):
        self.chapter_urls: Dict[int, str] = {}
        self.chapter_titles: Dict[int, str] = {}
        self.cached_html: Dict[str, str] = {}
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        })

    def get_name(self) -> str:
        return "Universal Story Parser (Tự động thích ứng mọi website)"

    def get_cached_html(self, url: str) -> Optional[str]:
        """Lấy HTML đã cache trong quá trình quét cấu trúc chapter"""
        if not url:
            return None
        clean = url.split("?")[0].split("#")[0].rstrip("/")
        for k, v in self.cached_html.items():
            if k == url or k.split("?")[0].split("#")[0].rstrip("/") == clean:
                return v
        return None

    def _clean_title(self, text: str) -> str:
        """Loại bỏ tên trang web và ký tự thừa ở cuối tiêu đề"""
        if not text:
            return ""
        # Tách các đuôi phân cách tên trang web như | SiteName, :: SiteName
        for sep in [" | ", " :: "]:
            if sep in text:
                text = text.split(sep)[0]
        # Nếu có dấu " - " ở cuối phân cách với domain hoặc site name (ví dụ: Title - Brand)
        if " - " in text:
            parts = text.split(" - ")
            # Chỉ cắt nếu phần trước không phải là Chapter/Part (ví dụ: Chapter 1 - Title)
            if not re.match(r"^(?:chapter|part|chương|tập)\s*\d+$", parts[0].strip(), re.I):
                text = parts[0]
        return text.strip()

    def _has_story_content(self, html: str) -> bool:
        """Kiểm tra xem trang có nội dung truyện (đoạn văn thực sự) hay chỉ là placeholder rỗng"""
        if not html:
            return False
        soup = BeautifulSoup(html, "lxml")
        for noise in soup.select("script, style, noscript, iframe, nav, header, footer, .series-nav, .comment, .report, .modal, form"):
            noise.decompose()
        # Tìm các thẻ p có độ dài ký tự đáng kể và không phải là thông báo báo cáo/report
        ps = [
            p.get_text(strip=True) for p in soup.find_all("p")
            if len(p.get_text(strip=True)) > 25 and not any(k in p.get_text(strip=True).lower() for k in ["select a reason", "report this", "cookie"])
        ]
        return len(ps) >= 2

    def _find_nav_url(self, soup: BeautifulSoup, current_url: str, direction: str = "next") -> Optional[str]:
        """Tìm URL của nút Next hoặc Previous, tự động bỏ qua các nút bị disabled"""
        if direction == "next":
            selectors = [
                "a.series-nav__btn--next",
                "a[rel='next']",
                "a.next-chapter",
                "a.next",
                "a.next-post",
                ".nav-next a",
                "a[class*='next']",
            ]
            text_patterns = [
                r"^(?:next|tiếp|chương sau|hồi sau|chap sau|next chapter|next part|part \d+|chapter \d+)\s*(?:→|>|»)?$",
            ]
            direct_matches = {"next", "next→", "next >", "next chapter", "chương sau", "tiếp theo", "hồi sau"}
        else:
            selectors = [
                "a.series-nav__btn--prev",
                "a[rel='prev']",
                "a.prev-chapter",
                "a.prev",
                "a.previous",
                "a.prev-post",
                ".nav-prev a",
                "a[class*='prev']",
            ]
            text_patterns = [
                r"^(?:prev|previous|trước|chương trước|hồi trước|chap trước|previous chapter|prev part)\s*(?:←|<|«)?$",
            ]
            direct_matches = {"prev", "previous", "←prev", "←previous", "< prev", "chương trước", "trang trước"}

        for sel in selectors:
            for btn in soup.select(sel):
                classes = btn.get("class", [])
                if isinstance(classes, str):
                    classes = classes.split()
                if any("disabled" in c for c in classes) or btn.get("aria-disabled") == "true":
                    continue
                href = btn.get("href", "").strip()
                if href and not href.startswith("#") and not href.startswith("javascript:"):
                    return urljoin(current_url, href)

        for a in soup.find_all("a"):
            classes = a.get("class", [])
            if isinstance(classes, str):
                classes = classes.split()
            if any("disabled" in c for c in classes) or a.get("aria-disabled") == "true":
                continue
            txt = a.get_text(strip=True).lower()
            href = a.get("href", "").strip()
            if not href or href.startswith("#") or href.startswith("javascript:"):
                continue
            if txt in direct_matches or any(re.match(p, txt) for p in text_patterns):
                return urljoin(current_url, href)

        return None

    def _discover_chapters(self, start_url: str, start_html: str) -> Tuple[Dict[int, str], bool]:
        """
        Dò tìm danh sách chapter:
        1. Kiểm tra TOC / Chapter List trên trang (loại trừ các thanh điều hướng pagination/series-nav)
        2. Dò tìm Next/Previous link chain hai chiều (Backward & Forward)
        3. Kiểm tra URL pattern
        Trả về: (dict {chapter_num: url}, is_single_page)
        """
        clean_start_url = start_url.split("?")[0].split("#")[0].rstrip("/")
        soup = BeautifulSoup(start_html, "lxml")
        self.cached_html[start_url] = start_html
        self.cached_html[clean_start_url] = start_html

        # Bước 1: Tìm Table of Contents (TOC) thực thụ (không phải thanh điều hướng nav/series-nav)
        toc_candidates = soup.find_all(
            ["ol", "ul", "div", "section"],
            class_=re.compile(r"\b(?:chapter-list|toc-list|story-chapters|table-of-contents|chapter-toc|ql-table|inkitt-reader)\b", re.I)
        )
        for container in toc_candidates:
            # Loại trừ nếu là thanh điều hướng next/prev hoặc pagination
            c_classes = " ".join(container.get("class", []))
            if re.search(r"\b(?:series-nav|pagination|pager|nav-links|breadcrumb)\b", c_classes, re.I):
                continue

            links = container.find_all("a")
            temp_urls: Dict[int, str] = {}
            for idx, a in enumerate(links, 1):
                href = a.get("href")
                if not href or href.startswith("#") or href.startswith("javascript:"):
                    continue
                txt = a.get_text(strip=True)
                # Bỏ qua các nút next/previous nếu có trong container
                if any(k in txt.lower() for k in ["next", "prev", "previous", "tiếp", "trước"]):
                    continue

                full_href = urljoin(start_url, href).split("?")[0].split("#")[0]

                # Tìm số chapter trong text hoặc URL
                m = re.search(r"(?:chapter|part|chương|tập|hồi)\s*(\d+)", txt, re.I)
                if not m:
                    m = re.search(r"/(?:chapter|part|chap)-(\d+)", full_href, re.I)

                if m:
                    ch_num = int(m.group(1))
                    temp_urls[ch_num] = full_href
                elif len(links) >= 3 and any(k in full_href.lower() for k in ["chapter", "part", "chap", "blog"]):
                    temp_urls[len(temp_urls) + 1] = full_href

            # Chỉ chấp nhận nếu có từ 3 chapter thực thụ trở lên
            if len(temp_urls) >= 3:
                sorted_keys = sorted(temp_urls.keys())
                normalized_urls = {i: temp_urls[k] for i, k in enumerate(sorted_keys, 1)}
                return normalized_urls, False

        # Bước 2: Dò tìm theo nút Next / Previous (Bidirectional chain tracing)
        next_button = self._find_nav_url(soup, start_url, direction="next")
        prev_button = self._find_nav_url(soup, start_url, direction="prev")

        if next_button or prev_button:
            visited_urls = set()
            back_chain: List[str] = []

            # 2.1 Quét ngược về các chapter trước (Previous)
            curr_url = clean_start_url
            curr_html = start_html
            while len(back_chain) < 100:
                prev_u = self._find_nav_url(BeautifulSoup(curr_html, "lxml"), curr_url, direction="prev")
                if not prev_u:
                    break
                prev_clean = prev_u.split("?")[0].split("#")[0].rstrip("/")
                if prev_clean == curr_url or prev_clean in visited_urls or prev_clean == clean_start_url:
                    break

                # Đảm bảo cùng domain
                parsed_curr = urlparse(curr_url)
                parsed_prev = urlparse(prev_clean)
                if parsed_prev.netloc != parsed_curr.netloc:
                    break
                if not parsed_prev.path or parsed_prev.path in ("/", ""):
                    break

                # Kiểm tra số chapter nếu cả 2 đều có: prev_num phải nhỏ hơn curr_num
                m_curr = re.search(r"/(?:chapter|part|chap)-(\d+)", curr_url, re.I)
                m_prev = re.search(r"/(?:chapter|part|chap)-(\d+)", prev_clean, re.I)
                if m_curr and m_prev and int(m_prev.group(1)) >= int(m_curr.group(1)):
                    break

                visited_urls.add(prev_clean)
                try:
                    r = self.session.get(prev_clean, timeout=12)
                    if r.status_code != 200:
                        break
                    prev_html = r.text
                    self.cached_html[prev_u] = prev_html
                    self.cached_html[prev_clean] = prev_html

                    # Chỉ thêm vào danh sách nếu trang có nội dung truyện (bỏ qua trang landing rỗng)
                    if self._has_story_content(prev_html):
                        back_chain.append(prev_clean)

                    curr_url = prev_clean
                    curr_html = prev_html
                except Exception:
                    break

            # 2.2 Quét xuôi về các chapter sau (Next)
            forward_chain: List[str] = []
            curr_url = clean_start_url
            curr_html = start_html
            visited_urls.add(clean_start_url)

            # Kiểm tra trang bắt đầu có nội dung truyện không
            if self._has_story_content(start_html):
                forward_chain.append(clean_start_url)

            while len(back_chain) + len(forward_chain) < 200:
                curr_soup = BeautifulSoup(curr_html, "lxml")
                next_u = self._find_nav_url(curr_soup, curr_url, direction="next")
                if not next_u:
                    break
                next_clean = next_u.split("?")[0].split("#")[0].rstrip("/")
                if next_clean == curr_url or next_clean in visited_urls:
                    break

                # Đảm bảo cùng domain
                parsed_curr = urlparse(curr_url)
                parsed_next = urlparse(next_clean)
                if parsed_next.netloc != parsed_curr.netloc:
                    break
                if not parsed_next.path or parsed_next.path in ("/", ""):
                    break

                # Kiểm tra số chapter nếu cả 2 đều có: next_num phải lớn hơn curr_num
                m_curr = re.search(r"/(?:chapter|part|chap)-(\d+)", curr_url, re.I)
                m_next = re.search(r"/(?:chapter|part|chap)-(\d+)", next_clean, re.I)
                if m_curr and m_next and int(m_next.group(1)) <= int(m_curr.group(1)):
                    # Số chapter nhỏ hơn hoặc bằng hiện tại -> đã nhảy sang truyện khác
                    break

                visited_urls.add(next_clean)
                try:
                    r = self.session.get(next_clean, timeout=12)
                    if r.status_code != 200:
                        break
                    next_html = r.text
                    self.cached_html[next_u] = next_html
                    self.cached_html[next_clean] = next_html

                    if self._has_story_content(next_html):
                        forward_chain.append(next_clean)

                    curr_url = next_clean
                    curr_html = next_html
                except Exception:
                    break

            full_chain = list(reversed(back_chain)) + forward_chain
            if not full_chain:
                full_chain = [clean_start_url]

            if len(full_chain) >= 2:
                chapter_urls = {i: u for i, u in enumerate(full_chain, 1)}
                return chapter_urls, False
            elif len(full_chain) == 1 and not (next_button or prev_button):
                return {1: full_chain[0]}, True

        # Bước 3: Kiểm tra pattern trong URL
        m = re.search(r"/(?:chapter|part|chap)-(\d+)", clean_start_url, re.I)
        if m:
            # Thử tìm text 'Chapter X / Y' hoặc 'Chapter X of Y'
            total_m = re.search(r"(?:chapter|part|chương)\s+\d+\s*(?:/|of|\s+trên\s+)\s*(\d+)", soup.get_text(), re.I)
            if total_m:
                total_cnt = int(total_m.group(1))
                prefix = clean_start_url[:m.start(1)]
                suffix = clean_start_url[m.end(1):]
                pattern_urls = {i: f"{prefix}{i}{suffix}" for i in range(1, total_cnt + 1)}
                return pattern_urls, False

        # Bước 4: Mặc định là Single Page Story (Truyện 1 chapter / bài viết độc lập)
        return {1: clean_start_url}, True

    def get_story_info(self, html: str, url: str) -> StoryInfo:
        soup = BeautifulSoup(html, "lxml")
        clean_url = url.split("?")[0].split("#")[0].rstrip("/")
        parsed_url = urlparse(clean_url)

        # 1. Trích xuất Tiêu đề truyện
        title = ""
        og_title = soup.find("meta", property="og:title")
        og_text = self._clean_title(og_title["content"].strip()) if (og_title and og_title.get("content")) else ""

        # Kiểm tra h1
        h1_candidates = soup.find_all("h1")
        h1_text = ""
        for h in h1_candidates:
            txt = h.get_text(strip=True)
            if not re.match(r"^(?:end of|report|comment)", txt, re.I):
                h1_text = txt
                break

        # Nếu h1 có dạng "Chapter X - Title", thì h1 là chapter title, còn og:title thường là story title
        is_h1_chapter = bool(re.match(r"^(?:chapter|part|chương|tập)\s*\d+", h1_text, re.I))
        is_og_chapter = bool(re.match(r"^(?:chapter|part|chương|tập)\s*\d+", og_text, re.I))

        if og_text and not is_og_chapter:
            title = og_text
        elif h1_text and not is_h1_chapter:
            title = h1_text
        elif og_text:
            title = og_text
        elif h1_text:
            title = h1_text
        elif soup.title:
            title = self._clean_title(soup.title.get_text(strip=True))

        raw_title = self._clean_title(title)
        # Nếu tiêu đề vẫn còn dạng "Chapter 1 – The Woman Who Came Back", lấy phần tên truyện chính
        clean_story_title = re.sub(
            r"^(?:chapter|part|chương|tập)\s*\d+\s*(?:[:–—\-]|\s+–\s+|\s+—\s+|\s+-\s+)\s*",
            "",
            raw_title,
            flags=re.I
        ).strip()
        story_title = clean_story_title if len(clean_story_title) >= 3 else raw_title

        # 2. Trích xuất Cover Image
        cover_image = None
        og_image = soup.find("meta", property="og:image") or soup.find("meta", attrs={"name": "twitter:image"})
        if og_image and og_image.get("content"):
            cover_image = urljoin(url, og_image["content"])
        else:
            first_img = soup.find("img")
            if first_img and first_img.get("src"):
                src = first_img.get("src")
                if not src.startswith("data:") and not any(k in src.lower() for k in ["icon", "avatar", "logo"]):
                    cover_image = urljoin(url, src)

        # 3. Dò tìm chapters
        self.chapter_urls, is_single_page = self._discover_chapters(clean_url, html)
        total_chapters = len(self.chapter_urls)

        # 4. Xác định base_url và slug
        if is_single_page:
            base_url = clean_url
            slug = parsed_url.path.strip("/").split("/")[-1]
        else:
            # Bỏ phần chapter cuối cùng để lấy base_url
            base_path = re.sub(r"/(?:chapter|part|chap)[-_/]?\d+.*$", "", parsed_url.path)
            base_url = f"{parsed_url.scheme}://{parsed_url.netloc}{base_path}".rstrip("/")
            slug = parsed_url.path.strip("/").split("/")[-1]
            slug = re.sub(r"^(?:chapter|part|chap)-\d+-?", "", slug) or "story"

        return StoryInfo(
            title=story_title or "Untitled Story",
            slug=slug or "story",
            base_url=base_url,
            total_chapters=total_chapters,
            cover_image=cover_image,
            is_single_page=is_single_page,
        )

    def build_chapter_url(self, base_url: str, chapter_number: int, is_single_page: bool = False) -> str:
        """Tạo URL cho chapter cụ thể"""
        if is_single_page:
            return base_url
        if chapter_number in self.chapter_urls:
            return self.chapter_urls[chapter_number]
        return f"{base_url}/chapter-{chapter_number}"

    def parse_chapter(self, html: str, chapter_number: int) -> ChapterContent:
        soup = BeautifulSoup(html, "lxml")

        # 1. Lấy tiêu đề chapter
        title = ""
        # Thử lấy từ og:title nếu chứa thông tin chapter cụ thể
        og_t = soup.find("meta", property="og:title")
        if og_t and og_t.get("content"):
            og_text = self._clean_title(og_t["content"])
            if re.search(r"\b(?:chapter|part|chương)\b", og_text, re.I):
                title = og_text

        if not title:
            h1_list = soup.find_all("h1")
            for h in h1_list:
                txt = h.get_text(strip=True)
                if not any(k in txt.lower() for k in ["end of", "report", "comment"]):
                    title = txt
                    break

        if not title and soup.title:
            title = self._clean_title(soup.title.get_text(strip=True))

        if not title:
            title = f"Chapter {chapter_number}"

        # 2. Tìm container nội dung chính
        content_div = None
        selectors = [
            ".inkitt-reader__content",
            ".module-article-content__body",
            ".v5-prose", ".v4-prose", ".prose",
            ".entry-content", ".post-content", ".article-content",
            ".chapter-content", ".story-content", ".reading-content",
            "article", "[itemprop='articleBody']", "main",
        ]
        for sel in selectors:
            elem = soup.select_one(sel)
            if elem and len(elem.find_all("p")) >= 2:
                content_div = elem
                break

        # Fallback heuristic: tìm div/section có nhiều thẻ <p> dài nhất
        if not content_div:
            best_elem = None
            max_p_count = 0
            for elem in soup.find_all(["div", "section", "article"]):
                valid_ps = [p for p in elem.find_all("p", recursive=False) if len(p.get_text(strip=True)) > 20]
                if len(valid_ps) > max_p_count:
                    max_p_count = len(valid_ps)
                    best_elem = elem
            content_div = best_elem or soup.body

        paragraphs: List[str] = []
        images: List[str] = []
        content_elements: List[tuple] = []

        if content_div:
            # Loại bỏ các thành phần rác: script, style, ads, social, popup
            for tag in content_div.find_all(["script", "style", "noscript", "iframe"]):
                tag.decompose()

            noise_class = re.compile(
                r"ad-|ad_|ads|not-prose|share|social|author|related|recommend|comment|report|modal|breadcrumb|pagination",
                re.I
            )
            for noise in content_div.find_all(attrs={"class": noise_class}):
                noise.decompose()

            for el in content_div.descendants:
                if not getattr(el, "name", None):
                    continue

                # Heading (h2, h3, h4, h5, h6)
                if el.name in ("h2", "h3", "h4", "h5", "h6"):
                    txt = clean_formatted_text(el)
                    if txt and not any(k in txt.lower() for k in ["end of chapter", "report this", "share this"]):
                        paragraphs.append(txt)
                        content_elements.append(("heading", txt))

                # Paragraph
                elif el.name == "p":
                    if el.find_parent(["p", "blockquote"]):
                        continue
                    txt = clean_formatted_text(el)
                    if not txt:
                        continue
                    # Bỏ qua các thông báo rác cuối trang
                    if any(k in txt.lower() for k in ["end of chapter", "report this article", "select a reason"]):
                        continue

                    # Kiểm tra heading markdown trong thẻ p như "## Chapter 1"
                    m = re.match(r"^#{1,6}\s+(.+)$", txt)
                    if m:
                        clean_head = m.group(1).strip()
                        paragraphs.append(clean_head)
                        content_elements.append(("heading", clean_head))
                    else:
                        paragraphs.append(txt)
                        content_elements.append(("text", txt))

                # Blockquote
                elif el.name == "blockquote":
                    txt = clean_formatted_text(el)
                    if txt:
                        paragraphs.append(txt)
                        content_elements.append(("quote", txt))

                # Thẻ div đóng vai trò đoạn văn bản độc lập (không chứa thẻ block con)
                elif el.name == "div" and not el.find(["p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "ul", "ol"]):
                    if el.find_parent(["p", "blockquote"]):
                        continue
                    txt = clean_formatted_text(el)
                    if txt and len(txt) > 20 and not any(k in txt.lower() for k in ["end of chapter", "report this article", "select a reason"]):
                        paragraphs.append(txt)
                        content_elements.append(("text", txt))

                # Image
                elif el.name == "img":
                    src = (
                        el.get("src")
                        or el.get("data-src")
                        or el.get("data-original")
                        or el.get("data-lazy-src")
                        or ""
                    )
                    if src and not src.startswith("data:") and not any(k in src.lower() for k in ["icon", "avatar", "logo", "badge", "pixel"]):
                        if src not in images:
                            images.append(src)
                            content_elements.append(("image", src))

        return ChapterContent(
            chapter_number=chapter_number,
            title=title,
            paragraphs=paragraphs,
            images=images,
            content_elements=content_elements,
        )
