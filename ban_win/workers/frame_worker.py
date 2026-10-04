"""
Worker thread trích xuất frame video Facebook/MP4.
"""
from PySide6.QtCore import QThread, Signal
from typing import List, Optional
from ban_win.core.frame_extractor import extract_frame_from_reel, ensure_local_frames_db
from ban_win.core.database import get_db

class FrameWorker(QThread):
    frameProgress = Signal(int, int, str)
    frameFinished = Signal(dict)

    def __init__(self, stt_list: Optional[List[str]] = None, single_stt: Optional[str] = None, single_url: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.stt_list = stt_list
        self.single_stt = single_stt
        self.single_url = single_url

    def run(self):
        if self.single_stt:
            res = extract_frame_from_reel(self.single_stt, self.single_url or "")
            self.frameFinished.emit(res)
            return

        db = get_db()
        items = db.get_all_videos()
        if self.stt_list:
            items = [it for it in items if it.get("stt") in self.stt_list]

        total = len(items)
        success = 0
        for idx, it in enumerate(items):
            stt = str(it.get("stt", ""))
            url = it.get("bai_goc", "")
            self.frameProgress.emit(idx + 1, total, f"Đang trích xuất frame STT {stt} ({idx+1}/{total})")
            res = extract_frame_from_reel(stt, url)
            if res.get("ok"):
                success += 1

        self.frameFinished.emit({
            "ok": True,
            "message": f"Đã xử lý xong {total} dòng. Trích xuất thành công {success} frame.",
            "success_count": success,
            "total": total
        })
