# -*- coding: utf-8 -*-
"""面板六:代理配置助手。

电脑起一个轻量 HTTP 服务,展示指向 /proxy 配置页的二维码;
手机扫码打开页面:复制代理地址、看对应系统的设置步骤、
确认抓包端口在线。服务跑守护线程,日志经信号回主线程。
"""
from __future__ import annotations

from PyQt6.QtCore import QUrl, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QDesktopServices, QImage, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QVBoxLayout,
)

from ...core.assistant import ProxyAssistant, get_lan_ip
from ...qrterm import qr_matrix
from ..widgets import chip, set_chip
from .base import PanelBase

_DEFAULT_SERVE_PORT = 8770
_DEFAULT_PROXY_PORT = 8888


class AssistantPanel(PanelBase):
    name = "配置助手"

    # 服务线程 -> 主线程的日志桥
    _log_sig = pyqtSignal(str)

    def _build(self) -> None:
        self._log_sig.connect(self._write_log)
        self._assistant: ProxyAssistant | None = None
        self._poll: QTimer | None = None

        root = QHBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # ---- 左列:标题 + 控制 ----
        left = QVBoxLayout()
        left.setSpacing(12)

        title = QLabel("代理配置助手")
        title.setObjectName("panelTitle")
        hint = QLabel("手机扫码打开配置页:复制代理地址、按系统查看设置步骤、确认抓包服务在线")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        left.addWidget(title)
        left.addWidget(hint)

        group = QGroupBox("助手服务")
        form = QFormLayout(group)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        self._serve_port = QLineEdit(str(_DEFAULT_SERVE_PORT))
        self._proxy_port = QLineEdit(str(_DEFAULT_PROXY_PORT))
        form.addRow("页面端口:", self._serve_port)
        form.addRow("代理端口:", self._proxy_port)

        row = QHBoxLayout()
        self._chip = chip("○ 未启动", "chipDim")
        self._start_btn = QPushButton("启动助手")
        self._start_btn.setObjectName("primary")
        self._start_btn.clicked.connect(self.start)
        self._stop_btn = QPushButton("停止助手")
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self.stop)
        row.addWidget(self._chip)
        row.addStretch(1)
        row.addWidget(self._start_btn)
        row.addWidget(self._stop_btn)
        form.addRow(row)

        url_row = QHBoxLayout()
        self._url_lbl = QLabel("—")
        self._url_lbl.setObjectName("urlLabel")
        copy = QPushButton("复制链接")
        copy.clicked.connect(self._copy_url)
        open_btn = QPushButton("打开页面(电脑预览)")
        open_btn.clicked.connect(self._open_page)
        url_row.addWidget(self._url_lbl, 1)
        url_row.addWidget(copy)
        url_row.addWidget(open_btn)
        form.addRow("配置页:", url_row)

        note = QLabel("前提:电脑与手机同一 Wi-Fi;抓包工具(Charles / mitmproxy)已在电脑上启动,\n"
                      "并勾选允许局域网连接。二维码指向本机配置页,局域网内免登录直达。")
        note.setObjectName("hint")
        note.setWordWrap(True)
        form.addRow(note)
        left.addWidget(group)
        left.addStretch(1)
        root.addLayout(left, 3)

        # ---- 右列:二维码 ----
        qr_box = QGroupBox("手机扫码打开配置页")
        qlay = QVBoxLayout(qr_box)
        qlay.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._qr_lbl = QLabel("未启动")
        self._qr_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._qr_lbl.setMinimumSize(230, 230)
        qlay.addStretch(1)
        qlay.addWidget(self._qr_lbl)
        self._qr_hint = QLabel("启动后显示二维码\n或手机浏览器直接输入配置页地址")
        self._qr_hint.setObjectName("hint")
        self._qr_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        qlay.addWidget(self._qr_hint)
        qlay.addStretch(1)
        root.addWidget(qr_box, 2)

    # ---------------- 启停 ----------------
    def start(self) -> None:
        if self._assistant is not None and self._assistant.running:
            return
        try:
            serve_port = int(self._serve_port.text().strip())
            proxy_port = int(self._proxy_port.text().strip())
            if not (0 < serve_port < 65536 and 0 < proxy_port < 65536):
                raise ValueError
        except ValueError:
            self.app.show_status("✗ 端口必须是 1-65535 的数字", error=True)
            return

        ast = ProxyAssistant(proxy_host=get_lan_ip(), proxy_port=proxy_port,
                             serve_port=serve_port)
        ast.on_log = self._log_sig.emit
        ast.start()
        self._assistant = ast
        self._set_starting_ui()
        self._poll = QTimer(self)
        self._poll.timeout.connect(lambda: self._poll_start(ast))
        self._poll.start(80)

    def _poll_start(self, ast: ProxyAssistant) -> None:
        if not ast.started.is_set():
            return
        self._poll.stop()
        self._poll = None
        if ast.last_error:
            self._assistant = None
            self._reset_ui()
            self.app.show_status(f"✗ 助手启动失败(端口被占用?): {ast.last_error}", error=True)
            return
        self._set_running_ui(ast)

    def stop(self) -> None:
        if self._assistant is None:
            return
        self._assistant.stop()
        self._assistant = None
        self._reset_ui()
        self.app.show_status("✓ 配置助手已停止")

    def on_close(self) -> None:
        """主窗口关闭时回收服务。"""
        if self._assistant is not None:
            self._assistant.stop()
            self._assistant = None

    # ---------------- 状态切换 ----------------
    def _set_starting_ui(self) -> None:
        set_chip(self._chip, "● 启动中…", "chipWarn")
        self._start_btn.setEnabled(False)
        self._serve_port.setEnabled(False)
        self._proxy_port.setEnabled(False)

    def _set_running_ui(self, ast: ProxyAssistant) -> None:
        set_chip(self._chip, "● 运行中", "chipOk")
        self._url_lbl.setText(ast.url)
        self._stop_btn.setEnabled(True)
        self._qr_lbl.setPixmap(self._render_qr(ast.url))
        self._qr_hint.setText("手机扫码 · 或浏览器输入上方地址")
        self.app.show_status(f"✓ 配置助手运行中: {ast.url}")

    def _reset_ui(self) -> None:
        set_chip(self._chip, "○ 未启动", "chipDim")
        self._url_lbl.setText("—")
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._serve_port.setEnabled(True)
        self._proxy_port.setEnabled(True)
        self._qr_lbl.setText("未启动")
        self._qr_lbl.setPixmap(QPixmap())
        self._qr_hint.setText("启动后显示二维码\n或手机浏览器直接输入配置页地址")

    # ---------------- 小动作 ----------------
    def refresh(self) -> None:
        """Tab 切换刷新:助手与设备无关,无需动作。"""

    def _render_qr(self, url: str) -> QPixmap:
        matrix = qr_matrix(url)
        n = len(matrix)
        scale, quiet = 6, 4
        total = (n + quiet * 2) * scale
        img = QImage(total, total, QImage.Format.Format_RGB32)
        p = QPainter(img)
        p.fillRect(0, 0, total, total, QColor("white"))
        for y in range(n):
            for x in range(n):
                if matrix[y][x]:
                    p.fillRect((x + quiet) * scale, (y + quiet) * scale,
                               scale, scale, QColor("black"))
        p.end()
        return QPixmap.fromImage(img)

    def _copy_url(self) -> None:
        from PyQt6.QtWidgets import QApplication
        url = self._url_lbl.text()
        if url and url != "—":
            QApplication.clipboard().setText(url)
            self.app.show_status(f"✓ 已复制 {url}")

    def _open_page(self) -> None:
        url = self._url_lbl.text()
        if url and url != "—":
            QDesktopServices.openUrl(QUrl(url))

    def _write_log(self, text: str) -> None:
        self.app.log_line(text)
