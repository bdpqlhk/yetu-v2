# -*- coding: utf-8 -*-
"""设备抽象层:把「信息 / 应用 / 网络 / 代理 / 安装」等功能组织成对设备的方法。

Device 只暴露功能方法,底层调用由 Connector(Adb/Hdc)完成。
新增设备能力时:在下面加方法,或直接在对应 UI 面板里复用 Connector。
"""
from __future__ import annotations

from dataclasses import dataclass

from . import adb as _adb
from .adb import Adb, DeviceEntry


@dataclass
class Device:
    """一台已连接设备。serial 唯一,transport 决定走 adb 还是 hdc。"""
    serial: str
    transport: str          # 'adb' | 'hdc'
    model: str = ""
    status: str = "device"

    @property
    def is_hdc(self) -> bool:
        return self.transport == "hdc"

    @property
    def label(self) -> str:
        kind = "鸿蒙" if self.is_hdc else "安卓"
        model = f" ({self.model})" if self.model else ""
        return f"{self.serial} [{kind}]{model}"

    def connector(self) -> Adb:
        return _adb.get_connector(self.transport)


def from_entry(entry: DeviceEntry, transport: str) -> Device:
    return Device(serial=entry.serial, transport=transport, model=entry.model, status=entry.status)


# --------------------------------------------------------------------------- #
# 手机信息
# --------------------------------------------------------------------------- #
# 各传输方式的属性键映射:(标签, adb键, hdc键)
_INFO_KEYS = [
    ("型号", "ro.product.model", "const.product.model"),
    ("厂商", "ro.product.manufacturer", "const.product.manufacturer"),
    ("系统版本", "ro.build.version.release", "const.ohos.version"),
    ("软件版本", "ro.build.display.id", "const.product.software.version"),
    ("API 级别", "ro.build.version.sdk", "const.ohos.apiversion"),
    ("序列号", "ro.serialno", "const.product.deviceid"),
    ("ABI", "ro.product.cpu.abi", "const.product.cpu.abilist"),
]

_EXTRA_ADB = [
    ("分辨率", "wm size"),
    ("屏幕密度", "wm density"),
]

_EXTRA_HDC = [
    ("分辨率", "wm size"),
]


def get_device_info(dev: Device) -> list[tuple[str, str]]:
    """返回 [(属性名, 值)] 列表,用于界面展示。单项失败显示 '—'。"""
    conn = dev.connector()
    rows: list[tuple[str, str]] = []

    for label, adb_key, hdc_key in _INFO_KEYS:
        key = hdc_key if dev.is_hdc else adb_key
        value = conn.get_prop(dev.serial, key) or "—"
        rows.append((label, value))

    for label, cmd in (_EXTRA_HDC if dev.is_hdc else _EXTRA_ADB):
        try:
            raw = conn.shell(dev.serial, cmd, timeout=15.0)
            rows.append((label, raw.splitlines()[0].strip() if raw else "—"))
        except Exception:
            rows.append((label, "—"))

    try:  # 电池
        bat = conn.shell(dev.serial, "dumpsys battery | grep -E 'level|status' | head -4", timeout=15.0)
        level, status = "—", "—"
        for line in bat.splitlines():
            if "level" in line:
                level = line.split(":", 1)[-1].strip() + "%"
            if "status" in line:
                status = line.split(":", 1)[-1].strip()
        rows.append(("电池电量", f"{level} ({status})"))
    except Exception:
        rows.append(("电池电量", "—"))

    return rows


# --------------------------------------------------------------------------- #
# 应用列表
# --------------------------------------------------------------------------- #
def list_apps(dev: Device, third_party_only: bool = True) -> list[tuple[str, str]]:
    """返回 [(包名, 版本)]。包多时版本查询慢,这里只取前若干项的版本以提速。"""
    conn = dev.connector()
    pkgs = conn.list_packages(dev.serial, third_party_only=third_party_only)
    # 版本号逐包查询较慢:最多为前 60 个查版本,其余标记为待查
    rows: list[tuple[str, str]] = []
    for i, pkg in enumerate(pkgs):
        if i < 60:
            rows.append((pkg, conn.package_version(dev.serial, pkg)))
        else:
            rows.append((pkg, "—"))
    return rows


# --------------------------------------------------------------------------- #
# 网络信息
# --------------------------------------------------------------------------- #
def get_network_text(dev: Device) -> str:
    return dev.connector().network_text(dev.serial)


# --------------------------------------------------------------------------- #
# 全局代理
# --------------------------------------------------------------------------- #
def get_proxy(dev: Device) -> str:
    return dev.connector().get_global_proxy(dev.serial)


def set_proxy(dev: Device, host: str, port: str) -> None:
    dev.connector().set_global_proxy(dev.serial, host, port)


def clear_proxy(dev: Device) -> None:
    dev.connector().clear_global_proxy(dev.serial)
