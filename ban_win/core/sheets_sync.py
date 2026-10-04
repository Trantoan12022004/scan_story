"""
Đồng bộ 2 chiều Realtime giữa SQLite và Google Sheets.
Hỗ trợ MD5 caching, conflict protection (< 25s), và webhook push.
"""
import csv
import io
import time
import json
import hashlib
import urllib.request
import threading
from typing import Dict, List, Any, Tuple, Optional
from .database import get_db
from .config import Config
from .video_checker import normalize_stt, build_default_video_link
from .content_generator import compute_post_status

LAST_CSV_HASH = ""
LAST_SYNC_TIME = 0.0

def fetch_google_sheet_csv(url: Optional[str] = None) -> Tuple[List[Dict[str, Any]], str]:
    """Tải và phân tích dữ liệu CSV trực tiếp từ Google Sheets, trả về (danh_sách_dòng, md5_hash)"""
    target_url = url or Config.sheet_csv_url()
    try:
        req = urllib.request.Request(
            target_url,
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
            "bai_viet_da_dang": bai_viet,
        })

    return data, csv_hash


def sync_with_google_sheet(overwrite_all: bool = False, force: bool = False) -> Dict[str, Any]:
    """
    Đồng bộ dữ liệu từ Google Sheets vào SQLite:
    - Nếu hash MD5 không đổi và không force -> trả về nhanh không làm gì
    - overwrite_all=False: Merge thông minh, giữ thay đổi local < 25s
    - overwrite_all=True: Nạp đè toàn bộ
    """
    global LAST_CSV_HASH, LAST_SYNC_TIME

    remote_rows, csv_hash = fetch_google_sheet_csv()
    if not remote_rows:
        return {"ok": False, "message": "Không nhận được dữ liệu từ Google Sheets"}

    if not force and not overwrite_all and (csv_hash == LAST_CSV_HASH) and LAST_CSV_HASH:
        return {
            "ok": True,
            "changed": False,
            "message": "Dữ liệu Google Sheets không đổi",
            "count": len(remote_rows)
        }

    LAST_CSV_HASH = csv_hash
    LAST_SYNC_TIME = time.time()
    db = get_db()

    now = time.time()
    count_saved = 0

    if overwrite_all:
        for r in remote_rows:
            db.upsert_video(r, mark_local=False)
            count_saved += 1
        return {
            "ok": True,
            "changed": True,
            "message": f"Đã nạp đè thành công {count_saved} dòng từ Google Sheet!",
            "count": count_saved
        }

    # Merge thông minh
    for rem in remote_rows:
        stt = normalize_stt(rem.get("stt"))
        if not stt:
            continue

        loc = db.get_video_by_stt(stt)
        if not loc:
            db.upsert_video(rem, mark_local=False)
            count_saved += 1
            continue

        loc_mod_time = loc.get("local_modified_time") or 0.0
        is_recent_local = (now - loc_mod_time) < 25.0

        if is_recent_local:
            # Ưu tiên các trường local vừa chỉnh sửa
            merged = {
                "stt": stt,
                "trang_thai_video": loc.get("trang_thai_video") or rem.get("trang_thai_video") or "Lấy video",
                "bai_goc": loc.get("bai_goc") or rem.get("bai_goc", ""),
                "prompt_video": loc.get("prompt_video") or rem.get("prompt_video", ""),
                "frame_dau_tien": loc.get("frame_dau_tien") or rem.get("frame_dau_tien", ""),
                "bao_goc": loc.get("bao_goc") or rem.get("bao_goc", ""),
                "bao_moi": loc.get("bao_moi") or rem.get("bao_moi", ""),
                "trang_thai_dang_bai": loc.get("trang_thai_dang_bai") or rem.get("trang_thai_dang_bai", "chưa hoàn thành"),
                "content": loc.get("content") or rem.get("content", ""),
                "link_video": loc.get("link_video") or rem.get("link_video") or build_default_video_link(stt),
                "bai_viet_da_dang": loc.get("bai_viet_da_dang") or rem.get("bai_viet_da_dang", "")
            }
            db.upsert_video(merged, mark_local=True)
        else:
            # Google Sheets là nguồn chuẩn
            final_content = loc.get("content") or rem.get("content", "")
            rem_bao_moi = rem.get("bao_moi", "").strip()
            if loc.get("content") and (not rem_bao_moi or rem_bao_moi in loc.get("content", "")):
                final_content = loc.get("content")

            merged = {
                "stt": stt,
                "trang_thai_video": rem.get("trang_thai_video") or loc.get("trang_thai_video") or "Lấy video",
                "bai_goc": rem.get("bai_goc") or loc.get("bai_goc", ""),
                "prompt_video": rem.get("prompt_video") or loc.get("prompt_video", ""),
                "frame_dau_tien": loc.get("frame_dau_tien") or rem.get("frame_dau_tien", ""),
                "bao_goc": rem.get("bao_goc") or loc.get("bao_goc", ""),
                "bao_moi": rem.get("bao_moi") or loc.get("bao_moi", ""),
                "trang_thai_dang_bai": rem.get("trang_thai_dang_bai") or loc.get("trang_thai_dang_bai", "chưa hoàn thành"),
                "content": final_content,
                "link_video": loc.get("link_video") or rem.get("link_video") or build_default_video_link(stt),
                "bai_viet_da_dang": rem.get("bai_viet_da_dang") or loc.get("bai_viet_da_dang", "")
            }
            db.upsert_video(merged, mark_local=False)

        count_saved += 1

    return {
        "ok": True,
        "changed": True,
        "message": f"Đã đồng bộ Realtime thành công {count_saved} dòng từ Google Sheets!",
        "count": count_saved
    }


def push_to_google_sheet(webhook_url: Optional[str] = None) -> Dict[str, Any]:
    """
    Đẩy toàn bộ 11 cột từ SQLite lên Google Sheets qua Apps Script Webhook.
    """
    target_url = (webhook_url or Config.webhook_url()).strip()
    if not target_url:
        return {"ok": False, "message": "Chưa cài đặt Webhook URL Google Apps Script!"}

    db = get_db()
    rows = db.get_all_videos()

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
            item.get("bai_viet_da_dang", "")
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


def push_to_google_sheet_async(webhook_url: Optional[str] = None):
    def _worker():
        try:
            push_to_google_sheet(webhook_url)
        except Exception as e:
            print(f"[push_to_google_sheet_async] Warning: {e}")
    threading.Thread(target=_worker, daemon=True).start()
