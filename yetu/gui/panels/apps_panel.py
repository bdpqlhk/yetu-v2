# -*- coding: utf-8 -*-
"""面板二:已装应用。"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QCheckBox, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QVBoxLayout,
)

from ...core.device import list_apps
from ..widgets import make_table, set_rows
from .base import PanelBase


class AppsPanel(PanelBase):
    name = "已装应用"

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        bar = QHBoxLayout()
        title = QLabel("已装应用")
        title.setObjectName("panelTitle")
        refresh = QPushButton("↻ 刷新")
        refresh.clicked.connect(self.refresh)
        self._third_only = QCheckBox("仅第三方应用")
        self._third_only.setChecked(True)
        self._third_only.stateChanged.connect(lambda *_: self.refresh())
        self._search = QLineEdit()
        self._search.setPlaceholderText("按包名过滤…")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(lambda *_: self._apply_filter())
        self._count = QLabel("共 0 个")
        self._count.setObjectName("hint")
        bar.addWidget(title)
        bar.addSpacing(10)
        bar.addWidget(self._search)
        bar.addWidget(self._third_only)
        bar.addStretch(1)
        bar.addWidget(self._count)
        bar.addWidget(refresh)
        root.addLayout(bar)

        group = QGroupBox("应用列表")
        lay = QVBoxLayout(group)
        self._table = make_table(["包名", "版本"], stretch_col=0)
        lay.addWidget(self._table)
        root.addWidget(group, 1)

        self._all_rows: list[tuple[str, str]] = []

    def on_device_changed(self, device) -> None:
        super().on_device_changed(device)
        self.refresh()

    def refresh(self) -> None:
        self._all_rows = []
        self._apply_filter()
        if self.device is None:
            return
        third_only = self._third_only.isChecked()
        self.run_async(
            lambda: list_apps(self.device, third_party_only=third_only),
            self._show_apps,
            cmd=f"list-apps {self.device.serial} third_party={third_only}",
        )

    def _show_apps(self, rows) -> None:
        self._all_rows = rows or []
        self._apply_filter()

    def _apply_filter(self) -> None:
        keyword = self._search.text().strip().lower()
        rows = [[pkg, ver] for pkg, ver in self._all_rows
                if not keyword or keyword in pkg.lower()]
        set_rows(self._table, rows)
        self._count.setText(f"共 {len(rows)} 个")
