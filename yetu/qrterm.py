#!/usr/bin/env python3
"""
qrterm - 零依赖的终端二维码
============================
只用 Python 标准库实现 QR 编码(字节模式, 版本 1-10, 纠错级别 M)
和终端渲染(ANSI 半块字符, 明暗双色保证对比度, 适配深色/浅色主题)。

公开接口:
    qr_matrix(text)      -> list[list[bool]]  (True = 深色模块)
    print_qr(text)       -> 直接打印到终端(自动选择渲染方式)
    render_ansi(matrix)  -> ANSI 彩色字符串(彩色终端)
    render_ascii(matrix) -> 纯 ASCII 字符串(重定向/不支持 ANSI 时)

参考: ISO/IEC 18004; 编码结构移植自 Nayuki QR-Code-generator (MIT)。
"""

from __future__ import annotations

import itertools
import os
import sys

# ── 纠错级别 M 的版本表: 版本 -> (总数据码字, 每块 EC 码字, [(块数, 每块数据码字)]) ──
_EC_M = {
    1: (16, 10, [(1, 16)]),
    2: (28, 16, [(1, 28)]),
    3: (44, 26, [(1, 44)]),
    4: (64, 18, [(2, 32)]),
    5: (86, 24, [(2, 43)]),
    6: (108, 16, [(4, 27)]),
    7: (124, 18, [(4, 31)]),
    8: (154, 22, [(2, 38), (2, 39)]),
    9: (182, 22, [(3, 36), (2, 37)]),
    10: (216, 26, [(4, 43), (1, 44)]),
}

# 各版本对齐图案中心坐标(V1 无; 与定位/时序图案重叠的按规范省略)
_ALIGNMENT = {
    2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30], 6: [6, 34],
    7: [6, 22, 38], 8: [6, 24, 42], 9: [6, 26, 46], 10: [6, 28, 50],
}

# 各版本剩余位数量(v2-6 为 7, 其余为 0)
_REMAINDER_BITS = {1: 0, 2: 7, 3: 7, 4: 7, 5: 7, 6: 7, 7: 0, 8: 0, 9: 0, 10: 0}

ECC_LEVEL_BITS = {"L": 1, "M": 0, "Q": 3, "H": 2}  # 格式信息中的 2 bit 编码
_FORMAT_MASK = 0x5412          # 格式信息异或掩码
_FORMAT_BCH_GEN = 0x537        # 格式信息 BCH 生成多项式
_VERSION_BCH_GEN = 0x1F25      # 版本信息 BCH 生成多项式


# ── GF(256) 伽罗瓦域运算(Reed-Solomon 纠错用) ─────────────────

def _build_gf_tables():
    exp = [0] * 512
    log = [0] * 256
    x = 1
    for i in range(255):
        exp[i] = x
        log[x] = i
        x <<= 1
        if x & 0x100:
            x ^= 0x11D  # QR 本原多项式
    for i in range(255, 512):
        exp[i] = exp[i - 255]
    return exp, log


_GF_EXP, _GF_LOG = _build_gf_tables()


def _gf_mul(x: int, y: int) -> int:
    if x == 0 or y == 0:
        return 0
    return _GF_EXP[_GF_LOG[x] + _GF_LOG[y]]


def _poly_mul(p: list[int], q: list[int]) -> list[int]:
    out = [0] * (len(p) + len(q) - 1)
    for i, a in enumerate(p):
        if a == 0:
            continue
        for j, b in enumerate(q):
            if b != 0:
                out[i + j] ^= _gf_mul(a, b)
    return out


def _rs_generator(degree: int) -> list[int]:
    """RS 生成多项式系数(最高次在前): ∏ (x - α^i)。"""
    poly = [1]
    root = 1
    for _ in range(degree):
        poly = _poly_mul(poly, [1, root])
        root = _gf_mul(root, 2)
    return poly


def _rs_encode(data: list[int], degree: int) -> list[int]:
    """多项式除法取余, 得到 degree 个 EC 码字。"""
    gen = _rs_generator(degree)
    buf = data + [0] * degree
    for i in range(len(data)):
        factor = buf[i]
        if factor == 0:
            continue
        for j in range(1, len(gen)):
            buf[i + j] ^= _gf_mul(gen[j], factor)
    return buf[-degree:]


