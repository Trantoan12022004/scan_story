"""
Trang Quản Lý Bản Quyền Phần Mềm theo Mã Máy HWID & Kích Hoạt Key Offline.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFormLayout, QApplication
)
from qfluentwidgets import (
    LineEdit, ComboBox, PrimaryPushButton, PushButton,
    SubtitleLabel, CaptionLabel, BodyLabel, FluentIcon,
    CardWidget
)

from ban_win.core.license_manager import get_machine_id, LicenseManager
from ban_win.core.keygen import generate_key
from ban_win.ui.widgets.toast import Toast

class LicensePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("LicensePage")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # Header
        top_box = QVBoxLayout()
        title_lbl = SubtitleLabel("Bản Quyền & Kích Hoạt Phần Mềm", self)
        title_lbl.setStyleSheet("font-size: 20px; font-weight: 700; color: #1e293b;")
        sub_lbl = CaptionLabel("Xác thực bản quyền theo mã máy (HWID) bảo mật qua Google Sheets & Offline", self)
        sub_lbl.setStyleSheet("color: #64748b; font-size: 12px;")
        top_box.addWidget(title_lbl)
        top_box.addWidget(sub_lbl)
        layout.addLayout(top_box)

        # 1. Card Trạng Thái Bản Quyền & HWID
        hwid_card = CardWidget(self)
        h_layout = QVBoxLayout(hwid_card)
        h_layout.setContentsMargins(18, 16, 18, 16)
        h_layout.setSpacing(12)

        lbl_hwid_title = SubtitleLabel("Thông Tin Thiết Bị", hwid_card)
        lbl_hwid_title.setStyleSheet("font-size: 16px; font-weight: 600;")
        h_layout.addWidget(lbl_hwid_title)

        # HWID Row
        hwid_row = QHBoxLayout()
        hwid_row.addWidget(BodyLabel("Mã máy (HWID):", hwid_card))

        self.hwid_val = get_machine_id()
        self.in_hwid = LineEdit(hwid_card)
        self.in_hwid.setText(self.hwid_val)
        self.in_hwid.setReadOnly(True)
        hwid_row.addWidget(self.in_hwid, 1)

        self.btn_copy_hwid = PushButton(FluentIcon.COPY, "Sao Chép HWID", hwid_card)
        self.btn_copy_hwid.clicked.connect(self._copy_hwid)
        hwid_row.addWidget(self.btn_copy_hwid)
        h_layout.addLayout(hwid_row)

        # Status row
        self.status_box = QHBoxLayout()
        self.lbl_status = BodyLabel("Trạng thái: Đang kiểm tra...", hwid_card)
        self.status_box.addWidget(self.lbl_status)
        self.status_box.addStretch()

        self.btn_check_online = PushButton(FluentIcon.SYNC, "Kiểm Tra Online", hwid_card)
        self.btn_check_online.clicked.connect(self._check_online)
        self.status_box.addWidget(self.btn_check_online)
        h_layout.addLayout(self.status_box)

        layout.addWidget(hwid_card)

        # 2. Card Kích Hoạt Bản Quyền Bằng Key
        act_card = CardWidget(self)
        a_layout = QVBoxLayout(act_card)
        a_layout.setContentsMargins(18, 16, 18, 16)
        a_layout.setSpacing(12)

        lbl_act_title = SubtitleLabel("Kích Hoạt Bằng License Key", act_card)
        lbl_act_title.setStyleSheet("font-size: 16px; font-weight: 600;")
        a_layout.addWidget(lbl_act_title)

        key_row = QHBoxLayout()
        self.in_key = LineEdit(act_card)
        self.in_key.setPlaceholderText("Dán mã kích hoạt bản quyền (License Key) vào đây...")
        self.in_key.setClearButtonEnabled(True)
        key_row.addWidget(self.in_key, 1)

        self.btn_activate = PrimaryPushButton(FluentIcon.ACCEPT, "Kích Hoạt Ngay", act_card)
        self.btn_activate.clicked.connect(self._activate_key)
        key_row.addWidget(self.btn_activate)
        a_layout.addLayout(key_row)

        layout.addWidget(act_card)

        # 3. Card Dành Cho Admin: Tạo Key Cho Khách
        admin_card = CardWidget(self)
        ad_layout = QVBoxLayout(admin_card)
        ad_layout.setContentsMargins(18, 16, 18, 16)
        ad_layout.setSpacing(12)

        lbl_ad_title = SubtitleLabel("Công Cụ Quản Trị: Tạo License Key", admin_card)
        lbl_ad_title.setStyleSheet("font-size: 16px; font-weight: 600; color: #4338ca;")
        ad_layout.addWidget(lbl_ad_title)

        form = QFormLayout()
        form.setSpacing(8)

        self.in_user_name = LineEdit(admin_card)
        self.in_user_name.setText("Khách hàng")
        form.addRow("Tên khách hàng:", self.in_user_name)

        self.in_gen_hwid = LineEdit(admin_card)
        self.in_gen_hwid.setPlaceholderText("Nhập HWID máy khách...")
        form.addRow("HWID khách:", self.in_gen_hwid)

        self.cb_days = ComboBox(admin_card)
        self.cb_days.addItem("7 Ngày (Dùng thử)", userData=7)
        self.cb_days.addItem("30 Ngày (1 Tháng)", userData=30)
        self.cb_days.addItem("90 Ngày (3 Tháng)", userData=90)
        self.cb_days.addItem("365 Ngày (1 Năm)", userData=365)
        self.cb_days.addItem("Vĩnh Viễn (Lifetime)", userData=3650)
        form.addRow("Thời hạn:", self.cb_days)

        self.in_result_key = LineEdit(admin_card)
        self.in_result_key.setReadOnly(True)
        self.in_result_key.setPlaceholderText("Key tạo ra sẽ hiển thị tại đây...")
        form.addRow("Key tạo ra:", self.in_result_key)

        ad_layout.addLayout(form)

        ad_btn_row = QHBoxLayout()
        self.btn_gen_key = PrimaryPushButton(FluentIcon.TILES, "Tạo Key Mới", admin_card)
        self.btn_gen_key.clicked.connect(self._generate_key)
        ad_btn_row.addWidget(self.btn_gen_key)

        self.btn_copy_gen_key = PushButton(FluentIcon.COPY, "Sao Chép Key", admin_card)
        self.btn_copy_gen_key.clicked.connect(lambda: (
            QApplication.clipboard().setText(self.in_result_key.text()),
            Toast.info(self, "Đã chép", "Đã sao chép License Key vào clipboard!")
        ))
        ad_btn_row.addWidget(self.btn_copy_gen_key)
        ad_btn_row.addStretch()
        ad_layout.addLayout(ad_btn_row)

        layout.addWidget(admin_card)
        layout.addStretch()

        self._check_current_license()

    def _copy_hwid(self):
        QApplication.clipboard().setText(self.hwid_val)
        Toast.success(self, "Đã sao chép", "Đã chép mã HWID vào clipboard!")

    def _check_current_license(self):
        res = LicenseManager.check_current_license()
        if res.get("valid"):
            exp = res.get("expires", "Vĩnh viễn")
            self.lbl_status.setText(f"Trạng thái: ✅ Đã kích hoạt bản quyền! (Hạn: {exp})")
            self.lbl_status.setStyleSheet("color: #15803d; font-weight: 600; font-size: 14px;")
        else:
            self.lbl_status.setText(f"Trạng thái: ⚠️ {res.get('message', 'Chưa kích hoạt bản quyền')}")
            self.lbl_status.setStyleSheet("color: #dc2626; font-weight: 600; font-size: 14px;")

    def _check_online(self):
        self.btn_check_online.setEnabled(False)
        Toast.info(self, "Đang kiểm tra", "Đang kết nối hệ thống kiểm tra online...")
        res = LicenseManager.check_online_sheet()
        self.btn_check_online.setEnabled(True)
        if res.get("valid"):
            Toast.success(self, "Hợp lệ", f"Bản quyền online hợp lệ! Hạn dùng: {res.get('expires')}")
        else:
            Toast.warning(self, "Chưa kích hoạt", res.get("message", ""))
        self._check_current_license()

    def _activate_key(self):
        key = self.in_key.text().strip()
        if not key:
            Toast.warning(self, "Chưa nhập key", "Vui lòng nhập License Key.")
            return

        res = LicenseManager.verify_key(key)
        if res.get("valid"):
            LicenseManager.save_license(key)
            Toast.success(self, "Kích hoạt thành công!", res.get("message", "Đã kích hoạt thành công."))
            self._check_current_license()
        else:
            Toast.error(self, "Kích hoạt thất bại", res.get("message", "Key không hợp lệ."))

    def _generate_key(self):
        target_hwid = self.in_gen_hwid.text().strip() or self.hwid_val
        user = self.in_user_name.text().strip() or "Khách hàng"
        days = self.cb_days.currentData()
        key, exp_date = generate_key(user, target_hwid, days=days)
        self.in_result_key.setText(key)
        Toast.success(self, "Đã tạo key", f"Tạo License Key thành công cho HWID: {target_hwid} (Hạn: {exp_date})")
