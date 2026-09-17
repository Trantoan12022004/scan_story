#!/usr/bin/env python3
# publish.py
# Shortcut để tải truyện, dịch sang tiếng Anh và tự động đăng lên CMS BlogBio

import sys

if __name__ == "__main__":
    # Tự động kích hoạt cờ --publish nếu chưa có
    if "--publish" not in sys.argv:
        sys.argv.append("--publish")
    import main
    main.main()
