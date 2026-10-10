# -*- coding: utf-8 -*-
"""深色主题(样式参考 tcode GUI):配色常量 + 全局 QSS。"""
from __future__ import annotations

from PyQt6.QtGui import QColor

GREEN = QColor("#4ade80")
RED = QColor("#f87171")
YELLOW = QColor("#fbbf24")
DIM = QColor("#8b93a0")

BLUE = "#2e70ef"  # 主色:主按钮 / 选中 Tab 下划线 / 表格选中

QSS = """
QWidget {
    background-color: #171a1f;
    color: #e6e8eb;
    font-family: "PingFang SC", "Microsoft YaHei", "Helvetica Neue", "Segoe UI", sans-serif;
    font-size: 13px;
}
QMainWindow { background-color: #171a1f; }

#header { background-color: #1d2128; border-bottom: 1px solid #2a2f38; }
#brand { font-size: 20px; font-weight: 700; color: #ffffff; letter-spacing: 1px; }
#subtitle { color: #8b93a0; font-size: 12px; }
#version { color: #6f7784; font-size: 12px; font-family: "Menlo", "Consolas", monospace; }
#busy { color: #fbbf24; font-size: 12px; }
#panelTitle { font-size: 16px; font-weight: 600; color: #ffffff; }
#hint { font-size: 12px; color: #8b93a0; }
#kvKey { color: #8b93a0; }
#kvVal { color: #e6e8eb; }

/* 状态徽标 */
#chipOk, #chipWarn, #chipErr, #chipDim {
    border-radius: 8px; padding: 6px 14px; font-size: 13px; font-weight: 600;
}
#chipOk   { background-color: #16321f; color: #4ade80; border: 1px solid #1f5c35; }
#chipWarn { background-color: #3a2c12; color: #fbbf24; border: 1px solid #6b5316; }
#chipErr  { background-color: #3a1518; color: #f87171; border: 1px solid #6b2429; }
#chipDim  { background-color: #20242b; color: #8b93a0; border: 1px solid #333a45; }

/* 顶部设备栏 + 内置工具状态 */
#devbar { background-color: #1d2128; border-bottom: 1px solid #2a2f38; }
#toolOk  { color: #4ade80; font-family: "Menlo", "Consolas", monospace; font-size: 12px; }
#toolMiss { color: #f87171; font-family: "Menlo", "Consolas", monospace; font-size: 12px; }

QTabWidget::pane { border: none; background-color: #171a1f; }
QTabBar::tab {
    background: transparent; color: #9aa3ad; padding: 10px 20px;
    border-bottom: 2px solid transparent;
}
QTabBar::tab:selected { color: #ffffff; border-bottom: 2px solid #2e70ef; }
QTabBar::tab:hover { color: #d0d5dc; }

QGroupBox {
    border: 1px solid #2a2f38; border-radius: 8px; margin-top: 12px;
    padding-top: 8px; background-color: #1b1f26;
}
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; color: #9aa3ad; }

QPushButton {
    background-color: #262b33; color: #e6e8eb; border: 1px solid #333a45;
    border-radius: 6px; padding: 7px 16px;
}
QPushButton:hover { background-color: #2f3540; border-color: #4a5360; }
QPushButton:pressed { background-color: #242932; }
QPushButton:disabled { color: #5c6470; background-color: #20242b; }
QPushButton#primary {
    background-color: #2e70ef; border-color: #2e70ef; color: #ffffff; font-weight: 600;
}
QPushButton#primary:hover { background-color: #3d7cf2; }
QPushButton#primary:disabled { background-color: #24437e; color: #8fa8d8; }

QCheckBox { color: #c0c6cf; }
QCheckBox::indicator {
    width: 15px; height: 15px; border: 1px solid #333a45; border-radius: 4px;
    background-color: #20242b;
}
QCheckBox::indicator:checked { background-color: #2e70ef; border-color: #2e70ef; }

QLineEdit, QComboBox {
    background-color: #20242b; color: #e6e8eb; border: 1px solid #333a45;
    border-radius: 6px; padding: 7px 10px; selection-background-color: #2e70ef;
}
QLineEdit:focus, QComboBox:focus { border-color: #2e70ef; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView {
    background-color: #20242b; color: #e6e8eb; border: 1px solid #333a45;
    selection-background-color: #2e70ef;
}

QTableWidget {
    background-color: #1b1f26; alternate-background-color: #1f242c;
    gridline-color: #2a2f38; border: 1px solid #2a2f38; border-radius: 6px;
    color: #d6dae0;
}
QHeaderView::section {
    background-color: #232830; color: #9aa3ad; padding: 6px 8px; border: none;
    border-right: 1px solid #2a2f38; border-bottom: 1px solid #2a2f38;
    font-weight: 600;
}
QTableWidget::item:selected { background-color: #2e70ef; color: #ffffff; }

QPlainTextEdit, QTextEdit {
    background-color: #14171c; color: #c9d1d9; border: 1px solid #2a2f38;
    border-radius: 6px; font-family: "Menlo", "Consolas", monospace; font-size: 12px;
}

QScrollBar:vertical { background: #1b1f26; width: 10px; }
QScrollBar::handle:vertical { background: #3a4150; border-radius: 5px; min-height: 30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { background: #1b1f26; height: 10px; }
QScrollBar::handle:horizontal { background: #3a4150; border-radius: 5px; min-width: 30px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

QStatusBar {
    background-color: #1d2128; color: #8b93a0; border-top: 1px solid #2a2f38;
}
QMainWindow::separator {
    background: #1d2128; height: 2px; width: 2px;
}
QMainWindow::separator:hover { background: #2e70ef; }
QDockWidget::title {
    background-color: #1d2128; padding: 6px 10px; color: #9aa3ad;
}
QDockWidget { color: #9aa3ad; titlebar-close-icon: none; }
QMessageBox { background-color: #1b1f26; }
QMenu { background-color: #20242b; border: 1px solid #333a45; }
QMenu::item:selected { background-color: #2e70ef; }
"""
