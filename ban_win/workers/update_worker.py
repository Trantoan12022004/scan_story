"""
Worker thread kiểm tra bản cập nhật từ GitHub.
"""
from PySide6.QtCore import QThread, Signal
from ban_win.core.updater import check_for_updates

class UpdateWorker(QThread):
    updateChecked = Signal(dict)

    def run(self):
        res = check_for_updates()
        self.updateChecked.emit(res)
