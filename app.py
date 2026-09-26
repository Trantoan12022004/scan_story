#!/usr/bin/env python3
# app.py
# Web UI Server cho Story Scraper & Auto CMS Publisher

import os
import sys
import json
import time
import queue
import threading
import subprocess
import webbrowser
import urllib.parse
from urllib.parse import urlparse, urljoin
from flask import Flask, render_template, request, Response, jsonify, send_from_directory

# Fix encoding cho Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from parsers import detect_parser
from downloader import Downloader
from translator import Translator
from publisher import CMSPublisher
from main import save_chapter, save_full_story, sanitize_filename
from license_manager import LicenseManager, get_machine_id

# Cấu hình đường dẫn templates và thư mục gốc tương thích cả chạy code gốc và chạy qua PyInstaller EXE
if getattr(sys, 'frozen', False):
    base_dir = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    template_folder = os.path.join(base_dir, "templates")
    app = Flask(__name__, template_folder=template_folder)
    APP_ROOT = os.path.dirname(sys.executable)
else:
    app = Flask(__name__)
    APP_ROOT = os.path.dirname(os.path.abspath(__file__))

app.config["TEMPLATES_AUTO_RELOAD"] = True
app.jinja_env.auto_reload = True

# Quản lý danh sách các subscriber SSE để hỗ trợ nhiều tab trình duyệt
subscribers = []
subscribers_lock = threading.Lock()
is_processing = False


def emit_event(event_type: str, message: str = "", data: dict = None):
    """Phát sự kiện tới tất cả các client đang mở giao diện"""
    payload = {
        "type": event_type,
        "message": message,
        "time": time.strftime("%H:%M:%S"),
        "data": data or {}
    }
    encoded = json.dumps(payload, ensure_ascii=False)
    with subscribers_lock:
        for q in list(subscribers):
            try:
                q.put_nowait(encoded)
            except Exception:
                subscribers.remove(q)


def is_admin_mode() -> bool:
    """Kiểm tra ứng dụng đang chạy ở chế độ Admin hay User"""
    return ("--admin" in sys.argv) or (os.environ.get("STORY_APP_MODE", "").lower() == "admin")


@app.route("/")
def index():
    if is_admin_mode():
        return render_template("index_admin.html")
    return render_template("index_user.html")


@app.route("/api/stream-logs")
def stream_logs():
    """SSE endpoint truyền log và tiến trình thời gian thực"""
    client_queue = queue.Queue(maxsize=100)
    with subscribers_lock:
        subscribers.append(client_queue)

    def event_stream():
        try:
            while True:
                try:
                    data = client_queue.get(timeout=25)
                    yield f"data: {data}\n\n"
                except queue.Empty:
                    yield ": keep-alive\n\n"
        except GeneratorExit:
            with subscribers_lock:
                if client_queue in subscribers:
                    subscribers.remove(client_queue)

    return Response(event_stream(), mimetype="text/event-stream")