# ── 位流与数据编码 ───────────────────────────────────────────

def _encode_segment(data: bytes, version: int) -> list[int]:
    """模式头 + 字符计数 + 数据 + 终止符 + 填充, 输出恰好占满全部数据码字。"""
    total_data_cw = _EC_M[version][0]
    capacity = total_data_cw * 8
    bits: list[int] = []

    def append(value: int, length: int) -> None:
        for i in range(length - 1, -1, -1):
            bits.append((value >> i) & 1)

    append(0b0100, 4)                                  # 字节模式
    append(len(data), 16 if version >= 10 else 8)      # 字符计数
    for b in data:
        append(b, 8)
    append(0, min(4, capacity - len(bits)))            # 终止符
    if len(bits) % 8:                                  # 补齐字节边界
        append(0, 8 - len(bits) % 8)
    data_cw = []
    for i in range(0, len(bits), 8):
        byte = 0
        for b in bits[i:i + 8]:
            byte = (byte << 1) | b
        data_cw.append(byte)
    pads = itertools.cycle([0xEC, 0x11])               # 交替填充字节
    while len(data_cw) < total_data_cw:
        data_cw.append(next(pads))
    return data_cw


def _add_ec(data_cw: list[int], version: int) -> list[int]:
    """分块计算 EC 码字, 数据与 EC 分别按列交织。"""
    _, ec_per_block, blocks = _EC_M[version]
    chunks, pos = [], 0
    for count, size in blocks:
        for _ in range(count):
            chunks.append(data_cw[pos:pos + size])
            pos += size
    ec_chunks = [_rs_encode(chunk, ec_per_block) for chunk in chunks]
    out: list[int] = []
    for i in range(max(size for _, size in blocks)):   # 数据码字逐列交织
        for chunk in chunks:
            if i < len(chunk):
                out.append(chunk[i])
    for i in range(ec_per_block):                      # EC 码字逐列交织
        for ec in ec_chunks:
            out.append(ec[i])
    return out


# ── 功能图案与矩阵构建 ────────────────────────────────────────

def _build_function_modules(size: int):
    """返回 (modules, is_function): 功能图案固定为规范值, 其余留白数据区。"""
    version = (size - 17) // 4
    modules = [[False] * size for _ in range(size)]
    fn = [[False] * size for _ in range(size)]

    def set_fn(y: int, x: int, dark: bool) -> None:
        modules[y][x] = dark
        fn[y][x] = True

    def finder(cx: int, cy: int) -> None:
        for dy in range(-4, 5):        # 7x7 图案 + 1 圈分隔符
            for dx in range(-4, 5):
                y, x = cy + dy, cx + dx
                if 0 <= y < size and 0 <= x < size:
                    dist = max(abs(dy), abs(dx))
                    set_fn(y, x, dist not in (2, 4))

    finder(3, 3)
    finder(size - 4, 3)
    finder(3, size - 4)
    for i in range(size):              # 时序图案(明暗交替)
        if not fn[6][i]:
            set_fn(6, i, i % 2 == 0)
        if not fn[i][6]:
            set_fn(i, 6, i % 2 == 0)
    for cy in _ALIGNMENT.get(version, []):   # 对齐图案
        for cx in _ALIGNMENT.get(version, []):
            # 只跳过与三个定位图案重合的角部组合;
            # 与时序线重合的对齐图案必须绘制(其明暗与时序天然一致)
            if (cy, cx) in {(6, 6), (6, size - 7), (size - 7, 6)}:
                continue
            for dy in (-2, -1, 0, 1, 2):
                for dx in (-2, -1, 0, 1, 2):
                    set_fn(cy + dy, cx + dx, max(abs(dy), abs(dx)) != 1)
    for i in range(9):                 # 格式信息区(值稍后按掩码填)
        if i != 6:
            set_fn(8, i, False)
            set_fn(i, 8, False)
    for i in range(8):
        set_fn(8, size - 1 - i, False)
        set_fn(size - 1 - i, 8, False)
    set_fn(size - 8, 8, True)          # 固定深色模块
    if version >= 7:                   # 版本信息区(两处 3x6 块)必须保留, 否则数据会写入
        rem = version
        for _ in range(12):
            rem = (rem << 1) ^ ((rem >> 11) * _VERSION_BCH_GEN)
        bits = (version << 12) | rem
        for i in range(18):
            a, b = size - 11 + i % 3, i // 3
            bit = (bits >> i) & 1 == 1
            set_fn(a, b, bit)
            set_fn(b, a, bit)
    return modules, fn


