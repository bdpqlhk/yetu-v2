# -*- coding: utf-8 -*-
"""通用小组件:等宽字体、只读表格、键值表单、状态徽标。"""
from __future__ import annotations

import sys
from typing import Callable, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QAbstractItemView, QFormLayout, QHBoxLayout, QHeaderView, QLabel,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from .theme import DIM  # noqa: F401  (常用色再导出,面板可直接 from widgets import)


def make_mono(plain) -> None:
    """等宽字体(Windows → Consolas,macOS/Linux → Menlo)。"""
    family = "Consolas" if sys.platform == "win32" else "Menlo"
    f = QFont(family)
    f.setStyleHint(QFont.StyleHint.Monospace)
    plain.setFont(f)


def make_table(headers: list[str], stretch_col: int = -1) -> QTableWidget:
    """构造只读表格(隔行变色,行选中)。"""
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setAlternatingRowColors(True)
    table.verticalHeader().setVisible(False)
    table.setWordWrap(False)
    header = table.horizontalHeader()
    header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    if 0 <= stretch_col < len(headers):
        header.setSectionResizeMode(stretch_col, QHeaderView.ResizeMode.Stretch)
    return table


def set_rows(table: QTableWidget, rows: list[list[str]],
             color_fn: Optional[Callable[[int, int, str], Optional[QColor]]] = None) -> None:
    """整体重填表格。color_fn(r, c, value) 返回前景色或 None。"""
    table.setRowCount(0)
    for r, row in enumerate(rows):
        table.insertRow(r)
        for c, val in enumerate(row):
            item = QTableWidgetItem(val)
            if color_fn and (color := color_fn(r, c, val)):
                item.setForeground(color)
            table.setItem(r, c, item)


def fill_form(form: QFormLayout, pairs: list[tuple[str, str]]) -> list[QLabel]:
    """重填 QFormLayout 的键值行;返回值 Label 便于着色。"""
    while form.rowCount():
        form.removeRow(0)
    labels: list[QLabel] = []
    for key, val in pairs:
        k = QLabel(key)
        k.setObjectName("kvKey")
        v = QLabel(val)
        v.setObjectName("kvVal")
        v.setWordWrap(True)
        v.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        form.addRow(k, v)
        labels.append(v)
    return labels


def chip(text: str = "", kind: str = "chipDim") -> QLabel:
    """状态徽标(圆角色块),配合 set_chip 切换语义色。"""
    lbl = QLabel(text)
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setObjectName(kind)
    return lbl


def set_chip(lbl: QLabel, text: str, kind: str) -> None:
    """更新徽标文案与语义色(objectName 变更后需重刷样式)。"""
    lbl.setText(text)
    lbl.setObjectName(kind)
    lbl.style().unpolish(lbl)
    lbl.style().polish(lbl)


def hbar(*widgets: QWidget, stretch_before_last: bool = False) -> QHBoxLayout:
    """快速拼一行控件;传入 None 表示 addStretch。"""
    lay = QHBoxLayout()
    for i, w in enumerate(widgets):
        if w is None:
            lay.addStretch(1)
            continue
        lay.addWidget(w)
        if stretch_before_last and i == len(widgets) - 1:
            lay.addStretch(1)
    return lay