def process_story_thread(params):
    global is_processing
    is_processing = True

    url = params.get("url", "").strip()
    translate_en = params.get("translate", True)
    publish_cms = params.get("publish", True)
    download_img = params.get("download_images", True)
    from_ch = int(params.get("from_chapter") or 1)
    to_ch = int(params.get("to_chapter") or 0)
    delay = float(params.get("delay") or 1.5)
    cms_url = (params.get("cms_url") or "https://vmnewstoryus.cfx.bz").strip()
    cms_user = (params.get("cms_user") or "admin").strip()
    cms_pass = (params.get("cms_pass") or "admin123").strip()

    emit_event("info", f"🔍 Phân tích URL: {url}")

    try:
        parser = detect_parser(url)
        emit_event("success", f"✅ Đã nhận diện: {parser.get_name()}")
    except Exception as e:
        emit_event("error", f"❌ {e}")
        is_processing = False
        emit_event("done", "Đã dừng do lỗi.", {"status": "error"})
        return

    emit_event("info", "📥 Đang tải trang để lấy thông tin truyện...")
    downloader = Downloader(delay=delay)
    html = downloader.fetch_html(url)
    if not html:
        emit_event("error", "❌ Không thể tải trang. Vui lòng kiểm tra lại URL hoặc kết nối mạng.")
        is_processing = False
        emit_event("done", "Đã dừng do lỗi tải trang.", {"status": "error"})
        return

    story_info = parser.get_story_info(html, url)
    translator = Translator(target_lang="en") if translate_en else None

    # Dịch tên truyện nếu được bật
    if translator and story_info.title:
        emit_event("info", "🌐 Đang dịch tên truyện sang tiếng Anh...")
        orig_title = story_info.title
        story_info.title = translator.translate_text(story_info.title)
        if story_info.title != orig_title:
            emit_event("success", f"🌐 Tên truyện tiếng Anh: {story_info.title}")

    emit_event("story_info", f"📚 Tên truyện: {story_info.title}", {
        "title": story_info.title,
        "slug": story_info.slug,
        "total_chapters": story_info.total_chapters,
        "base_url": story_info.base_url,
        "cover_image": story_info.cover_image,
        "parser_name": parser.get_name()
    })

    # Xử lý tổng số chapter
    if story_info.total_chapters == 0:
        emit_event("warning", "⚠ Không thấy số chapter, thử tải chapter-1...")
        ch1_url = parser.build_chapter_url(story_info.base_url, 1, story_info.is_single_page)
        ch1_html = downloader.fetch_html(ch1_url)
        if ch1_html:
            story_info = parser.get_story_info(ch1_html, ch1_url)
            emit_event("info", f"📄 Tổng số chapter xác định: {story_info.total_chapters}")

    total_chapters = story_info.total_chapters or 1
    start_ch = max(1, min(from_ch, total_chapters))
    end_ch = max(start_ch, min(to_ch, total_chapters)) if to_ch > 0 else total_chapters
    total_to_download = end_ch - start_ch + 1

    emit_event("info", f"📋 Sẽ xử lý chapter {start_ch} → {end_ch} ({total_to_download} chapters)")

    # Tạo thư mục output
    story_dir_name = sanitize_filename(story_info.slug)
    output_dir = os.path.join(APP_ROOT, "output", story_dir_name)
    images_dir_name = "images"
    images_dir = os.path.join(output_dir, images_dir_name)
    os.makedirs(output_dir, exist_ok=True)
    if download_img:
        os.makedirs(images_dir, exist_ok=True)

    chapters = []
    image_map = {}
    failed_chapters = []

    for idx, ch_num in enumerate(range(start_ch, end_ch + 1), 1):
        progress_pct = int((idx / total_to_download) * 100)
        emit_event("progress", f"📄 [{idx}/{total_to_download}] Đang tải Chapter {ch_num}...", {
            "current": idx,
            "total": total_to_download,
            "percent": progress_pct,
            "chapter": ch_num
        })

        ch_url = parser.build_chapter_url(story_info.base_url, ch_num, story_info.is_single_page)
        
        ch_html = getattr(parser, "get_cached_html", lambda u: None)(ch_url)
        if ch_html:
            emit_event("info", f"   ♻ Sử dụng cache từ lần quét cấu trúc")
        else:
            current_chapter_match = urlparse(url).path
            clean_ch_url = ch_url.split("?")[0].split("#")[0].rstrip("/")
            clean_init_url = url.split("?")[0].split("#")[0].rstrip("/")
            is_cached = (story_info.is_single_page and ch_num == 1) or (clean_ch_url == clean_init_url) or (f"/chapter-{ch_num}" in current_chapter_match)

            if is_cached and html:
                ch_html = html
                emit_event("info", f"   ♻ Sử dụng cache từ lần tải đầu")
            else:
                ch_html = downloader.fetch_html(ch_url)
                if ch_num < end_ch:
                    downloader.wait()

        if not ch_html:
            emit_event("error", f"   ❌ Thất bại khi tải Chapter {ch_num}")
            failed_chapters.append(ch_num)
            continue

        chapter = parser.parse_chapter(ch_html, ch_num)
        emit_event("info", f"   📝 Chapter {ch_num}: {len(chapter.paragraphs)} đoạn văn, {len(chapter.images)} ảnh")

        # Chuẩn hóa URLs ảnh
        for i_idx, img_u in enumerate(chapter.images):
            if not img_u.startswith("http"):
                chapter.images[i_idx] = urljoin(ch_url, img_u)
        for i, (etype, evalue) in enumerate(chapter.content_elements):
            if etype == "image" and not evalue.startswith("http"):
                chapter.content_elements[i] = ("image", urljoin(ch_url, evalue))

        # Tải hình ảnh
        if download_img and chapter.images:
            for i_idx, img_u in enumerate(chapter.images, 1):
                img_name = Downloader.get_image_filename(img_u, ch_num, i_idx)
                img_path = os.path.join(images_dir, img_name)
                if downloader.download_image(img_u, img_path):
                    image_map[img_u] = img_name

        # Dịch tiếng Anh
        if translator:
            emit_event("info", f"   🌐 Đang dịch Chapter {ch_num} sang tiếng Anh...")
            chapter = translator.translate_chapter(chapter)
            emit_event("success", f"   ✅ Tiêu đề EN: {chapter.title[:60]}...")

        # Lưu chapter dạng folder title.md + content.md
        ch_dir_name = save_chapter(chapter, output_dir)
        chapters.append(chapter)
        emit_event("success", f"   💾 Đã lưu local: {ch_dir_name}/ (title.md, content.md)")

    # Lưu full_story.md
    if chapters:
        save_full_story(chapters, story_info, output_dir)
        emit_event("info", "📝 Đã tạo file tổng hợp full_story.md")

    # Tải cover image
    if download_img and story_info.cover_image:
        cover_url = story_info.cover_image
        if not cover_url.startswith("http"):
            cover_url = urljoin(story_info.base_url, cover_url)
        cover_ext = os.path.splitext(urlparse(cover_url).path)[1] or ".webp"
        cover_path = os.path.join(output_dir, f"cover{cover_ext}")
        if downloader.download_image(cover_url, cover_path):
            emit_event("info", f"🖼️ Đã lưu ảnh cover: cover{cover_ext}")

    # Đăng bài lên CMS nếu có bật
    cms_posts = []
    if publish_cms and chapters:
        emit_event("info", f"🚀 Bắt đầu đăng lên CMS ({cms_url}) với user '{cms_user}' (Content mode: chapter)...")
        publisher = CMSPublisher(base_url=cms_url, username=cms_user, password=cms_pass)
        if publisher.login():
            emit_event("success", f"🔑 Đăng nhập CMS thành công (User: {cms_user})!")
            created = publisher.publish_story(story_info, chapters)
            if created:
                cms_posts = created
                emit_event("success", f"🎉 Đăng bài thành công ({len(created)} posts đã tạo trên CMS)!", {"cms_posts": created})
                for p in created:
                    emit_event("success", f"   📄 ID: {p.get('id')} | Tiêu đề: {p.get('title')}")
            else:
                emit_event("error", "❌ Lỗi đăng bài lên CMS.")
        else:
            emit_event("error", f"❌ Đăng nhập CMS thất bại cho user '{cms_user}'. Vui lòng kiểm tra lại URL hoặc mật khẩu.")

    is_processing = False
    emit_event("done", "🎉 Đã hoàn tất toàn bộ quy trình!", {
        "output_dir": os.path.abspath(output_dir),
        "total_chapters": len(chapters),
        "cms_posts": cms_posts,
        "story_title": story_info.title,
        "cover_image": story_info.cover_image
    })


