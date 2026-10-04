#!/usr/bin/env python3
# quan_ly_manager.py
# Quản lý dữ liệu tiến độ tạo video & đăng bài đồng bộ Google Sheets

import os
import re
import sys
import csv
import io
import json
import time
import urllib.request
import subprocess
import requests
import threading
import hashlib
from typing import Dict, List, Any, Optional

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(APP_ROOT, "quan_ly_data.json")
FRAMES_DIR = os.path.join(APP_ROOT, "output", "frames")
os.makedirs(FRAMES_DIR, exist_ok=True)

GOOGLE_SHEET_ID = "1t4nyagzl-ySljwSK6nSxXPFttv11Vx-az2exQ9pKBuA"
CSV_EXPORT_URL = f"https://docs.google.com/spreadsheets/d/{GOOGLE_SHEET_ID}/export?format=csv"
DEFAULT_VIDEO_DIR = r"C:\Users\Trant\Videos\Seedance\anhtonton\AI_VIDEO"
CONFIG_FILE = os.path.join(APP_ROOT, "quan_ly_config.json")

# Biến theo dõi đồng bộ Google Sheet
LAST_SYNC_TIME = 0.0
LAST_CSV_HASH = ""
MIN_SYNC_INTERVAL = 3.0  # Tự động kéo Google Sheet định kỳ 3 giây để đồng bộ Realtime

# Danh sách trạng thái video hợp lệ
VALID_VIDEO_STATUSES = [
    "Xong video",
    "Đang tạo video",
    "Xong báo",
    "Lấy video",
    "không tạo được",
    "bị từ chối"
]

# Danh sách trạng thái đăng bài hợp lệ
VALID_POST_STATUSES = [
    "chưa hoàn thành",
    "hoàn thành",
    "đăng bài"
]


def normalize_stt(val: Any) -> str:
    """Chuẩn hóa STT thành chuỗi sạch"""
    if val is None:
        return ""
    s = str(val).strip()
    if s.endswith(".0"):
        s = s[:-2]
    return s


def build_default_video_link(stt: str, base_dir: str = DEFAULT_VIDEO_DIR) -> str:
    """Tạo link video mặc định theo định dạng C:\\Users\\Trant\\Videos\\Seedance\\anhtonton\\AI_VIDEO\\(STT).mp4"""
    clean_stt = normalize_stt(stt)
    if not clean_stt:
        return ""
    return os.path.normpath(os.path.join(base_dir, f"{clean_stt}.mp4"))


def compute_post_status(current_status: str, content: str, link_video: str) -> str:
    """
    Tính toán trạng thái đăng bài:
    - chưa hoàn thành: chưa có nội dung ở hai cột content và link video
    - hoàn thành: có nội dung ở hai cột content và link video
    - đăng bài: người dùng thao tác
    """
    cur = (current_status or "").strip().lower()
    if cur == "đăng bài" or cur == "dang bai":
        return "đăng bài"

    has_content = bool(content and content.strip())
    has_video = bool(link_video and link_video.strip())

    if has_content and has_video:
        return "hoàn thành"
    return "chưa hoàn thành"


def check_video_file(path_str: str) -> Dict[str, Any]:
    """Kiểm tra file video đã có sẵn trên máy tính chưa"""
    if not path_str:
        return {"exists": False, "size": "", "path": ""}
    p = path_str.strip('"\'')
    if os.path.isfile(p):
        try:
            sz = os.path.getsize(p)
            mb = sz / (1024 * 1024)
            size_str = f"{mb:.1f} MB" if mb >= 1 else f"{sz / 1024:.0f} KB"
            return {"exists": True, "size": size_str, "bytes": sz, "path": p}
        except Exception:
            return {"exists": True, "size": "Có sẵn", "path": p}
    return {"exists": False, "size": "", "path": p}


def extract_frame_from_local_video(video_path: str, output_filepath: str) -> bool:
    """Trích xuất frame đầu tiên từ file video mp4 trên máy bằng ffmpeg (cực nhanh 0.04s)"""
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


