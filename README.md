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
- **Thiết kế dạng Module (Plugin-based)**: Dễ dàng mở rộng thêm parser cho các website truyện mới chỉ bằng cách kế thừa `BaseParser`.

---

## 🚀 Hướng dẫn sử dụng

### 1. Khởi động Web UI (Giao diện đồ họa trực quan)
Chỉ cần chạy lệnh sau, trình duyệt sẽ tự động mở giao diện điều khiển:
```bash
python app.py
```
👉 Truy cập: `http://localhost:5000`

---

### 2. Sử dụng qua dòng lệnh (CLI)

#### Tải truyện, dịch tiếng Anh và tự động đăng lên CMS:
```bash
python publish.py "https://sad.treeiq.biz/blog/story-slug/chapter-1"
```
hoặc với tài khoản CMS tùy chỉnh:
```bash
python main.py "https://sad.treeiq.biz/blog/story-slug/chapter-1" --publish --cms-url "https://your-cms.com" --cms-user "your_email" --cms-pass "your_password"
```

### 2. Chỉ tải truyện về máy (mặc định tự dịch tiếng Anh, không đăng CMS)
```bash
python main.py "https://intelligence.treeiq.biz/blog/story-slug"
```

### 3. Tải truyện giữ nguyên ngôn ngữ gốc (không dịch)
```bash
python main.py "https://intelligence.treeiq.biz/blog/story-slug" --no-translate
```

### 4. Tải theo khoảng chapter cụ thể
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
python keygen.py -u "TenNguoiDung" -m "XXXX-XXXX-XXXX" -d 30

# Cấp 60 ngày (2 tháng)
python keygen.py -u "TenNguoiDung" -m "XXXX-XXXX-XXXX" -d 60
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

File `.exe` độc lập đã được biên dịch sẵn tại:
👉 **`dist/StoryScraper.exe`** (Dung lượng ~13MB)

### Cách gửi cho người dùng:
1. Bạn chỉ cần copy duy nhất **1 file `StoryScraper.exe`** trong thư mục `dist/` gửi cho người dùng (qua Zalo, Telegram, Google Drive,...).
2. Người dùng nhận file chỉ cần **click đúp vào `StoryScraper.exe`** để sử dụng (tự động bật server và tự mở trình duyệt web `http://localhost:5000`).
3. Khi người dùng mở lần đầu:
   - Tool sẽ báo chưa kích hoạt và hiển thị **Mã máy (HWID)**.
   - Người dùng copy mã máy gửi cho bạn.
   - Bạn dùng `keygen.py` tạo key cấp cho họ.
   - Khi kích hoạt xong, file `.license` và thư mục truyện `output/` sẽ tự động sinh ra ngay bên cạnh file `StoryScraper.exe`.

### Cách build lại file EXE sau khi chỉnh sửa code:
- **Cách 1**: Click đúp vào file **`build_exe.bat`** để tự động build.
- **Cách 2**: Chạy lệnh terminal:
  ```bash
  pyinstaller --noconfirm --onefile --console --name "StoryScraper" --add-data "templates;templates" app.py
  ```



