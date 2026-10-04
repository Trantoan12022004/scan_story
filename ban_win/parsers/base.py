# parsers/base.py
# Base class cho tất cả parser - định nghĩa interface chung

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ChapterContent:
    """Dữ liệu của một chapter sau khi parse"""
    chapter_number: int
    title: str
    paragraphs: List[str]  # Danh sách đoạn văn (text thuần)
    images: List[str]       # Danh sách URL hình ảnh
    # Nội dung đầy đủ dạng danh sách các element (text hoặc image)
    # Mỗi phần tử là tuple: ("text", "nội dung") hoặc ("image", "url")
    content_elements: List[tuple] = field(default_factory=list)


@dataclass
class StoryInfo:
    """Thông tin tổng quan về truyện"""
    title: str
    slug: str
    base_url: str  # URL gốc không có /chapter-X
    total_chapters: int
    cover_image: Optional[str] = None
    is_single_page: bool = False


class BaseParser(ABC):
    """
    Interface chung cho tất cả parser.
    Mỗi trang web cần implement class kế thừa từ đây.
    """

    @abstractmethod
    def get_story_info(self, html: str, url: str) -> StoryInfo:
        """
        Trích xuất thông tin truyện từ HTML của bất kỳ trang chapter nào.
        Trả về StoryInfo chứa title, slug, base_url, total_chapters.
        """
        pass

    @abstractmethod
    def parse_chapter(self, html: str, chapter_number: int) -> ChapterContent:
        """
        Parse nội dung một chapter từ HTML.
        Trả về ChapterContent chứa title, paragraphs, images, content_elements.
        """
        pass

    @abstractmethod
    def build_chapter_url(self, base_url: str, chapter_number: int, is_single_page: bool = False) -> str:
        """
        Tạo URL cho chapter cụ thể từ base_url và số chapter.
        """
        pass

    def get_name(self) -> str:
        """Tên parser để hiển thị log"""
        return self.__class__.__name__


import re
from bs4 import NavigableString, Tag


def tag_to_markdown(node) -> str:
    """
    Chuyển đổi một phần tử HTML (Tag hoặc NavigableString) sang định dạng Markdown,
    bảo toàn chính xác in đậm (**text**), in nghiêng (*text*), gạch ngang (~~text~~),
    và các style CSS inline tương ứng (font-weight: bold, font-style: italic).
    """
    if isinstance(node, NavigableString):
        return str(node)

    if not isinstance(node, Tag):
        return ""

    # Bỏ qua các thẻ ẩn, thẻ điều khiển
    if node.name in ("script", "style", "noscript", "iframe", "svg", "button", "input", "select"):
        return ""

    # Xử lý thẻ xuống dòng
    if node.name == "br":
        return "\n"

    # Lấy nội dung bên trong của các con đệ quy
    inner_parts = []
    for child in node.children:
        inner_parts.append(tag_to_markdown(child))
    inner = "".join(inner_parts)

    if not inner.strip():
        # Nếu chỉ toàn khoảng trắng hoặc rỗng, giữ nguyên khoảng trắng
        return inner

    # Kiểm tra style font-weight và font-style
    style = (node.get("style") or "").lower()
    is_bold = node.name in ("b", "strong") or any(
        kw in style for kw in [
            "font-weight:bold", "font-weight: bold",
            "font-weight:700", "font-weight: 700",
            "font-weight:600", "font-weight: 600",
            "font-weight:800", "font-weight:900"
        ]
    )
    is_italic = node.name in ("i", "em") or any(
        kw in style for kw in [
            "font-style:italic", "font-style: italic",
            "font-style:oblique", "font-style: oblique"
        ]
    )
    is_strike = node.name in ("s", "del", "strike")
    is_code = node.name == "code" and (node.parent is None or node.parent.name != "pre")

    def wrap_format(text: str, prefix: str, suffix: str) -> str:
        match = re.match(r"^(\s*)(.*?)(\s*)$", text, re.DOTALL)
        if not match:
            return f"{prefix}{text}{suffix}"
        lead, core, trail = match.groups()
        if not core:
            return text
        # Tránh lồng trùng lặp nếu core đã được bọc bởi chính prefix/suffix đó
        if core.startswith(prefix) and core.endswith(suffix) and len(core) >= len(prefix) + len(suffix):
            return text
        return f"{lead}{prefix}{core}{suffix}{trail}"

    res = inner
    if is_code:
        res = wrap_format(res, "`", "`")
    if is_strike:
        res = wrap_format(res, "~~", "~~")
    if is_italic:
        res = wrap_format(res, "*", "*")
    if is_bold:
        res = wrap_format(res, "**", "**")

    return res


