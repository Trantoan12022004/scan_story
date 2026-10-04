"""
Script đóng gói ứng dụng ban_win thành file EXE độc lập chạy trên Windows bằng PyInstaller.
"""
import os
import sys
import shutil
import subprocess

APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BAN_WIN_DIR = os.path.join(APP_ROOT, "ban_win")
MAIN_SCRIPT = os.path.join(BAN_WIN_DIR, "main.py")
ICON_PATH = os.path.join(BAN_WIN_DIR, "assets", "app_icon.ico")
DIST_DIR = os.path.join(BAN_WIN_DIR, "dist")
BUILD_DIR = os.path.join(BAN_WIN_DIR, "build")

def build_exe():
    print("=" * 60)
    print("   BẮT ĐẦU ĐÓNG GÓI SCAN STORY STUDIO WINDOWS EXE")
    print("=" * 60)

    # 1. Đảm bảo icon tồn tại
    if not os.path.isfile(ICON_PATH):
        print(f"[-] Cảnh báo: Không tìm thấy icon tại {ICON_PATH}")

    # 2. Xây dựng lệnh PyInstaller
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name=ScanStoryStudio",
        "--noconsole",
        "--onefile",
        "--clean",
        "--exclude-module=PyQt5",
        "--exclude-module=tkinter",
        f"--icon={ICON_PATH}",
        f"--distpath={DIST_DIR}",
        f"--workpath={BUILD_DIR}",
        # Add data
        f"--add-data={os.path.join(BAN_WIN_DIR, 'assets')};ban_win/assets",
        f"--add-data={os.path.join(BAN_WIN_DIR, 'parsers')};ban_win/parsers",
        # Hidden imports
        "--hidden-import=qfluentwidgets",
        "--hidden-import=PySide6.QtMultimedia",
        "--hidden-import=PySide6.QtMultimediaWidgets",
        "--hidden-import=sqlite3",
        "--hidden-import=bs4",
        "--hidden-import=lxml",
        "--hidden-import=requests",
        "--hidden-import=yt_dlp",
        "--hidden-import=PIL",
        # Entry script
        MAIN_SCRIPT
    ]

    print("[*] Đang thực thi lệnh:")
    print(" ".join(cmd))
    print("\nQuá trình đóng gói có thể mất 1-3 phút...")

    res = subprocess.run(cmd, cwd=APP_ROOT)
    if res.returncode == 0:
        exe_path = os.path.join(DIST_DIR, "ScanStoryStudio.exe")
        print("\n" + "=" * 60)
        print("🎉 ĐÓNG GÓI HOÀN TẤT THÀNH CÔNG!")
        print(f"File thực thi: {exe_path}")
        if os.path.isfile(exe_path):
            sz_mb = os.path.getsize(exe_path) / (1024 * 1024)
            print(f"Dung lượng: {sz_mb:.1f} MB")
        print("=" * 60)
    else:
        print("\n[-] Lỗi đóng gói PyInstaller! Mã lỗi:", res.returncode)

if __name__ == "__main__":
    build_exe()