def _draw_format(modules, mask_id: int) -> None:
    """两处格式信息: (EC 级别, 掩码) 经 BCH(15,5) 并异或掩码 0x5412。"""
    size = len(modules)
    data = (ECC_LEVEL_BITS["M"] << 3) | mask_id
    rem = data
    for _ in range(10):
        rem = (rem << 1) ^ ((rem >> 9) * _FORMAT_BCH_GEN)
    bits = ((data << 10) | rem) ^ _FORMAT_MASK

    def get(i: int) -> bool:
        return (bits >> i) & 1 == 1

    for i in range(6):                 # 第一份(左上, 分两段绕定位图案)
        modules[i][8] = get(i)
    modules[7][8] = get(6)
    modules[8][8] = get(7)
    modules[8][7] = get(8)
    for i in range(9, 15):
        modules[8][14 - i] = get(i)
    for i in range(8):                 # 第二份(右上竖 + 左下横)
        modules[8][size - 1 - i] = get(i)
    for i in range(8, 15):
        modules[size - 15 + i][8] = get(i)


def _draw_version(modules, version: int) -> None:
    """版本信息块(仅 v7+ 需要本工具未用, 保留以备扩展)。"""
    if version < 7:
        return
    size = len(modules)
    rem = version
    for _ in range(12):
        rem = (rem << 1) ^ ((rem >> 11) * _VERSION_BCH_GEN)
    bits = (version << 12) | rem
    for i in range(18):
        bit = (bits >> i) & 1 == 1
        a, b = size - 11 + i % 3, i // 3
        modules[a][b] = bit
        modules[b][a] = bit


def _data_cells(fn) -> list[tuple[int, int]]:
    """之字形顺序返回全部数据模块坐标(自右向左成对列, 避开第 6 列)。"""
    size = len(fn)
    cells: list[tuple[int, int]] = []
    right = size - 1
    while right >= 1:
        if right == 6:
            right = 5
        for vert in range(size):
            for j in range(2):
                x = right - j
                upward = ((right + 1) & 2) == 0
                y = size - 1 - vert if upward else vert
                if not fn[y][x]:
                    cells.append((y, x))
        right -= 2
    return cells


