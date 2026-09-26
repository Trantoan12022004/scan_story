#!/usr/bin/env python3
# entry_admin.py
# Điểm khởi chạy cho phiên bản Quản trị viên (StoryScraper_Admin)

import os
import sys

# Thiết lập chế độ chạy là Admin
os.environ["STORY_APP_MODE"] = "admin"

if "--user" in sys.argv:
    sys.argv.remove("--user")
if "--admin" not in sys.argv:
    sys.argv.append("--admin")

from app import start_server

if __name__ == "__main__":
    start_server()
