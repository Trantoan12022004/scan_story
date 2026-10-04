"""
Trích xuất ảnh Thumbnail / Frame đầu tiên từ link Facebook Reel hoặc video cục bộ.
"""
import os
import re
import time
import subprocess
import requests
from typing import Dict, Any, Optional
from .database import get_db
from .video_checker import normalize_stt, build_default_video_link

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRAMES_DIR = os.path.join(APP_DIR, "data", "frames")
os.makedirs(FRAMES_DIR, exist_ok=True)

def extract_frame_from_local_video(video_path: str, output_filepath: str) -> bool:
    """Trích xuất frame đầu tiên từ file video mp4 trên máy bằng ffmpeg"""
    if not video_path or not os.path.isfile(video_path):
        return False
    try:
        cmd = [
            "ffmpeg", "-y",
            "-ss", "00:00:00.5",
            "-i", video_path,
            "-vframes", "1",
            "-update", "1",
            output_filepath
        ]
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=8)
        return res.returncode == 0 and os.path.isfile(output_filepath) and os.path.getsize(output_filepath) > 500
    except Exception as e:
        print(f"[extract_frame_from_local_video] Lỗi: {e}")
        return False

def extract_frame_from_reel(stt: str, url: str) -> Dict[str, Any]:
    """
    Trích xuất ảnh Thumbnail / Frame đầu tiên từ link Facebook Reel hoặc video cục bộ.
    Lưu ảnh vào data/frames/frame_{stt}.jpg và cập nhật vào SQLite.
    """
    stt = normalize_stt(stt)
    filename = f"frame_{stt}.jpg" if stt else f"frame_{int(time.time())}.jpg"
    filepath = os.path.join(FRAMES_DIR, filename)

    # 1. Nếu file ảnh frame đã có sẵn trên máy
    if os.path.isfile(filepath) and os.path.getsize(filepath) > 500:
        if stt:
            get_db().update_single_field(stt, "frame_dau_tien", filepath)
        return {
            "ok": True,
            "message": "Đã có sẵn ảnh frame!",
            "frame_path": filepath,
            "filename": filename
        }

    # 2. Nếu file video MP4 đã có sẵn trên máy, trích xuất bằng ffmpeg
    v_path = build_default_video_link(stt)
    if os.path.isfile(v_path):
        if extract_frame_from_local_video(v_path, filepath):
            if stt:
                get_db().update_single_field(stt, "frame_dau_tien", filepath)
            return {
                "ok": True,
                "message": "Đã trích xuất frame từ video thành công!",
                "frame_path": filepath,
                "filename": filename
            }

    url = (url or "").strip()
    if not url:
        return {"ok": False, "message": "Link bài gốc đang trống."}

    thumbnail_url = ""
    # 3. Dùng yt-dlp probe
    try:
        from .fb_downloader import probe_facebook_video
        info = probe_facebook_video(url)
        thumbnail_url = info.get("thumbnail") or ""
    except Exception as e:
        print(f"[extract_frame] Lỗi probe video: {e}")

    # 4. Dự phòng: Thử scrape thẻ og:image
    if not thumbnail_url:
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            }
            resp = requests.get(url, headers=headers, timeout=10)
            m = re.search(r'property=["\']og:image["\']\s+content=["\']([^"\']+)["\']', resp.text)
            if m:
                thumbnail_url = m.group(1).replace("&amp;", "&")
        except Exception:
            pass

    if not thumbnail_url:
        return {"ok": False, "message": "Không tìm thấy ảnh frame từ video Facebook này. Vui lòng kiểm tra lại link."}

    # Tải ảnh về lưu trữ cục bộ
    try:
        img_resp = requests.get(
            thumbnail_url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15
        )
        if img_resp.status_code == 200:
            with open(filepath, "wb") as f:
                f.write(img_resp.content)

            if stt:
                get_db().update_single_field(stt, "frame_dau_tien", filepath)

            return {
                "ok": True,
                "message": "Đã lấy frame đầu tiên thành công!",
                "frame_path": filepath,
                "filename": filename
            }
    except Exception as e:
        # Nếu không tải được về máy, vẫn lưu link online
        if stt:
            get_db().update_single_field(stt, "frame_dau_tien", thumbnail_url)
        return {
            "ok": True,
            "message": "Đã lấy link frame online thành công (không lưu file nội bộ)",
            "frame_path": thumbnail_url,
            "filename": filename
        }

    return {"ok": False, "message": "Không thể tải ảnh frame về máy"}


def ensure_local_frames_db() -> int:
    """
    Quét toàn bộ bản ghi trong SQLite:
    - Nếu đã có file ảnh frame_{stt}.jpg trên máy: gán đường dẫn
    - Nếu có file video mp4 trên máy: trích xuất frame bằng ffmpeg
    """
    db = get_db()
    videos = db.get_all_videos()
    updated_count = 0

    for item in videos:
        stt = normalize_stt(item.get("stt"))
        if not stt:
            continue
        filename = f"frame_{stt}.jpg"
        filepath = os.path.join(FRAMES_DIR, filename)

        # 1. Nếu file ảnh frame đã có trên ổ cứng
        if os.path.isfile(filepath) and os.path.getsize(filepath) > 500:
            if item.get("frame_dau_tien") != filepath:
                db.update_single_field(stt, "frame_dau_tien", filepath, mark_local=False)
                updated_count += 1
            continue

        # 2. Nếu chưa có ảnh frame, nhưng file video MP4 đã có sẵn trên máy
        v_path = (item.get("link_video") or "").strip('"\'') or build_default_video_link(stt)
        if os.path.isfile(v_path):
            if extract_frame_from_local_video(v_path, filepath):
                db.update_single_field(stt, "frame_dau_tien", filepath, mark_local=False)
                updated_count += 1

    return updated_count
