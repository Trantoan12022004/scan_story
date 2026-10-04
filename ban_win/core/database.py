"""
SQLite database engine with WAL mode for ban_win application.
Thread-safe helper with migration and CRUD support.
"""
import os
import sqlite3
import json
import time
from typing import List, Dict, Any, Optional

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DB_PATH = os.path.join(DB_DIR, "app.db")

class Database:
    _instance = None

    def __new__(cls, db_path: Optional[str] = None):
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, db_path: Optional[str] = None):
        if self._initialized:
            return
        self.db_path = db_path or DB_PATH
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.init_database()
        self._initialized = True

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=15.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def init_database(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # 1. Bảng videos (11 cột chính + metadata)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS videos (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                stt                 TEXT    NOT NULL UNIQUE,
                trang_thai_video     TEXT    DEFAULT '',
                bai_goc             TEXT    DEFAULT '',
                prompt_video        TEXT    DEFAULT '',
                frame_dau_tien      TEXT    DEFAULT '',
                bao_goc             TEXT    DEFAULT '',
                bao_moi             TEXT    DEFAULT '',
                trang_thai_dang_bai TEXT    DEFAULT 'chưa hoàn thành',
                content             TEXT    DEFAULT '',
                link_video          TEXT    DEFAULT '',
                bai_viet_da_dang    TEXT    DEFAULT '',
                created_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
                synced_at           DATETIME,
                local_modified      INTEGER DEFAULT 0,
                local_modified_time REAL    DEFAULT 0.0
            );
            """)

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_stt ON videos(stt);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_status ON videos(trang_thai_video);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_post_status ON videos(trang_thai_dang_bai);")

            # 2. Bảng downloaded_videos
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS downloaded_videos (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                url             TEXT    NOT NULL,
                title           TEXT    DEFAULT '',
                author          TEXT    DEFAULT '',
                duration        TEXT    DEFAULT '',
                quality         TEXT    DEFAULT '',
                file_path       TEXT    DEFAULT '',
                file_size       TEXT    DEFAULT '',
                thumbnail_url   TEXT    DEFAULT '',
                downloaded_at   DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_dl_url ON downloaded_videos(url);")

            # 3. Bảng scraped_stories
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS scraped_stories (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                url             TEXT    NOT NULL,
                title           TEXT    DEFAULT '',
                slug            TEXT    DEFAULT '',
                chapters_count  INTEGER DEFAULT 0,
                output_dir      TEXT    DEFAULT '',
                translated      INTEGER DEFAULT 0,
                published       INTEGER DEFAULT 0,
                cms_url         TEXT    DEFAULT '',
                scraped_at      DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            """)

            # 4. Bảng prompts
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS prompts (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                name            TEXT    NOT NULL,
                content         TEXT    NOT NULL,
                created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            """)

            # 5. Bảng settings
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key             TEXT    PRIMARY KEY,
                value           TEXT    DEFAULT ''
            );
            """)

            # Defaults for settings
            defaults = [
                ('video_dir', r'C:\Users\Trant\Videos\Seedance\anhtonton\AI_VIDEO'),
                ('google_sheet_id', '1t4nyagzl-ySljwSK6nSxXPFttv11Vx-az2exQ9pKBuA'),
                ('sheet_csv_url', 'https://docs.google.com/spreadsheets/d/1t4nyagzl-ySljwSK6nSxXPFttv11Vx-az2exQ9pKBuA/export?format=csv'),
                ('webhook_url', ''),
                ('sync_interval', '3'),
                ('theme', 'light'),
                ('cms_url', 'https://vmnewstoryus.cfx.bz'),
                ('cms_user', 'admin'),
                ('cms_pass', ''),
                ('auto_sync', '1'),
            ]
            cursor.executemany("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?);", defaults)
            conn.commit()

        # Seed initial data if tables are empty
        self._seed_initial_data()

    def _seed_initial_data(self):
        """Tự động migrate dữ liệu từ file JSON cũ nếu SQLite còn trống."""
        try:
            parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

            # Seed videos from quan_ly_data.json
            with self.get_connection() as conn:
                count = conn.execute("SELECT COUNT(*) FROM videos;").fetchone()[0]
                if count == 0:
                    json_path = os.path.join(parent_dir, "quan_ly_data.json")
                    if os.path.exists(json_path):
                        with open(json_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        rows = []
                        now = time.time()
                        for item in data:
                            stt = str(item.get("stt", "")).strip()
                            if not stt:
                                continue
                            rows.append((
                                stt,
                                item.get("trang_thai_video", "") or "",
                                item.get("bai_goc", "") or "",
                                item.get("prompt_video", "") or "",
                                item.get("frame_dau_tien", "") or "",
                                item.get("bao_goc", "") or "",
                                item.get("bao_moi", "") or "",
                                item.get("trang_thai_dang_bai", "chưa hoàn thành") or "chưa hoàn thành",
                                item.get("content", "") or "",
                                item.get("link_video", "") or "",
                                item.get("bai_viet_da_dang", "") or "",
                                0,
                                0.0
                            ))
                        if rows:
                            conn.executemany("""
                            INSERT OR IGNORE INTO videos (
                                stt, trang_thai_video, bai_goc, prompt_video, frame_dau_tien,
                                bao_goc, bao_moi, trang_thai_dang_bai, content, link_video,
                                bai_viet_da_dang, local_modified, local_modified_time
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                            """, rows)
                            conn.commit()

                # Seed prompts from prompts.json
                p_count = conn.execute("SELECT COUNT(*) FROM prompts;").fetchone()[0]
                if p_count == 0:
                    prompts_file = os.path.join(parent_dir, "prompts.json")
                    if os.path.exists(prompts_file):
                        with open(prompts_file, "r", encoding="utf-8") as f:
                            p_data = json.load(f)
                        p_rows = []
                        if isinstance(p_data, list):
                            for idx, p in enumerate(p_data):
                                if isinstance(p, dict):
                                    p_rows.append((p.get("name", f"Prompt {idx+1}"), p.get("content", "")))
                                elif isinstance(p, str):
                                    p_rows.append((f"Prompt {idx+1}", p))
                        elif isinstance(p_data, dict):
                            for k, v in p_data.items():
                                p_rows.append((k, str(v)))
                        if p_rows:
                            conn.executemany("INSERT INTO prompts (name, content) VALUES (?, ?);", p_rows)
                            conn.commit()
        except Exception as e:
            print(f"[Database] Error seeding initial data: {e}")

    # ================= CRUD VIDEOS =================

    def get_all_videos(self, search: Optional[str] = None,
                       trang_thai_video: Optional[str] = None,
                       trang_thai_dang_bai: Optional[str] = None) -> List[Dict[str, Any]]:
        query = "SELECT * FROM videos WHERE 1=1"
        params = []

        if search:
            query += " AND (stt LIKE ? OR prompt_video LIKE ? OR content LIKE ? OR bai_goc LIKE ? OR bao_moi LIKE ?)"
            s = f"%{search}%"
            params.extend([s, s, s, s, s])

        if trang_thai_video:
            query += " AND trang_thai_video = ?"
            params.append(trang_thai_video)

        if trang_thai_dang_bai:
            query += " AND trang_thai_dang_bai = ?"
            params.append(trang_thai_dang_bai)

        # Natural sort by STT if numeric, otherwise text sort
        query += " ORDER BY CAST(stt AS INTEGER) ASC, stt ASC"

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_video_by_stt(self, stt: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM videos WHERE stt = ? LIMIT 1;", (stt,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def upsert_video(self, data: Dict[str, Any], mark_local: bool = True) -> bool:
        stt = str(data.get("stt", "")).strip()
        if not stt:
            return False

        now = time.time()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, local_modified_time FROM videos WHERE stt = ?;", (stt,))
            existing = cursor.fetchone()

            if existing:
                # If this is from sync and local row was modified within 25s, prevent overwrite
                if not mark_local and (now - (existing["local_modified_time"] or 0)) < 25.0:
                    return False

                update_fields = [
                    "trang_thai_video = ?", "bai_goc = ?", "prompt_video = ?",
                    "frame_dau_tien = ?", "bao_goc = ?", "bao_moi = ?",
                    "trang_thai_dang_bai = ?", "content = ?", "link_video = ?",
                    "bai_viet_da_dang = ?", "updated_at = CURRENT_TIMESTAMP"
                ]
                params = [
                    data.get("trang_thai_video", ""),
                    data.get("bai_goc", ""),
                    data.get("prompt_video", ""),
                    data.get("frame_dau_tien", ""),
                    data.get("bao_goc", ""),
                    data.get("bao_moi", ""),
                    data.get("trang_thai_dang_bai", "chưa hoàn thành"),
                    data.get("content", ""),
                    data.get("link_video", ""),
                    data.get("bai_viet_da_dang", "")
                ]
                if mark_local:
                    update_fields.append("local_modified = 1")
                    update_fields.append("local_modified_time = ?")
                    params.append(now)
                else:
                    update_fields.append("synced_at = CURRENT_TIMESTAMP")

                params.append(stt)
                cursor.execute(f"UPDATE videos SET {', '.join(update_fields)} WHERE stt = ?;", params)
            else:
                cursor.execute("""
                INSERT INTO videos (
                    stt, trang_thai_video, bai_goc, prompt_video, frame_dau_tien,
                    bao_goc, bao_moi, trang_thai_dang_bai, content, link_video,
                    bai_viet_da_dang, local_modified, local_modified_time
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    stt,
                    data.get("trang_thai_video", ""),
                    data.get("bai_goc", ""),
                    data.get("prompt_video", ""),
                    data.get("frame_dau_tien", ""),
                    data.get("bao_goc", ""),
                    data.get("bao_moi", ""),
                    data.get("trang_thai_dang_bai", "chưa hoàn thành"),
                    data.get("content", ""),
                    data.get("link_video", ""),
                    data.get("bai_viet_da_dang", ""),
                    1 if mark_local else 0,
                    now if mark_local else 0.0
                ))
            conn.commit()
            return True

    def delete_video(self, stt: str) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM videos WHERE stt = ?;", (stt,))
            conn.commit()
            return cursor.rowcount > 0

    def update_single_field(self, stt: str, field: str, value: Any, mark_local: bool = True) -> bool:
        allowed = [
            "trang_thai_video", "bai_goc", "prompt_video", "frame_dau_tien",
            "bao_goc", "bao_moi", "trang_thai_dang_bai", "content",
            "link_video", "bai_viet_da_dang"
        ]
        if field not in allowed:
            return False

        now = time.time()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if mark_local:
                cursor.execute(f"""
                UPDATE videos
                SET {field} = ?, updated_at = CURRENT_TIMESTAMP, local_modified = 1, local_modified_time = ?
                WHERE stt = ?;
                """, (value, now, stt))
            else:
                cursor.execute(f"""
                UPDATE videos
                SET {field} = ?, updated_at = CURRENT_TIMESTAMP
                WHERE stt = ?;
                """, (value, stt))
            conn.commit()
            return cursor.rowcount > 0

    def get_stat_counts(self) -> Dict[str, int]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            total = cursor.execute("SELECT COUNT(*) FROM videos;").fetchone()[0]
            video_done = cursor.execute("SELECT COUNT(*) FROM videos WHERE trang_thai_video = 'Xong video';").fetchone()[0]
            has_file = cursor.execute("SELECT COUNT(*) FROM videos WHERE link_video != '' AND link_video IS NOT NULL;").fetchone()[0]
            post_done = cursor.execute("SELECT COUNT(*) FROM videos WHERE trang_thai_dang_bai = 'hoàn thành';").fetchone()[0]
            return {
                "total": total,
                "video_done": video_done,
                "has_file": has_file,
                "post_done": post_done
            }

    # ================= SETTINGS =================

    def get_setting(self, key: str, default: str = "") -> str:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = ?;", (key,))
            row = cursor.fetchone()
            return row["value"] if row else default

    def set_setting(self, key: str, value: str):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value;
            """, (key, str(value)))
            conn.commit()

    def get_all_settings(self) -> Dict[str, str]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM settings;")
            return {row["key"]: row["value"] for row in cursor.fetchall()}

    # ================= DOWNLOADED VIDEOS =================

    def add_downloaded_video(self, data: Dict[str, Any]) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO downloaded_videos (url, title, author, duration, quality, file_path, file_size, thumbnail_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                data.get("url", ""),
                data.get("title", ""),
                data.get("author", ""),
                data.get("duration", ""),
                data.get("quality", ""),
                data.get("file_path", ""),
                data.get("file_size", ""),
                data.get("thumbnail_url", "")
            ))
            conn.commit()
            return cursor.lastrowid

    def get_downloaded_videos(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM downloaded_videos ORDER BY id DESC LIMIT ?;", (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def delete_downloaded_video(self, vid_id: int):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM downloaded_videos WHERE id = ?;", (vid_id,))
            conn.commit()

    # ================= SCRAPED STORIES =================

    def add_scraped_story(self, data: Dict[str, Any]) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO scraped_stories (url, title, slug, chapters_count, output_dir, translated, published, cms_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                data.get("url", ""),
                data.get("title", ""),
                data.get("slug", ""),
                data.get("chapters_count", 0),
                data.get("output_dir", ""),
                data.get("translated", 0),
                data.get("published", 0),
                data.get("cms_url", "")
            ))
            conn.commit()
            return cursor.lastrowid

    def get_scraped_stories(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM scraped_stories ORDER BY id DESC LIMIT ?;", (limit,))
            return [dict(row) for row in cursor.fetchall()]

    # ================= PROMPTS =================

    def get_all_prompts(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM prompts ORDER BY id ASC;")
            return [dict(row) for row in cursor.fetchall()]

    def save_prompt(self, name: str, content: str, prompt_id: Optional[int] = None) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if prompt_id:
                cursor.execute("UPDATE prompts SET name = ?, content = ? WHERE id = ?;", (name, content, prompt_id))
                return prompt_id
            else:
                cursor.execute("INSERT INTO prompts (name, content) VALUES (?, ?);", (name, content))
                conn.commit()
                return cursor.lastrowid

    def delete_prompt(self, prompt_id: int):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM prompts WHERE id = ?;", (prompt_id,))
            conn.commit()


# Singleton accessor
_db_instance: Optional[Database] = None

def get_db() -> Database:
    global _db_instance
    if _db_instance is None:
        _db_instance = Database()
    return _db_instance
