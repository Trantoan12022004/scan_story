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