def _mask_bit(mask_id: int, x: int, y: int) -> bool:
    if mask_id == 0:
        return (x + y) % 2 == 0
    if mask_id == 1:
        return y % 2 == 0
    if mask_id == 2:
        return x % 3 == 0
    if mask_id == 3:
        return (x + y) % 3 == 0
    if mask_id == 4:
        return (x // 3 + y // 2) % 2 == 0
    if mask_id == 5:
        return (x * y) % 2 + (x * y) % 3 == 0
    if mask_id == 6:
        return ((x * y) % 2 + (x * y) % 3) % 2 == 0
    return ((x + y) % 2 + (x * y) % 3) % 2 == 0


def _penalty(modules) -> int:
    """掩码评分(规则 1 同色行列 + 规则 2 2x2 色块); 分低者更易扫。"""
    size = len(modules)
    score = 0

    def line(values) -> int:
        run, s, cur = 1, 0, None
        for v in values:
            if v == cur:
                run += 1
                if run == 5:
                    s += 3
                elif run > 5:
                    s += 1
            else:
                cur, run = v, 1
        return s

    for row in modules:
        score += line(row)
    for col in zip(*modules):
        score += line(col)
    for y in range(size - 1):
        for x in range(size - 1):
            v = modules[y][x]
            if v == modules[y][x + 1] == modules[y + 1][x] == modules[y + 1][x + 1]:
                score += 3
    return score


def qr_matrix(text: str, mask: int | None = None) -> list[list[bool]]:
    """文本 -> QR 矩阵(True = 深色)。自动选最小可容纳版本。

    mask: 指定掩码(0-7), None 则按评分自动挑选。
    """
    data = text.encode("utf-8")
    version = None
    for v in sorted(_EC_M):
        cci = 16 if v >= 10 else 8
        if 4 + cci + 8 * len(data) <= _EC_M[v][0] * 8:
            version = v
            break
    if version is None:
        max_bytes = (_EC_M[10][0] * 8 - 4 - 16) // 8
        raise ValueError(f"内容过长({len(data)} 字节), 纠错 M 级最多 {max_bytes} 字节")

    codewords = _add_ec(_encode_segment(data, version), version)
    data_bits: list[int] = []
    for cw in codewords:
        for i in range(7, -1, -1):
            data_bits.append((cw >> i) & 1)
    data_bits += [0] * _REMAINDER_BITS[version]  # 剩余位固定为 0, 参与掩码

    size = 17 + 4 * version
    base, fn = _build_function_modules(size)
    cells = _data_cells(fn)

    best, best_score = None, None
    for mask_id in range(8 if mask is None else mask + 1):
        if mask is not None and mask_id != mask:
            continue
        modules = [row[:] for row in base]
        for (y, x), bit in zip(cells, data_bits):
            modules[y][x] = bit ^ _mask_bit(mask_id, x, y)
        _draw_format(modules, mask_id)
        _draw_version(modules, version)
        s = _penalty(modules)
        if best_score is None or s < best_score:
            best, best_score = modules, s
    return best


# ── 终端渲染 ─────────────────────────────────────────────────

_HALF_BLOCK = "▀"   # 上半块字符: 前景色=上半行, 背景色=下半行, 一行画两行模块
_FG = {False: "\033[30m", True: "\033[97m"}    # 黑 / 白 前景
_BG = {False: "\033[40m", True: "\033[107m"}   # 黑 / 白 背景
_RESET = "\033[0m"


def render_ansi(matrix: list[list[bool]], quiet_zone: int = 4) -> str:
    """ANSI 半块渲染: 白底黑码, 深浅终端下都有足够对比度。"""
    size = len(matrix)
    n = size + quiet_zone * 2

    def light(y: int, x: int) -> bool:
        """该格是否为浅色(静区恒为浅色)。"""
        if quiet_zone <= y < quiet_zone + size and quiet_zone <= x < quiet_zone + size:
            return not matrix[y - quiet_zone][x - quiet_zone]
        return True

    lines = []
    for y in range(0, n, 2):
        parts = []
        for x in range(n):
            top = light(y, x)
            bot = light(min(y + 1, n - 1), x)
            parts.append(f"{_FG[top]}{_BG[bot]}{_HALF_BLOCK}{_RESET}")
        lines.append("".join(parts))
    return "\n".join(lines)


def render_ascii(matrix: list[list[bool]], quiet_zone: int = 4) -> str:
    """纯 ASCII 渲染(无 ANSI / 输出重定向时): 深色 ##, 浅色空格。"""
    size = len(matrix)
    lines = []
    for y in range(-quiet_zone, size + quiet_zone):
        row = []
        for x in range(-quiet_zone, size + quiet_zone):
            dark = matrix[y][x] if 0 <= y < size and 0 <= x < size else False
            row.append("##" if dark else "  ")
        lines.append("".join(row))
    return "\n".join(lines)


def print_qr(text: str, quiet_zone: int = 4, stream=None) -> None:
    """打印二维码: TTY 用 ANSI 彩色, 非 TTY(重定向/管道)退化为 ASCII。"""
    matrix = qr_matrix(text)
    out = stream or sys.stdout
    if hasattr(out, "isatty") and out.isatty():
        if sys.platform == "win32":
            os.system("")  # 启用 Windows 控制台的 VT 转义序列支持
        out.write(render_ansi(matrix, quiet_zone) + "\n")
    else:
        out.write(render_ascii(matrix, quiet_zone) + "\n")
    out.flush()