def ensure_local_frames(rows: List[Dict[str, Any]]) -> bool:
    """
    Tự động kiểm tra và đồng bộ frame đầu tiên khi vào web:
    - Nếu đã có file ảnh frame_{stt}.jpg trên máy: tự gán URL webview.
    - Nếu chưa có ảnh nhưng file video mp4 đã có sẵn trên máy: tự dùng ffmpeg bóc frame ngay lập tức.
    """
    updated = False
    for item in rows:
        stt = normalize_stt(item.get("stt"))
        if not stt:
            continue
        filename = f"frame_{stt}.jpg"
        filepath = os.path.join(FRAMES_DIR, filename)
        local_url = f"/api/quan-ly/frame/{filename}"

        # 1. Nếu file ảnh frame đã có trên ổ cứng
        if os.path.isfile(filepath) and os.path.getsize(filepath) > 500:
            if item.get("frame_dau_tien") != local_url:
                item["frame_dau_tien"] = local_url
                updated = True
            continue

        # 2. Nếu chưa có ảnh frame, nhưng file video MP4 đã có sẵn trên máy
        v_path = (item.get("link_video") or "").strip('"\'') or build_default_video_link(stt)
        if os.path.isfile(v_path):
            if extract_frame_from_local_video(v_path, filepath):
                item["frame_dau_tien"] = local_url
                updated = True

    return updated


