# 📖 Story Scraper - Tool Lấy Nội Dung & Hình Ảnh Truyện

Tool Python hỗ trợ tải nội dung truyện và toàn bộ hình ảnh minh họa từ nhiều trang web truyện, tự động chuyển đổi sang định dạng **Markdown** (.md) sạch sẽ kèm ảnh local.

---

> 🚀 **PHIÊN BẢN MỚI**: **Ứng Dụng Windows Desktop Native (Fluent Design + SQLite)** hiện đã có sẵn tại thư mục [`ban_win/`](ban_win/).
> - Khởi chạy 1-Click: Chạy file `ban_win\run.bat` hoặc `ban_win\run.vbs`.
> - Đóng gói EXE độc lập: Chạy `ban_win\build.bat`.
> - Xem chi tiết tài liệu tại: [`ban_win/README.md`](ban_win/README.md).

---

## 🌟 Tính năng nổi bật

- **Tự động nhận diện trang web**: Tự phát hiện CMS/template dựa vào URL truyện.
- **Lấy trọn vẹn văn bản & hình ảnh**:
  - Trích xuất toàn bộ đoạn văn, tiêu đề từng chương, trích dẫn.
  - Tải tất cả hình ảnh minh họa trong chương về thư mục `images/`.
  - Tự động thay thế link ảnh trong Markdown thành đường dẫn ảnh nội bộ (`images/chapter-XX-img-YY.ext`).
  - Tải ảnh bìa truyện (`cover.webp` / `cover.jpg`).
- **Tự động dịch sang tiếng Anh**: Toàn bộ từ tên truyện, tiêu đề chapter đến nội dung đều được tự động dịch sang tiếng Anh (sử dụng `--no-translate` nếu muốn giữ nguyên bản gốc).
- **Tự động đăng lên CMS BlogBio (`--publish` hoặc `publish.py`)**: Tự động đăng nhập, điền Featured image URL, tạo bài viết dạng **Content mode: chapter**, tự động tạo đủ số chapter kèm ảnh cover chung ở đầu description và liên kết điều hướng Next/Prev.
- **Xuất file linh hoạt**:
  - Thư mục chapter riêng biệt: `chapter_01/title.md`, `chapter_01/content.md` (nội dung thuần text không chứa ảnh).
  - File tổng hợp toàn bộ câu chuyện: `full_story.md`.
- **Tùy chọn phong phú**:
  - Tải toàn bộ truyện hoặc tải theo khoảng chương (`--from X --to Y`).
  - Tùy chỉnh thư mục xuất (`--output path`).
  - Tùy chỉnh khoảng dừng giữa các request (`--delay seconds`) chống chặn IP.
  - Tùy chọn chỉ lấy chữ, bỏ qua ảnh (`--no-images`).
  - Tự động đăng lên CMS (`--publish` hoặc `python publish.py <url>`).
- **Tải Video & Reels Facebook Đa Chất Lượng**: Dò tìm và tải video từ link Facebook Reel hoặc Facebook Video với đầy đủ các mức chất lượng (1080p Full HD, 720p HD, SD, Audio M4A), tự động gộp âm thanh và hình ảnh qua `ffmpeg`.
- **Thiết kế dạng Module (Plugin-based)**: Dễ dàng mở rộng thêm parser cho các website truyện mới chỉ bằng cách kế thừa `BaseParser`.

---

## 🚀 Hướng dẫn sử dụng

### 1. Khởi động Web UI (Giao diện đồ họa trực quan)
Chỉ cần chạy lệnh sau, trình duyệt sẽ tự động mở giao diện điều khiển:
```bash
python app.py
```
👉 Truy cập: `http://localhost:5000`
- Tab **📖 Cào & Đăng Truyện**: Quét, dịch tiếng Anh và đăng truyện lên CMS.
- Tab **🎬 Tải Reels & Video Facebook**: Dán link Facebook Reel/Video, quét chất lượng và tải nhanh về máy.

---

### 2. Tải Video Reels / Facebook qua dòng lệnh (CLI)
```bash
# Phân tích các mức chất lượng và tự động tải chất lượng cao nhất:
python fb_downloader.py "https://www.facebook.com/reel/1142203028130644"

# Tải định dạng cụ thể (best, hd, sd, bestaudio):
python fb_downloader.py "https://www.facebook.com/reel/1142203028130644" hd
```
File video sẽ được lưu tự động vào thư mục: `output/videos/`.

---

### 3. Cào truyện qua dòng lệnh (CLI)

#### Tải truyện, dịch tiếng Anh và tự động đăng lên CMS:
```bash
python publish.py "https://sad.treeiq.biz/blog/story-slug/chapter-1"
```
hoặc với tài khoản CMS tùy chỉnh:
```bash
python main.py "https://sad.treeiq.biz/blog/story-slug/chapter-1" --publish --cms-url "https://your-cms.com" --cms-user "your_email" --cms-pass "your_password"
```

