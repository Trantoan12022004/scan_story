"""
Configuration management for ban_win, reading/writing from SQLite settings table.
"""
from typing import Dict, Any
from .database import get_db

class Config:
    @staticmethod
    def get(key: str, default: str = "") -> str:
        return get_db().get_setting(key, default)

    @staticmethod
    def set(key: str, value: Any):
        get_db().set_setting(key, str(value))

    @staticmethod
    def get_all() -> Dict[str, str]:
        return get_db().get_all_settings()

    # Convenience properties
    @classmethod
    def video_dir(cls) -> str:
        return cls.get("video_dir", r"C:\Users\Trant\Videos\Seedance\anhtonton\AI_VIDEO")

    @classmethod
    def set_video_dir(cls, path: str):
        cls.set("video_dir", path)

    @classmethod
    def google_sheet_id(cls) -> str:
        return cls.get("google_sheet_id", "1t4nyagzl-ySljwSK6nSxXPFttv11Vx-az2exQ9pKBuA")

    @classmethod
    def set_google_sheet_id(cls, sheet_id: str):
        cls.set("google_sheet_id", sheet_id)
        # Update sheet_csv_url accordingly if standard format
        csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
        cls.set("sheet_csv_url", csv_url)

    @classmethod
    def sheet_csv_url(cls) -> str:
        return cls.get("sheet_csv_url", f"https://docs.google.com/spreadsheets/d/{cls.google_sheet_id()}/export?format=csv")

    @classmethod
    def webhook_url(cls) -> str:
        return cls.get("webhook_url", "")

    @classmethod
    def set_webhook_url(cls, url: str):
        cls.set("webhook_url", url)

    @classmethod
    def sync_interval(cls) -> int:
        try:
            return max(2, int(cls.get("sync_interval", "3")))
        except ValueError:
            return 3

    @classmethod
    def set_sync_interval(cls, sec: int):
        cls.set("sync_interval", str(sec))

    @classmethod
    def theme(cls) -> str:
        return cls.get("theme", "light")

    @classmethod
    def set_theme(cls, theme: str):
        cls.set("theme", theme)

    @classmethod
    def cms_url(cls) -> str:
        return cls.get("cms_url", "https://vmnewstoryus.cfx.bz")

    @classmethod
    def cms_user(cls) -> str:
        return cls.get("cms_user", "admin")

    @classmethod
    def cms_pass(cls) -> str:
        return cls.get("cms_pass", "")
