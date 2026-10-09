# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['entry_admin.py'],
    pathex=[],
    binaries=[],
    datas=[('templates', 'templates'), ('static', 'static'), ('version.json', '.')],
    hiddenimports=['parsers', 'parsers.base', 'parsers.treeiq', 'parsers.ahcms', 'parsers.universal', 'downloader', 'translator', 'publisher', 'license_manager', 'fb_downloader', 'bs4', 'lxml', 'requests', 'keygen'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'matplotlib', 'IPython', 'tkinter', 'tornado', 'scipy'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='StoryScraper_Admin',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