#### Chỉ tải truyện về máy (mặc định tự dịch tiếng Anh, không đăng CMS):
```bash
python main.py "https://intelligence.treeiq.biz/blog/story-slug"
```

#### Tải truyện giữ nguyên ngôn ngữ gốc (không dịch):
```bash
python main.py "https://intelligence.treeiq.biz/blog/story-slug" --no-translate
```

#### Tải theo khoảng chapter cụ thể:
```bash
python main.py "https://sad.treeiq.biz/blog/story-slug/chapter-1" --from 1 --to 5
```


---

## 📁 Cấu trúc thư mục Output

```
output/
└── <story-slug>/
    ├── cover.webp                   # Ảnh bìa truyện
    ├── chapter_01/
    │   ├── title.md                 # Tiêu đề chapter 1 (thuần text)
    │   └── content.md               # Nội dung chapter 1 (thuần text, không có ảnh)
    ├── chapter_02/
    │   ├── title.md
    │   └── content.md
    ├── ...
    ├── full_story.md                # File tổng hợp toàn bộ các chapter đã tải
    └── images/                      # Thư mục chứa toàn bộ hình ảnh tải về
```

---

## 🛠️ Cấu trúc mã nguồn

```
scan_story/
├── main.py                  # CLI điều khiển chính, điều phối tải, xuất Markdown, gọi CMS
├── publish.py               # Shortcut tự động tải và đăng thẳng lên CMS
├── publisher.py             # Quản lý xác thực và đăng bài REST API CMS BlogBio
├── translator.py            # Tự động dịch tiêu đề và nội dung sang tiếng Anh
├── downloader.py            # Quản lý HTTP session, User-Agent, tải HTML & ảnh, retry
├── parsers/
│   ├── base.py              # Interface BaseParser chung
│   ├── treeiq.py            # Parser TreeIQ CMS (hỗ trợ cả multi-chapter và single-page)
│   └── ahcms.py             # Parser AH CMS Script
└── output/                  # Thư mục lưu kết quả mặc định
```

---

## 🔑 Quản lý Bản quyền & Cấp Key theo tháng

Hệ thống bảo mật sử dụng cơ chế **khóa theo Mã Máy (Hardware ID / HWID)** và **thời hạn ngày sử dụng**:

### 1. Dành cho Admin

> ⚠️ **LƯU Ý:** File `keygen.py` chỉ admin giữ, **KHÔNG** gửi file này khi chia sẻ tool cho người khác!

#### A. Tự kích hoạt quyền Admin cho chính máy tính này (Hạn 10 năm):
Chỉ cần chạy lệnh 1 chạm:
```bash
python keygen.py --self
```
Hoặc tùy chỉnh tên Admin:
```bash
python keygen.py --self -u "TenCuaBan"
```
Tool sẽ tự động nhận diện mã máy hiện tại và kích hoạt sẵn vào file `.license` (hạn dùng 10 năm).

#### B. Cấp License Key cho người dùng khác (theo tháng):
Khi người dùng gửi mã máy (HWID) cho bạn, chạy lệnh sau để tạo License Key:
```bash
# Cấp 30 ngày (1 tháng)
python keygen.py -u "TenNguoiDung" -m "E423-C46C-6B90" -d 30

# Cấp 60 ngày (2 tháng)
python keygen.py -u "TenNguoiDung" -m "920E-2DA4-DAC5" -d 60
```
Sau đó copy chuỗi `KEY` được tạo gửi cho người dùng.

---

### 2. Dành cho Người dùng (Kích hoạt tool)
- **Cách 1 (Trên Web UI)**: Mở `http://localhost:5000` -> Bấm vào huy hiệu Bản quyền ở góc trên -> Dán Key vào và bấm **Kích hoạt**.
- **Cách 2 (Trên dòng lệnh CLI)**:
  ```bash
  python main.py "<story_url>" --license-key "<KEY_DO_ADMIN_CAP>"
  ```
- **Cách 3**: Lưu trực tiếp chuỗi key vào file `.license` trong thư mục tool.

---

## 📦 Đóng gói File EXE cho Người dùng (Không cần cài Python)

Hệ thống hỗ trợ đóng gói thành 2 phiên bản độc lập hoàn toàn bằng PyInstaller:
* 👉 **`dist/StoryScraper_User.exe`**: Bản dành riêng cho Khách hàng (giao diện User, không có công cụ sinh key).
* 👉 **`dist/StoryScraper_Admin.exe`**: Bản Quản trị viên (giao diện Admin, tích hợp sẵn công cụ sinh keygen và kích hoạt).

