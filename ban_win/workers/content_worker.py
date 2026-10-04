"""
Worker thread tạo content tự động (ghép caption FB Reel + link báo mới).
"""
from PySide6.QtCore import QThread, Signal
from typing import List, Optional
from ban_win.core.content_generator import auto_generate_content
from ban_win.core.database import get_db

class ContentWorker(QThread):
    contentProgress = Signal(int, int, str)
    contentFinished = Signal(dict)

    def __init__(self, stt_list: Optional[List[str]] = None, single_stt: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.stt_list = stt_list
        self.single_stt = single_stt

    def run(self):
        if self.single_stt:
            res = auto_generate_content(self.single_stt)
            self.contentFinished.emit(res)
            return

        db = get_db()
        items = db.get_all_videos()
        if self.stt_list:
            items = [it for it in items if it.get("stt") in self.stt_list]

        # Lọc những dòng có báo mới
        targets = [it for it in items if it.get("bao_moi")]
        total = len(targets)
        success = 0

        for idx, it in enumerate(targets):
            stt = str(it.get("stt", ""))
            self.contentProgress.emit(idx + 1, total, f"Đang tạo Content STT {stt} ({idx+1}/{total})")
            res = auto_generate_content(stt, it.get("bai_goc", ""), it.get("bao_moi", ""))
            if res.get("ok"):
                success += 1

        self.contentFinished.emit({
            "ok": True,
            "message": f"Đã ghép xong {total} dòng có báo mới. Thành công: {success}.",
            "success_count": success,
            "total": total
        })
