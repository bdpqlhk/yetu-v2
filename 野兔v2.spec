# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置:macOS → 野兔v2.app(自带 tools/adb、tools/hdc)。

用法: pyinstaller 野兔v2.spec --noconfirm --clean
"""
import os
import sys

spec_dir = SPECPATH

datas = [
    (os.path.join(spec_dir, "tools"), "tools"),
    # 配置助手的手机页面(运行时按包内路径读取)
    (os.path.join(spec_dir, "yetu", "core", "assistant_page.html"),
     os.path.join("yetu", "core")),
]

icon = None
if sys.platform == "darwin" and os.path.exists(os.path.join(spec_dir, "assets", "icon.icns")):
    icon = os.path.join(spec_dir, "assets", "icon.icns")
elif sys.platform == "win32" and os.path.exists(os.path.join(spec_dir, "assets", "icon.ico")):
    icon = os.path.join(spec_dir, "assets", "icon.ico")

a = Analysis(
    ["main.py"],
    pathex=[spec_dir],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="野兔v2",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,          # GUI 程序,不开控制台
    icon=icon,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="野兔v2",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="野兔v2.app",
        icon=icon,
        bundle_identifier="com.yetu.toolbox.v2",
    )
