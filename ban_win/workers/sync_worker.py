"""
Worker thread đồng bộ dữ liệu Google Sheets ngầm (polling định kỳ hoặc chạy thủ công).
"""
import time
from PySide6.QtCore import QThread, Signal
from ban_win.core.sheets_sync import sync_with_google_sheet
from ban_win.core.config import Config
from ban_win.core.frame_extractor import ensure_local_frames_db
from ban_win.core.content_generator import ensure_auto_content_db

class SyncWorker(QThread):
    syncCompleted = Signal(dict)
    syncStatus = Signal(str)

    def __init__(self, continuous: bool = True, force: bool = False, overwrite_all: bool = False, parent=None):
        super().__init__(parent)
        self.continuous = continuous
        self.force = force
        self.overwrite_all = overwrite_all
        self._running = True

    def run(self):
        if not self.continuous:
            # Chạy 1 lần theo yêu cầu
            self.syncStatus.emit("Đang kết nối Google Sheets...")
            res = sync_with_google_sheet(overwrite_all=self.overwrite_all, force=self.force)
            # Tự động quét local frames và ghép content nếu cần
            ensure_local_frames_db()
            ensure_auto_content_db()
            self.syncCompleted.emit(res)
            return

        # Vòng lặp đồng bộ nền định kỳ
        while self._running:
            try:
                auto_sync_enabled = Config.get("auto_sync", "1") == "1"
                if auto_sync_enabled:
                    res = sync_with_google_sheet(overwrite_all=False, force=False)
                    if res.get("changed"):
                        ensure_local_frames_db()
                        ensure_auto_content_db()
                        self.syncCompleted.emit(res)
            except Exception as e:
                print(f"[SyncWorker] Polling error: {e}")

            interval = Config.sync_interval()
            for _ in range(int(interval * 2)):
                if not self._running:
                    break
                time.sleep(0.5)

    def stop(self):
        self._running = False
        self.wait(2000)
