# -*- coding: utf-8 -*-
"""后台线程执行器。

Qt 的 UI 控件只能在主线程操作;而 adb / hdc 命令动辄数秒,
一律经 Worker / InstallWorker 放到后台线程执行,结果与安装
进度通过信号(跨线程自动排队)回传主线程刷新界面。
"""
from __future__ import annotations

import traceback

from PyQt6.QtCore import QThread, pyqtSignal


class Worker(QThread):
    """执行 fn() 并把结果(或异常实例)经 done 信号发回主线程。"""

    done = pyqtSignal(object)

    def __init__(self, fn, parent=None):
        super().__init__(parent)
        self._fn = fn

    def run(self) -> None:  # QThread 线程体
        try:
            result = self._fn()
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            result = e
        self.done.emit(result)


class InstallWorker(QThread):
    """流式安装 APK / HAP:每行输出经 line 信号实时回传。"""

    line = pyqtSignal(str)
    done = pyqtSignal(object)

    def __init__(self, conn, serial: str, path: str, parent=None):
        super().__init__(parent)
        self._conn = conn
        self._serial = serial
        self._path = path

    def run(self) -> None:
        try:
            proc = self._conn.install(self._serial, self._path,
                                      on_line=self.line.emit)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            proc = e
        self.done.emit(proc)