def load_quan_ly_config() -> Dict[str, Any]:
    """Tải cấu hình quản lý và Webhook Google Sheets"""
    default_cfg = {
        "google_sheet_id": GOOGLE_SHEET_ID,
        "google_sheet_url": f"https://docs.google.com/spreadsheets/d/{GOOGLE_SHEET_ID}/edit?usp=sharing",
        "webhook_url": "",
        "auto_sync_interval": 15
    }
    if os.path.isfile(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                default_cfg.update(data)
        except Exception:
            pass
    return default_cfg


def save_quan_ly_config(cfg: Dict[str, Any]) -> bool:
    """Lưu cấu hình quản lý và Webhook Google Sheets"""
    try:
        cur = load_quan_ly_config()
        cur.update(cfg)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cur, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def ensure_auto_content(rows: List[Dict[str, Any]]) -> bool:
    """
    Tự động kiểm tra dữ liệu ở bảng:
    Nếu đã có link Báo mới (bao_moi), tự động ghép với bài gốc để tạo Content.
    Quy tắc:
    - Nếu content đã có và đã chứa bao_moi: Giữ nguyên.
    - Nếu content đã có caption bài gốc nhưng chưa có bao_moi: Tách caption ra và ghép bao_moi ngay lập tức (0.001s).
    - Nếu content hoàn toàn trống: Tự động trích xuất caption từ link Reels Facebook, bỏ link cũ, ghép bao_moi.
    - Tự động cập nhật lại trang_thai_dang_bai.
    """
    updated = False
    for item in rows:
        bao_moi = (item.get("bao_moi") or "").strip()
        bai_goc = (item.get("bai_goc") or "").strip()
        content = (item.get("content") or "").strip()
        stt = normalize_stt(item.get("stt"))

        if not bao_moi or not bai_goc:
            continue

        # 1. Nếu content đã chứa link báo mới hiện tại -> Hoàn hảo
        if content and (bao_moi in content):
            continue

        # 2. Nếu đã có sẵn văn bản content từ trước (ít nhất 30 ký tự), chỉ cần bỏ link cũ và ghép link báo mới (0.001s)
        clean_prev = re.sub(r'https?://\S+', '', content).strip()
        if len(clean_prev) >= 30:
            final_content = f"{clean_prev}\n\n{bao_moi}"
            item["content"] = final_content
            item["trang_thai_dang_bai"] = compute_post_status(
                item.get("trang_thai_dang_bai", ""),
                final_content,
                item.get("link_video", "")
            )
            updated = True
            continue

        # 3. Nếu chưa có caption, gọi hàm auto_generate_content để cào từ Reels
        try:
            res = auto_generate_content(stt, bai_goc, bao_moi)
            if res.get("ok") and res.get("content"):
                item["content"] = res.get("content")
                item["trang_thai_dang_bai"] = compute_post_status(
                    item.get("trang_thai_dang_bai", ""),
                    res.get("content"),
                    item.get("link_video", "")
                )
                updated = True
        except Exception as e:
            print(f"[ensure_auto_content] Lỗi STT {stt}: {e}")

    return updated


def get_data_with_meta(force_sheet_sync: bool = False) -> Dict[str, Any]:
    """Trả về dữ liệu kèm metadata kiểm tra file video và thống kê tổng quan, tự động đồng bộ Google Sheet"""
    global LAST_SYNC_TIME
    now = time.time()

    # Tự động kéo Google Sheet tối đa 1 lần mỗi MIN_SYNC_INTERVAL (6s) hoặc khi được yêu cầu
    if force_sheet_sync or (now - LAST_SYNC_TIME >= MIN_SYNC_INTERVAL):
        try:
            sync_with_google_sheet(overwrite_all=False)
            LAST_SYNC_TIME = now
        except Exception as e:
            print(f"[get_data_with_meta] Sync warning: {e}")

    rows = load_quan_ly_data()

    # 1. Tự động nạp/trích xuất frame đầu tiên cho các video đã có sẵn trên máy
    changed = False
    if ensure_local_frames(rows):
        changed = True

    # 2. Tự động kiểm tra dữ liệu ở bảng nếu đã có link báo mới thì tự động ghép Content
    if ensure_auto_content(rows):
        changed = True

    if changed:
        save_quan_ly_data(rows)

    # Thống kê
    stats = {
        "total": len(rows),
        "video_status": {},
        "post_status": {},
        "video_files_ready": 0,
        "has_content": 0,
        "has_frame": 0
    }

    for item in rows:
        v_status = item.get("trang_thai_video", "Lấy video") or "Lấy video"
        stats["video_status"][v_status] = stats["video_status"].get(v_status, 0) + 1

        p_status = item.get("trang_thai_dang_bai", "chưa hoàn thành") or "chưa hoàn thành"
        stats["post_status"][p_status] = stats["post_status"].get(p_status, 0) + 1

        v_info = check_video_file(item.get("link_video", ""))
        item["video_info"] = v_info
        if v_info["exists"]:
            stats["video_files_ready"] += 1

        if item.get("content"):
            stats["has_content"] += 1
        if item.get("frame_dau_tien"):
            stats["has_frame"] += 1

    cfg = load_quan_ly_config()

    return {
        "rows": rows,
        "stats": stats,
        "video_dir": DEFAULT_VIDEO_DIR,
        "google_sheet_url": cfg.get("google_sheet_url") or f"https://docs.google.com/spreadsheets/d/{GOOGLE_SHEET_ID}/edit?usp=sharing",
        "last_sync_time": int(LAST_SYNC_TIME),
        "webhook_configured": bool(cfg.get("webhook_url"))
    }


def fetch_google_sheet_csv() -> tuple[List[Dict[str, str]], str]:
    """Tải và phân tích dữ liệu CSV trực tiếp từ Google Sheets, trả về (danh_sách_dòng, md5_hash)"""
    try:
        req = urllib.request.Request(
            CSV_EXPORT_URL,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            content = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"[fetch_google_sheet_csv] Lỗi kết nối Google Sheets: {e}")
        return [], ""

    csv_hash = hashlib.md5(content.encode("utf-8")).hexdigest()

    reader = csv.reader(io.StringIO(content))
    rows = list(reader)
    if not rows:
        return [], csv_hash

    data = []
    for r in rows[1:]:
        if not r or not any(field.strip() for field in r):
            continue

        def get_col(idx: int) -> str:
            if idx < len(r):
                val = r[idx].strip()
                if val.startswith('"""') and val.endswith('"""'):
                    val = val[3:-3].strip()
                elif val.startswith('"') and val.endswith('"') and len(val) >= 2:
                    val = val[1:-1].strip()
                return val
            return ""

        stt = normalize_stt(get_col(0))
        if not stt:
            continue

        video_status = get_col(1) or "Lấy video"
        bai_goc = get_col(2)
        prompt_video = get_col(3)
        frame_dau = get_col(4)
        bao_goc = get_col(5)
        bao_moi = get_col(6)
        post_status = get_col(7)
        content_txt = get_col(8)
        link_video = get_col(9) or build_default_video_link(stt)
        bai_viet = get_col(10)

        final_post_status = post_status or compute_post_status("", content_txt, link_video)

        data.append({
            "stt": stt,
            "trang_thai_video": video_status,
            "bai_goc": bai_goc,
            "prompt_video": prompt_video,
            "frame_dau_tien": frame_dau,
            "bao_goc": bao_goc,
            "bao_moi": bao_moi,
            "trang_thai_dang_bai": final_post_status,
            "content": content_txt,
            "link_video": link_video,
            "bai_viet": bai_viet,
            "updated_at": int(time.time())
        })

    return data, csv_hash


def load_quan_ly_data() -> List[Dict[str, Any]]:
    """Đọc dữ liệu từ file JSON local. Nếu chưa có, tự động kéo từ Google Sheets"""
    if os.path.isfile(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list) and len(data) > 0:
                    return data
        except Exception as e:
            print(f"[quan_ly_manager] Lỗi đọc {DATA_FILE}: {e}")

    # Nếu chưa có file hoặc file rỗng, tải từ Google Sheet
    try:
        data, _ = fetch_google_sheet_csv()
        ensure_local_frames(data)
        ensure_auto_content(data)
        save_quan_ly_data(data)
        return data
    except Exception as e:
        print(f"[quan_ly_manager] Lỗi tải dữ liệu Google Sheet: {e}")
        return []


def save_quan_ly_data(data: List[Dict[str, Any]]) -> bool:
    """Lưu danh sách bản ghi vào file JSON local"""
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"[quan_ly_manager] Lỗi lưu {DATA_FILE}: {e}")
        return False


