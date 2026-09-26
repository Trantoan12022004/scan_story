# 📖 Story Scraper - Tool Lấy Nội Dung & Hình Ảnh Truyện

Tool Python hỗ trợ tải nội dung truyện và toàn bộ hình ảnh minh họa từ nhiều trang web truyện, tự động chuyển đổi sang định dạng **Markdown** (.md) sạch sẽ kèm ảnh local.

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
python keygen.py --self -u "anhtonton"
```
Tool sẽ tự động nhận diện mã máy hiện tại và kích hoạt sẵn vào file `.license` (hạn dùng 10 năm).

### 1. Quản lý Bản quyền Online qua Google Sheets (Khuyên dùng)
Admin không cần tạo key thủ công hay gửi mã cho từng máy nữa:
1. **Thiết lập bảng tính Google Sheets:**
   - Dòng 1 đặt 4 cột: `Mã máy (HWID)` | `Tên khách` | `Ngày hết hạn` | `Trạng thái`
   - Nhập thông tin khách hàng, ví dụ:
     - `3FD0-DB7D-FA39` | `Toàn Admin` | `2026-12-31` *(hoặc `Vĩnh viễn`)* | `Active`
     - Khi muốn khóa máy nào, chỉ cần đổi trạng thái sang `Block`.
2. **Lấy link xuất bản CSV:**
   - Trên Google Sheets: Vào menu **Tệp (File)** > **Chia sẻ (Share)** > **Xuất bản lên web (Publish to the web)**.
   - Tại ô **Web page**, chuyển sang chọn **`Comma-separated values (.csv)`**.
   - Bấm nút **Publish** > Bấm **OK** xác nhận.
   - Sao chép đường link xuất hiện.
3. **Cấu hình vào Tool:**
   - Trên giao diện Web: Bấm vào huy hiệu **Bản quyền** ở góc trên > Mở mục **⚙ Cấu hình Google Sheets (Dành cho Admin)** > Dán link vào và bấm **Lưu URL Google Sheet**.
   - Phía người dùng chỉ cần mở tool hoặc bấm **⚡ Kiểm tra kích hoạt online** là máy tự động kích hoạt tức thì.

---

### 2. Tự động Cập nhật 1-Click Cho File EXE & Mã Nguồn
- **Đối với người dùng file `.exe` (`StoryScraper_User.exe`)**:
  - Ứng dụng tự động kiểm tra phiên bản mới từ GitHub (`version.json`).
  - Khi bạn phát hành phiên bản mới (ví dụ: `v2.0.1`), trên giao diện người dùng sẽ hiện thông báo nổi bật kèm mô tả thay đổi.
  - Người dùng chỉ cần bấm **⚡ Cập nhật ngay**:
    1. Tool tự động tải file `.exe` mới về ngầm.
    2. Tự động thay thế file `.exe` cũ và khởi động lại phiên bản mới trong vòng 2 giây mà không bị khóa file Windows.
- **Đối với người chạy mã nguồn Python**:
  - Tool tự động kiểm tra commit Git và chạy lệnh `git pull origin main` khi bấm cập nhật.
- **Quy trình Admin phát hành bản mới**:
  1. Chạy `python build.py --target user` hoặc click `build_exe.bat` để build file `StoryScraper_User.exe`.
  2. Tạo **Release** mới trên GitHub (ví dụ: tag `v2.0.1`) và đính kèm file `StoryScraper_User.exe`.
  3. Cập nhật số phiên bản trong file `version.json` và `git push`. Toàn bộ khách hàng sẽ tự động nhận được thông báo cập nhật!

---

### 3. Cấp License Key Offline (Dự phòng cho máy không có mạng)
- Admin dùng lệnh: `python keygen.py -u "TenKhach" -m "HWID" -d 30`
- Người dùng dán key vào mục **Kích hoạt Key offline dự phòng** trong Modal bản quyền.

---

## 📦 Đóng gói 2 Phiên Bản File EXE Độc Lập

Hệ thống hỗ trợ đóng gói ra 2 phiên bản chuyên biệt độc lập:
1. 👉 **`dist/StoryScraper_User.exe`** (Dành cho Khách hàng):
   - Giao diện sạch sẽ, giấu kín toàn bộ cấu hình Admin và URL Google Sheets.
   - Nhúng sẵn Google Sheets quản lý bản quyền, khách chỉ cần sao chép mã máy (HWID) gửi cho Admin và bấm **⚡ Kiểm tra kích hoạt online**.
   - Khóa toàn bộ tính năng cào truyện & tải video nếu chưa được Admin duyệt trên Sheets.
2. 👉 **`dist/StoryScraper_Admin.exe`** (Dành riêng cho Quản trị viên):
   - Toàn quyền truy cập vĩnh viễn (SuperAdmin).
   - Nút mở trực tiếp Google Sheets quản trị để thêm/sửa khách hàng.
   - Panel cấu hình URL Google Sheets & nút kiểm tra kết nối Sheets.
   - Tích hợp công cụ tạo License Key Offline trực tiếp trên Web UI.

### Cách build file EXE:
- **Cách 1 (Khuyên dùng)**: Click đúp vào file **`build_exe.bat`** để chọn phiên bản cần build (Phím 1: Cả 2 bản, Phím 2: Bản User, Phím 3: Bản Admin).
- **Cách 2**: Chạy lệnh terminal:
  ```bash
  # Build cả 2 phiên bản cùng lúc:
  python build.py --target all

  # Hoặc chỉ build bản User gửi khách hàng:
  python build.py --target user

  # Hoặc chỉ build bản Admin:
  python build.py --target admin
  ```

---

# 📖 CẨM NANG HƯỚNG DẪN SỬ DỤNG & QUY TRÌNH CẬP NHẬT (ADMIN & USER)

Hệ thống hỗ trợ 2 môi trường vận hành: **Mã nguồn Python (Terminal)** và **File thực thi đóng gói (.exe)**.

---

## 👑 PHẦN I: DÀNH CHO ADMIN (QUẢN TRỊ VIÊN)

### 1. Khởi động ứng dụng chế độ Admin

* **Chạy bằng Terminal (Mã nguồn Python)**:
  ```bash
  # Cách 1: Chạy qua cờ --admin
  python app.py --admin

  # Cách 2: Chạy qua file entry chuyên dụng
  python entry_admin.py
  ```
  👉 Server chạy tại `http://localhost:5000` với huy hiệu **👑 QUẢN TRỊ VIÊN (ADMIN)**, mở khóa toàn bộ tính năng và cấu hình Google Sheets.

