"""
Core data models for ban_win application.
"""
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any

@dataclass
class VideoRow:
    id: Optional[int] = None
    stt: str = ""
    trang_thai_video: str = ""
    bai_goc: str = ""
    prompt_video: str = ""
    frame_dau_tien: str = ""
    bao_goc: str = ""
    bao_moi: str = ""
    trang_thai_dang_bai: str = "chưa hoàn thành"
    content: str = ""
    link_video: str = ""
    bai_viet_da_dang: str = ""
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    synced_at: Optional[str] = None
    local_modified: int = 0
    local_modified_time: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VideoRow":
        keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in keys}
        return cls(**filtered)


@dataclass
class DownloadedVideo:
    id: Optional[int] = None
    url: str = ""
    title: str = ""
    author: str = ""
    duration: str = ""
    quality: str = ""
    file_path: str = ""
    file_size: str = ""
    thumbnail_url: str = ""
    downloaded_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ScrapedStory:
    id: Optional[int] = None
    url: str = ""
    title: str = ""
    slug: str = ""
    chapters_count: int = 0
    output_dir: str = ""
    translated: int = 0
    published: int = 0
    cms_url: str = ""
    scraped_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PromptItem:
    id: Optional[int] = None
    name: str = ""
    content: str = ""
    created_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
