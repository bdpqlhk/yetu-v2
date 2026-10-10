# -*- coding: utf-8 -*-
"""面板四:全局代理设置 / 清除(抓包用)。"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout,
)

from ...core.device import clear_proxy, get_proxy, set_proxy
from ..widgets import chip, set_chip
from .base import PanelBase


class ProxyPanel(PanelBase):
    name = "全局代理"

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel("全局代理")
        title.setObjectName("panelTitle")
        root.addWidget(title)

        current = QGroupBox("当前代理")
        curlay = QHBoxLayout(current)
        self._current = chip("未查询", "chipDim")
        self._read_btn = QPushButton("↻ 读取当前代理")
        self._read_btn.clicked.connect(self.refresh)
        curlay.addWidget(self._current, 1)
        curlay.addWidget(self._read_btn)
        root.addWidget(current)

        edit = QGroupBox("设置代理(Charles / mitmproxy 抓包)")
        elay = QHBoxLayout(edit)
        self._host = QLineEdit()
        self._host.setPlaceholderText("主机,如 192.168.1.100")
        self._port = QLineEdit()
        self._port.setPlaceholderText("端口,如 8888")
        self._port.setMaximumWidth(120)
        self._set_btn = QPushButton("设置代理")
        self._set_btn.setObjectName("primary")
        self._set_btn.clicked.connect(self._on_set)
        self._clear_btn = QPushButton("清除代理")
        self._clear_btn.clicked.connect(self._on_clear)
        elay.addWidget(QLabel("主机:"))
        elay.addWidget(self._host, 1)
        elay.addWidget(QLabel("端口:"))
        elay.addWidget(self._port)
        elay.addWidget(self._set_btn)
        elay.addWidget(self._clear_btn)
        root.addWidget(edit)

        tip = QLabel("提示:设置后设备的 http/https 流量将走该代理;清除即恢复直连。"
                     "安卓与鸿蒙的代理均为全局 settings 写入。")
        tip.setObjectName("hint")
        tip.setWordWrap(True)
        root.addWidget(tip)
        root.addStretch(1)

    def on_device_changed(self, device) -> None:
        super().on_device_changed(device)
        self.refresh()

    def refresh(self) -> None:
        if self.device is None:
            set_chip(self._current, "未连接设备", "chipDim")
            return
        self.run_async(
            lambda: get_proxy(self.device),
            self._show_current,
            cmd=f"get-proxy {self.device.serial}",
        )

    def _show_current(self, value: str) -> None:
        if value.startswith("("):
            set_chip(self._current, f"○ {value}", "chipDim")
        else:
            set_chip(self._current, f"● {value}", "chipOk")

    def _on_set(self) -> None:
        if self.device is None:
            self.app.show_status("✗ 请先在顶部选择设备", error=True)
            return
        host, port = self._host.text().strip(), self._port.text().strip()
        if not host or not port:
            self.app.show_status("✗ 请填写代理主机和端口", error=True)
            return
        self.run_async(
            lambda: set_proxy(self.device, host, port),
            lambda _: (set_chip(self._current, f"● {host}:{port}", "chipOk"),
                       self.app.show_status(f"✓ 已设置代理 {host}:{port}")),
            busy_btn=self._set_btn,
            busy_text="设置中…",
            cmd=f"set-proxy {self.device.serial} {host}:{port}",
        )

    def _on_clear(self) -> None:
        if self.device is None:
            self.app.show_status("✗ 请先在顶部选择设备", error=True)
            return
        self.run_async(
            lambda: clear_proxy(self.device),
            lambda _: (set_chip(self._current, "○ (未设置)", "chipDim"),
                       self.app.show_status("✓ 已清除全局代理")),
            busy_btn=self._clear_btn,
            busy_text="清除中…",
            cmd=f"clear-proxy {self.device.serial}",
        )