* **Chạy bằng File EXE**:
  - Nhấp đúp vào file `dist/StoryScraper_Admin.exe`.
  - Được tích hợp sẵn bản quyền SuperAdmin vĩnh viễn, không cần kích hoạt.
  - Tích hợp nút **📊 Bảng Tính Bản Quyền** trên thanh tiêu đề mở trực tiếp Google Sheets quản trị.

---

### 2. Quy trình phát hành bản cập nhật mới cho người dùng

Khi Admin có code mới hoặc nâng cấp giao diện, thực hiện theo 4 bước sau:

* **Bước 1: Đóng gói lại file `.exe` cho khách hàng**:
  ```bash
  # Trên terminal:
  python build.py --target user
  # Hoặc nhấp đúp file build_exe.bat và chọn phím 2
  ```
  File mới tạo sẽ nằm tại `dist/StoryScraper_User.exe`.

* **Bước 2: Cập nhật số phiên bản vào `version.json`**:
  Chỉnh sửa file `version.json` với số version mới và mô tả cập nhật:
  ```json
  {
    "version": "2.0.1",
    "release_date": "2026-09-27",
    "changelog": "Thêm tính năng cào truyện nâng cao và tối ưu tốc độ tải video",
    "download_url_user": "https://github.com/Trantoan12022004/scan_story/releases/latest/download/StoryScraper_User.exe",
    "download_url_admin": "https://github.com/Trantoan12022004/scan_story/releases/latest/download/StoryScraper_Admin.exe"
  }
  ```

* **Bước 3: Đẩy mã nguồn lên GitHub**:
  ```bash
  git add .
  git commit -m "Phát hành bản v2.0.1"
  git push origin main
  ```

* **Bước 4: Đính kèm file EXE vào GitHub Releases**:
  1. Vào kho GitHub: `https://github.com/Trantoan12022004/scan_story/releases`
  2. Bấm **Draft a new release**, đặt tag `v2.0.1`.
  3. Kéo thả file `dist/StoryScraper_User.exe` vào mục đính kèm tệp (Assets).
  4. Bấm **Publish release**.

  🎉 **Ngay lập tức**: Tất cả người dùng đang mở `StoryScraper_User.exe` sẽ nhìn thấy banner thông báo có bản cập nhật mới và có thể bấm cập nhật tự động 1-click!

---

### 3. Quản lý bản quyền khách hàng qua Google Sheets

1. Bấm vào nút **📊 Bảng Tính Bản Quyền** trên giao diện Admin để mở trực tiếp Google Sheets.
2. Thêm dòng mới cho khách hàng:
   | Mã máy (HWID) | Tên khách | Ngày hết hạn | Trạng thái |
   |---|---|---|---|
   | `3FD0-DB7D-FA39` | Anh Toàn | `2026-12-31` | `Active` |