@app.route("/api/test-cms", methods=["POST"])
def test_cms():
    """Kiểm tra kết nối và đăng nhập CMS"""
    data = request.json or {}
    cms_url = (data.get("cms_url") or "https://vmnewstoryus.cfx.bz").strip()
    cms_user = (data.get("cms_user") or "admin").strip()
    cms_pass = (data.get("cms_pass") or "").strip()

    if not cms_pass:
        return jsonify({"ok": False, "message": "Vui lòng nhập mật khẩu CMS"}), 400

    try:
        publisher = CMSPublisher(base_url=cms_url, username=cms_user, password=cms_pass)
        if publisher.login():
            return jsonify({
                "ok": True,
                "message": f"Kết nối & Đăng nhập thành công CMS với tài khoản '{cms_user}'!"
            })
        else:
            return jsonify({
                "ok": False,
                "message": f"Đăng nhập thất bại! Kiểm tra lại tài khoản '{cms_user}', mật khẩu hoặc CMS URL."
            }), 401
    except Exception as e:
        return jsonify({"ok": False, "message": f"Lỗi kết nối tới CMS: {str(e)}"}), 500


@app.route("/api/license-info")
def get_license_info():
    """Lấy thông tin trạng thái bản quyền hiện tại, mã máy và cấu hình Sheet"""
    admin = is_admin_mode()
    info = LicenseManager.check_current_license(is_admin_mode=admin)
    sheet_url = LicenseManager.get_sheet_url() if admin else ""
    sheet_web_url = LicenseManager.get_sheet_web_url() if admin else ""
    return jsonify({
        "ok": True,
        "is_admin": admin,
        "data": info,
        "sheet_url": sheet_url,
        "sheet_web_url": sheet_web_url
    })


