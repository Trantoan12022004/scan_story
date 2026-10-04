"""
Tự động tạo Content theo quy tắc:
Trích xuất caption từ bài viết gốc Facebook Reel (loại bỏ link cũ) + ghép với link báo mới.
Cập nhật trực tiếp vào SQLite và tính toán trạng thái đăng bài.
"""
import re
import requests
from typing import Dict, Any, Optional
from .database import get_db
from .video_checker import normalize_stt

def compute_post_status(current_status: str, content: str, link_video: str) -> str:
    """
    Tính toán trạng thái đăng bài:
    - chưa hoàn thành: chưa có nội dung ở hai cột content và link video
    - hoàn thành: có nội dung ở hai cột content và link video
    - đăng bài: người dùng thao tác
    """
    cur = (current_status or "").strip().lower()
    if cur in ("đăng bài", "dang bai"):
        return "đăng bài"

    has_content = bool(content and content.strip())
    has_video = bool(link_video and link_video.strip())

    if has_content and has_video:
        return "hoàn thành"
    return "chưa hoàn thành"

def auto_generate_content(stt: str, bai_goc_url: str = "", bao_moi_url: str = "") -> Dict[str, Any]:
    stt = normalize_stt(stt)
    bai_goc_url = (bai_goc_url or "").strip()
    bao_moi_url = (bao_moi_url or "").strip()

    db = get_db()
    target_row = db.get_video_by_stt(stt) if stt else None

    if target_row:
        if not bai_goc_url:
            bai_goc_url = (target_row.get("bai_goc") or "").strip()
        if not bao_moi_url:
            bao_moi_url = (target_row.get("bao_moi") or "").strip()

    if not bai_goc_url:
        return {"ok": False, "message": "Chưa có link Bài gốc (Facebook Reel)."}

    # 1. Đường tắt siêu tốc: nếu dòng đã có content trước đó, bóc caption cũ và ghép link báo mới ngay lập tức
    if target_row and target_row.get("content"):
        clean_exist = re.sub(r'https?://\S+', '', target_row.get("content")).strip()
        if len(clean_exist) >= 30:
            final_content = f"{clean_exist}\n\n{bao_moi_url}" if bao_moi_url else clean_exist
            if stt:
                db.update_single_field(stt, "content", final_content)
                new_post_status = compute_post_status(
                    target_row.get("trang_thai_dang_bai", ""),
                    final_content,
                    target_row.get("link_video", "")
                )
                db.update_single_field(stt, "trang_thai_dang_bai", new_post_status)
            return {
                "ok": True,
                "message": "Đã tự động ghép Báo mới với Content thành công!",
                "content": final_content,
                "clean_caption": clean_exist,
                "bao_moi": bao_moi_url
            }

    raw_caption = ""
    # 2. Thử lấy description bằng yt-dlp
    try:
        import yt_dlp
        ydl_opts = {"quiet": True, "skip_download": True, "no_warnings": True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(bai_goc_url, download=False)
            raw_caption = info.get("description") or info.get("title") or ""
    except Exception as e:
        print(f"[auto_generate_content] yt-dlp warning: {e}")

    # 3. Fallback: scrape thẻ og:description hoặc title
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

    final_content = f"{clean_caption}\n\n{bao_moi_url}" if bao_moi_url else clean_caption
    if stt and target_row:
        db.update_single_field(stt, "content", final_content)
        new_post_status = compute_post_status(
            target_row.get("trang_thai_dang_bai", ""),
            final_content,
            target_row.get("link_video", "")
        )
        db.update_single_field(stt, "trang_thai_dang_bai", new_post_status)

    return {
        "ok": True,
        "message": "Đã tự động tạo Content thành công!",
        "content": final_content,
        "clean_caption": clean_caption,
        "bao_moi": bao_moi_url
    }

def ensure_auto_content_db() -> int:
    """
    Quét toàn bộ bản ghi trong SQLite:
    Nếu đã có link Báo mới (bao_moi), tự động ghép với bài gốc để tạo Content.
    """
    db = get_db()
    videos = db.get_all_videos()
    updated_count = 0

    for item in videos:
        stt = normalize_stt(item.get("stt"))
        bao_moi = (item.get("bao_moi") or "").strip()
        bai_goc = (item.get("bai_goc") or "").strip()
        content = (item.get("content") or "").strip()

        if not bao_moi or not bai_goc:
            continue

        if content and (bao_moi in content):
            continue

        # Đã có content từ trước, chỉ cần ghép link báo mới (0.001s)
        clean_prev = re.sub(r'https?://\S+', '', content).strip()
        if len(clean_prev) >= 30:
            final_content = f"{clean_prev}\n\n{bao_moi}"
            db.update_single_field(stt, "content", final_content, mark_local=False)
            new_p = compute_post_status(item.get("trang_thai_dang_bai", ""), final_content, item.get("link_video", ""))
            db.update_single_field(stt, "trang_thai_dang_bai", new_p, mark_local=False)
            updated_count += 1
            continue

        # Chưa có caption, cào từ Reels
        try:
            res = auto_generate_content(stt, bai_goc, bao_moi)
            if res.get("ok"):
                updated_count += 1
        except Exception:
            pass

    return updated_count
