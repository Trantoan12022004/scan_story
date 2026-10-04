"""
Module bóc tách và tải video Facebook Reels & Videos với đa dạng chất lượng (HD/SD/Audio).
Hỗ trợ callback tiến trình cho PySide6 GUI.
"""
import os
import re
import sys
import json
import time
import requests
from urllib.parse import urlparse
from typing import Dict, List, Optional, Any, Callable

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

def sanitize_filename(name: str, max_len: int = 60) -> str:
    """Loại bỏ ký tự không hợp lệ trong tên file Windows"""
    if not name:
        return f"fb_video_{int(time.time())}"
    name = name.replace("|", "-").replace("｜", "-").replace("—", "-").replace("–", "-")
    clean = re.sub(r'[<>:"/\\|?*\n\r\t]', "", name)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean[:max_len].strip(". -") or f"fb_video_{int(time.time())}"

def format_duration(seconds: Optional[float]) -> str:
    if not seconds or seconds <= 0:
        return "--:--"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

def format_size(bytes_val: Optional[int]) -> str:
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

    title_m = re.search(r"<title>(.*?)</title>", html, re.I)
    raw_title = title_m.group(1).replace(" | Facebook", "").strip() if title_m else "Facebook Reel"

    thumb_m = re.search(r'property=["\']og:image["\']\s+content=["\']([^"\']+)["\']', html)
    thumbnail = thumb_m.group(1).replace("&amp;", "&") if thumb_m else ""

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

    return {
        "title": raw_title,
        "author": "Facebook User",
        "duration": "--:--",
        "duration_sec": 0,
        "thumbnail": thumbnail,
        "url": url,
        "qualities": qualities,
        "source": "html_scraper"
    }

def probe_facebook_video(url: str) -> Dict[str, Any]:
    """Phân tích video từ URL Facebook, trả về danh sách các độ phân giải có sẵn"""
    url = url.strip()
    if not url:
        return {"error": "Đường link URL không được để trống"}

    info = None
    if yt_dlp:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extract_flat": False,
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as e:
            print(f"[fb_downloader] yt-dlp warning: {e}")

    if not info:
        try:
            fallback_res = fallback_scrape_facebook(url)
            if fallback_res.get("qualities"):
                return fallback_res
        except Exception as e:
            print(f"[fb_downloader] Scrape fallback error: {e}")
        return {"error": "Không thể bóc tách video Facebook này. Vui lòng kiểm tra link công khai."}

    raw_title = info.get("title") or info.get("description") or "Facebook Reel"
    first_line = raw_title.split("\n")[0].strip()
    clean_title = re.sub(r'https?://\S+', '', first_line).strip() or "Facebook Reel"
    author = info.get("uploader") or info.get("channel") or "Facebook Creator"
    duration = format_duration(info.get("duration"))
    duration_sec = info.get("duration") or 0
    thumbnail = info.get("thumbnail") or ""

    formats = info.get("formats", [])
    qualities = []
    seen_labels = set()

    for f in formats:
        vcodec = f.get("vcodec", "none")
        if vcodec == "none":
            continue
        acodec = f.get("acodec", "none")
        has_audio = acodec != "none"
        height = f.get("height") or 0
        fmt_id = f.get("format_id")
        filesize = f.get("filesize") or f.get("filesize_approx")
        size_str = format_size(filesize)

        if height >= 1080:
            lbl = "Full HD (1080p)"
            badge = "Siêu nét"
        elif height >= 720:
            lbl = "HD (720p)"
            badge = "Khuyên dùng"
        elif height >= 480:
            lbl = "SD (480p)"
            badge = "Tiêu chuẩn"
        elif height > 0:
            lbl = f"SD ({height}p)"
            badge = "Tiết kiệm"
        else:
            lbl = f"Mặc định ({fmt_id})"
            badge = ""

        if not has_audio:
            lbl += " [Không tiếng]"

        if lbl in seen_labels:
            continue
        seen_labels.add(lbl)

        qualities.append({
            "id": fmt_id,
            "label": lbl,
            "badge": badge,
            "resolution": f"{height}p" if height else "Auto",
            "ext": f.get("ext", "mp4"),
            "size": size_str,
            "has_audio": has_audio,
            "url": f.get("url"),
        })

    # Thêm tùy chọn MP3 Audio
    qualities.append({
        "id": "bestaudio",
        "label": "Chỉ lấy âm thanh (MP3 / Audio)",
        "badge": "Nhạc nền",
        "resolution": "Audio",
        "ext": "mp3",
        "size": "Nhẹ",
        "has_audio": True,
        "url": "",
    })

    if not qualities:
        fallback = fallback_scrape_facebook(url)
        if fallback.get("qualities"):
            return fallback

    return {
        "title": clean_title,
        "author": author,
        "duration": duration,
        "duration_sec": duration_sec,
        "thumbnail": thumbnail,
        "url": url,
        "qualities": qualities,
        "source": "yt_dlp"
    }

