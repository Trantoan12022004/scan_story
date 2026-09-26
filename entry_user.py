#!/usr/bin/env python3
# entry_user.py
# Điểm khởi chạy cho phiên bản Người dùng / Khách hàng (StoryScraper_User)

import os
import sys

# Thiết lập chế độ chạy là User
os.environ["STORY_APP_MODE"] = "user"

if "--admin" in sys.argv:
    sys.argv.remove("--admin")
if "--user" not in sys.argv:
    sys.argv.append("--user")

from app import start_server

if __name__ == "__main__":
    start_server()
