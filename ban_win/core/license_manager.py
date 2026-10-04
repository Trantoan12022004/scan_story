# license_manager.py
# Module quản lý bản quyền phần mềm:
# 1. Hỗ trợ xác thực Online qua Google Sheets theo Mã Máy (HWID)
# 2. Hỗ trợ bộ nhớ đệm Offline có mã hóa chữ ký HMAC (48 giờ)
# 3. Tương thích ngược với hệ thống License Key offline

import os
import sys
import hmac
import hashlib
import base64
import json
import subprocess
import csv
import io
import re
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

try:
    import requests
except ImportError:
    requests = None

SECRET_SALT = "STORY_SCRAPER_SECRET_KEY_2026_@#!%987"

# Hỗ trợ đường dẫn khi đóng gói EXE (PyInstaller)
if getattr(sys, 'frozen', False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))

LICENSE_FILE = os.path.join(APP_DIR, ".license")
LICENSE_CACHE_FILE = os.path.join(APP_DIR, ".license_cache")
LICENSE_CONFIG_FILE = os.path.join(APP_DIR, "license_config.json")

# URL Google Sheet mặc định (Đã cấu hình theo link mới của bạn)
DEFAULT_SHEET_URL = "https://docs.google.com/spreadsheets/d/1WKYyFFyURvMXY5pgzlJw_S56sBxrHEqYEdyMfMFgMNA/export?format=csv"
DEFAULT_SHEET_WEB_URL = "https://docs.google.com/spreadsheets/d/1WKYyFFyURvMXY5pgzlJw_S56sBxrHEqYEdyMfMFgMNA/edit?usp=sharing"


def normalize_hwid(hwid_str: str) -> str:
    """Chuẩn hóa HWID: bỏ ký tự đặc biệt, chuyển chữ hoa để so khớp chính xác"""
    return re.sub(r'[^A-Za-z0-9]', '', str(hwid_str or '')).upper()


def normalize_sheet_url(url: str) -> str:
    """
    Tự động chuẩn hóa đường dẫn Google Sheets về định dạng xuất CSV:
    - Link xuất bản web: /pubhtml -> /pub?output=csv
    - Link chia sẻ xem: /edit... -> /export?format=csv
    """
    url = (url or "").strip()
    if not url:
        return ""
    if "/pubhtml" in url:
        return url.replace("/pubhtml", "/pub?output=csv")
    if "/pub" in url and "output=csv" not in url:
        sep = "&" if "?" in url else "?"
        return f"{url}{sep}output=csv"
    match = re.search(r"https://docs\.google\.com/spreadsheets/d/([a-zA-Z0-9-_]+)", url)
    if match and "/pub" not in url:
        doc_id = match.group(1)
        gid_match = re.search(r"[#&?]gid=([0-9]+)", url)
        gid = gid_match.group(1) if gid_match else "0"
        return f"https://docs.google.com/spreadsheets/d/{doc_id}/export?format=csv&gid={gid}"
    return url


def fetch_sheet_csv(csv_url: str) -> Optional[str]:
    """Tải nội dung CSV từ Google Sheets kèm cơ chế phá Cache (Cache Buster) thời gian thực"""
    if not requests:
        raise ImportError("Thư viện requests chưa được cài đặt")

    sep = "&" if "?" in csv_url else "?"
    cache_buster_url = f"{csv_url}{sep}_cb={int(time.time() * 1000)}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0"
    }

    try:
        resp = requests.get(cache_buster_url, timeout=8, headers=headers)
        if resp.status_code == 200:
            return resp.content.decode("utf-8-sig", errors="replace")
    except Exception:
        pass

    # Thử lại 1 lần với URL gốc nếu có lỗi
    try:
        resp = requests.get(csv_url, timeout=8, headers=headers)
        if resp.status_code == 200:
            return resp.content.decode("utf-8-sig", errors="replace")
    except Exception:
        pass

    return None


def parse_expire_date(date_str: str):
    """Phân tích chuỗi ngày hết hạn từ Google Sheet (hỗ trợ nhiều định dạng ngày hoặc Vĩnh viễn)"""
    if not date_str:
        return None
    d = date_str.strip()
    if d.lower() in ['vĩnh viễn', 'vinh vien', 'forever', 'lifetime', 'unlimited', 'trọn đời', 'tron doi', 'none', '']:
        return None
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%Y/%m/%d'):
        try:
            return datetime.strptime(d, fmt).date()
        except ValueError:
            pass
    return None


