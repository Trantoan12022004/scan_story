"""
Module kiểm tra và tự động cập nhật phần mềm từ GitHub repository.
"""
import os
import sys
import json
import urllib.request
from typing import Dict, Any, Optional

CURRENT_VERSION = "2.0.7"
VERSION_JSON_URL = "https://raw.githubusercontent.com/Trantoan12022004/scan_story/main/version.json"

def get_current_version() -> str:
    return CURRENT_VERSION

def check_for_updates() -> Dict[str, Any]:
    """Kiểm tra xem có bản cập nhật mới trên GitHub không"""
    try:
        req = urllib.request.Request(
            VERSION_JSON_URL,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        remote_ver = data.get("version", CURRENT_VERSION)
        changelog = data.get("changelog", "Bản cập nhật tối ưu hóa hiệu suất và giao diện.")
        download_url = data.get("download_url", "")

        def parse_v(v_str):
            parts = [int(p) for p in re.findall(r'\d+', v_str)]
            return parts

        import re
        curr_parts = parse_v(CURRENT_VERSION)
        rem_parts = parse_v(remote_ver)

        has_update = rem_parts > curr_parts

        return {
            "has_update": has_update,
            "current_version": CURRENT_VERSION,
            "latest_version": remote_ver,
            "changelog": changelog,
            "download_url": download_url,
            "release_date": data.get("release_date", "")
        }
    except Exception as e:
        return {
            "has_update": False,
            "current_version": CURRENT_VERSION,
            "error": str(e)
        }
