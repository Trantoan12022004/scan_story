# translator.py
# Module tự động dịch nội dung truyện sang tiếng Anh

import time
import requests
from typing import List, Tuple
from parsers.base import ChapterContent


class Translator:
    """Tự động dịch văn bản sang tiếng Anh sử dụng Google Translate endpoint"""

    def __init__(self, target_lang: str = "en", max_chunk_chars: int = 3000):
        self.target_lang = target_lang
        self.max_chunk_chars = max_chunk_chars
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })
        self.url = "https://clients5.google.com/translate_a/t"

    def translate_text(self, text: str) -> str:
        """Dịch một đoạn text ngắn (tiêu đề, tên truyện...)"""
        text = text.strip()
        if not text:
            return ""
        try:
            params = {
                "client": "dict-chrome-ex",
                "sl": "auto",
                "tl": self.target_lang,
                "q": text
            }
            r = self.session.get(self.url, params=params, timeout=15)
            if r.status_code == 200:
                data = r.json()
                if data and isinstance(data, list) and len(data) > 0 and len(data[0]) > 0:
                    return data[0][0]
        except Exception as e:
            print(f"  ⚠ Lỗi dịch text: {e}")
        return text

    def translate_elements(self, content_elements: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
        """
        Dịch danh sách content_elements [("text", ...), ("heading", ...), ("quote", ...)]
        Gom các đoạn văn bản thành cụm (batch) để dịch nhanh và giảm request.
        """
        if not content_elements:
            return []

        result = []
        batch_texts = []
        batch_indices = []
        current_len = 0

        for idx, (elem_type, elem_val) in enumerate(content_elements):
            if elem_type in ("text", "heading", "quote"):
                elem_val = elem_val.strip()
                if not elem_val:
                    result.append((elem_type, elem_val))
                    continue

                if current_len + len(elem_val) > self.max_chunk_chars and batch_texts:
                    translated_batch = self._translate_batch(batch_texts)
                    for b_idx, trans_text in zip(batch_indices, translated_batch):
                        result.append((content_elements[b_idx][0], trans_text))
                    batch_texts = []
                    batch_indices = []
                    current_len = 0
                    time.sleep(0.1)

                batch_texts.append(elem_val)
                batch_indices.append(idx)
                current_len += len(elem_val)
            else:
                if batch_texts:
                    translated_batch = self._translate_batch(batch_texts)
                    for b_idx, trans_text in zip(batch_indices, translated_batch):
                        result.append((content_elements[b_idx][0], trans_text))
                    batch_texts = []
                    batch_indices = []
                    current_len = 0
                result.append((elem_type, elem_val))

        if batch_texts:
            translated_batch = self._translate_batch(batch_texts)
            for b_idx, trans_text in zip(batch_indices, translated_batch):
                result.append((content_elements[b_idx][0], trans_text))

        return result

    def _translate_batch(self, texts: List[str]) -> List[str]:
        """Dịch 1 danh sách chuỗi bằng cách ghép delimiter để dịch trong 1 request"""
        delimiter = "\n====SPLIT====\n"
        combined = delimiter.join(texts)
        try:
            params = {
                "client": "dict-chrome-ex",
                "sl": "auto",
                "tl": self.target_lang,
                "q": combined
            }
            r = self.session.get(self.url, params=params, timeout=20)
            if r.status_code == 200:
                data = r.json()
                if data and isinstance(data, list) and len(data) > 0 and len(data[0]) > 0:
                    translated_combined = data[0][0]
                    parts = translated_combined.split("====SPLIT====")
                    if len(parts) == len(texts):
                        return [p.strip() for p in parts]
                    # Fallback nếu số đoạn sau khi tách không khớp
                    return [self.translate_text(t) for t in texts]
        except Exception as e:
            print(f"  ⚠ Lỗi dịch batch: {e}")
        return texts

    def translate_chapter(self, chapter: ChapterContent) -> ChapterContent:
        """Dịch tiêu đề và nội dung của một ChapterContent sang tiếng Anh"""
        translated_title = self.translate_text(chapter.title) if chapter.title else chapter.title
        translated_elements = self.translate_elements(chapter.content_elements)

        # Cập nhật danh sách paragraphs
        translated_paragraphs = [val for etype, val in translated_elements if etype in ("text", "heading", "quote")]

        return ChapterContent(
            chapter_number=chapter.chapter_number,
            title=translated_title,
            paragraphs=translated_paragraphs,
            images=chapter.images,
            content_elements=translated_elements
        )
