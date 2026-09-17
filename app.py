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
from urllib.parse import urlparse, urljoin
from flask import Flask, render_template, request, Response, jsonify

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


@app.route("/")
def index():
    return render_template("index.html")


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
    cms_pass = (params.get("cms_pass") or "Vnpt@123").strip()

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
        "cover_image": story_info.cover_image
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
        current_chapter_match = urlparse(url).path
        is_cached = (story_info.is_single_page and ch_num == 1) or (f"/chapter-{ch_num}" in current_chapter_match)

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
    """Lấy thông tin trạng thái bản quyền hiện tại và mã máy"""
    info = LicenseManager.check_current_license()
    return jsonify({"ok": True, "data": info})


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
    lic = LicenseManager.check_current_license()
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


@app.route("/api/open-folder", methods=["POST"])
def open_folder():
    """Mở thư mục trên Windows Explorer"""
    data = request.json or {}
    folder_path = data.get("path") or os.path.abspath(os.path.join(APP_ROOT, "output"))
    if os.path.exists(folder_path):
        if sys.platform == "win32":
            os.startfile(folder_path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", folder_path])
        else:
            subprocess.Popen(["xdg-open", folder_path])
        return jsonify({"ok": True})
    return jsonify({"ok": False, "message": "Thư mục không tồn tại"}), 404


if __name__ == "__main__":
    port = 5000
    url = f"http://localhost:{port}"
    print(f"\n{'=' * 60}")
    print(f"📖 STORY SCRAPER & CMS PUBLISHER - WEB UI")
    print(f"{'=' * 60}")
    print(f"🚀 Server đang chạy tại: {url}")
    print(f"Nhấn Ctrl+C để dừng server.\n")
    # Tự động mở trình duyệt sau 1 giây
    threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    app.run(host="0.0.0.0", port=port, debug=False)