def sync_with_google_sheet(overwrite_all: bool = False, force: bool = False) -> Dict[str, Any]:
    """
    Đồng bộ với Google Sheets theo cơ chế Realtime.
    - So sánh hash MD5 của CSV để tránh tính toán dư thừa nếu Sheet chưa đổi.
    - overwrite_all=False: Đồng bộ 2 chiều thông minh, bảo toàn các sửa đổi trên web chưa kịp lên Sheet.
    - overwrite_all=True: Nạp đè 100% dữ liệu từ Sheet.
    """
    global LAST_CSV_HASH, LAST_SYNC_TIME

    remote_rows, csv_hash = fetch_google_sheet_csv()
    if not remote_rows:
        return {"ok": False, "message": "Không nhận được dữ liệu từ Google Sheets"}

    # Nếu dữ liệu Google Sheet không đổi và không ép buộc -> trả về data hiện tại cực nhanh (0ms)
    if not force and not overwrite_all and (csv_hash == LAST_CSV_HASH) and LAST_CSV_HASH:
        current_data = load_quan_ly_data()
        return {
            "ok": True,
            "changed": False,
            "message": "Dữ liệu Google Sheets không đổi",
            "count": len(current_data),
            "data": current_data
        }

    LAST_CSV_HASH = csv_hash
    LAST_SYNC_TIME = time.time()

    if overwrite_all:
        ensure_local_frames(remote_rows)
        ensure_auto_content(remote_rows)
        save_quan_ly_data(remote_rows)
        return {
            "ok": True,
            "changed": True,
            "message": f"Đã nạp đè thành công {len(remote_rows)} dòng từ Google Sheet!",
            "count": len(remote_rows),
            "data": remote_rows
        }

    local_rows = load_quan_ly_data()
    local_map = {normalize_stt(r.get("stt")): r for r in local_rows if r.get("stt")}

    now = time.time()
    merged = []
    for rem in remote_rows:
        stt = normalize_stt(rem.get("stt"))
        if not stt:
            continue

        loc = local_map.get(stt, {})
        loc_updated_at = loc.get("updated_at", 0)
        is_recent_local = (now - loc_updated_at) < 25  # Vừa chỉnh sửa trên Web trong 25 giây gần nhất

        rem_bai_goc = (rem.get("bai_goc") or "").strip()
        rem_bao_goc = (rem.get("bao_goc") or "").strip()
        rem_bao_moi = (rem.get("bao_moi") or "").strip()
        rem_v_status = (rem.get("trang_thai_video") or "").strip()
        rem_prompt = (rem.get("prompt_video") or "").strip()
        rem_post_status = (rem.get("trang_thai_dang_bai") or "").strip()
        rem_content = (rem.get("content") or "").strip()
        rem_link_video = (rem.get("link_video") or "").strip()
        rem_bai_viet = (rem.get("bai_viet") or "").strip()

        loc_bai_goc = (loc.get("bai_goc") or "").strip()
        loc_bao_goc = (loc.get("bao_goc") or "").strip()
        loc_bao_moi = (loc.get("bao_moi") or "").strip()
        loc_v_status = (loc.get("trang_thai_video") or "").strip()
        loc_prompt = (loc.get("prompt_video") or "").strip()
        loc_post_status = (loc.get("trang_thai_dang_bai") or "").strip()
        loc_content = (loc.get("content") or "").strip()
        loc_link_video = (loc.get("link_video") or "").strip()
        loc_bai_viet = (loc.get("bai_viet") or "").strip()
        loc_frame = (loc.get("frame_dau_tien") or "").strip()

        if is_recent_local:
            # Người dùng vừa thao tác trên web -> Ưu tiên giá trị web để không bị Sheet ghi đè ngược lại
            final_v_status = loc_v_status or rem_v_status or "Lấy video"
            final_bai_goc = loc_bai_goc or rem_bai_goc
            final_bao_goc = loc_bao_goc or rem_bao_goc
            final_bao_moi = loc_bao_moi or rem_bao_moi
            final_prompt = loc_prompt or rem_prompt
            final_bai_viet = loc_bai_viet or rem_bai_viet
        else:
            # Google Sheet là nguồn dữ liệu chuẩn
            final_v_status = rem_v_status or loc_v_status or "Lấy video"
            final_bai_goc = rem_bai_goc or loc_bai_goc
            final_bao_goc = rem_bao_goc or loc_bao_goc
            final_bao_moi = rem_bao_moi or loc_bao_moi
            final_prompt = rem_prompt or loc_prompt
            final_bai_viet = rem_bai_viet or loc_bai_viet

        # Link video: ưu tiên local nếu đã có hoặc rem, nếu rỗng thì tạo link mặc định
        final_link_video = loc_link_video or rem_link_video or build_default_video_link(stt)

        # Frame: ưu tiên local vì đã có file ảnh trên máy
        final_frame = loc_frame or rem.get("frame_dau_tien", "").strip()

        # Content:
        # Nếu local đã có content và đã ghép final_bao_moi -> giữ local_content
        if loc_content and (not final_bao_moi or final_bao_moi in loc_content):
            final_content = loc_content
        elif rem_content and (not final_bao_moi or final_bao_moi in rem_content):
            final_content = rem_content
        else:
            final_content = loc_content or rem_content

        # Trạng thái đăng bài:
        if loc_post_status == "đăng bài" or rem_post_status == "đăng bài":
            final_post_status = "đăng bài"
        else:
            final_post_status = compute_post_status("", final_content, final_link_video)

        merged_item = {
            "stt": stt,
            "trang_thai_video": final_v_status,
            "bai_goc": final_bai_goc,
            "prompt_video": final_prompt,
            "frame_dau_tien": final_frame,
            "bao_goc": final_bao_goc,
            "bao_moi": final_bao_moi,
            "trang_thai_dang_bai": final_post_status,
            "content": final_content,
            "link_video": final_link_video,
            "bai_viet": final_bai_viet,
            "updated_at": int(loc_updated_at or time.time())
        }
        merged.append(merged_item)
        if stt in local_map:
            del local_map[stt]

    # Thêm các dòng local mới thêm chưa có trên sheet
    for stt, loc in local_map.items():
        merged.append(loc)

    # Sắp xếp theo STT
    def stt_sort_key(item):
        try:
            return (0, int(item.get("stt", 0)))
        except (ValueError, TypeError):
            return (1, str(item.get("stt", "")))

    merged.sort(key=stt_sort_key)

    # Tự động nạp frame từ máy
    ensure_local_frames(merged)

    # TỰ ĐỘNG GHÉP BÁO MỚI NẾU ĐÃ CÓ LINK BÁO MỚI
    ensure_auto_content(merged)

    save_quan_ly_data(merged)

    return {
        "ok": True,
        "changed": True,
        "message": f"Đã đồng bộ Realtime thành công {len(merged)} dòng từ Google Sheets!",
        "count": len(merged),
        "data": merged
    }