@app.route("/api/config-sheet", methods=["POST"])
def config_sheet():
    """Cấu hình URL Google Sheets để quản lý bản quyền online (Chỉ dành cho Admin)"""
    if not is_admin_mode():
        return jsonify({"ok": False, "message": "Chức năng chỉ dành riêng cho Quản trị viên."}), 403
    data = request.json or {}
    sheet_url = (data.get("sheet_url") or "").strip()
    LicenseManager.set_sheet_url(sheet_url)
    info = LicenseManager.check_current_license(is_admin_mode=True)
    return jsonify({
        "ok": True,
        "message": "Đã lưu cấu hình Google Sheets thành công!",
        "data": info,
        "sheet_url": LicenseManager.get_sheet_url(),
        "sheet_web_url": LicenseManager.get_sheet_web_url()
    })


@app.route("/api/admin/generate-key", methods=["POST"])
def admin_generate_key():
    """Tạo License Key Offline dự phòng cấp cho khách (Chỉ dành cho Admin)"""
    if not is_admin_mode():
        return jsonify({"ok": False, "message": "Chức năng chỉ dành riêng cho Quản trị viên."}), 403
    data = request.json or {}
    user = (data.get("user") or "").strip()
    hwid = (data.get("hwid") or "").strip()
    days = int(data.get("days") or 30)
    if not user or not hwid:
        return jsonify({"ok": False, "message": "Vui lòng nhập Tên khách hàng và Mã máy (HWID)."}), 400
    try:
        from keygen import generate_key
        key, expire_date = generate_key(user, hwid, days)
        return jsonify({
            "ok": True,
            "message": "Đã tạo License Key thành công!",
            "key": key,
            "user": user,
            "hwid": hwid.upper(),
            "expires": expire_date,
            "days": days
        })
    except Exception as e:
        return jsonify({"ok": False, "message": f"Lỗi tạo key: {str(e)}"}), 500


@app.route("/api/admin/test-sheet", methods=["POST"])
def admin_test_sheet():
    """Kiểm tra kết nối và dữ liệu trả về từ Google Sheets (Chỉ dành cho Admin)"""
    if not is_admin_mode():
        return jsonify({"ok": False, "message": "Chức năng chỉ dành riêng cho Quản trị viên."}), 403
    data = request.json or {}
    sheet_url = (data.get("sheet_url") or "").strip()
    res = LicenseManager.check_online_sheet(sheet_url or None)
    return jsonify({
        "ok": True,
        "data": res
    })


@app.route("/api/check-update")
def check_update_route():
    """Kiểm tra xem có commit mới nào trên GitHub repo chính không"""
    repo = "Trantoan12022004/scan_story"
    branch = "main"

    # 1. Lấy SHA của commit hiện tại trên máy local
    local_sha = ""
    try:
        local_sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=APP_ROOT,
            stderr=subprocess.DEVNULL,
            timeout=5
        ).decode().strip()
    except Exception as e:
        return jsonify({
            "ok": False,
            "message": f"Không thể đọc mã commit git cục bộ: {str(e)}"
        })

    # 2. Truy vấn GitHub API lấy thông tin commit mới nhất trên branch main
    api_url = f"https://api.github.com/repos/{repo}/commits/{branch}"
    try:
        import requests
        resp = requests.get(
            api_url,
            headers={
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "ScanStory-App"
            },
            timeout=7
        )
        if resp.status_code != 200:
            return jsonify({
                "ok": False,
                "message": f"GitHub API trả về mã lỗi: {resp.status_code}"
            })

        commit_data = resp.json()
        remote_sha = commit_data.get("sha", "")
        commit_info = commit_data.get("commit", {})
        commit_msg = (commit_info.get("message") or "").split("\n")[0]
        commit_date = commit_info.get("author", {}).get("date", "")
        html_url = commit_data.get("html_url", "")

        has_update = (local_sha[:10].lower() != remote_sha[:10].lower())

        return jsonify({
            "ok": True,
            "has_update": has_update,
            "local_sha": local_sha[:7],
            "remote_sha": remote_sha[:7],
            "commit_message": commit_msg,
            "commit_date": commit_date,
            "html_url": html_url
        })
    except Exception as e:
        return jsonify({
            "ok": False,
            "message": f"Lỗi kết nối GitHub API: {str(e)}"
        })


