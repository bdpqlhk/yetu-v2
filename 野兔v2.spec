# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置(跨平台):
    macOS    → dist/野兔v2.app (onedir bundle, 自带 tools/adb、tools/hdc)
    Windows  → dist/野兔v2.exe (单文件)

用法: pyinstaller 野兔v2.spec --noconfirm --clean
"""
import importlib.util
import os
import sys

# 依赖快速失败: PyQt6 未安装时 PyInstaller 仍会"成功"打出缺模块的包,
# 直到运行才报 No module named 'PyQt6' —— 构建期就拦住并给出明确提示。
if importlib.util.find_spec("PyQt6") is None:
    raise SystemExit(
        "[FAIL] 未检测到 PyQt6, 打包会产出无法运行的 exe。\n"
        "       请先安装依赖(与执行打包的 python 保持一致):\n"
        "           python -m pip install -r requirements.txt\n"
        "       网络慢可用镜像: -i https://pypi.tuna.tsinghua.edu.cn/simple")

spec_dir = SPECPATH
NAME = "野兔v2"

datas = [
    (os.path.join(spec_dir, "tools"), "tools"),
    # 配置助手的手机页面(运行时按包内路径读取)
    (os.path.join(spec_dir, "yetu", "core", "assistant_page.html"),
     os.path.join("yetu", "core")),
]


def _icon(ext: str):
    path = os.path.join(spec_dir, "assets", f"icon.{ext}")
    return path if os.path.exists(path) else None


ICON = _icon("ico") if sys.platform == "win32" else _icon("icns")

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

if sys.platform == "win32":
    # 单文件: 二进制与资源全部打进 exe
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name=NAME,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=False,
        icon=ICON,
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name=NAME,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=False,
        icon=ICON,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=False,
        name=NAME,
    )
    if sys.platform == "darwin":
        app = BUNDLE(
            coll,
            name=f"{NAME}.app",
            icon=ICON,
            bundle_identifier="com.yetu.toolbox.v2",
        )
