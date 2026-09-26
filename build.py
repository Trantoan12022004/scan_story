# build.py
# Script đóng gói StoryScraper thành 2 phiên bản độc lập (User & Admin) bằng PyInstaller

import os
import sys
import dis
import argparse

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


COMMON_HIDDEN_IMPORTS = [
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
    '--hidden-import', 'requests',
]


def build_version(target: str):
    """
    target: 'user' hoặc 'admin'
    """
    is_admin = (target.lower() == "admin")
    exe_name = "StoryScraper_Admin" if is_admin else "StoryScraper_User"
    entry_script = "entry_admin.py" if is_admin else "entry_user.py"
    desc = "BẢN QUẢN TRỊ VIÊN (ADMIN)" if is_admin else "BẢN KHÁCH HÀNG (USER)"

    print("\n" + "=" * 65)
    print(f"🚀 BẮT ĐẦU ĐÓNG GÓI: {exe_name}.exe ({desc})")
    print("=" * 65)

    # Đóng tiến trình cũ nếu đang chạy để không bị khóa file dist/
    if sys.platform == "win32":
        os.system(f"taskkill /F /IM {exe_name}.exe 2>nul")

    pyinstaller_args = [
        '--noconfirm',
        '--onefile',
        '--console',
        '--name', exe_name,
        '--add-data', 'templates;templates',
    ] + COMMON_HIDDEN_IMPORTS

    if is_admin:
        pyinstaller_args += ['--hidden-import', 'keygen']

    pyinstaller_args.append(entry_script)

    PyInstaller.__main__.run(pyinstaller_args)

    print("\n" + "=" * 65)
    print(f"✅ ĐÃ BUILD THÀNH CÔNG: dist/{exe_name}.exe")
    print("=" * 65 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Đóng gói StoryScraper thành 2 phiên bản độc lập (Admin & User)"
    )
    parser.add_argument(
        "--target",
        choices=["all", "user", "admin"],
        default="all",
        help="Chọn phiên bản cần build: all (cả 2 bản), user (khách hàng), admin (quản trị viên)"
    )
    args = parser.parse_args()

    if args.target in ["user", "all"]:
        build_version("user")

    if args.target in ["admin", "all"]:
        build_version("admin")


if __name__ == "__main__":
    main()
