"""
Kiểm tra file video trên ổ cứng local theo STT và thư mục cấu hình.
"""
import os
from typing import Dict, Any, Optional
from .config import Config

def normalize_stt(val: Any) -> str:
    if val is None:
        return ""
    s = str(val).strip()
    if s.endswith(".0"):
        s = s[:-2]
    return s

def build_default_video_link(stt: str, base_dir: Optional[str] = None) -> str:
    clean_stt = normalize_stt(stt)
    if not clean_stt:
        return ""
    dir_path = base_dir or Config.video_dir()
    return os.path.normpath(os.path.join(dir_path, f"{clean_stt}.mp4"))

def check_video_file(path_str: str, stt: Optional[str] = None) -> Dict[str, Any]:
    """
    Kiểm tra file video đã có sẵn trên máy tính chưa.
    Nếu path_str rỗng, thử kiểm tra file mặc định theo STT.
    """
    target_path = (path_str or "").strip('"\'')
    if not target_path and stt:
        target_path = build_default_video_link(stt)

    if not target_path:
        return {"exists": False, "size": "", "bytes": 0, "path": ""}

    # Kiểm tra trực tiếp đường dẫn
    if os.path.isfile(target_path):
        try:
            sz = os.path.getsize(target_path)
            mb = sz / (1024 * 1024)
            size_str = f"{mb:.1f} MB" if mb >= 1 else f"{sz / 1024:.0f} KB"
            return {"exists": True, "size": size_str, "bytes": sz, "path": target_path}
        except Exception:
            return {"exists": True, "size": "Có sẵn", "bytes": 0, "path": target_path}

    # Nếu target_path không tồn tại nhưng có STT, thử tìm trong thư mục video cấu hình
    if stt:
        default_p = build_default_video_link(stt)
        if default_p != target_path and os.path.isfile(default_p):
            try:
                sz = os.path.getsize(default_p)
                mb = sz / (1024 * 1024)
                size_str = f"{mb:.1f} MB" if mb >= 1 else f"{sz / 1024:.0f} KB"
                return {"exists": True, "size": size_str, "bytes": sz, "path": default_p}
            except Exception:
                return {"exists": True, "size": "Có sẵn", "bytes": 0, "path": default_p}

    return {"exists": False, "size": "", "bytes": 0, "path": target_path}