3. **Khóa khách hàng**: Chỉ cần sửa cột Trạng thái thành `Block` là máy đó sẽ bị ngắt quyền truy cập ngay lập tức.

---

## 👤 PHẦN II: DÀNH CHO USER (KHÁCH HÀNG / NGƯỜI DÙNG CUỐI)

### 1. Khởi động ứng dụng

* **Người dùng dùng file EXE (Phổ biến nhất)**:
  - Chỉ cần nhấp đúp file **`StoryScraper_User.exe`**.
  - Trình duyệt sẽ tự động mở trang điều khiển tại `http://localhost:5000`.
  - Toàn bộ link Google Sheets và tính năng quản trị đã được ẩn hoàn toàn để bảo mật.

* **Người dùng chạy mã nguồn Python**:
  ```bash
  python app.py
  # hoặc:
  python entry_user.py
  ```

---

### 2. Kích hoạt bản quyền lần đầu

1. Khi mở ứng dụng, nếu chưa được kích hoạt, tool sẽ hiện thông báo kèm **Mã máy (HWID)** (Ví dụ: `3FD0-DB7D-FA39`).
2. Bấm **📋 Sao chép mã máy** và gửi mã này cho Admin.
3. Sau khi Admin báo đã thêm lên Google Sheets:
   - Người dùng chỉ cần bấm nút **⚡ Kiểm tra kích hoạt online** (hoặc mở lại tool).
   - Tool sẽ nhận diện tức thì và chuyển trạng thái sang **✅ Bản quyền hợp lệ**.

---

### 3. Cách cập nhật lên phiên bản mới nhất

* **Đối với người dùng file `.exe` (`StoryScraper_User.exe`)**:
  - Khi Admin phát hành bản mới, ở đầu trang sẽ tự động hiện thông báo màu tím nổi bật:
    > *🚀 Phát hiện bản cập nhật mới (v2.0.1): '...' - [⚡ Cập nhật ngay]*
  - Người dùng chỉ cần bấm **⚡ Cập nhật ngay**:
    1. Tool tự động tải file `.exe` mới ngầm từ GitHub.
    2. Tự động tắt bản cũ, thay thế bằng file mới và khởi động lại trong 2 giây.
    3. Trang web tự tải lại, không cần người dùng tải thủ công hay cài đặt lại.
  - Người dùng cũng có thể bấm nút **🔄 Cập nhật** trên thanh Menu bất kỳ lúc nào để kiểm tra bản mới.

* **Đối với người dùng chạy Terminal (Mã nguồn Python)**:
  - Bấm nút **⚡ Cập nhật ngay** trên giao diện: Tool sẽ tự động chạy lệnh `git pull origin main` và tự reload trang.
  - Hoặc mở Terminal gõ:
    ```bash
    git pull origin main
    ```

---

## ⚡ PHẦN III: BẢNG TRA CỨU LỆNH NHANH (CHEAT SHEET)

| Thao tác | Lệnh Terminal (CLI) | File .BAT / File EXE |
|---|---|---|
| **Chạy Web UI (Bản User)** | `python app.py` hoặc `python entry_user.py` | Chạy file `StoryScraper_User.exe` |
| **Chạy Web UI (Bản Admin)** | `python app.py --admin` hoặc `python entry_admin.py` | Chạy file `StoryScraper_Admin.exe` |
| **Đóng gói cả 2 bản EXE** | `python build.py --target all` | Chạy `build_exe.bat` chọn `1` |
| **Chỉ đóng gói bản User** | `python build.py --target user` | Chạy `build_exe.bat` chọn `2` |
| **Chỉ đóng gói bản Admin** | `python build.py --target admin` | Chạy `build_exe.bat` chọn `3` |
| **Cập nhật code qua Git** | `git pull origin main` | Bấm nút **⚡ Cập nhật ngay** trên Web |
| **Cào truyện & đăng CMS** | `python publish.py "<url_truyen>"` | Dùng tab **Cào & Đăng Truyện** trên Web |
| **Tải video/reel Facebook** | `python fb_downloader.py "<url_fb>"` | Dùng tab **Tải Reels & Video FB** trên Web |
| **Cấp key Admin 10 năm** | `python keygen.py --self -u "Admin"` | Đã tích hợp sẵn trong `StoryScraper_Admin.exe` |
| **Tạo key offline cho khách**| `python keygen.py -u "Khach" -m "HWID" -d 30` | Dùng nút tạo key trong modal Admin |