def update_row_field(stt: str, field: str, value: Any) -> Dict[str, Any]:
    """Cập nhật 1 trường dữ liệu của 1 dòng theo STT"""
    stt = normalize_stt(stt)
    data = load_quan_ly_data()
    found = False

    for item in data:
        if normalize_stt(item.get("stt")) == stt:
            item[field] = value
            item["updated_at"] = int(time.time())

            # Tự động ghép lại Content nếu trường vừa cập nhật là báo mới (bao_moi)
            if field == "bao_moi" and value:
                new_bao_moi = str(value).strip()
                prev_content = item.get("content", "")
                if prev_content:
                    clean_prev = re.sub(r'https?://\S+', '', prev_content).strip()
                    if len(clean_prev) >= 30:
                        item["content"] = f"{clean_prev}\n\n{new_bao_moi}"
                elif item.get("bai_goc"):
                    try:
                        res = auto_generate_content(stt, item.get("bai_goc"), new_bao_moi)
                        if res.get("ok") and res.get("content"):
                            item["content"] = res.get("content")
                    except Exception:
                        pass

            # Tự động tính toán lại trạng thái đăng bài nếu sửa content, bao_moi hoặc link_video
            if field in ("content", "bao_moi", "link_video", "trang_thai_dang_bai"):
                item["trang_thai_dang_bai"] = compute_post_status(
                    item.get("trang_thai_dang_bai", ""),
                    item.get("content", ""),
                    item.get("link_video", "")
                )
            found = True
            break

    if not found:
        return {"ok": False, "message": f"Không tìm thấy dòng có STT = {stt}"}

    save_quan_ly_data(data)
    push_to_google_sheet_async()
    return {"ok": True, "message": f"Đã cập nhật STT {stt} thành công!", "row": item}