def sign_cache_payload(data: dict) -> str:
    """Tạo chữ ký HMAC-SHA256 cho bộ nhớ đệm bản quyền"""
    msg = f"{data.get('hwid')}:{data.get('user')}:{data.get('expires')}:{data.get('verified_at')}"
    return hmac.new(SECRET_SALT.encode("utf-8"), msg.encode("utf-8"), hashlib.sha256).hexdigest()[:16]


def save_license_cache(hwid: str, user: str, expires: str):
    """Lưu thông tin bản quyền đã xác thực vào bộ nhớ đệm máy"""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    payload = {
        "hwid": hwid,
        "user": user,
        "expires": expires,
        "verified_at": now_str
    }
    payload["sig"] = sign_cache_payload(payload)
    try:
        with open(LICENSE_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def load_license_cache(current_hwid: str, max_hours: int = 48) -> Optional[Dict[str, Any]]:
    """Đọc và kiểm tra tính toàn vẹn của bộ nhớ đệm (dùng khi mất kết nối mạng)"""
    if not os.path.exists(LICENSE_CACHE_FILE):
        return None
    try:
        with open(LICENSE_CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        saved_sig = data.pop("sig", "")
        expected_sig = sign_cache_payload(data)
        if not hmac.compare_digest(saved_sig, expected_sig):
            return None
        if normalize_hwid(data.get("hwid")) != normalize_hwid(current_hwid):
            return None

        # Kiểm tra thời gian lưu cache (mặc định cho phép tối đa 48 giờ offline)
        verified_at_str = data.get("verified_at", "")
        if verified_at_str:
            verified_at = datetime.strptime(verified_at_str, "%Y-%m-%d %H:%M:%S")
            if datetime.now() - verified_at > timedelta(hours=max_hours):
                return None

        expires_str = data.get("expires")
        exp_date = parse_expire_date(expires_str)
        today = datetime.now().date()
        if exp_date and today > exp_date:
            return None

        days_left = (exp_date - today).days if exp_date else 9999
        exp_display = expires_str if expires_str else "Vĩnh viễn"
        return {
            "valid": True,
            "message": f"Bản quyền hợp lệ (Chế độ Offline - Đã xác thực lúc {verified_at_str})",
            "user": data.get("user", "User"),
            "expires": exp_display,
            "days_left": days_left,
            "hwid": current_hwid,
            "source": "cache"
        }
    except Exception:
        return None


def clear_license_cache():
    """Xóa bộ nhớ đệm khi bản quyền bị Admin hủy kích hoạt hoặc hết hạn"""
    try:
        if os.path.exists(LICENSE_CACHE_FILE):
            os.remove(LICENSE_CACHE_FILE)
    except Exception:
        pass


def get_sheet_config() -> dict:
    """Đọc cấu hình URL Google Sheets từ file config"""
    if os.path.exists(LICENSE_CONFIG_FILE):
        try:
            with open(LICENSE_CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"sheet_url": DEFAULT_SHEET_URL}


def save_sheet_config(sheet_url: str) -> bool:
    """Lưu cấu hình URL Google Sheets"""
    config = get_sheet_config()
    config["sheet_url"] = normalize_sheet_url(sheet_url)
    try:
        with open(LICENSE_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


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
    @classmethod
    def get_sheet_url(cls) -> str:
        """Lấy URL Google Sheets hiện tại đang được cấu hình"""
        cfg = get_sheet_config()
        return cfg.get("sheet_url") or DEFAULT_SHEET_URL

    @classmethod
    def set_sheet_url(cls, url: str) -> bool:
        """Thiết lập URL Google Sheets mới"""
        clean_url = normalize_sheet_url(url)
        return save_sheet_config(clean_url)

    @classmethod
    def check_online_sheet(cls, sheet_url: str = None) -> Dict[str, Any]:
        """
        Kiểm tra bản quyền online trực tiếp từ Google Sheets.
        Bảng tính gồm các cột: [Mã máy | Tên khách | Ngày hết hạn | Trạng thái | Ghi chú]
        """
        current_hwid = get_machine_id()
        target_hwid_clean = normalize_hwid(current_hwid)

        target_url = sheet_url or cls.get_sheet_url()
        if not target_url:
            return {
                "valid": False,
                "message": "Chưa cấu hình URL Google Sheets quản lý bản quyền!",
                "code": "MISSING_SHEET_URL",
                "hwid": current_hwid
            }

        csv_url = normalize_sheet_url(target_url)

        try:
            content_text = fetch_sheet_csv(csv_url)
            if not content_text:
                raise ConnectionError("Không tải được dữ liệu từ Google Sheets!")

            f = io.StringIO(content_text)
            reader = csv.reader(f)
            rows = list(reader)

            if not rows:
                return {
                    "valid": False,
                    "message": "Google Sheet rỗng hoặc không tải được dữ liệu!",
                    "code": "EMPTY_SHEET",
                    "hwid": current_hwid
                }

            # Tự động phát hiện vị trí các cột theo tiêu đề
            headers = [h.strip().lower() for h in rows[0]]
            hwid_col = 0
            user_col = 1
            expire_col = 2
            status_col = 3

            for idx, h in enumerate(headers):
                if any(k in h for k in ['hwid', 'mã máy', 'ma may', 'device', 'thiết bị', 'thiet bi']):
                    hwid_col = idx
                elif any(k in h for k in ['user', 'khách', 'khach', 'tên', 'ten', 'name']):
                    user_col = idx
                elif any(k in h for k in ['hạn', 'han', 'expire', 'ngày', 'ngay', 'date']):
                    expire_col = idx
                elif any(k in h for k in ['status', 'trạng thái', 'trang thai', 'kích hoạt', 'kich hoat', 'active']):
                    status_col = idx

            found_machine = False
            today = datetime.now().date()

            for row in rows[1:]:
                if len(row) <= hwid_col:
                    continue

                row_hwid = normalize_hwid(row[hwid_col])
                if row_hwid == target_hwid_clean:
                    found_machine = True
                    user = row[user_col].strip() if len(row) > user_col else "User"
                    exp_str = row[expire_col].strip() if len(row) > expire_col else ""
                    status_str = row[status_col].strip().lower() if len(row) > status_col else "active"

                    is_active_status = status_str in [
                        'active', 'hoạt động', 'hoat dong', 'kich hoat', 'kích hoạt',
                        'ok', '1', 'true', 'enable', 'enabled'
                    ]
                    is_blocked = status_str in [
                        'block', 'khóa', 'khoa', 'banned', 'chặn', 'chan', '0', 'false'
                    ]

                    # 1. Bị Admin chặn
                    if is_blocked:
                        clear_license_cache()
                        return {
                            "valid": False,
                            "message": f"Mã máy {current_hwid} đã bị Admin khóa!",
                            "code": "BLOCKED",
                            "user": user,
                            "hwid": current_hwid
                        }

                    # 2. Chưa được bật trạng thái Active
                    if not is_active_status:
                        clear_license_cache()
                        return {
                            "valid": False,
                            "message": f"Mã máy {current_hwid} đang ở trạng thái: '{status_str}' (Chưa được Active)",
                            "code": "INACTIVE",
                            "user": user,
                            "hwid": current_hwid
                        }

                    # 3. Kiểm tra ngày hết hạn
                    exp_date = parse_expire_date(exp_str)
                    if exp_date and today > exp_date:
                        clear_license_cache()
                        return {
                            "valid": False,
                            "message": f"Bản quyền đã hết hạn vào ngày {exp_date}. Vui lòng liên hệ Admin để gia hạn!",
                            "code": "EXPIRED",
                            "user": user,
                            "expires": str(exp_date),
                            "days_left": 0,
                            "hwid": current_hwid
                        }

                    days_left = (exp_date - today).days if exp_date else 9999
                    exp_display = str(exp_date) if exp_date else "Vĩnh viễn"

                    # Lưu bộ nhớ đệm để máy có thể dùng khi mất mạng
                    save_license_cache(current_hwid, user, exp_display)

                    return {
                        "valid": True,
                        "message": f"Bản quyền hợp lệ! Cấp cho {user} (Hết hạn: {exp_display})",
                        "code": "ACTIVE",
                        "user": user,
                        "expires": exp_display,
                        "days_left": days_left,
                        "hwid": current_hwid,
                        "source": "online"
                    }

            if not found_machine:
                # Bảo vệ khách hàng: Nếu máy này đã từng active hợp lệ trước đó và còn hạn
                # giữ nguyên quyền truy cập, tránh bị văng do hiện tượng mạng/CDN delay.
                existing_cache = load_license_cache(current_hwid)
                if existing_cache and existing_cache.get("valid"):
                    return existing_cache

                clear_license_cache()
                return {
                    "valid": False,
                    "message": f"Mã máy '{current_hwid}' chưa được thêm vào Google Sheets. Vui lòng gửi mã máy này cho Admin để kích hoạt!",
                    "code": "NOT_REGISTERED",
                    "hwid": current_hwid
                }

        except Exception as e:
            # Gặp lỗi mạng hoặc Google Sheet bị ngắt kết nối: Thử đọc bộ nhớ đệm
            cache_info = load_license_cache(current_hwid)
            if cache_info and cache_info.get("valid"):
                return cache_info

            return {
                "valid": False,
                "message": f"Không thể kết nối đến Google Sheets để kiểm tra bản quyền: {str(e)}",
                "code": "NETWORK_ERROR",
                "hwid": current_hwid
            }

    @classmethod
    def get_sheet_web_url(cls) -> str:
        """Lấy URL Google Sheets dạng Web để mở trực tiếp trong trình duyệt"""
        return DEFAULT_SHEET_WEB_URL

    @classmethod
    def check_current_license(cls, force_online: bool = False, is_admin_mode: bool = False) -> Dict[str, Any]:
        """
        Kiểm tra bản quyền tổng thể:
        0. Nếu là bản Admin (is_admin_mode=True), tự động cấp quyền vĩnh viễn.
        1. Ưu tiên kiểm tra Online qua Google Sheets (nếu có cấu hình URL).
        2. Nếu mất mạng hoặc chưa cấu hình Sheet, kiểm tra bộ nhớ đệm Offline hoặc Key offline đã lưu.
        """
        current_hwid = get_machine_id()

        # 0. Đặc quyền dành riêng cho bản Admin
        if is_admin_mode:
            return {
                "valid": True,
                "message": "Phiên bản Quản trị viên (Admin) - Toàn quyền sử dụng vĩnh viễn",
                "code": "ACTIVE",
                "user": "SuperAdmin",
                "expires": "Vĩnh viễn",
                "days_left": 9999,
                "hwid": current_hwid,
                "source": "admin_master",
                "is_admin": True
            }

        sheet_url = cls.get_sheet_url()

        # 1. Kiểm tra qua Google Sheets nếu có URL
        if sheet_url:
            online_res = cls.check_online_sheet(sheet_url)
            if online_res.get("valid"):
                return online_res
            # Nếu Google Sheets báo mã máy chưa đăng ký hoặc bị khóa thì trả về luôn
            if online_res.get("code") in ["BLOCKED", "INACTIVE", "EXPIRED", "NOT_REGISTERED"]:
                return online_res

        # 2. Kiểm tra bộ nhớ đệm offline cache nếu có
        cache_res = load_license_cache(current_hwid)
        if cache_res and cache_res.get("valid"):
            return cache_res

        # 3. Fallback: Kiểm tra License Key lưu cục bộ (nếu có cấp key offline)
        saved_key = cls.load_license()
        if saved_key:
            res = cls.verify_key(saved_key)
            res["hwid"] = current_hwid
            if res.get("valid"):
                res["source"] = "offline_key"
                return res

        return {
            "valid": False,
            "message": "Chưa kích hoạt bản quyền. Vui lòng gửi mã máy cho Admin để kích hoạt!",
            "code": "NOT_ACTIVATED",
            "hwid": current_hwid,
            "days_left": 0
        }

    @staticmethod
    def verify_key(license_key: str) -> Dict[str, Any]:
        """
        Xác thực tính hợp lệ của License Key offline:
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
