# -*- coding: utf-8 -*-
"""工具环境解析:内置 adb / hdc 优先,其次系统 PATH。

「野兔」要求工具自带 adb(及可选的 hdc)环境,不依赖用户机器预装。
打包时通过 PyInstaller 把 tools/ 目录一并带上;运行时按下面的优先级查找:
  1. 环境变量 YETU_TOOLS 指定目录
  2. 打包后 exe 所在目录下的 tools/
  3. macOS .app 的 Contents/Resources/tools/
  4. onedir 的 _internal/tools/
  5. 开发态项目根目录 tools/
  6. 系统 PATH 里的 adb / hdc
"""
from __future__ import annotations

import os
import shutil
import sys

APP_NAME = "野兔"

# 每个工具在 tools 目录下的子目录名(便于 adb/hdc 各自带库文件)
TOOL_SUBDIR = {"adb": "adb", "hdc": "hdc"}


def _bundle_roots() -> list[str]:
    """打包后可能放置 tools 的候选根目录。"""
    roots: list[str] = []
    if getattr(sys, "frozen", False):  # PyInstaller 打包态
        exe_dir = os.path.dirname(sys.executable)
        roots.append(exe_dir)  # Contents/MacOS
        roots.append(os.path.join(exe_dir, "..", "Resources"))  # Contents/Resources
        meipass = getattr(sys, "_MEIPASS", None)  # onefile 解压目录
        if meipass:
            roots.append(meipass)
        # onedir 的 _internal
        roots.append(os.path.join(exe_dir, "_internal"))
    return roots


def _dev_roots() -> list[str]:
    """开发态下 tools 所在位置:本项目根目录。"""
    here = os.path.dirname(os.path.abspath(__file__))  # yetu/core
    project_root = os.path.dirname(os.path.dirname(here))  # 项目根
    return [project_root]


def find_tool(name: str) -> str | None:
    """返回工具绝对路径;找不到返回 None。"""
    subdir = TOOL_SUBDIR.get(name, name)

    candidates: list[str] = []
    env_dir = os.environ.get("YETU_TOOLS")
    if env_dir:
        candidates.append(os.path.join(env_dir, subdir, name))

    for root in _bundle_roots():
        candidates.append(os.path.join(root, "tools", subdir, name))
        candidates.append(os.path.join(root, subdir, name))

    for root in _dev_roots():
        candidates.append(os.path.join(root, "tools", subdir, name))

    for cand in candidates:
        if os.path.isfile(cand) and os.access(cand, os.X_OK):
            return cand

    # 最后退回系统 PATH
    found = shutil.which(name)
    if found:
        return os.path.abspath(found)
    return None


def adb_path() -> str | None:
    return find_tool("adb")


def hdc_path() -> str | None:
    return find_tool("hdc")


def tool_status() -> dict[str, str | None]:
    """返回工具可用性,用于界面提示。"""
    return {"adb": adb_path(), "hdc": hdc_path()}
