# -*- coding: utf-8 -*-
"""adb / hdc 命令行封装。

对外提供两个连接器类 Adb / Hdc,接口一致,便于上层统一调用:
  - devices()        设备列表
  - shell()          执行 shell 命令
  - get_prop()       读系统属性
  - list_packages()  已安装包
  - package_info()   单个包信息(版本号等)
  - get/set/clear_proxy()  全局代理
  - install()        安装 APK / HAP(支持流式进度)

adb 与 hdc 的命令差异(如 pm list vs bm list、getprop vs param get)
全部收敛在这一层,上层核心与界面无需关心连接器类型。
"""
from __future__ import annotations

import shlex
import subprocess
from dataclasses import dataclass, field

from .env import adb_path, hdc_path


class ToolNotFoundError(RuntimeError):
    """对应的 adb / hdc 不存在。"""


@dataclass
class DeviceEntry:
    """设备行(来自 devices 输出)。"""
    serial: str
    model: str = ""
    status: str = "device"


def _run(exe: str, args: list[str], timeout: float = 30.0) -> subprocess.CompletedProcess:
    """执行命令并捕获输出,失败抛 ToolNotFoundError / 命令异常。"""
    if not exe:
        raise ToolNotFoundError("未找到 adb/hdc 可执行文件")
    return subprocess.run(
        [exe, *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def _stream(exe: str, args: list[str], on_line, timeout: float | None = 120.0) -> subprocess.CompletedProcess:
    """流式执行:每行输出回调 on_line。用于安装 APK/HAP 显示进度。"""
    if not exe:
        raise ToolNotFoundError("未找到 adb/hdc 可执行文件")
    proc = subprocess.Popen(
        [exe, *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        on_line(line.rstrip("\n"))
    proc.wait(timeout=timeout)
    return proc


class Adb:
    """Android Debug Bridge 连接器。"""

    transport = "adb"

    def __init__(self, exe: str | None = None):
        self.exe = exe or adb_path()

    # ---- 设备 ----
    def devices(self, timeout: float = 15.0) -> list[DeviceEntry]:
        proc = _run(self.exe, ["devices", "-l"], timeout=timeout)
        out = (proc.stdout or "") + (proc.stderr or "")
        result: list[DeviceEntry] = []
        for raw in out.splitlines()[1:]:  # 跳过 "List of devices attached"
            raw = raw.strip()
            if not raw:
                continue
            parts = raw.split()
            serial = parts[0]
            status = parts[1] if len(parts) > 1 else "unknown"
            if status != "device" and status != "unauthorized":
                continue  # offline 等一律跳过
            model = ""
            for p in parts[2:]:
                if p.startswith("model:"):
                    model = p.split(":", 1)[1]
            result.append(DeviceEntry(serial=serial, model=model, status=status))
        return result

    # ---- shell 与属性 ----
    def shell(self, serial: str, cmd: str, timeout: float = 20.0) -> str:
        proc = _run(self.exe, ["-s", serial, "shell", cmd], timeout=timeout)
        if proc.returncode != 0:
            raise RuntimeError((proc.stderr or "").strip() or "shell 命令失败")
        return (proc.stdout or "").strip()

    def get_prop(self, serial: str, key: str, timeout: float = 15.0) -> str:
        try:
            return self.shell(serial, f"getprop {shlex.quote(key)}", timeout=timeout)
        except RuntimeError:
            return ""

    def get_all_props(self, serial: str, timeout: float = 20.0) -> dict[str, str]:
        raw = self.shell(serial, "getprop", timeout=timeout)
        props: dict[str, str] = {}
        for line in raw.splitlines():
            # 格式: [key]: [value]
            if "]: [" in line:
                line = line.strip()
                key, _, value = line[1:-1].partition("]: [")
                props[key] = value
        return props

    # ---- 应用 ----
    def list_packages(self, serial: str, third_party_only: bool = True, timeout: float = 30.0) -> list[str]:
        flag = " -3" if third_party_only else ""
        raw = self.shell(serial, f"pm list packages{flag}", timeout=timeout)
        pkgs: list[str] = []
        for line in raw.splitlines():
            line = line.strip()
            if line.startswith("package:"):
                pkgs.append(line.split(":", 1)[1])
        return sorted(pkgs)

    def package_version(self, serial: str, pkg: str, timeout: float = 20.0) -> str:
        try:
            raw = self.shell(serial, f"dumpsys package {shlex.quote(pkg)}", timeout=timeout)
        except RuntimeError:
            return "—"
        for line in raw.splitlines():
            if "versionName" in line:
                return line.split("=", 1)[-1].strip()
        return "—"

    # ---- 网络 ----
    def network_text(self, serial: str, timeout: float = 25.0) -> str:
        parts: list[str] = []
        try:
            parts.append("【接口地址】\n" + self.shell(serial, "ip addr", timeout=timeout))
        except RuntimeError:
            parts.append("【接口地址】\n(读取失败)")
        try:
            dns = self.shell(serial, "getprop | grep -E 'dns|http_proxy'", timeout=timeout)
            parts.append("【DNS / 代理属性】\n" + (dns or "(无)"))
        except RuntimeError:
            pass
        try:
            wifi = self.shell(serial, "cmd wifi status 2>/dev/null || dumpsys wifi | grep -iE 'mWifiInfo|SSID' | head -5", timeout=timeout)
            parts.append("【WiFi】\n" + (wifi or "(无)"))
        except RuntimeError:
            pass
        try:
            proxy = self.get_global_proxy(serial, timeout=timeout)
            parts.append(f"【当前全局代理】\n{proxy}")
        except Exception:
            pass
        return "\n\n".join(parts)

    # ---- 全局代理 ----
    def get_global_proxy(self, serial: str, timeout: float = 15.0) -> str:
        try:
            raw = self.shell(serial, "settings get global http_proxy", timeout=timeout)
        except RuntimeError:
            return "—"
        raw = raw.strip()
        if not raw or raw in ("null", ":0", "0.0.0.0:0"):
            return "(未设置)"
        return raw

    def set_global_proxy(self, serial: str, host: str, port: str, timeout: float = 15.0) -> None:
        if not host or not port:
            raise ValueError("代理主机和端口不能为空")
        addr = f"{host}:{port}"
        # 优先用 host/port 字段写入,兼容性更好;再写整体值
        try:
            self.shell(serial, f"settings put global http_proxy {shlex.quote(addr)}", timeout=timeout)
        except RuntimeError:
            self.shell(serial, f"settings put global global_http_proxy_host {shlex.quote(host)}", timeout=timeout)
            self.shell(serial, f"settings put global global_http_proxy_port {shlex.quote(port)}", timeout=timeout)

    def clear_global_proxy(self, serial: str, timeout: float = 15.0) -> None:
        # :0 表示清除;delete 在某些 ROM 上不生效,双保险
        try:
            self.shell(serial, "settings put global http_proxy :0", timeout=timeout)
        except RuntimeError:
            pass
        self.shell(serial, "settings delete global http_proxy", timeout=timeout)

    # ---- 安装 ----
    def install(self, serial: str, apk_path: str, on_line, timeout: float | None = 600.0) -> subprocess.CompletedProcess:
        """adb install -r -t(允许降级/测试包),流式回显进度。"""
        return _stream(
            self.exe,
            ["-s", serial, "install", "-r", "-t", apk_path],
            on_line=on_line,
            timeout=timeout,
        )


class Hdc(Adb):
    """HarmonyOS Device Connector 连接器(命令语法与 adb 有差异)。"""

    transport = "hdc"

    def __init__(self, exe: str | None = None):
        super().__init__(exe or hdc_path())

    def devices(self, timeout: float = 15.0) -> list[DeviceEntry]:
        if not self.exe:
            return []
        proc = _run(self.exe, ["list", "targets"], timeout=timeout)
        result: list[DeviceEntry] = []
        for raw in (proc.stdout or "").splitlines():
            raw = raw.strip()
            if not raw:
                continue
            # hdc 无设备时输出 "[Empty]";有设备时每行一个序列号
            if raw in ("[Empty]", "No target device"):
                continue
            result.append(DeviceEntry(serial=raw))
        return result

    def shell(self, serial: str, cmd: str, timeout: float = 20.0) -> str:
        proc = _run(self.exe, ["-t", serial, "shell", cmd], timeout=timeout)
        if proc.returncode != 0:
            raise RuntimeError((proc.stderr or "").strip() or "shell 命令失败")
        return (proc.stdout or "").strip()

    def get_prop(self, serial: str, key: str, timeout: float = 15.0) -> str:
        try:
            return self.shell(serial, f"param get {shlex.quote(key)}", timeout=timeout)
        except RuntimeError:
            return ""

    def get_all_props(self, serial: str, timeout: float = 20.0) -> dict[str, str]:
        # HarmonyOS: param get 需要逐个取,这里直接返回空映射,避免超时
        return {}

    def list_packages(self, serial: str, third_party_only: bool = True, timeout: float = 30.0) -> list[str]:
        # HarmonyOS 用 bm 工具;不加 -3,后面按需过滤
        raw = self.shell(serial, "bm list -p", timeout=timeout)
        pkgs: list[str] = []
        for line in raw.splitlines():
            pkg = line.strip()
            if pkg:
                pkgs.append(pkg)
        return sorted(set(pkgs))

    def package_version(self, serial: str, pkg: str, timeout: float = 20.0) -> str:
        try:
            raw = self.shell(serial, f"bm dump -n {shlex.quote(pkg)}", timeout=timeout)
        except RuntimeError:
            return "—"
        for line in raw.splitlines():
            if "versionName" in line or "versionCode" in line:
                return line.split(":", 1)[-1].strip()
        return "—"

    def network_text(self, serial: str, timeout: float = 25.0) -> str:
        parts: list[str] = []
        try:
            parts.append("【接口地址】\n" + self.shell(serial, "ifconfig", timeout=timeout))
        except RuntimeError:
            parts.append("【接口地址】\n(读取失败)")
        try:
            proxy = self.get_global_proxy(serial, timeout=timeout)
            parts.append(f"【当前全局代理】\n{proxy}")
        except Exception:
            pass
        return "\n\n".join(parts)

    def set_global_proxy(self, serial: str, host: str, port: str, timeout: float = 15.0) -> None:
        if not host or not port:
            raise ValueError("代理主机和端口不能为空")
        addr = f"{host}:{port}"
        self.shell(serial, f"settings put global http_proxy {shlex.quote(addr)}", timeout=timeout)

    def install(self, serial: str, hap_path: str, on_line, timeout: float | None = 600.0) -> subprocess.CompletedProcess:
        return _stream(self.exe, ["-t", serial, "install", hap_path], on_line=on_line, timeout=timeout)


def get_connector(transport: str) -> Adb:
    """按设备传输方式返回连接器实例。"""
    if transport == "hdc":
        return Hdc()
    return Adb()


def build_connector(serial: str) -> Adb | None:
    """自动探测:先试 adb,再试 hdc,返回能连上的连接器。"""
    adb, hdc = Adb(), Hdc()
    for conn in (adb, hdc):
        if conn.exe:
            try:
                if any(d.serial == serial for d in conn.devices()):
                    return conn
            except Exception:
                continue
    return None


def list_all_devices() -> list[tuple[DeviceEntry, str]]:
    """汇总 adb + hdc 的设备,返回 [(DeviceEntry, transport)]。

    同一台鸿蒙设备可能同时出现在 adb 与 hdc 里,按 (serial, transport)
    去重,界面可分别以「安卓 / 鸿蒙」标识展示。
    """
    seen: set[tuple[str, str]] = set()
    result: list[tuple[DeviceEntry, str]] = []
    for conn in (Adb(), Hdc()):
        if not conn.exe:
            continue
        try:
            for dev in conn.devices():
                key = (dev.serial, conn.transport)
                if key not in seen:
                    seen.add(key)
                    result.append((dev, conn.transport))
        except Exception:
            continue
    return result