def fix_mojibake(text: str) -> str:
    """
    Tự động nhận diện và sửa lỗi mã hóa (Mojibake) phổ biến:
    - Khi chuỗi UTF-8 bị decode nhầm bằng MacRoman:
      ‚Äú -> “, ‚Äù -> ”, ‚Äî -> —, ‚Äô -> ’, √© -> é, √≥ -> ó, √≠ -> í, √£ -> ã, etc.
    - Khi chuỗi UTF-8 bị decode nhầm bằng Windows-1252 / Latin-1:
      â€œ -> “, â€ -> ”, â€” -> —, â€™ -> ’, Ã¡ -> á, Ã© -> é, etc.
    """
    if not text or not isinstance(text, str):
        return text or ""

    # 1. Kiểm tra dấu hiệu MacRoman Mojibake
    mac_indicators = ["‚Äú", "‚Äù", "‚Äî", "‚Äô", "‚Äò", "‚Ä¶", "‚Äì", "√©", "√≥", "√≠", "√£", "√°", "√§", "√±"]
    if any(ind in text for ind in mac_indicators):
        try:
            # Thử encode lại bằng mac_roman rồi decode utf-8
            repaired = text.encode("mac_roman").decode("utf-8")
            text = repaired
        except Exception:
            # Fallback bảng thay thế nếu có ký tự lạ không thể encode mac_roman
            replacements = {
                "‚Äú": "“", "‚Äù": "”", "‚Äî": "—", "‚Äô": "’",
                "‚Äò": "‘", "‚Ä¶": "…", "‚Äì": "–",
                "√°": "á", "√©": "é", "√≠": "í", "√≥": "ó", "√∫": "ú",
                "√£": "ã", "√µ": "õ", "√¢": "â", "√™": "ê", "√¥": "ô",
                "√ß": "ç", "√ü": "ü", "√Å": "Á", "√É": "É", "√ç": "Í",
                "√ì": "Ó", "√ö": "Ú", "√Õ": "Õ", "√Ç": "Â", "√ä": "Ê",
                "√î": "Ô", "√á": "Ç",
            }
            for k, v in replacements.items():
                text = text.replace(k, v)

    # 2. Kiểm tra dấu hiệu Latin-1 / CP1252 Mojibake
    latin_indicators = ["â€œ", "â€", "â€”", "â€™", "â€˜", "â€¦", "Ã¡", "Ã©", "Ã³", "Ãº", "Ã£", "Ãµ", "Ã§", "Ã¢", "Ãª", "Ã´"]
    if any(ind in text for ind in latin_indicators):
        try:
            text = text.encode("cp1252").decode("utf-8")
        except Exception:
            try:
                text = text.encode("latin1").decode("utf-8")
            except Exception:
                pass

    return text


def clean_formatted_text(html_element) -> str:
    """
    Rút trích văn bản từ element HTML có giữ định dạng Markdown (in đậm, in nghiêng...),
    đồng thời chuẩn hóa khoảng trắng thừa và sửa lỗi font Mojibake.
    """
    if not html_element:
        return ""
    raw_md = tag_to_markdown(html_element)

    # Chuẩn hóa khoảng trắng
    lines = []
    for line in raw_md.split("\n"):
        line = re.sub(r"[ \t]+", " ", line).strip()
        if line:
            lines.append(line)
    return fix_mojibake(" ".join(lines).strip())


def markdown_to_html_formatting(text: str) -> str:
    """
    Chuyển đổi các cú pháp markdown (in đậm, in nghiêng, gạch ngang) sang thẻ HTML tương ứng cho CMS:
    - ***text*** -> <strong><em>text</em></strong>
    - **text** -> <strong>text</strong>
    - *text* -> <em>text</em>
    - ~~text~~ -> <del>text</del>
    """
    if not text:
        return ""

    # Bold + Italic: ***text*** hoặc ___text___
    text = re.sub(r"\*\*\*(.+?)\*\*\*", r"<strong><em>\1</em></strong>", text)
    text = re.sub(r"___(.+?)___", r"<strong><em>\1</em></strong>", text)

    # Bold: **text** hoặc __text__
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"__(.+?)__", r"<strong>\1</strong>", text)

    # Italic: *text* hoặc _text_
    text = re.sub(r"(?<!\*)\*(?!\*)([^\*]+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", text)
    text = re.sub(r"(?<!\w)_(?!_)([^_]+?)(?<!_)_(?!\w)", r"<em>\1</em>", text)

    # Strikethrough: ~~text~~
    text = re.sub(r"~~(.+?)~~", r"<del>\1</del>", text)

    return text

