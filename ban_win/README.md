# 🖥️ Scan Story & Video Studio Pro — Phiên Bản Windows Desktop Native

Ứng dụng máy tính (Desktop App) hoàn chỉnh chuẩn Windows 11 Fluent Design, chạy cục bộ 100% không phụ thuộc trình duyệt web, lưu trữ dữ liệu tốc độ cao bằng **SQLite 3**, tích hợp đầy đủ mọi tính năng của phiên bản Web Flask.

---

## 🌟 ĐẶC ĐIỂM NỔI BẬT

1. **Giao diện chuẩn Fluent Design Windows 11**:
   - Tối ưu giao diện **Sáng (Light Mode)** hiện đại, bo góc 12px, shadow mềm, font Segoe UI / Inter sắc nét.
   - 6 Tab điều hướng Sidebar thông minh: *Quản Lý Video*, *Tải Video FB*, *Gemini AI Video*, *Cào Truyện & CMS*, *Bản Quyền HWID*, *Cài Đặt*.
   - Stat Cards thống kê tương tác lọc 1-click.
   - Bảng 11 cột định dạng **1 dòng duy nhất**, badge trạng thái đa màu sắc, popup chỉnh sửa và xem chi tiết tức thì.
2. **Cơ sở dữ liệu SQLite Local (WAL Mode)**:
   - Sử dụng file database nhúng `data/app.db` với chế độ Write-Ahead Logging (WAL) cực nhanh, an toàn đa luồng.
   - Không lo xung đột file JSON, xử lý mượt mà hàng chục nghìn dòng dữ liệu.
3. **✨ Nhúng Trực Tiếp Google Gemini AI & Quản Lý Prompt**:
   - Tích hợp trình duyệt Chromium nhúng (`QWebEngineView`) mở trực tiếp `https://gemini.google.com/app` ngay trong app, không bị lỗi chặn iframe.
   - **Video Context Card**: Tự động hiển thị video đang làm việc, 1-click chép đường dẫn file video, mở thư mục chứa video.
   - **Soạn thảo & Quản lý Prompt chuẩn Cinematic**: Tự động chèn đường dẫn video vào đầu prompt, đếm ký tự & số từ realtime, lưu mẫu vào SQLite.
   - Nút chuyển nhanh: Bấm **✨ Sang Tab Gemini Phân Tích** từ Tab Tải Video hoặc Menu chuột phải ở Bảng Quản Lý để tự động nạp video sang Gemini.
4. **Đồng bộ Google Sheets 2 chiều Realtime**:
   - Tự động kiểm tra thay đổi qua MD5 hash mỗi 3 giây (Background QThread).
   - Bảo vệ chống xung đột dữ liệu: các dòng chỉnh sửa cục bộ trong vòng 25 giây được ưu tiên bảo toàn.
   - Nút đẩy trực tiếp 11 cột lên Google Sheets qua Apps Script Webhook.
5. **Tự động ghép Content & trích xuất Frame**:
   - Tự động nhận diện khi có link báo mới (`bao_moi`) và ghép với caption bài gốc Facebook Reel.
   - Trích xuất frame đầu tiên bằng FFmpeg cực nhanh (0.04s) hoặc bóc tách ảnh bìa Facebook Reel.
   - Xem trước phóng to ảnh frame trực tiếp trong ứng dụng.
6. **Cào & Tải Video Facebook Đa Chất Lượng**:
   - Phân tích link Facebook Reels/Video: Full HD (1080p), HD (720p), SD (480p), Tách âm thanh MP3.
   - Thanh tiến trình tải phần trăm và dung lượng trực quan.
   - Trình phát video nhúng xem lại tức thì.
7. **Cào Truyện & Tự Động Đăng CMS BlogBio (Chuẩn 100% Web Logic)**:
   - Tự động nhận diện cấu trúc trang web truyện (TreeIQ, AHCMS, Universal Parser cho mọi website).
   - Tải hình ảnh, dịch tự động sang tiếng Anh, lưu từng chapter `title.md` + `content.md` và file tổng hợp `full_story.md`.
   - Đăng bài tự động lên CMS BlogBio qua REST API (hỗ trợ tách PART, tạo Next/Prev chapter link).
   - Console terminal xem log trực tiếp theo thời gian thực (Real-time).
8. **Bản Quyền Phần Mềm (HWID)**:
   - Tự động nhận diện mã máy duy nhất (Hardware ID).
   - Xác thực bản quyền Online qua Google Sheets hoặc Offline qua License Key mã hóa HMAC-SHA256.
   - Tích hợp công cụ Admin tạo key cho khách hàng (7 ngày, 30 ngày, 1 năm, vĩnh viễn).

