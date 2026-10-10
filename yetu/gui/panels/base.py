# -*- coding: utf-8 -*-
"""面板基类:设备注入 + 统一的后台执行(run_async)。

后台执行约定:
    adb / hdc 命令可能耗时数秒,一律经 Worker 放后台线程;
    完成后通过 done 信号回主线程,再刷新控件。
"""
from __future__ import annotations

from typing import Callable, Optional

from PyQt6.QtWidgets import QPushButton, QWidget

from ..workers import Worker


class PanelBase(QWidget):
    """所有功能面板的基类。子类实现 _build / refresh,可选 on_device_changed。"""

    name = "未命名"

    def __init__(self, app: "MainWindow", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.app = app
        self.device = None  # 当前设备(由主窗口注入)
        self._build()

    # ---------------- 子类可覆写 ----------------
    def _build(self) -> None:
        """搭建本面板界面。"""

    def on_device_changed(self, device) -> None:
        """设备切换或列表刷新后回调。默认记录设备。"""
        self.device = device

    def refresh(self) -> None:
        """刷新本面板数据(用户点刷新 / 切到该 Tab 时)。"""

    # ---------------- 后台执行 ----------------
    def run_async(self, fn: Callable, on_done: Callable,
                  busy_btn: Optional[QPushButton] = None,
                  busy_text: str = "执行中…", cmd: str = "") -> None:
        """后台执行 fn,完成后在主线程回调 on_done(result)。

        busy_btn: 执行期间禁用的按钮(防重复点击),结束还原文字。
        cmd:      命令描述,写入主窗口底部「命令日志」。
        """
        if cmd:
            self.app.log_command(cmd)
        if busy_btn is not None:
            busy_btn.setEnabled(False)
            busy_btn.setProperty("origText", busy_btn.text())
            busy_btn.setText(busy_text)

        def handle(result) -> None:
            if isinstance(result, BaseException):
                if cmd:
                    self.app.log_result(ok=False, note=str(result))
                self.app.show_status(f"✗ {result}", error=True)
            else:
                if cmd:
                    self.app.log_result(ok=True)
                on_done(result)

        def cleanup() -> None:
            self.app.set_busy(-1)
            if busy_btn is not None:
                busy_btn.setEnabled(True)
                orig = busy_btn.property("origText")
                if orig:
                    busy_btn.setText(orig)
                busy_btn.setProperty("origText", None)

        w = Worker(fn, parent=self)
        w.done.connect(handle)
        w.finished.connect(cleanup)
        w.finished.connect(w.deleteLater)
        w.start()
        self.app.set_busy(+1)