@app.route("/api/perform-update", methods=["POST"])
def perform_update_route():
    """Thực hiện lệnh git pull origin main để tự động cập nhật mã nguồn mới nhất"""
    try:
        proc = subprocess.run(
            ["git", "pull", "origin", "main"],
            cwd=APP_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=40
        )
        output_text = proc.stdout.strip() if proc.stdout else ""
        if proc.returncode == 0:
            return jsonify({
                "ok": True,
                "message": f"Cập nhật thành công từ GitHub!\n{output_text}"
            })
        else:
            return jsonify({
                "ok": False,
                "message": f"Lỗi khi cập nhật (mã lỗi {proc.returncode}):\n{output_text}"
            }), 500
    except Exception as e:
        return jsonify({
            "ok": False,
            "message": f"Không thể thực hiện cập nhật: {str(e)}"
        }), 500


@app.route("/api/activate-license", methods=["POST"])
def activate_license():
    """Kích hoạt License Key do người dùng nhập"""
    data = request.json or {}
    key = (data.get("key") or "").strip()
    if not key:
        return jsonify({"ok": False, "message": "Vui lòng nhập License Key"}), 400

    res = LicenseManager.verify_key(key)
    if res.get("valid"):
        LicenseManager.save_license(key)
        return jsonify({
            "ok": True,
            "message": "Kích hoạt bản quyền thành công!",
            "data": res
        })
    else:
        return jsonify({
            "ok": False,
            "message": res.get("message", "Key không hợp lệ"),
            "data": res
        }), 400


@app.route("/api/start", methods=["POST"])
def start_process():
    global is_processing

    # Kiểm tra bản quyền trước khi cho phép chạy
    admin_mode = is_admin_mode()
    lic = LicenseManager.check_current_license(is_admin_mode=admin_mode)
    if not lic.get("valid"):
        return jsonify({
            "ok": False,
            "message": f"Lỗi bản quyền: {lic.get('message')}",
            "license_required": True,
            "hwid": lic.get("hwid")
        }), 403

    if is_processing:
        return jsonify({"ok": False, "message": "Đang có một tác vụ đang chạy. Vui lòng chờ!"}), 400

    data = request.json or {}
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"ok": False, "message": "Vui lòng nhập link URL truyện"}), 400

    threading.Thread(target=process_story_thread, args=(data,), daemon=True).start()
    return jsonify({"ok": True, "message": "Đã bắt đầu xử lý"})


@app.route("/api/history")
def get_history():
    """Lấy danh sách các truyện đã cào trong thư mục output"""
    output_base = os.path.join(APP_ROOT, "output")
    history = []
    if os.path.exists(output_base):
        for item in os.listdir(output_base):
            item_path = os.path.join(output_base, item)
            if os.path.isdir(item_path):
                # Đếm số chapter
                ch_dirs = [d for d in os.listdir(item_path) if d.startswith("chapter_") and os.path.isdir(os.path.join(item_path, d))]
                history.append({
                    "slug": item,
                    "path": os.path.abspath(item_path),
                    "chapters_count": len(ch_dirs),
                    "modified": os.path.getmtime(item_path)
                })
    history.sort(key=lambda x: x["modified"], reverse=True)
    return jsonify({"ok": True, "data": history[:15]})


