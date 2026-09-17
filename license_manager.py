# license_manager.py
# Module quản lý bản quyền phần mềm, mã hóa kiểm tra theo Mã Máy và Hạn sử dụng

import os
import sys
import hmac
import hashlib
import base64
import json
import subprocess
from datetime import datetime
from typing import Dict, Any

SECRET_SALT = "STORY_SCRAPER_SECRET_KEY_2026_@#!%987"

# Hỗ trợ đường dẫn khi đóng gói EXE (PyInstaller)
if getattr(sys, 'frozen', False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))

LICENSE_FILE = os.path.join(APP_DIR, ".license")


def get_machine_id() -> str:
    """
    Tạo mã định danh phần cứng duy nhất cho máy (HWID)
    Sử dụng UUID hệ thống hoặc mã máy kết hợp CPU
    """
    raw_id = ""
    try:
        if sys.platform == "win32":
            # Lấy UUID phần cứng trên Windows qua PowerShell
            cmd = 'powershell -NoProfile -Command "(Get-CimInstance Win32_ComputerSystemProduct).UUID"'
            raw_id = subprocess.check_output(cmd, shell=True, timeout=5).decode(errors="ignore").strip()
            if not raw_id or "UUID" in raw_id or len(raw_id) < 8:
                # Fallback lấy SerialNumber của BIOS
                cmd2 = 'powershell -NoProfile -Command "(Get-CimInstance Win32_BIOS).SerialNumber"'
                raw_id = subprocess.check_output(cmd2, shell=True, timeout=5).decode(errors="ignore").strip()
        elif sys.platform == "darwin":
            cmd = "ioreg -rd1 -c IOPlatformExpertDevice | awk '/IOPlatformUUID/ { print $3; }'"
            raw_id = subprocess.check_output(cmd, shell=True, timeout=5).decode(errors="ignore").strip().replace('"', '')
        else:
            if os.path.exists("/etc/machine-id"):
                with open("/etc/machine-id", "r") as f:
                    raw_id = f.read().strip()
    except Exception:
        pass

    if not raw_id:
        raw_id = os.environ.get("COMPUTERNAME") or os.environ.get("HOSTNAME") or "DEFAULT_MACHINE_ID"

    # Băm kết hợp muối để tạo chuỗi HWID định dạng XXXX-XXXX-XXXX
    hashed = hashlib.sha256((raw_id + "_SCAN_STORY_DEVICE_2026").encode("utf-8")).hexdigest().upper()
    return f"{hashed[:4]}-{hashed[4:8]}-{hashed[8:12]}"


class LicenseManager:
    @staticmethod
    def verify_key(license_key: str) -> Dict[str, Any]:
        """
        Xác thực tính hợp lệ của License Key:
        - Kiểm tra tính toàn vẹn qua chữ ký HMAC-SHA256
        - Kiểm tra mã máy (HWID) có đúng máy hiện tại không
        - Kiểm tra ngày hết hạn sử dụng
        """
        key_clean = (license_key or "").strip()
        if not key_clean:
            return {
                "valid": False,
                "message": "Chưa nhập License Key!",
                "code": "MISSING_KEY"
            }

        try:
            # Giải mã Base64
            decoded_bytes = base64.b64decode(key_clean.encode("utf-8"))
            decoded_text = decoded_bytes.decode("utf-8")
            if "::" not in decoded_text:
                return {"valid": False, "message": "Định dạng Key không hợp lệ!", "code": "INVALID_FORMAT"}

            payload_str, signature = decoded_text.rsplit("::", 1)

            # 1. Kiểm tra chữ ký HMAC
            expected_sig = hmac.new(
                SECRET_SALT.encode("utf-8"),
                payload_str.encode("utf-8"),
                hashlib.sha256
            ).hexdigest()[:16]

            if not hmac.compare_digest(expected_sig, signature):
                return {
                    "valid": False,
                    "message": "Key không hợp lệ hoặc đã bị chỉnh sửa!",
                    "code": "BAD_SIGNATURE"
                }

            # 2. Đọc thông tin bên trong Key
            data = json.loads(payload_str)
            user = data.get("user", "User")
            key_hwid = (data.get("hwid") or "").strip().upper()
            expires_str = data.get("expires")  # Format: YYYY-MM-DD

            # 3. So khớp mã máy
            current_hwid = get_machine_id()
            if key_hwid != current_hwid:
                return {
                    "valid": False,
                    "message": f"Key không dùng được cho máy này! (Mã máy của Key: {key_hwid} != Máy hiện tại: {current_hwid})",
                    "code": "MISMATCH_MACHINE",
                    "current_hwid": current_hwid,
                    "key_hwid": key_hwid
                }

            # 4. Kiểm tra ngày hết hạn
            expire_date = datetime.strptime(expires_str, "%Y-%m-%d").date()
            today = datetime.now().date()
            if today > expire_date:
                return {
                    "valid": False,
                    "message": f"Bản quyền đã hết hạn vào ngày {expires_str}. Vui lòng liên hệ Admin để gia hạn!",
                    "code": "EXPIRED",
                    "user": user,
                    "expires": expires_str,
                    "days_left": 0
                }

            days_left = (expire_date - today).days
            return {
                "valid": True,
                "message": f"Bản quyền hợp lệ! Còn {days_left} ngày (Hết hạn: {expires_str})",
                "code": "ACTIVE",
                "user": user,
                "expires": expires_str,
                "days_left": days_left,
                "hwid": current_hwid
            }

        except Exception as e:
            return {
                "valid": False,
                "message": f"Lỗi xác thực Key: {str(e)}",
                "code": "ERROR"
            }

    @staticmethod
    def save_license(key: str) -> bool:
        """Lưu key vào file .license"""
        try:
            with open(LICENSE_FILE, "w", encoding="utf-8") as f:
                f.write(key.strip())
            return True
        except Exception:
            return False

    @staticmethod
    def load_license() -> str:
        """Đọc key từ file .license"""
        if os.path.exists(LICENSE_FILE):
            try:
                with open(LICENSE_FILE, "r", encoding="utf-8") as f:
                    return f.read().strip()
            except Exception:
                return ""
        return ""

    @classmethod
    def check_current_license(cls) -> Dict[str, Any]:
        """Kiểm tra bản quyền hiện tại đã lưu trên máy"""
        current_hwid = get_machine_id()
        saved_key = cls.load_license()
        if not saved_key:
            return {
                "valid": False,
                "message": "Chưa kích hoạt bản quyền. Vui lòng gửi mã máy cho Admin để nhận Key!",
                "code": "NOT_ACTIVATED",
                "hwid": current_hwid,
                "days_left": 0
            }

        res = cls.verify_key(saved_key)
        res["hwid"] = current_hwid
        return res
