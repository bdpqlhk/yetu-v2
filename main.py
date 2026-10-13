#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""野兔 v2 入口(PyQt6 版)。

用法:
    python3 main.py                        # 启动 GUI
    python3 main.py --selftest             # 自检(不弹界面):内置工具 / 已注册面板 / 设备
    python3 main.py --smoke                # 无头自检:配置助手起服务 -> 请求配置页 -> 停止
    python3 main.py --screenshot out.png   # 无头渲染并截图(验证 / 演示用)
"""
import os
import sys
import traceback
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _install_excepthook() -> None:
    """兜底:PyQt6.5+ 中 slot 内未处理异常默认 qFatal 直接闪退;
    换成自定义 excepthook 后 PyQt 会把异常交给它,记录日志并继续运行。"""
    def hook(t, v, tb):
        text = "".join(traceback.format_exception(t, v, tb))
        sys.stderr.write(text)
        try:
            log = Path.home() / ("Library/Logs/野兔v2.log"
                                 if sys.platform == "darwin" else "野兔v2.log")
            with open(log, "a", encoding="utf-8") as f:
                f.write(text + "\n")
        except Exception:
            pass
    sys.excepthook = hook


def _selftest() -> int:
    """打包后冒烟验证:内置工具、核心模块、设备发现。"""
    from yetu import __version__
    from yetu.core.adb import list_all_devices
    from yetu.core.env import tool_status

    print("YETU_V2_SELFTEST_START")
    print("version:", __version__)
    print("tools:", tool_status())
    print("panels:", [cls.name for cls in __import__("yetu.gui.panels", fromlist=["PANELS"]).PANELS])
    try:
        devs = [(d.serial, t) for d, t in list_all_devices()]
        print("devices:", devs or "(none)")
    except Exception as e:  # noqa: BLE001
        print("devices: ERROR", e)
    print("YETU_V2_SELFTEST_END")
    return 0


def run_screenshot(path: str) -> int:
    """以 offscreen 平台渲染窗口并截图(无显示环境验证)。"""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QApplication

    from yetu.gui.main_window import MainWindow, QSS

    app = QApplication(sys.argv[:1])
    app.setStyleSheet(QSS)
    win = MainWindow()
    win.resize(1000, 720)
    win.show()

    def save_and_quit() -> None:
        win.grab().save(path)
        print(f"screenshot saved: {path}")
        app.quit()

    QTimer.singleShot(3000, save_and_quit)
    return app.exec()


def _smoke() -> int:
    """无头自检:配置助手起服务 -> 请求 /proxy 与 /api/status -> 停止。"""
    import json
    import socket
    import time
    import urllib.request

    from yetu.core.assistant import ProxyAssistant

    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    serve_port = probe.getsockname()[1]
    probe.close()

    ast = ProxyAssistant(proxy_host="127.0.0.1", proxy_port=18888,
                         serve_port=serve_port)
    ast.start()
    ok = False
    deadline = time.time() + 10
    while time.time() < deadline:
        if ast.started.wait(0.2):
            break
    if not ast.last_error:
        try:
            with urllib.request.urlopen(
                    f"http://127.0.0.1:{serve_port}/proxy", timeout=3) as r:
                body = r.read().decode("utf-8")
                ok = r.status == 200 and "代理配置助手" in body
            with urllib.request.urlopen(
                    f"http://127.0.0.1:{serve_port}/api/status", timeout=3) as r:
                status = json.loads(r.read().decode("utf-8"))
                ok = ok and status["port"] == 18888 and status["listening"] is False
        except Exception:
            ok = False
    ast.stop()
    print("SMOKE_OK" if ok else "SMOKE_FAIL")
    return 0 if ok else 1


def main() -> int:
    if "--selftest" in sys.argv:
        return _selftest()
    if "--smoke" in sys.argv:
        return _smoke()
    if "--screenshot" in sys.argv:
        i = sys.argv.index("--screenshot")
        path = sys.argv[i + 1] if len(sys.argv) > i + 1 else "/tmp/yetu-v2.png"
        return run_screenshot(path)

    from PyQt6.QtCore import QEvent, Qt
    from PyQt6.QtWidgets import QApplication

    from yetu.gui.main_window import MainWindow, QSS

    _install_excepthook()

    class YetoApp(QApplication):
        """macOS:主窗口收到托盘后,点 Dock 图标重新打开。"""
        mainwin = None

        def event(self, e):
            if (e.type() == QEvent.Type.ApplicationStateChange
                    and self.applicationState() == Qt.ApplicationState.ApplicationActive
                    and sys.platform == "darwin"):
                w = YetoApp.mainwin
                if w is not None and not w.isVisible():
                    w.show()
                    w.raise_()
                    w.activateWindow()
            return super().event(e)

    app = YetoApp(sys.argv)
    app.setApplicationName("野兔v2")
    app.setStyleSheet(QSS)
    win = MainWindow()
    YetoApp.mainwin = win
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
