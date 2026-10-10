# -*- coding: utf-8 -*-
"""面板五:安装 APK / HAP。

- APK(安卓)走 adb install;HAP(鸿蒙)走 hdc install。
- 安装进度经 InstallWorker.line 信号流式显示在下方日志框。
"""
from __future__ import annotations

import os

from PyQt6.QtWidgets import (
    QFileDialog, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QPlainTextEdit, QVBoxLayout,
)

from ...core.adb import Adb, Hdc
from ...core.env import tool_status
from ..widgets import make_mono
from .base import PanelBase

_EXT_LABEL = {".apk": "安卓 APK", ".hap": "鸿蒙 HAP"}
_EXT_BY_CONN = {".apk": "adb", ".hap": "hdc"}


class InstallPanel(PanelBase):
    name = "安装应用"

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel("安装应用")
        title.setObjectName("panelTitle")
        root.addWidget(title)

        box = QGroupBox("安装包")
        blay = QVBoxLayout(box)
        row1 = QHBoxLayout()
        self._file = QLineEdit()
        self._file.setPlaceholderText("选择 .apk / .hap 安装包…")
        self._file.setReadOnly(True)
        browse = QPushButton("选择文件…")
        browse.clicked.connect(self._browse)
        row1.addWidget(self._file, 1)
        row1.addWidget(browse)
        blay.addLayout(row1)

        row2 = QHBoxLayout()
        self._install_btn = QPushButton("开始安装")
        self._install_btn.setObjectName("primary")
        self._install_btn.clicked.connect(self._install)
        self._detail = QLabel("未选择安装包")
        self._detail.setObjectName("hint")
        row2.addWidget(self._install_btn)
        row2.addSpacing(10)
        row2.addWidget(self._detail, 1)
        blay.addLayout(row2)
        root.addWidget(box)

        log_group = QGroupBox("安装日志")
        llay = QVBoxLayout(log_group)
        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setPlaceholderText("安装输出…")
        self._log.setMaximumBlockCount(5000)
        make_mono(self._log)
        llay.addWidget(self._log)
        root.addWidget(log_group, 1)

        tip = QLabel("提示:.apk 需设备经 adb 连接;.hap 需设备经 hdc(鸿蒙)连接 — 顶部下拉选对应条目。")
        tip.setObjectName("hint")
        tip.setWordWrap(True)
        root.addWidget(tip)

    # ---------------- 文件选择 ----------------
    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选择安装包", "",
            "安卓/鸿蒙安装包 (*.apk *.hap);;APK (*.apk);;HAP (*.hap)")
        if not path:
            return
        self._file.setText(path)
        ext = os.path.splitext(path)[1].lower()
        name = os.path.basename(path)
        if ext in _EXT_LABEL:
            self._detail.setText(f"已识别:{_EXT_LABEL[ext]}({name})")
        else:
            self._detail.setText(f"⚠ 不支持的类型:{name},请选 .apk 或 .hap")

    # ---------------- 安装 ----------------
    def _install(self) -> None:
        if self.device is None:
            self.app.show_status("✗ 请先在顶部选择已连接的设备", error=True)
            return
        path = self._file.text().strip()
        if not path or not os.path.isfile(path):
            self.app.show_status("✗ 请先选择一个有效的安装包文件", error=True)
            return
        ext = os.path.splitext(path)[1].lower()
        if ext not in _EXT_LABEL:
            self.app.show_status("✗ 仅支持 .apk / .hap 安装包", error=True)
            return

        need = _EXT_BY_CONN[ext]
        if not tool_status().get(need):
            self.app.show_status(f"✗ 未找到 {need},无法安装 {_EXT_LABEL[ext]}", error=True)
            return

        conn = Adb() if need == "adb" else Hdc()
        self._log.appendPlainText(
            f"$ {need} install {os.path.basename(path)}\n  → {self.device.label}\n")
        self.app.log_command(f"{need} install {os.path.basename(path)} → {self.device.serial}")

        self._install_btn.setEnabled(False)
        self._install_btn.setText("安装中…")
        self.app.set_busy(+1)

        from ..workers import InstallWorker
        self._worker = InstallWorker(conn, self.device.serial, path, parent=self)
        self._worker.line.connect(lambda line: self._log.appendPlainText(line))
        self._worker.done.connect(lambda proc: self._on_done(proc, ext))
        self._worker.finished.connect(self._finish)
        self._worker.start()

    def _on_done(self, proc, ext: str) -> None:
        if isinstance(proc, BaseException):
            self._log.appendPlainText(f"\n✗ 安装出错:{proc}\n")
            self.app.show_status(f"✗ {_EXT_LABEL[ext]} 安装出错", error=True)
        elif proc.returncode == 0:
            self._log.appendPlainText(f"\n✓ {_EXT_LABEL[ext]} 安装成功\n")
            self.app.show_status(f"✓ {_EXT_LABEL[ext]} 安装成功")
        else:
            self._log.appendPlainText(f"\n✗ 安装失败(退出码 {proc.returncode})\n")
            self.app.show_status(f"✗ {_EXT_LABEL[ext]} 安装失败", error=True)

    def _finish(self) -> None:
        self.app.log_result(ok=True)
        self.app.set_busy(-1)
        self._install_btn.setEnabled(True)
        self._install_btn.setText("开始安装")