def force_bring_window_foreground(class_filter=None, title_filter=None):
    """
    Đưa cửa sổ mong muốn (Windows Explorer, Media Player, Chrome) lên trước màn hình (Foreground),
    giải quyết triệt để vấn đề ứng dụng bị mở ngầm dưới trình duyệt.
    """
    if sys.platform != "win32":
        return

    def _bring():
        time.sleep(0.35)
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32

            # Tap phím Alt để bypass cơ chế ForegroundLockTimeout của Windows
            user32.keybd_event(0x12, 0, 0, 0)
            user32.keybd_event(0x12, 0, 2, 0)

            hwnds = []
            @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
            def enum_proc(hwnd, lparam):
                if user32.IsWindowVisible(hwnd):
                    c_buf = ctypes.create_unicode_buffer(256)
                    user32.GetClassNameW(hwnd, c_buf, 256)
                    cls = c_buf.value
                    t_buf = ctypes.create_unicode_buffer(256)
                    user32.GetWindowTextW(hwnd, t_buf, 256)
                    title = t_buf.value

                    match = True
                    if class_filter and class_filter.lower() not in cls.lower():
                        match = False
                    if title_filter and title_filter.lower() not in title.lower():
                        match = False
                    if match and (title or cls == "CabinetWClass"):
                        hwnds.append(hwnd)
                return True

            user32.EnumWindows(enum_proc, 0)

            if hwnds:
                target_hwnd = hwnds[0]
                fore_hwnd = user32.GetForegroundWindow()
                fore_tid = user32.GetWindowThreadProcessId(fore_hwnd, None)
                cur_tid = kernel32.GetCurrentThreadId()
                target_tid = user32.GetWindowThreadProcessId(target_hwnd, None)

                if fore_tid and cur_tid and fore_tid != cur_tid:
                    user32.AttachThreadInput(fore_tid, cur_tid, True)
                if target_tid and cur_tid and target_tid != cur_tid:
                    user32.AttachThreadInput(cur_tid, target_tid, True)

                user32.ShowWindow(target_hwnd, 9)  # SW_RESTORE
                user32.BringWindowToTop(target_hwnd)
                user32.SetForegroundWindow(target_hwnd)

                if fore_tid and cur_tid and fore_tid != cur_tid:
                    user32.AttachThreadInput(fore_tid, cur_tid, False)
                if target_tid and cur_tid and target_tid != cur_tid:
                    user32.AttachThreadInput(cur_tid, target_tid, False)
        except Exception:
            pass

    threading.Thread(target=_bring, daemon=True).start()


def resolve_video_path(req_path: str) -> str:
    """
    Tìm và chuẩn hóa đường dẫn file video một cách cực kỳ mạnh mẽ:
    - Sửa các lỗi escape backslash từ JS (ví dụ \t -> Tab, \v -> Vertical Tab, \3 -> Octal, C:\ bị mất).
    - Tự động quét tìm file trong thư mục output/videos theo mã ID video Facebook hoặc tên tương đồng.
    """
    if not req_path:
        return ""

    videos_dir = os.path.abspath(os.path.join(APP_ROOT, "output", "videos"))
    os.makedirs(videos_dir, exist_ok=True)

    # Chuẩn hóa về forward slash
    clean_path = req_path.replace("\\", "/").strip()

    # 1. Kiểm tra trực tiếp file có tồn tại
    if os.path.isfile(clean_path):
        return os.path.abspath(clean_path)

    # 2. Kiểm tra nếu ghép với APP_ROOT
    joined_root = os.path.abspath(os.path.join(APP_ROOT, clean_path.lstrip("/")))
    if os.path.isfile(joined_root):
        return joined_root

    # 3. Thử với basename trong videos_dir
    base_name = os.path.basename(clean_path)
    cand_base = os.path.join(videos_dir, base_name)
    if os.path.isfile(cand_base):
        return cand_base

    # 4. Tìm kiếm thông minh trong videos_dir nếu chuỗi bị lỗi parse từ JS
    try:
        existing_files = [f for f in os.listdir(videos_dir) if f.lower().endswith((".mp4", ".m4a", ".webm", ".mkv"))]
    except Exception:
        existing_files = []

    if not existing_files:
        return ""

    # 4a. Tìm theo mã số Facebook (chuỗi số dài >= 8 ký tự, ví dụ 1450514546921034)
    import re
    ids = re.findall(r"\d{8,}", clean_path)
    if ids:
        for vid_id in reversed(ids):
            for ef in existing_files:
                if vid_id in ef:
                    return os.path.join(videos_dir, ef)

    # 4b. Khớp một phần tên file (nếu tên file thật nằm trong clean_path hoặc ngược lại)
    for ef in existing_files:
        ef_stem = os.path.splitext(ef)[0]
        if len(ef_stem) > 10 and (ef_stem in clean_path or clean_path in ef):
            return os.path.join(videos_dir, ef)

    # 4c. Tìm theo từ khóa (chia tách theo ký tự đặc biệt)
    clean_no_ext = os.path.splitext(base_name)[0]
    keywords = [seg for seg in re.split(r"[^a-zA-Z0-9]", clean_no_ext) if len(seg) >= 4]
    if keywords:
        best_match = None
        best_score = 0
        for ef in existing_files:
            score = sum(1 for kw in keywords if kw.lower() in ef.lower())
            if score > best_score:
                best_score = score
                best_match = ef
        if best_match and best_score >= 2:
            return os.path.join(videos_dir, best_match)

    # Nếu chỉ có duy nhất 1 video trong thư mục
    if len(existing_files) == 1:
        return os.path.join(videos_dir, existing_files[0])

    return ""