def download_facebook_video(
    url: str,
    output_dir: str,
    format_id: Optional[str] = None,
    custom_filename: Optional[str] = None,
    progress_callback: Optional[Callable[[float, str], None]] = None
) -> Dict[str, Any]:
    """
    Tải video Facebook về thư mục chỉ định kèm báo tiến trình.
    progress_callback(percent: float, status_text: str)
    """
    os.makedirs(output_dir, exist_ok=True)
    if progress_callback:
        progress_callback(5.0, "Đang phân tích thông tin video...")

    probe = probe_facebook_video(url)
    if "error" in probe:
        return {"ok": False, "message": probe["error"]}

    base_name = custom_filename or sanitize_filename(probe.get("title", "facebook_reel"))

    # 1. Tải trực tiếp nếu là Direct URL từ Scraper HTML
    if format_id in ("direct_hd", "direct_sd"):
        direct_url = None
        for q in probe.get("qualities", []):
            if q.get("id") == format_id:
                direct_url = q.get("url")
                break
        if direct_url:
            target_file = os.path.join(output_dir, f"{base_name}.mp4")
            try:
                if progress_callback:
                    progress_callback(20.0, "Đang tải dữ liệu...")
                resp = requests.get(direct_url, stream=True, timeout=30)
                total_len = int(resp.headers.get("content-length", 0))
                dl = 0
                with open(target_file, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=1024 * 64):
                        if chunk:
                            f.write(chunk)
                            dl += len(chunk)
                            if total_len > 0 and progress_callback:
                                pct = 20.0 + (dl / total_len) * 75.0
                                mb_done = dl / (1024 * 1024)
                                mb_total = total_len / (1024 * 1024)
                                progress_callback(pct, f"Đang tải: {mb_done:.1f}/{mb_total:.1f} MB ({int(pct)}%)")

                if progress_callback:
                    progress_callback(100.0, "Tải hoàn tất!")
                sz = os.path.getsize(target_file)
                return {
                    "ok": True,
                    "file_path": target_file,
                    "filename": os.path.basename(target_file),
                    "size_str": format_size(sz),
                    "title": probe.get("title"),
                    "author": probe.get("author"),
                    "duration": probe.get("duration"),
                    "thumbnail": probe.get("thumbnail")
                }
            except Exception as e:
                print(f"[Direct DL] Lỗi: {e}")

    # 2. Tải qua yt-dlp
    ext = "mp3" if format_id == "bestaudio" else "mp4"
    out_template = os.path.join(output_dir, f"{base_name}.%(ext)s")

    def ytdl_hook(d):
        if d.get("status") == "downloading" and progress_callback:
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes") or 0
            if total > 0:
                pct = 10.0 + (downloaded / total) * 85.0
                mb_d = downloaded / (1024 * 1024)
                mb_t = total / (1024 * 1024)
                progress_callback(min(pct, 98.0), f"Đang tải: {mb_d:.1f}/{mb_t:.1f} MB ({int(pct)}%)")
        elif d.get("status") == "finished" and progress_callback:
            progress_callback(99.0, "Đang xử lý hoàn tất file...")

    ydl_opts = {
        "outtmpl": out_template,
        "progress_hooks": [ytdl_hook],
        "quiet": True,
        "no_warnings": True,
    }

    if format_id == "bestaudio":
        ydl_opts["format"] = "bestaudio/best"
        ydl_opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }]
    elif format_id:
        ydl_opts["format"] = f"{format_id}+bestaudio/best"
    else:
        ydl_opts["format"] = "bestvideo+bestaudio/best"

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            res_info = ydl.extract_info(url, download=True)
            downloaded_file = ydl.prepare_filename(res_info)
            if format_id == "bestaudio":
                downloaded_file = os.path.splitext(downloaded_file)[0] + ".mp3"

        if os.path.isfile(downloaded_file):
            if progress_callback:
                progress_callback(100.0, "Tải thành công!")
            sz = os.path.getsize(downloaded_file)
            return {
                "ok": True,
                "file_path": downloaded_file,
                "filename": os.path.basename(downloaded_file),
                "size_str": format_size(sz),
                "title": probe.get("title"),
                "author": probe.get("author"),
                "duration": probe.get("duration"),
                "thumbnail": probe.get("thumbnail")
            }
        else:
            return {"ok": False, "message": "Không tìm thấy file sau khi tải."}
    except Exception as e:
        return {"ok": False, "message": f"Lỗi tải video: {e}"}
