"""
Widget cấu hình tài khoản CMS BlogBio và kiểm tra kết nối REST API.
"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout
)
from qfluentwidgets import (
    LineEdit, PrimaryPushButton, PushButton,
    SubtitleLabel, CaptionLabel, FluentIcon, CardWidget
)
from ban_win.core.config import Config
from ban_win.core.publisher import CMSPublisher
from ban_win.ui.widgets.toast import Toast

class CMSConfigWidget(CardWidget):
    configSaved = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        header = SubtitleLabel("Cấu Hình CMS BlogBio (REST API)", self)
        header.setStyleSheet("font-size: 15px; font-weight: 600; color: #1e293b;")
        layout.addWidget(header)

        form = QFormLayout()
        form.setSpacing(8)

        self.in_cms_url = LineEdit(self)
        self.in_cms_url.setText(Config.cms_url())
        form.addRow("CMS Base URL:", self.in_cms_url)

        self.in_cms_user = LineEdit(self)
        self.in_cms_user.setText(Config.cms_user())
        form.addRow("Tài khoản CMS:", self.in_cms_user)

        self.in_cms_pass = LineEdit(self)
        self.in_cms_pass.setEchoMode(LineEdit.Password)
        self.in_cms_pass.setText(Config.cms_pass())
        form.addRow("Mật khẩu CMS:", self.in_cms_pass)

        layout.addLayout(form)

        btn_row = QHBoxLayout()
        self.btn_test = PushButton(FluentIcon.CONNECT, "Kiểm Tra Kết Nối", self)
        self.btn_test.clicked.connect(self._test_connection)
        btn_row.addWidget(self.btn_test)

        self.btn_save = PrimaryPushButton(FluentIcon.SAVE, "Lưu Cấu Hình", self)
        self.btn_save.clicked.connect(self._save_config)
        btn_row.addWidget(self.btn_save)

        btn_row.addStretch()
        layout.addLayout(btn_row)

    def _test_connection(self):
        url = self.in_cms_url.text().strip()
        user = self.in_cms_user.text().strip()
        pwd = self.in_cms_pass.text().strip()

        if not url or not user:
            Toast.warning(self, "Chưa điền đủ thông tin", "Vui lòng nhập URL và tài khoản CMS.")
            return

        self.btn_test.setEnabled(False)
        self.btn_test.setText("Đang kết nối...")

        pub = CMSPublisher(base_url=url, username=user, password=pwd)
        ok = pub.login()

        self.btn_test.setEnabled(True)
        self.btn_test.setText("Kiểm Tra Kết Nối")

        if ok:
            Toast.success(self, "Kết nối thành công", "Đăng nhập CMS BlogBio hoàn tất!")
        else:
            Toast.error(self, "Kết nối thất bại", "Vui lòng kiểm tra lại URL, tài khoản hoặc mật khẩu CMS.")

    def _save_config(self):
        Config.set("cms_url", self.in_cms_url.text().strip())
        Config.set("cms_user", self.in_cms_user.text().strip())
        Config.set("cms_pass", self.in_cms_pass.text().strip())
        Toast.success(self, "Đã lưu", "Đã cập nhật cấu hình CMS BlogBio.")
        self.configSaved.emit()