---

### 1. Hướng dẫn Build lại file EXE

#### Cách 1: Sử dụng công cụ tương tác 1 chạm (Khuyên dùng)
Click đúp chuột vào file:
👉 **`build_exe.bat`**
- Nhập **`1`**: Build **cả 2 phiên bản** (User & Admin).
- Nhập **`2`**: Chỉ build bản **User** (gửi cho khách hàng).
- Nhập **`3`**: Chỉ build bản **Admin** (dành riêng cho bạn).

#### Cách 2: Chạy trực tiếp qua dòng lệnh Terminal
```bash
# Build cả 2 phiên bản (User & Admin):
python build.py --target all

# Hoặc chỉ build bản User:
python build.py --target user

# Hoặc chỉ build bản Admin:
python build.py --target admin
```
*File sau khi build xong sẽ nằm tại thư mục `dist/`.*

---

### 2. Cách gửi file cho người dùng
1. Bạn chỉ cần copy file **`dist/StoryScraper_User.exe`** gửi cho khách hàng (qua Zalo, Telegram, Google Drive,...).
2. Khách hàng nhận file chỉ cần **click đúp vào file EXE** để sử dụng (tự động khởi động máy chủ và tự mở trình duyệt web).
3. Khi khách mở lần đầu:
   - Tool sẽ báo chưa kích hoạt và hiển thị **Mã máy (HWID)**.
   - Khách copy mã máy gửi cho bạn.
   - Bạn dùng bản Admin hoặc lệnh `python keygen.py -u "TenKhach" -m "HWID" -d 30` để tạo key cấp cho khách.
   - Khi kích hoạt xong, file `.license` sẽ được tạo và ghi nhớ vĩnh viễn trên máy khách.

---

## 🔄 Hướng Dẫn Cập Nhật & Phát Hành Phiên Bản Mới (Auto-Update)

Hệ thống tích hợp cơ chế **tự động kiểm tra bản mới và cập nhật 1-Click từ GitHub Releases**:
Khi có bản cập nhật mới, giao diện Web và ứng dụng EXE của khách sẽ tự động hiện thông báo kèm nút **⚡ Cập nhật ngay**. Khách bấm vào, tool sẽ tự tải bản mới ngầm, tự thay thế file EXE cũ và khởi động lại sau 2 giây.

### Quy trình 4 bước dành cho Admin để phát hành phiên bản mới:

#### 🔹 Bước 1: Nâng số phiên bản trong `version.json`
Mở file [version.json](file:///c:/Users/Trant/Documents/tools/scan_story/version.json) và tăng số version (ví dụ từ `2.0.7` lên `2.0.8`):
```json
{
  "version": "2.0.8",
  "release_date": "2026-10-04",
  "changelog": "Tối ưu giao diện, cập nhật tính năng mới...",
  "download_url_user": "https://github.com/Trantoan12022004/scan_story/releases/download/v2.0.8/StoryScraper_User.exe",
  "download_url_admin": "https://github.com/Trantoan12022004/scan_story/releases/download/v2.0.8/StoryScraper_Admin.exe"
}
```

#### 🔹 Bước 2: Build lại 2 file EXE mới
Chạy `build_exe.bat` (chọn số 1) hoặc chạy lệnh:
```bash
python build.py --target all
```
Sau bước này, bạn sẽ có 2 file EXE mới nhất trong thư mục `dist/`.

#### 🔹 Bước 3: Commit và Push mã nguồn lên GitHub
Đẩy toàn bộ code mới và file `version.json` vừa sửa lên nhánh `main` của repository GitHub:
```bash
git add .
git commit -m "Phát hành bản cập nhật v2.0.8"
git push origin main
```

#### 🔹 Bước 4: Tạo Release trên GitHub và đính kèm file EXE
1. Truy cập trang tạo Release mới trên GitHub:
   👉 **`https://github.com/Trantoan12022004/scan_story/releases/new`**
2. **Choose a tag**: Nhập tên tag đúng với version (ví dụ: `v2.0.8`) -> Bấm *Create new tag*.
3. **Release title**: Đặt tiêu đề (ví dụ: `Bản cập nhật v2.0.8`).
4. **Description**: Ghi các tính năng mới hoặc nội dung changelog.
5. **Attach binaries by dropping them here**: Kéo thả 2 file sau trong thư mục `dist/` vào:
   - `dist/StoryScraper_User.exe`
   - `dist/StoryScraper_Admin.exe`
6. Bấm nút **Publish release**.

---
🎉 **Hoàn tất!** Ngay sau khi bấm *Publish release*, bất kỳ khách hàng nào đang mở phiên bản cũ sẽ nhận được thông báo cập nhật lên bản mới và có thể nâng cấp chỉ với 1 cú click chuột.
