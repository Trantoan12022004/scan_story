#!/usr/bin/env python3
# fb_downloader.py
# Module bóc tách và tải video Facebook Reels & Videos với đa dạng chất lượng

import os
import re
import sys
import json
import time
import requests
from urllib.parse import urlparse
from typing import Dict, List, Optional, Any

# Fix encoding cho Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

try:
    import yt_dlp
except ImportError:
    yt_dlp = None


def sanitize_filename(name: str, max_len: int = 60) -> str:
    """Loại bỏ ký tự không hợp lệ trong tên file"""
    if not name:
        return f"fb_video_{int(time.time())}"
    # Thay các dạng dấu phân cách đặc biệt thành gạch ngang
    name = name.replace("|", "-").replace("｜", "-").replace("—", "-").replace("–", "-")
    clean = re.sub(r'[<>:"/\\|?*\n\r\t]', "", name)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean[:max_len].strip(". -") or f"fb_video_{int(time.time())}"


def format_duration(seconds: Optional[float]) -> str:
    """Định dạng thời lượng (giây) sang dạng mm:ss"""
    if not seconds or seconds <= 0:
        return "--:--"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def format_size(bytes_val: Optional[int]) -> str:
    """Định dạng kích thước byte sang MB / KB"""
    if not bytes_val or bytes_val <= 0:
        return "Tự động"
    mb = bytes_val / (1024 * 1024)
    if mb >= 1:
        return f"{mb:.1f} MB"
    kb = bytes_val / 1024
    return f"{kb:.0f} KB"


