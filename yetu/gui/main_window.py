# -*- coding: utf-8 -*-
"""野兔 v2 主窗口(样式参考 tcode GUI 深色开发者工具风格)。

结构:顶部 header(品牌/版本) → 设备栏(下拉+刷新+内置工具状态) →
功能 Tab(手机信息/已装应用/网络信息/全局代理/安装应用) →
底部「命令日志」Dock → 状态栏(设备消息 + 忙碌指示)。
所有 adb / hdc 调用经 Worker 放后台线程,UI 不冻结。
"""
from __future__ import annotations

import sys
from datetime import datetime

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QKeySequence, QTextCursor
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QDockWidget, QFrame, QHBoxLayout, QLabel,
    QMainWindow, QMessageBox, QPlainTextEdit, QPushButton, QStatusBar,
    QTabWidget, QVBoxLayout, QWidget,
)

from .. import __version__
from ..core.adb import list_all_devices
from ..core.device import Device, from_entry
from ..core.env import tool_status
from .panels import PANELS
from .theme import QSS
from .widgets import make_mono
from .workers import Worker


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"野兔 v{__version__} · 手机调试工具箱")
        self.resize(1000, 720)
        self.setMinimumSize(820, 560)

        self.current_device: Device | None = None
        self._devices: list[Device] = []
        self._busy = 0

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_header())
        layout.addWidget(self._build_devbar())

        self.tabs = QTabWidget()
        self._panels = [cls(self) for cls in PANELS]
        for panel in self._panels:
            self.tabs.addTab(panel, panel.name)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(self.tabs, 1)

        self._build_log_dock()
        self._build_statusbar()
        self._build_menus()

        self._update_tool_label()
        QTimer.singleShot(300, self.refresh_devices)

    # ------------------------------------------------------------------ #
    # 界面搭建
    # ------------------------------------------------------------------ #
    def _build_header(self) -> QFrame:
        header = QFrame()
        header.setObjectName("header")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(16, 12, 16, 12)
        brand = QLabel("🐇 野兔")
        brand.setObjectName("brand")
        subtitle = QLabel("手机调试工具箱 · ADB + HDC 一体化")
        subtitle.setObjectName("subtitle")
        version = QLabel(f"v{__version__} · PyQt6")
        version.setObjectName("version")
        hl.addWidget(brand)
        hl.addSpacing(12)
        hl.addWidget(subtitle)
        hl.addStretch(1)
        hl.addWidget(version)
        return header

    def _build_devbar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("devbar")
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(16, 10, 16, 10)
        lbl = QLabel("设备:")
        self.device_combo = QComboBox()
        self.device_combo.setMinimumWidth(420)
        self.device_combo.currentIndexChanged.connect(self._on_device_selected)
        self.refresh_btn = QPushButton("↻ 刷新设备")
        self.refresh_btn.setShortcut(QKeySequence("F5"))
        self.refresh_btn.clicked.connect(self.refresh_devices)
        bl.addWidget(lbl)
        bl.addWidget(self.device_combo)
        bl.addWidget(self.refresh_btn)
        bl.addStretch(1)
        self._adb_chip = QLabel("adb: …")
        self._hdc_chip = QLabel("hdc: …")
        bl.addWidget(self._adb_chip)
        bl.addSpacing(12)
        bl.addWidget(self._hdc_chip)
        return bar

    def _build_log_dock(self) -> None:
        self._log_dock = QDockWidget("命令日志", self)
        self._log_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetClosable)
        widget = QWidget()
        lay = QVBoxLayout(widget)
        lay.setContentsMargins(8, 4, 8, 8)
        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumBlockCount(5000)
        self._log.setPlaceholderText("adb / hdc 命令执行记录…")
        make_mono(self._log)
        lay.addWidget(self._log)
        self._log_dock.setWidget(widget)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self._log_dock)
        self.resizeDocks([self._log_dock], [140], Qt.Orientation.Vertical)

    def _build_statusbar(self) -> None:
        bar = QStatusBar()
        self.setStatusBar(bar)
        self._status_lbl = QLabel("就绪")
        bar.addWidget(self._status_lbl)
        self._busy_lbl = QLabel("⏳ 执行中…")
        self._busy_lbl.setObjectName("busy")
        bar.addPermanentWidget(self._busy_lbl)
        self._busy_lbl.hide()

    def _build_menus(self) -> None:
        m_file = self.menuBar().addMenu("文件")
        act_refresh = QAction("刷新全部", self)
        act_refresh.setShortcut(QKeySequence.StandardKey.Refresh)
        act_refresh.triggered.connect(self.refresh_devices)
        m_file.addAction(act_refresh)
        m_file.addAction("退出", self.close)

        m_view = self.menuBar().addMenu("视图")
        m_view.addAction(self._log_dock.toggleViewAction())

        m_help = self.menuBar().addMenu("帮助")
        act_about = QAction("关于", self)
        act_about.triggered.connect(self._about)
        m_help.addAction(act_about)

    def _about(self) -> None:
        QMessageBox.about(
            self, "关于 野兔 v2",
            f"<b>野兔 v{__version__}</b>(PyQt6 重写版)<br>"
            f"手机调试工具箱 · 内置 adb / hdc,无需预装环境<br><br>"
            f"功能:设备信息 / 已装应用 / 网络信息 / 全局代理 / 安装 APK·HAP<br>"
            f"界面样式参考 TCode GUI(深色开发者工具风格)")

    # ------------------------------------------------------------------ #
    # 设备管理
    # ------------------------------------------------------------------ #
    def refresh_devices(self) -> None:
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setText("刷新中…")
        self.log_command("adb devices -l  +  hdc list targets")
        w = Worker(list_all_devices, parent=self)
        w.done.connect(self._on_devices_loaded)
        w.finished.connect(self._on_refresh_finished)
        w.start()
        self.set_busy(+1)

    def _on_refresh_finished(self) -> None:
        self.set_busy(-1)
        self.refresh_btn.setEnabled(True)
        self.refresh_btn.setText("↻ 刷新设备")

    def _on_devices_loaded(self, result) -> None:
        if isinstance(result, BaseException):
            self.show_status(f"✗ 读取设备失败:{result}", error=True)
            self.log_result(False, str(result))
            return
        self.log_result(True)
        self._devices = [from_entry(entry, transport) for entry, transport in result]
        labels = [d.label for d in self._devices]
        self.device_combo.blockSignals(True)
        self.device_combo.clear()
        self.device_combo.addItems(labels)
        if not labels:
            self.device_combo.setCurrentIndex(-1)
            self._select_device(None)
        else:
            keep = self.current_device
            idx = 0
            if keep is not None:
                for i, d in enumerate(self._devices):
                    if d.serial == keep.serial and d.transport == keep.transport:
                        idx = i
                        break
            self.device_combo.setCurrentIndex(idx)
            self._select_device(self._devices[idx])
        self.device_combo.blockSignals(False)

    def _on_device_selected(self, idx: int) -> None:
        if idx < 0:
            return
        dev = self._devices[idx] if 0 <= idx < len(self._devices) else None
        self._select_device(dev)

    def _select_device(self, dev: Device | None) -> None:
        self.current_device = dev
        if dev is None:
            self.show_status("未连接设备 — 请用数据线连接手机并开启 USB 调试", error=True)
        else:
            kind = "鸿蒙" if dev.is_hdc else "安卓"
            self.show_status(f"已连接 {dev.serial}({kind})")
        for panel in self._panels:
            panel.on_device_changed(dev)

    def _on_tab_changed(self, idx: int) -> None:
        if 0 <= idx < len(self._panels) and self.current_device is not None:
            self._panels[idx].refresh()

    # ------------------------------------------------------------------ #
    # 日志 / 状态(tcode 风格)
    # ------------------------------------------------------------------ #
    def log_command(self, text: str) -> None:
        self._log.appendPlainText(f"\n[{datetime.now():%H:%M:%S}] $ {text}")

    def log_result(self, ok: bool, note: str = "") -> None:
        suffix = f"  ✗ {note}" if not ok and note else ""
        self._log.appendPlainText(
            f"[{datetime.now():%H:%M:%S}] ⏎ {'ok' if ok else 'failed'}{suffix}")

    def log_line(self, text: str) -> None:
        """一般事件日志(如配置助手的服务状态)。"""
        self._log.appendPlainText(f"[{datetime.now():%H:%M:%S}] {text}")

    def set_busy(self, delta: int) -> None:
        self._busy = max(0, self._busy + delta)
        self._busy_lbl.setVisible(self._busy > 0)

    def show_status(self, msg: str, error: bool = False) -> None:
        self._status_lbl.setText(msg)
        self._status_lbl.setStyleSheet(
            "color: #f87171;" if error else "color: #e6e8eb;")

    def _update_tool_label(self) -> None:
        status = tool_status()

        def mark(lbl: QLabel, name: str, ok: bool) -> None:
            lbl.setText(f"{name}: {'✓' if ok else '✗'}")
            lbl.setObjectName("toolOk" if ok else "toolMiss")
            lbl.style().unpolish(lbl)
            lbl.style().polish(lbl)

        mark(self._adb_chip, "adb", bool(status["adb"]))
        mark(self._hdc_chip, "hdc", bool(status["hdc"]))

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt 命名)
        """退出前回收后台服务(如配置助手)。"""
        for panel in self._panels:
            if hasattr(panel, "on_close"):
                panel.on_close()
        super().closeEvent(event)


def launch() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("野兔v2")
    app.setStyleSheet(QSS)
    win = MainWindow()
    win.show()
    return app.exec()
