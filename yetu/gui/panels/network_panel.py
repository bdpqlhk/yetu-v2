# -*- coding: utf-8 -*-
"""面板三:网络信息。"""
from __future__ import annotations

from PyQt6.QtWidgets import QGroupBox, QHBoxLayout, QLabel, QPushButton, QPlainTextEdit, QVBoxLayout

from ...core.device import get_network_text
from ..widgets import make_mono
from .base import PanelBase


class NetworkPanel(PanelBase):
    name = "网络信息"

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        bar = QHBoxLayout()
        title = QLabel("网络信息")
        title.setObjectName("panelTitle")
        refresh = QPushButton("↻ 刷新网络信息")
        refresh.clicked.connect(self.refresh)
        bar.addWidget(title)
        bar.addStretch(1)
        bar.addWidget(refresh)
        root.addLayout(bar)

        group = QGroupBox("接口 / DNS / 代理 / WiFi")
        lay = QVBoxLayout(group)
        self._text = QPlainTextEdit()
        self._text.setReadOnly(True)
        self._text.setPlaceholderText("连接设备后点「刷新网络信息」…")
        make_mono(self._text)
        lay.addWidget(self._text)
        root.addWidget(group, 1)

    def on_device_changed(self, device) -> None:
        super().on_device_changed(device)
        self.refresh()

    def refresh(self) -> None:
        if self.device is None:
            self._text.setPlainText("未连接设备")
            return
        self._text.setPlainText("正在读取网络信息 …")
        self.run_async(
            lambda: get_network_text(self.device),
            self._text.setPlainText,
            cmd=f"network-info {self.device.serial}",
        )
