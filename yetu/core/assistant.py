# -*- coding: utf-8 -*-
"""代理配置助手:轻量 HTTP 服务,手机扫码打开配置页。

零新依赖(标准库 http.server)。手机与电脑同一 Wi-Fi,扫码后页面提供:
  - 代理地址(IP / 端口)一键复制
  - 按手机 UA 分流的 Android / iOS 设置步骤
  - 抓包端口在线状态(电脑上 Charles / mitmproxy 是否在监听),5 秒自动刷新

对外接口:
    ast = ProxyAssistant(proxy_host, proxy_port, serve_port=8770)
    ast.on_log = cb(str)
    ast.start() / ast.stop() / ast.started / ast.last_error
    ast.url                 # http://<lan_ip>:<serve_port>/proxy
"""
from __future__ import annotations

import http.server
import json
import socket
import socketserver
import threading
import urllib.parse
from pathlib import Path

PAGE = Path(__file__).with_name("assistant_page.html").read_text(encoding="utf-8")


def get_lan_ip() -> str:
    """本机局域网 IP(UDP connect 探测,失败回退 127.0.0.1)。"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(1)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def port_listening(host: str, port: int, timeout: float = 0.8,
                   confirm_delay: float = 0.15) -> bool:
    """探测 host:port 是否有服务在监听(判断抓包工具是否在跑)。

    连续两次连接都成功才判定在线:监听刚关闭时内核 accept 队列的
    残留连接会让端口短暂还能握手成功,第二次连接即被拒绝;
    真实的抓包服务则会持续接受连接。
    """
    import time
    for _ in range(2):
        try:
            with socket.create_connection((host, port), timeout=timeout):
                pass
        except OSError:
            return False
        time.sleep(confirm_delay)
    return True


def _ua_kind(ua: str) -> str:
    low = (ua or "").lower()
    if "iphone" in low or "ipad" in low or "ipod" in low:
        return "ios"
    if "android" in low:
        return "android"
    return "both"


class _ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True

    def server_bind(self) -> None:
        """跳过 HTTPServer.server_bind 中的 socket.getfqdn() 反向 DNS 查询 ——
        在无反向解析的网络(部分内网 / CI runner)会阻塞 30 秒以上,
        导致配置助手迟迟不可用。本服务不需要 server_name 的 FQDN,直接用 IP。"""
        socketserver.TCPServer.server_bind(self)
        host, port = self.server_address[:2]
        self.server_name = host
        self.server_port = port

    def handle_error(self, request, client_address):
        pass  # 客户端断开等噪音


class ProxyAssistant:
    """配置助手服务(可实例化;一个实例一个端口)。"""

    def __init__(self, proxy_host: str, proxy_port: int, serve_port: int = 8770,
                 bind: str = "0.0.0.0"):
        self.proxy_host = proxy_host
        self.proxy_port = proxy_port
        self.serve_port = serve_port
        self.bind = bind
        self.on_log = None
        self.last_error = ""
        self.started = threading.Event()
        self._httpd: _ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def url(self) -> str:
        return f"http://{get_lan_ip()}:{self.serve_port}/proxy"

    @property
    def running(self) -> bool:
        return self._httpd is not None

    def status(self) -> dict:
        """抓包端口在线状态(给 /api/status 与页面刷新用)。"""
        online = port_listening(get_lan_ip(), self.proxy_port)
        return {"listening": online, "host": self.proxy_host,
                "port": self.proxy_port}

    def start(self) -> None:
        if self.running:
            return
        self.last_error = ""
        self.started.clear()
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        httpd, self._httpd = self._httpd, None
        if httpd is None:
            return
        try:
            httpd.shutdown()
        except Exception:
            pass
        try:
            httpd.server_close()
        except Exception:
            pass
        self._log("配置助手已停止")

    # ---------------- 内部 ----------------
    def _log(self, msg: str) -> None:
        if self.on_log:
            try:
                self.on_log(msg)
            except Exception:
                pass

    def _serve(self) -> None:
        try:
            assistant = self
            httpd = _ThreadingHTTPServer(
                (self.bind, self.serve_port),
                _make_handler(assistant))
            self._httpd = httpd
            self.started.set()
            self._log(f"配置助手已启动 {self.url}")
            httpd.serve_forever()
        except Exception as e:  # noqa: BLE001
            self.last_error = str(e)
            self.started.set()
            self._log(f"配置助手启动失败: {e}")


def _make_handler(assistant: ProxyAssistant) -> type[http.server.BaseHTTPRequestHandler]:
    class AssistantHandler(http.server.BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            assistant._log("[%s] %s" % (self.client_address[0], fmt % args))

        def _html(self, body: str, status: int = 200) -> None:
            data = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", len(data))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            path = urllib.parse.unquote(urllib.parse.urlparse(self.path).path)
            if path in ("/proxy", "/", "/index.html"):
                self._render_page()
            elif path == "/api/status":
                body = json.dumps(assistant.status()).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", len(body))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_error(404)

        def _render_page(self):
            host, port = assistant.proxy_host, assistant.proxy_port
            kind = _ua_kind(self.headers.get("User-Agent", ""))
            if kind == "android":
                steps = _SECTION_ANDROID
                title = "Android 设置步骤"
            elif kind == "ios":
                steps = _SECTION_IOS
                title = "iPhone 设置步骤"
            else:
                steps = _SECTION_ANDROID + _SECTION_IOS
                title = "设置步骤(Android / iPhone)"
            # 注意顺序: 先插步骤片段(其内部含 __HOST__/__PORT__ 字面量),
            # 再统一替换地址占位符
            html = (PAGE
                    .replace("__STEPS_TITLE__", title)
                    .replace("__STEPS__", steps)
                    .replace("__HOST__", host)
                    .replace("__PORT__", str(port)))
            self._html(html)

    return AssistantHandler


# 两种系统的设置步骤片段(UA 无法识别时两段都给)
_SECTION_ANDROID = """
<div class="card">
  <h2>Android 设置步骤</h2>
  <ol>
    <li>打开 <b>设置 → WLAN</b>,<b>长按</b>当前连接的 Wi-Fi</li>
    <li>点「修改网络」→ 展开「高级选项」</li>
    <li>代理选「手动」,主机名填 <b>__HOST__</b>,端口填 <b>__PORT__</b></li>
    <li>保存后打开任意网页,电脑抓包工具出现请求即成功</li>
  </ol>
</div>
"""

_SECTION_IOS = """
<div class="card">
  <h2>iPhone 设置步骤</h2>
  <ol>
    <li>打开 <b>设置 → 无线局域网</b>,点当前 Wi-Fi 右侧 <b>ⓘ</b></li>
    <li>拉到最底部点「<b>配置代理</b>」→ 选「手动」</li>
    <li>服务器填 <b>__HOST__</b>,端口填 <b>__PORT__</b>,鉴定留空</li>
    <li>点「存储」立即生效;抓完回来选「关闭」即可恢复直连</li>
  </ol>
</div>
"""