@app.route("/api/open-folder", methods=["POST"])
def open_folder():
    """Mở thư mục trên Windows Explorer và đưa cửa sổ lên màn hình chính"""
    data = request.get_json(silent=True) or {}
    req_path = (data.get("path") or "").strip()

    # Nếu người dùng truyền đường dẫn tới một video hoặc chuỗi video bị lỗi ký tự
    resolved_file = resolve_video_path(req_path) if req_path else ""
    if resolved_file and os.path.isfile(resolved_file):
        norm_path = os.path.normpath(resolved_file)
        try:
            if sys.platform == "win32":
                subprocess.Popen(f'explorer.exe /select,"{norm_path}"')
                force_bring_window_foreground(class_filter="CabinetWClass")
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-R", norm_path])
            else:
                subprocess.Popen(["xdg-open", os.path.dirname(norm_path)])
            return jsonify({
                "ok": True,
                "path": norm_path.replace("\\", "/"),
                "message": f"Đã hiển thị video trong thư mục: {os.path.basename(norm_path)}"
            })
        except Exception as e:
            return jsonify({"ok": False, "message": f"Lỗi hiển thị file: {e}"}), 500

    # Nếu là thư mục
    if not req_path:
        target_path = os.path.abspath(os.path.join(APP_ROOT, "output", "videos"))
    elif os.path.isabs(req_path):
        target_path = os.path.abspath(req_path)
    else:
        target_path = os.path.abspath(os.path.join(APP_ROOT, req_path))

    norm_path = os.path.normpath(target_path)
    os.makedirs(norm_path, exist_ok=True)

    try:
        if sys.platform == "win32":
            subprocess.Popen(f'explorer.exe "{norm_path}"')
            force_bring_window_foreground(class_filter="CabinetWClass")
        elif sys.platform == "darwin":
            subprocess.Popen(["open", norm_path])
        else:
            subprocess.Popen(["xdg-open", norm_path])
        return jsonify({
            "ok": True,
            "path": norm_path.replace("\\", "/"),
            "message": "Đã mở thư mục thành công."
        })
    except Exception as e:
        return jsonify({"ok": False, "message": f"Lỗi khi mở thư mục: {e}"}), 500


@app.route("/api/open-file", methods=["POST"])
def open_file():
    """Mở video bằng ứng dụng mặc định trên máy tính (Windows Media Player, VLC, ...)"""
    data = request.get_json(silent=True) or {}
    req_path = (data.get("path") or "").strip()
    if not req_path:
        return jsonify({"ok": False, "message": "Đường dẫn file không hợp lệ."}), 400

    resolved = resolve_video_path(req_path)
    if not resolved or not os.path.isfile(resolved):
        return jsonify({"ok": False, "message": f"Không tìm thấy file video: {os.path.basename(req_path)}"}), 404

    norm_path = os.path.normpath(resolved)

    try:
        if sys.platform == "win32":
            try:
                os.startfile(norm_path)
            except Exception:
                subprocess.Popen(f'cmd.exe /c start "" "{norm_path}"', shell=True)
            force_bring_window_foreground()
        elif sys.platform == "darwin":
            subprocess.Popen(["open", norm_path])
        else:
            subprocess.Popen(["xdg-open", norm_path])
        return jsonify({
            "ok": True,
            "path": norm_path.replace("\\", "/"),
            "message": f"Đã mở file: {os.path.basename(norm_path)}"
        })
    except Exception as e:
        return jsonify({"ok": False, "message": f"Không thể mở file: {e}"}), 500