def fallback_scrape_facebook(url: str) -> Dict[str, Any]:
    """Cơ chế dự phòng: Cào trực tiếp link HD và SD từ mã nguồn HTML Facebook"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    resp = requests.get(url, headers=headers, timeout=15)
    html = resp.text

    # Tìm title
    title_m = re.search(r"<title>(.*?)</title>", html, re.I)
    raw_title = title_m.group(1).replace(" | Facebook", "").strip() if title_m else "Facebook Reel"

    # Tìm thumbnail
    thumb_m = re.search(r'property=["\']og:image["\']\s+content=["\']([^"\']+)["\']', html)
    thumbnail = thumb_m.group(1).replace("&amp;", "&") if thumb_m else ""

    # Tìm link video HD / SD
    hd_m = re.findall(r'browser_native_hd_url["\']?\s*:\s*["\']([^"\']+)["\']', html)
    sd_m = re.findall(r'browser_native_sd_url["\']?\s*:\s*["\']([^"\']+)["\']', html)

    qualities = []
    if hd_m:
        clean_hd = hd_m[0].replace(r"\/", "/").replace("&amp;", "&")
        qualities.append({
            "id": "direct_hd",
            "label": "HD (720p / Chất lượng cao)",
            "badge": "Khuyên dùng",
            "resolution": "HD",
            "ext": "mp4",
            "size": "Tự động",
            "has_audio": True,
            "url": clean_hd,
        })
    if sd_m:
        clean_sd = sd_m[0].replace(r"\/", "/").replace("&amp;", "&")
        qualities.append({
            "id": "direct_sd",
            "label": "SD (Tiêu chuẩn / Tiết kiệm dung lượng)",
            "badge": "Chuẩn SD",
            "resolution": "SD",
            "ext": "mp4",
            "size": "Tự động",
            "has_audio": True,
            "url": clean_sd,
        })

    preview_url = ""
    if hd_m:
        preview_url = hd_m[0].replace(r"\/", "/").replace("&amp;", "&")
    elif sd_m:
        preview_url = sd_m[0].replace(r"\/", "/").replace("&amp;", "&")

    return {
        "title": raw_title,
        "thumbnail": thumbnail,
        "duration": "--:--",
        "uploader": "Facebook User",
        "qualities": qualities,
        "preview_url": preview_url,
        "is_fallback": True,
    }


def probe_facebook_video(url: str) -> Dict[str, Any]:
    """
    Dò tìm tất cả các mức chất lượng video khả dụng từ link Facebook Reel hoặc Video.
    Trả về metadata video và danh sách các tùy chọn chất lượng (1080p, HD, SD, Audio).
    """
    url = url.strip()
    if not url:
        raise ValueError("Vui lòng nhập đường dẫn URL Facebook.")

    if not yt_dlp:
        return fallback_scrape_facebook(url)

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        # Nếu yt-dlp gặp lỗi, tự động chuyển sang fallback regex
        try:
            fb_info = fallback_scrape_facebook(url)
            if fb_info.get("qualities"):
                return fb_info
        except Exception:
            pass
        raise RuntimeError(f"Không thể lấy thông tin video Facebook: {e}")

    title = info.get("title") or "Facebook Reel"
    # Cắt ngắn title nếu quá dài
    if len(title) > 100:
        title = title[:100] + "..."

    thumbnail = info.get("thumbnail") or ""
    duration_sec = info.get("duration")
    duration_str = format_duration(duration_sec)
    uploader = info.get("uploader") or info.get("channel") or "Facebook"

    formats = info.get("formats", [])
    qualities = []
    seen_resolutions = set()

    # 1. Tùy chọn tốt nhất (Tự động gộp video cao nhất + audio nét nhất qua ffmpeg)
    qualities.append({
        "id": "best",
        "label": "Siêu Nét Nhất (Full HD 1080p / Cao nhất)",
        "badge": "Chất lượng cao nhất",
        "resolution": "1080p / Best",
        "ext": "mp4",
        "size": "Tự động tối ưu",
        "has_audio": True,
        "note": "Tự động chọn luồng hình ảnh nét nhất và ghép âm thanh",
    })

    # 2. Tìm định dạng HD progressive có sẵn
    hd_format = next((f for f in formats if f.get("format_id") == "hd"), None)
    if hd_format:
        size_str = format_size(hd_format.get("filesize") or hd_format.get("filesize_approx"))
        qualities.append({
            "id": "hd",
            "label": "HD (720p - Sẵn âm thanh)",
            "badge": "Khuyên dùng",
            "resolution": "720p HD",
            "ext": "mp4",
            "size": size_str,
            "has_audio": True,
            "note": "Tải nhanh, không cần ghép file",
        })
        seen_resolutions.add("720p HD")

    # 3. Tìm định dạng SD progressive có sẵn
    sd_format = next((f for f in formats if f.get("format_id") == "sd"), None)
    if sd_format:
        size_str = format_size(sd_format.get("filesize") or sd_format.get("filesize_approx"))
        qualities.append({
            "id": "sd",
            "label": "SD (Tiêu chuẩn 360p/480p)",
            "badge": "Tiêu chuẩn",
            "resolution": "SD",
            "ext": "mp4",
            "size": size_str,
            "has_audio": True,
            "note": "Dung lượng nhẹ, tải siêu tốc",
        })
        seen_resolutions.add("SD")

    # 4. Tìm các độ phân giải DASH video riêng biệt (ví dụ 960x1708, 716x1274)
    dash_videos = [f for f in formats if f.get("vcodec") and f.get("vcodec") != "none" and f.get("height")]
    # Sắp xếp theo chiều cao / độ phân giải giảm dần
    dash_videos.sort(key=lambda x: (x.get("height", 0), x.get("tbr", 0)), reverse=True)

    for f in dash_videos:
        w = f.get("width")
        h = f.get("height")
        f_id = f.get("format_id")
        if not h:
            continue
        res_label = f"{w}x{h}" if w and h else f"{h}p"
        if res_label in seen_resolutions:
            continue
        seen_resolutions.add(res_label)

        size_str = format_size(f.get("filesize") or f.get("filesize_approx"))
        badge = "1080p" if h >= 1080 else ("720p" if h >= 720 else f"{h}p")

        qualities.append({
            "id": f"{f_id}+bestaudio/best",
            "label": f"Độ phân giải {res_label} ({badge})",
            "badge": badge,
            "resolution": res_label,
            "ext": "mp4",
            "size": size_str,
            "has_audio": True,
            "note": f"Video {res_label} + Audio chuẩn",
        })

    # 5. Tùy chọn chỉ lấy âm thanh (Audio Only)
    audio_formats = [f for f in formats if f.get("acodec") and f.get("acodec") != "none" and f.get("vcodec") == "none"]
    if audio_formats:
        best_audio = audio_formats[0]
        size_str = format_size(best_audio.get("filesize") or best_audio.get("filesize_approx"))
        qualities.append({
            "id": "bestaudio/best",
            "label": "Chỉ lấy âm thanh (Nhạc nền / Voice Audio)",
            "badge": "Audio M4A",
            "resolution": "Audio",
            "ext": "m4a",
            "size": size_str,
            "has_audio": True,
            "note": "Tách riêng file nhạc nền hoặc tiếng thoại của Reel",
        })

    # 6. Tìm luồng phát preview trực tiếp trên trình duyệt
    preview_url = ""
    if hd_format and hd_format.get("url"):
        preview_url = hd_format.get("url")
    elif sd_format and sd_format.get("url"):
        preview_url = sd_format.get("url")
    else:
        # Tìm format bất kỳ có sẵn URL trực tiếp
        for f in formats:
            if f.get("url") and f.get("vcodec") != "none" and f.get("acodec") != "none":
                preview_url = f.get("url")
                break
        if not preview_url:
            for f in formats:
                if f.get("url") and f.get("vcodec") != "none":
                    preview_url = f.get("url")
                    break

    return {
        "title": title,
        "thumbnail": thumbnail,
        "duration": duration_str,
        "uploader": uploader,
        "qualities": qualities,
        "preview_url": preview_url,
        "is_fallback": False,
    }


def download_facebook_video(
    url: str,
    format_id: str = "best",
    output_dir: str = "output/videos",
    progress_callback = None
) -> Dict[str, Any]:
    """
    Tải video Facebook về thư mục chỉ định theo format_id đã chọn.
    Trả về thông tin file đã tải: đường dẫn, tên file, kích thước.
    """
    os.makedirs(output_dir, exist_ok=True)

    # Nếu đây là direct link từ fallback
    if format_id.startswith("http://") or format_id.startswith("https://"):
        file_name = f"facebook_reel_{int(time.time())}.mp4"
        out_path = os.path.join(output_dir, file_name)
        resp = requests.get(format_id, stream=True, timeout=30)
        resp.raise_for_status()
        with open(out_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)
        size_mb = os.path.getsize(out_path) / (1024 * 1024)
        return {
            "ok": True,
            "file_name": file_name,
            "file_path": os.path.abspath(out_path),
            "file_size": f"{size_mb:.2f} MB",
        }

    if not yt_dlp:
        raise RuntimeError("Cần cài đặt thư viện yt-dlp để tải video.")

    outtmpl = os.path.join(output_dir, "%(title).60s_%(id)s.%(ext)s")

    def ydl_hook(d):
        if progress_callback and d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes") or 0
            pct = int((downloaded / total) * 100) if total > 0 else 0
            speed = d.get("speed")
            speed_str = f"{(speed / 1024 / 1024):.1f} MB/s" if speed else ""
            progress_callback({
                "percent": pct,
                "downloaded": downloaded,
                "total": total,
                "speed": speed_str,
            })

    ydl_opts = {
        "format": format_id,
        "outtmpl": outtmpl,
        "restrictfilenames": True,
        "progress_hooks": [ydl_hook] if progress_callback else [],
        "quiet": True,
        "no_warnings": True,
        "merge_output_format": "mp4" if "audio" not in format_id else None,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        meta = ydl.extract_info(url, download=True)
        downloaded_file = ydl.prepare_filename(meta)

        # Xử lý phần mở rộng sau khi merge ffmpeg
        if not os.path.exists(downloaded_file):
            base, _ = os.path.splitext(downloaded_file)
            if os.path.exists(f"{base}.mp4"):
                downloaded_file = f"{base}.mp4"

        file_size_mb = 0.0
        if os.path.exists(downloaded_file):
            file_size_mb = os.path.getsize(downloaded_file) / (1024 * 1024)

        return {
            "ok": True,
            "title": meta.get("title") or "Facebook Video",
            "file_name": os.path.basename(downloaded_file),
            "file_path": os.path.abspath(downloaded_file),
            "file_size": f"{file_size_mb:.2f} MB",
            "duration": format_duration(meta.get("duration")),
            "thumbnail": meta.get("thumbnail"),
        }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Sử dụng: python fb_downloader.py <URL_FACEBOOK_REEL> [FORMAT_ID]")
        print("Ví dụ:   python fb_downloader.py \"https://www.facebook.com/reel/1142203028130644\"")
        sys.exit(1)

    input_url = sys.argv[1]
    chosen_format = sys.argv[2] if len(sys.argv) > 2 else None

    print("=" * 60)
    print("🎬 FACEBOOK REELS & VIDEO DOWNLOADER")
    print("=" * 60)
    print(f"🔍 Đang phân tích video: {input_url}\n")

    info = probe_facebook_video(input_url)
    print(f"📌 Tiêu đề   : {info.get('title')}")
    print(f"⏱ Thời lượng : {info.get('duration')}")
    print(f"👤 Người đăng: {info.get('uploader')}")
    print("\n📋 Danh sách chất lượng khả dụng:")
    print("-" * 60)
    for idx, q in enumerate(info.get("qualities", []), 1):
        print(f" [{idx}] {q.get('label'):<38} | Độ phân giải: {q.get('resolution'):<10} | Dung lượng: {q.get('size')}")

    if not chosen_format:
        print("\n👉 Tự động tải chất lượng nét nhất [1] (hoặc truyền FORMAT_ID qua CLI)...")
        chosen_format = info["qualities"][0]["id"]

    print(f"\n🚀 Đang tải với định dạng [{chosen_format}]...")
    res = download_facebook_video(input_url, format_id=chosen_format, output_dir="output/videos")
    print(f"✅ Tải thành công!")
    print(f"📁 Đường dẫn file : {res.get('file_path')}")
    print(f"📦 Dung lượng     : {res.get('file_size')}\n")
