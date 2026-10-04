#!/usr/bin/env python3
# keygen.py
# Tool tạo License Key cho Admin Story Scraper
# Chỉ admin giữ file này để cấp quyền sử dụng cho người khác theo Mã Máy và Hạn sử dụng

import sys
import hmac
import hashlib
import base64
import json
import argparse
from datetime import datetime, timedelta

# Fix encoding cho Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SECRET_SALT = "STORY_SCRAPER_SECRET_KEY_2026_@#!%987"


def generate_key(user: str, hwid: str, days: int = 30) -> tuple[str, str]:
    """
    Tạo License Key có hạn sử dụng gắn theo mã máy (HWID)
    Trả về (license_key, expire_date_str)
    """
    expire_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
    payload = {
        "user": user.strip(),
        "hwid": hwid.strip().upper(),
        "expires": expire_date
    }
    payload_str = json.dumps(payload, separators=(',', ':'))

    # Ký số HMAC SHA-256
    signature = hmac.new(
        SECRET_SALT.encode("utf-8"),
        payload_str.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()[:16]

    combined = f"{payload_str}::{signature}"
    key = base64.b64encode(combined.encode("utf-8")).decode("utf-8")
    return key, expire_date


def main():
    parser = argparse.ArgumentParser(
        description="🔑 Công cụ cấp License Key cho Story Scraper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ví dụ tạo key:
  # Tự kích hoạt Admin cho chính máy tính này (hạn 10 năm):
  python keygen.py --self

  # Cấp key cho người dùng khác:
  python keygen.py -u "NguyenVanA" -m "A1B2-C3D4-E5F6" -d 30
  python keygen.py -u "TeamMarketing" -m "9F8A-12BC-33D1" -d 60
        """
    )
    parser.add_argument("--self", dest="self_activate", action="store_true",
                        help="Tự động kích hoạt quyền Admin cho chính máy tính hiện tại (10 năm)")
    parser.add_argument("--user", "-u", default="", help="Tên người dùng hoặc team")
    parser.add_argument("--hwid", "-m", default="", help="Mã máy (Machine ID do người dùng gửi)")
    parser.add_argument("--days", "-d", type=int, default=0, help="Số ngày sử dụng (mặc định: 30 ngày cho khách, 3650 ngày cho --self)")

    args = parser.parse_args()

    # Trường hợp 1: Tự kích hoạt Admin cho máy hiện tại
    if args.self_activate:
        from license_manager import get_machine_id, LicenseManager
        hwid = get_machine_id()
        user = args.user.strip() if args.user else "SuperAdmin"
        days = args.days if args.days > 0 else 3650  # Mặc định 10 năm

        key, expire_date = generate_key(user, hwid, days)
        LicenseManager.save_license(key)

        print("\n" + "=" * 65)
        print("👑 ĐÃ KÍCH HOẠT BẢN QUYỀN ADMIN CHO MÁY NÀY THÀNH CÔNG")
        print("=" * 65)
        print(f"💻 Mã máy (HWID) : {hwid}")
        print(f"👤 Quyền tài khoản : {user}")
        print(f"📅 Hạn sử dụng   : {expire_date} ({days} ngày ~ 10 năm)")
        print(f"💾 File lưu trữ  : .license (Đã kích hoạt sẵn)")
        print("=" * 65)
        print("🚀 Bạn có thể khởi động ngay Web UI (`python app.py`) hoặc chạy CLI!\n")
        return

    # Trường hợp 2: Cấp key cho người dùng khác
    if not args.user or not args.hwid:
        print("\n❌ Lỗi: Vui lòng cung cấp cả --user (-u) và --hwid (-m) khi tạo key cho người khác.")
        print("💡 Hoặc nếu muốn tự kích hoạt Admin cho máy này, chạy: python keygen.py --self\n")
        parser.print_help()
        sys.exit(1)

    days = args.days if args.days > 0 else 30
    key, expire_date = generate_key(args.user, args.hwid, days)

    print("\n" + "=" * 65)
    print("🔑 CẤP LICENSE KEY THÀNH CÔNG")
    print("=" * 65)
    print(f"👤 Người dùng  : {args.user}")
    print(f"💻 Mã máy (HWID): {args.hwid.upper()}")
    print(f"📅 Hạn sử dụng : {expire_date} ({days} ngày)")
    print("-" * 65)
    print("📋 KEY GỬI CHO KHÁCH HÀNG:\n")
    print(key)
    print("\n" + "=" * 65)
    print("💡 Hướng dẫn khách hàng:")
    print("  1. Mở giao diện Web UI -> Bấm 'Kích hoạt bản quyền' -> Dán key vào.")
    print("  2. Hoặc lưu nội dung key trên vào file `.license` cùng thư mục tool.")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()
