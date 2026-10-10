# -*- coding: utf-8 -*-
"""面板一:手机信息。"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFormLayout, QGroupBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from ...core.device import get_device_info
from ..widgets import fill_form
from .base import PanelBase


class DevicePanel(PanelBase):
    name = "手机信息"

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        bar = QHBoxLayout()
        title = QLabel("手机信息")
        title.setObjectName("panelTitle")
        self._hint = QLabel("")
        self._hint.setObjectName("hint")
        refresh = QPushButton("↻ 刷新信息")
        refresh.clicked.connect(self.refresh)
        bar.addWidget(title)
        bar.addSpacing(10)
        bar.addWidget(self._hint)
        bar.addStretch(1)
        bar.addWidget(refresh)
        root.addLayout(bar)

        self._group = QGroupBox("设备信息")
        self._form = QFormLayout(self._group)
        self._form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        root.addWidget(self._group, 1)

    def on_device_changed(self, device) -> None:
        super().on_device_changed(device)
        self.refresh()

    def refresh(self) -> None:
        self._hint.setText("")
        if self.device is None:
            self._group.setTitle("设备信息")
            fill_form(self._form, [("状态", "未连接设备 — 请插线并开启 USB 调试")])
            return
        self._group.setTitle(f"设备信息 — {self.device.label}")
        self._hint.setText(f"正在读取 {self.device.serial} …")
        self.run_async(
            lambda: get_device_info(self.device),
            self._show_info,
            cmd=f"get-device-info {self.device.serial}",
        )

    def _show_info(self, rows) -> None:
        self._hint.setText("")
        fill_form(self._form, rows or [("提示", "未读取到信息")])
