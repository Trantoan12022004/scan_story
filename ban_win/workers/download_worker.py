"""
Worker thread tải video Facebook Reels / Video đa chất lượng.
"""
from PySide6.QtCore import QThread, Signal
from typing import Optional
from ban_win.core.fb_downloader import download_facebook_video
from ban_win.core.database import get_db

class DownloadWorker(QThread):
    progressUpdated = Signal(float, str)
    downloadFinished = Signal(dict)

    def __init__(self, url: str, output_dir: str, format_id: Optional[str] = None, custom_filename: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.url = url
        self.output_dir = output_dir
        self.format_id = format_id
        self.custom_filename = custom_filename

    def run(self):
        def on_prog(pct: float, text: str):
            self.progressUpdated.emit(pct, text)

        res = download_facebook_video(
            url=self.url,
            output_dir=self.output_dir,
            format_id=self.format_id,
            custom_filename=self.custom_filename,
            progress_callback=on_prog
        )

        if res.get("ok"):
            try:
                get_db().add_downloaded_video({
                    "url": self.url,
                    "title": res.get("title", ""),
                    "author": res.get("author", ""),
                    "duration": res.get("duration", ""),
                    "quality": self.format_id or "Auto",
                    "file_path": res.get("file_path", ""),
                    "file_size": res.get("size_str", ""),
                    "thumbnail_url": res.get("thumbnail", "")
                })
            except Exception as e:
                print(f"[DownloadWorker] DB save error: {e}")

        self.downloadFinished.emit(res)
