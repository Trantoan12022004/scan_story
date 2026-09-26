# build.py
# Script build StoryScraper thành file EXE độc lập bằng PyInstaller

import os
import sys
import dis

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Vá lỗi chuẩn của thư viện dis trên Python 3.10.0 (bpo-45385: EXTENDED_ARG không được reset khi gặp opcode < HAVE_ARGUMENT)
orig_unpack = dis._unpack_opargs
def fixed_unpack_opargs(code):
    extended_arg = 0
    for i in range(0, len(code), 2):
        op = code[i]
        if op >= dis.HAVE_ARGUMENT:
            arg = code[i+1] | extended_arg
            extended_arg = (arg << 8) if op == dis.EXTENDED_ARG else 0
        else:
            arg = None
            extended_arg = 0
        yield (i, op, arg)
dis._unpack_opargs = fixed_unpack_opargs

import PyInstaller.__main__

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 ĐANG ĐÓNG GÓI STORY SCRAPER THÀNH FILE EXE...")
    print("=" * 60)

    # Đóng tiến trình cũ nếu đang chạy
    if sys.platform == "win32":
        os.system("taskkill /F /IM StoryScraper.exe 2>nul")

    PyInstaller.__main__.run([
        '--noconfirm',
        '--onefile',
        '--console',
        '--name', 'StoryScraper',
        '--add-data', 'templates;templates',
        '--hidden-import', 'parsers',
        '--hidden-import', 'parsers.base',
        '--hidden-import', 'parsers.treeiq',
        '--hidden-import', 'parsers.ahcms',
        '--hidden-import', 'parsers.universal',
        '--hidden-import', 'downloader',
        '--hidden-import', 'translator',
        '--hidden-import', 'publisher',
        '--hidden-import', 'license_manager',
        '--hidden-import', 'fb_downloader',
        '--hidden-import', 'bs4',
        '--hidden-import', 'lxml',
        'app.py'
    ])