@app.route("/api/fb/probe", methods=["POST"])
def fb_probe():
    """Dò tìm các mức chất lượng của video Facebook"""
    data = request.get_json(silent=True) or {}
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"ok": False, "message": "Vui lòng nhập link video hoặc Reel Facebook."}), 400
    try:
        from fb_downloader import probe_facebook_video
        info = probe_facebook_video(url)
        return jsonify({"ok": True, "data": info})
    except Exception as e:
        return jsonify({"ok": False, "message": str(e)}), 500


@app.route("/api/fb/download", methods=["POST"])
def fb_download():
    """Tải video Facebook theo chất lượng đã chọn"""
    admin_mode = is_admin_mode()
    lic = LicenseManager.check_current_license(is_admin_mode=admin_mode)
    if not lic.get("valid"):
        return jsonify({
            "ok": False,
            "message": f"Lỗi bản quyền: {lic.get('message')}",
            "license_required": True
        }), 403

    data = request.get_json(silent=True) or {}
    url = data.get("url", "").strip()
    format_id = data.get("format_id", "best").strip()
    if not url:
        return jsonify({"ok": False, "message": "Vui lòng nhập link video Facebook."}), 400

    output_dir = os.path.join(APP_ROOT, "output", "videos")
    os.makedirs(output_dir, exist_ok=True)
    try:
        from fb_downloader import download_facebook_video
        res = download_facebook_video(url, format_id=format_id, output_dir=output_dir)
        # Thêm stream_url và absolute path
        file_name = res.get("file_name", "")
        res["stream_url"] = f"/api/fb/stream-video/{urllib.parse.quote(file_name)}"
        res["abs_path"] = os.path.abspath(os.path.join(output_dir, file_name)).replace("\\", "/")
        return jsonify({"ok": True, "data": res})
    except Exception as e:
        return jsonify({"ok": False, "message": str(e)}), 500


@app.route("/api/fb/stream-video/<path:filename>")
def fb_stream_video(filename):
    """Truyền luồng phát video cho HTML5 Video Player trên giao diện web (hỗ trợ HTTP Range để tua nhanh và xem trực tiếp)"""
    videos_dir = os.path.abspath(os.path.join(APP_ROOT, "output", "videos"))
    target_file = os.path.abspath(os.path.join(videos_dir, filename))
    if not target_file.startswith(videos_dir) or not os.path.isfile(target_file):
        return jsonify({"ok": False, "message": "Video không tồn tại"}), 404

    ext = os.path.splitext(filename)[1].lower()
    mimetypes = {
        ".mp4": "video/mp4",
        ".webm": "video/webm",
        ".mkv": "video/x-matroska",
        ".m4a": "audio/mp4",
        ".mp3": "audio/mpeg",
    }
    mimetype = mimetypes.get(ext, "video/mp4")
    return send_from_directory(videos_dir, filename, conditional=True, mimetype=mimetype)


@app.route("/api/fb/videos", methods=["GET"])
def fb_list_videos():
    """Lấy danh sách video Facebook đã tải gần đây"""
    videos_dir = os.path.join(APP_ROOT, "output", "videos")
    if not os.path.exists(videos_dir):
        return jsonify({"ok": True, "data": []})

    items = []
    for f in os.listdir(videos_dir):
        if f.endswith((".mp4", ".m4a", ".webm", ".mkv")):
            f_path = os.path.join(videos_dir, f)
            st = os.stat(f_path)
            size_mb = st.st_size / (1024 * 1024)
            items.append({
                "name": f,
                "size": f"{size_mb:.2f} MB",
                "modified": st.st_mtime,
                "path": os.path.abspath(f_path),
                "stream_url": f"/api/fb/stream-video/{urllib.parse.quote(f)}"
            })
    items.sort(key=lambda x: x["modified"], reverse=True)
    return jsonify({"ok": True, "data": items[:25]})


def start_server(port: int = 5000):
    admin = is_admin_mode()
    mode_name = "QUẢN TRỊ VIÊN (ADMIN)" if admin else "NGƯỜI DÙNG (USER)"
    url = f"http://localhost:{port}"
    print(f"\n{'=' * 65}")
    print(f"📖 STORY SCRAPER & CMS PUBLISHER - [{mode_name}]")
    print(f"{'=' * 65}")
    print(f"🚀 Server đang chạy tại: {url}")
    print(f"Nhấn Ctrl+C để dừng server.\n")
    # Tự động mở trình duyệt sau 1.2 giây
    threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    start_server()
