#!/usr/bin/env bash
# 野兔 v2 打包脚本(PyQt6 + PyInstaller)
# 产物:dist/yetu-v2.app(macOS,自带 tools/adb、tools/hdc)
set -euo pipefail
cd "$(dirname "$0")"

NAME="yetu-v2"
APP="dist/$NAME.app"

echo ">> 使用解释器: $(python3 -c 'import sys; print(sys.executable, sys.version.split()[0])')"

echo ">> 用 PyInstaller 打包 $NAME (内置 tools/) …"
python3 -m PyInstaller yetu-v2.spec --noconfirm --clean

echo ""
echo ">> 冒烟验证打包产物(内置工具 + 配置助手服务) …"
"$APP/Contents/MacOS/$NAME" --smoke

echo ">> GUI 渲染自检(offscreen 构建主窗口) …"
"$APP/Contents/MacOS/$NAME" --screenshot "${TMPDIR:-/tmp}/yetu-gui-check.png" >/dev/null 2>&1
test -s "${TMPDIR:-/tmp}/yetu-gui-check.png" || { echo "[FAIL] GUI 构建失败"; exit 1; }
echo "   GUI 渲染 OK"

echo ""
echo "✓ 打包完成:"
ls -ld "$APP" 2>/dev/null || ls -ld "dist/$NAME"
echo ""
echo "  运行: open 'dist/$NAME.app'"
echo "  首次分发被 Gatekeeper 拦截时: xattr -dr com.apple.quarantine 'dist/$NAME.app'"