---

## 🚀 HƯỚNG DẪN KHỞI CHẠY NHANH

### Cách 1: Chạy 1-Click (Khuyên dùng)
- **Nhấp đúp chuột vào file `run.bat`**: Khởi chạy ứng dụng kèm cửa sổ log.
- Hoặc **nhấp đúp chuột vào file `run.vbs`**: Khởi chạy ứng dụng ngầm êm ái, **không hiện cửa sổ cmd đen**.

### Cách 2: Chạy bằng lệnh Terminal
```bash
# Cài đặt thư viện nếu chưa có
pip install -r ban_win/requirements.txt

# Khởi chạy ứng dụng
python -m ban_win.main
```

---

## 📦 HƯỚNG DẪN ĐÓNG GÓI THÀNH FILE EXE ĐỘC LẬP

Để tạo 1 file `.exe` duy nhất gửi cho khách hàng hoặc chuyển sang máy khác chạy không cần cài Python:

### Cách 1: Dùng file `build.bat`
- Nhấp đúp chuột vào file **`ban_win/build.bat`**.
- Đợi 1-2 phút, file thực thi sẽ được xuất ra tại thư mục: **`ban_win/dist/ScanStoryStudio.exe`**.

### Cách 2: Dùng lệnh Python
```bash
python ban_win/build.py
```

> **Lưu ý**: Bản build đã tự động loại trừ xung đột giữa `PySide6` và `PyQt5`, nhúng sẵn icon và toàn bộ tài nguyên cần thiết.

---

## 📁 CẤU TRÚC THƯ MỤC CHI TIẾT

```
ban_win/
├── main.py                     # Entry point chính của ứng dụng
├── requirements.txt            # Danh sách thư viện phụ thuộc
├── run.bat                     # File khởi chạy 1-click
├── run.vbs                     # File khởi chạy êm (không hiện console)
├── build.py                    # Script đóng gói EXE bằng PyInstaller
├── build.bat                   # File đóng gói 1-click
│
├── core/                       # Lõi xử lý nghiệp vụ & truy xuất dữ liệu
│   ├── database.py             # SQLite WAL engine & CRUD
│   ├── models.py               # Data models
│   ├── config.py               # Quản lý cài đặt cấu hình
│   ├── video_checker.py        # Kiểm tra file video trên ổ cứng
│   ├── content_generator.py    # Tự động tạo & ghép Content báo mới
│   ├── frame_extractor.py      # Trích xuất frame đầu tiên
│   ├── sheets_sync.py          # Đồng bộ 2 chiều Google Sheets
│   ├── fb_downloader.py        # Bóc tách & tải video Facebook
│   ├── story_scraper.py        # Cào truyện & đăng bài CMS
│   ├── license_manager.py      # Bản quyền HWID & offline key
│   └── updater.py              # Kiểm tra cập nhật từ GitHub
│
├── ui/                         # Giao diện đồ họa Fluent Design
│   ├── main_window.py          # Cửa sổ chính SplitFluentWindow + 5 Tabs
│   ├── quan_ly/                # Module Quản Lý Tiến Độ (Bảng 11 cột, Stat cards, Badges)
│   ├── downloader/             # Module Tải Video FB (Probe, Player, Lịch sử)
│   ├── scraper/                # Module Cào Truyện & CMS (Console log, Cấu hình CMS)
│   ├── license/                # Module Bản Quyền HWID & Tạo Key
│   ├── settings/               # Module Cài Đặt & Prompt AI
│   └── widgets/                # Widget dùng chung (Toast InfoBar)
│
├── workers/                    # Các luồng chạy ngầm (QThread đa nhiệm)
│   ├── sync_worker.py          # Đồng bộ Google Sheets ngầm mỗi 3s
│   ├── download_worker.py      # Tải video ngầm kèm tiến trình %
│   ├── scraper_worker.py       # Cào truyện ngầm kèm log realtime
│   ├── frame_worker.py         # Trích xuất frame hàng loạt
│   ├── content_worker.py       # Ghép content báo mới hàng loạt
│   └── update_worker.py        # Kiểm tra bản mới trên GitHub
│
├── assets/                     # Tài nguyên hình ảnh & icon
│   └── app_icon.ico            # Icon ứng dụng chuẩn đa kích thước
│
├── data/                       # Dữ liệu cục bộ
│   ├── app.db                  # File SQLite chính (chạy local độc lập)
│   └── frames/                 # Thư mục lưu ảnh frame đầu tiên
│
└── parsers/                    # Bộ parser cào truyện
```