def push_to_google_sheet(webhook_url: str = "") -> Dict[str, Any]:
    """
    Đẩy toàn bộ dữ liệu 11 cột từ web lên Google Sheets qua Apps Script Webhook.
    """
    cfg = load_quan_ly_config()
    target_url = (webhook_url or cfg.get("webhook_url", "")).strip()
    if not target_url:
        return {"ok": False, "message": "Chưa cài đặt Webhook URL Google Apps Script!"}

    rows = load_quan_ly_data()
    matrix = [[
        "STT", "Trạng thái video", "Bài gốc", "Prompt video",
        "Frame đầu tiên", "Báo gốc", "Báo mới", "Trạng thái đăng bài",
        "Content", "Link Video", "Bài viết"
    ]]
    for item in rows:
        matrix.append([
            item.get("stt", ""),
            item.get("trang_thai_video", ""),
            item.get("bai_goc", ""),
            item.get("prompt_video", ""),
            item.get("frame_dau_tien", ""),
            item.get("bao_goc", ""),
            item.get("bao_moi", ""),
            item.get("trang_thai_dang_bai", ""),
            item.get("content", ""),
            item.get("link_video", ""),
            item.get("bai_viet", "")
        ])

    try:
        req = urllib.request.Request(
            target_url,
            data=json.dumps({"action": "update_all", "rows": matrix}).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return {"ok": True, "message": f"Đã đẩy thành công {len(matrix)-1} dòng lên Google Sheets!", "response": raw}
    except Exception as e:
        return {"ok": False, "message": f"Lỗi đẩy dữ liệu lên Google Sheets: {e}"}


def push_to_google_sheet_async(webhook_url: str = ""):
    """Đẩy dữ liệu lên Google Sheets trong background thread để không chặn giao diện"""
    def _worker():
        try:
            cfg = load_quan_ly_config()
            target = (webhook_url or cfg.get("webhook_url", "")).strip()
            if target:
                push_to_google_sheet(target)
        except Exception as e:
            print(f"[push_to_google_sheet_async] Warning: {e}")
    threading.Thread(target=_worker, daemon=True).start()


def upsert_full_row(row_data: Dict[str, Any]) -> Dict[str, Any]:
    """Thêm mới hoặc cập nhật toàn bộ thông tin 1 dòng"""
    stt = normalize_stt(row_data.get("stt"))
    if not stt:
        return {"ok": False, "message": "STT không được để trống"}

    data = load_quan_ly_data()
    found_idx = -1
    for idx, item in enumerate(data):
        if normalize_stt(item.get("stt")) == stt:
            found_idx = idx
            break

    link_video = row_data.get("link_video") or build_default_video_link(stt)
    content_txt = row_data.get("content", "")
    post_status = compute_post_status(row_data.get("trang_thai_dang_bai", ""), content_txt, link_video)

    clean_item = {
        "stt": stt,
        "trang_thai_video": row_data.get("trang_thai_video", "Lấy video"),
        "bai_goc": row_data.get("bai_goc", "").strip(),
        "prompt_video": row_data.get("prompt_video", "").strip(),
        "frame_dau_tien": row_data.get("frame_dau_tien", "").strip(),
        "bao_goc": row_data.get("bao_goc", "").strip(),
        "bao_moi": row_data.get("bao_moi", "").strip(),
        "trang_thai_dang_bai": post_status,
        "content": content_txt,
        "link_video": link_video,
        "bai_viet": row_data.get("bai_viet", "").strip(),
        "updated_at": int(time.time())
    }

    if found_idx >= 0:
        data[found_idx] = clean_item
    else:
        data.append(clean_item)

    save_quan_ly_data(data)
    push_to_google_sheet_async()
    return {"ok": True, "message": f"Đã lưu thông tin STT {stt}!", "row": clean_item}


def delete_row(stt: str) -> Dict[str, Any]:
    """Xóa 1 dòng theo STT"""
    stt = normalize_stt(stt)
    data = load_quan_ly_data()
    initial_len = len(data)
    data = [item for item in data if normalize_stt(item.get("stt")) != stt]

    if len(data) == initial_len:
        return {"ok": False, "message": f"Không tìm thấy dòng có STT = {stt}"}

    save_quan_ly_data(data)
    push_to_google_sheet_async()
    return {"ok": True, "message": f"Đã xóa dòng STT {stt} thành công!"}


def extract_frame_from_reel(stt: str, url: str) -> Dict[str, Any]:
    """
    Trích xuất ảnh Thumbnail / Frame đầu tiên từ link Facebook Reel hoặc video cục bộ.
    Lưu ảnh vào output/frames/frame_{stt}.jpg và trả về đường dẫn webview.
    """
    stt = normalize_stt(stt)
    filename = f"frame_{stt}.jpg" if stt else f"frame_{int(time.time())}.jpg"
    filepath = os.path.join(FRAMES_DIR, filename)
    local_url = f"/api/quan-ly/frame/{filename}"

    # 1. Nếu file ảnh frame đã có sẵn trên máy
    if os.path.isfile(filepath) and os.path.getsize(filepath) > 500:
        if stt:
            update_row_field(stt, "frame_dau_tien", local_url)
        return {
            "ok": True,
            "message": "Đã có sẵn ảnh frame!",
            "frame_url": local_url,
            "local_path": filepath
        }

    # 2. Nếu file video MP4 đã có sẵn trên máy, bóc bằng ffmpeg cực nhanh (0.04s)
    v_path = build_default_video_link(stt)
    if os.path.isfile(v_path):
        if extract_frame_from_local_video(v_path, filepath):
            if stt:
                update_row_field(stt, "frame_dau_tien", local_url)
            return {
                "ok": True,
                "message": "Đã trích xuất frame từ video thành công!",
                "frame_url": local_url,
                "local_path": filepath
            }

    url = (url or "").strip()
    if not url:
        return {"ok": False, "message": "Link bài gốc đang trống."}

    thumbnail_url = ""
    # 3. Dùng yt-dlp hoặc fallback từ fb_downloader
    try:
        from fb_downloader import probe_facebook_video
        info = probe_facebook_video(url)
        thumbnail_url = info.get("thumbnail") or ""
    except Exception as e:
        print(f"[extract_frame] Lỗi probe video: {e}")

    # 2. Dự phòng: Thử scrape thẻ og:image
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
            filename = f"frame_{stt}.jpg" if stt else f"frame_{int(time.time())}.jpg"
            filepath = os.path.join(FRAMES_DIR, filename)
            with open(filepath, "wb") as f:
                f.write(img_resp.content)

            local_url = f"/api/quan-ly/frame/{filename}"
            # Cập nhật vào data
            if stt:
                update_row_field(stt, "frame_dau_tien", local_url)

            return {
                "ok": True,
                "message": "Đã lấy frame đầu tiên thành công!",
                "frame_url": local_url,
                "remote_url": thumbnail_url,
                "local_path": filepath
            }
    except Exception as e:
        # Nếu không tải được về máy, vẫn trả về link online
        if stt:
            update_row_field(stt, "frame_dau_tien", thumbnail_url)
        return {
            "ok": True,
            "message": "Đã lấy link frame online thành công (không lưu file nội bộ)",
            "frame_url": thumbnail_url
        }

    return {"ok": False, "message": "Không thể tải ảnh frame về máy"}


def auto_generate_content(stt: str, bai_goc_url: str = "", bao_moi_url: str = "") -> Dict[str, Any]:
    """
    Tự động tạo Content theo quy tắc:
    Lấy nội dung caption bài viết gốc (bỏ link nếu có) + ghép với link báo mới.
    Có cơ chế đường tắt cực nhanh: nếu đã có caption từ trước, ghép ngay lập tức (0.001s).
    """
    stt = normalize_stt(stt)
    bai_goc_url = (bai_goc_url or "").strip()
    bao_moi_url = (bao_moi_url or "").strip()

    data = load_quan_ly_data()
    target_row = None
    if stt:
        for it in data:
            if normalize_stt(it.get("stt")) == stt:
                target_row = it
                if not bai_goc_url:
                    bai_goc_url = (it.get("bai_goc") or "").strip()
                if not bao_moi_url:
                    bao_moi_url = (it.get("bao_moi") or "").strip()
                break

    if not bai_goc_url:
        return {"ok": False, "message": "Chưa có link Bài gốc (Facebook Reel)."}

    # Đường tắt siêu tốc: nếu dòng đã có content trước đó, bóc caption cũ và ghép link báo mới ngay lập tức
    if target_row and target_row.get("content"):
        clean_exist = re.sub(r'https?://\S+', '', target_row.get("content")).strip()
        if len(clean_exist) >= 30:
            final_content = f"{clean_exist}\n\n{bao_moi_url}" if bao_moi_url else clean_exist
            if stt:
                update_row_field(stt, "content", final_content)
            return {
                "ok": True,
                "message": "Đã tự động ghép Báo mới với Content thành công!",
                "content": final_content,
                "clean_caption": clean_exist,
                "bao_moi": bao_moi_url
            }

    raw_caption = ""
    # Thử lấy description bằng yt-dlp
    try:
        import yt_dlp
        ydl_opts = {"quiet": True, "skip_download": True, "no_warnings": True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(bai_goc_url, download=False)
            raw_caption = info.get("description") or info.get("title") or ""
    except Exception as e:
        print(f"[auto_generate_content] yt-dlp warning: {e}")

    # Fallback: scrape thẻ og:description hoặc title
    if not raw_caption:
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            resp = requests.get(bai_goc_url, headers=headers, timeout=10)
            m = re.search(r'property=["\']og:description["\']\s+content=["\']([^"\']+)["\']', resp.text)
            if m:
                raw_caption = m.group(1).replace("&amp;", "&")
            else:
                m_title = re.search(r"<title>(.*?)</title>", resp.text, re.I)
                if m_title:
                    raw_caption = m_title.group(1).replace(" | Facebook", "").strip()
        except Exception:
            pass

    if not raw_caption:
        return {"ok": False, "message": "Không thể lấy nội dung văn bản từ link Facebook Reel này."}

    # Bỏ các link URL có sẵn trong caption bài gốc
    clean_caption = re.sub(r'https?://\S+', '', raw_caption).strip()

    # Ghép với link báo mới
    if bao_moi_url:
        final_content = f"{clean_caption}\n\n{bao_moi_url}"
    else:
        final_content = clean_caption

    # Cập nhật dòng nếu có STT
    if stt:
        update_row_field(stt, "content", final_content)

    return {
        "ok": True,
        "message": "Đã tự động tạo Content thành công!",
        "content": final_content,
        "clean_caption": clean_caption,
        "bao_moi": bao_moi_url
    }


def generate_export_tsv(data: List[Dict[str, Any]]) -> str:
    """Tạo chuỗi TSV (Tab-Separated Values) để người dùng copy và Paste 1 lần vào Google Sheets"""
    output = io.StringIO()
    writer = csv.writer(output, delimiter="\t")
    # Header
    writer.writerow([
        "STT",
        "Trạng thái video",
        "Bài gốc",
        "Prompt video",
        "Frame đầu tiên",
        "Báo gốc",
        "Báo mới",
        "Trạng thái đăng bài",
        "Content",
        "Link Video",
        "Bài viết"
    ])
    for item in data:
        writer.writerow([
            item.get("stt", ""),
            item.get("trang_thai_video", ""),
            item.get("bai_goc", ""),
            item.get("prompt_video", ""),
            item.get("frame_dau_tien", ""),
            item.get("bao_goc", ""),
            item.get("bao_moi", ""),
            item.get("trang_thai_dang_bai", ""),
            item.get("content", ""),
            item.get("link_video", ""),
            item.get("bai_viet", "")
        ])
    return output.getvalue()


def generate_export_csv(data: List[Dict[str, Any]]) -> str:
    """Tạo chuỗi CSV chuẩn UTF-8 có BOM để mở bằng Excel không lỗi font tiếng Việt"""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "STT",
        "Trạng thái video",
        "Bài gốc",
        "Prompt video",
        "Frame đầu tiên",
        "Báo gốc",
        "Báo mới",
        "Trạng thái đăng bài",
        "Content",
        "Link Video",
        "Bài viết"
    ])
    for item in data:
        writer.writerow([
            item.get("stt", ""),
            item.get("trang_thai_video", ""),
            item.get("bai_goc", ""),
            item.get("prompt_video", ""),
            item.get("frame_dau_tien", ""),
            item.get("bao_goc", ""),
            item.get("bao_moi", ""),
            item.get("trang_thai_dang_bai", ""),
            item.get("content", ""),
            item.get("link_video", ""),
            item.get("bai_viet", "")
        ])
    return "\ufeff" + output.getvalue()
