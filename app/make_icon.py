#!/usr/bin/env python3
"""Orca Dash 앱 아이콘(PNG) 생성. 외부 라이브러리 없이 1024x1024 PNG 를 쓴다.

어두운 둥근 사각형 배경 위에 상태 점과 막대 세 줄(막힘·대기·작업 중 색)로 표를 암시한다.
"""
import struct, sys, zlib

SIZE = 1024
BG = (24, 28, 38)
PANEL = (38, 44, 58)
ROWS = [((235, 87, 87), 0.30), ((245, 196, 66), 0.52), ((86, 196, 148), 0.74)]  # (색, 세로 위치 비율)


def rounded_rect(x, y, x0, y0, x1, y1, r):
    if x < x0 or x > x1 or y < y0 or y > y1:
        return False
    cx = min(max(x, x0 + r), x1 - r)
    cy = min(max(y, y0 + r), y1 - r)
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r


def circle(x, y, cx, cy, r):
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r


def pixel(x, y):
    m = SIZE * 0.10
    if not rounded_rect(x, y, m, m, SIZE - m, SIZE - m, SIZE * 0.22):
        return (0, 0, 0, 0)
    color = BG
    px0, py0, px1, py1 = SIZE * 0.20, SIZE * 0.20, SIZE * 0.80, SIZE * 0.80
    if rounded_rect(x, y, px0, py0, px1, py1, SIZE * 0.06):
        color = PANEL
    bar_h = SIZE * 0.075
    for col, fy in ROWS:
        cy = SIZE * fy
        if circle(x, y, px0 + SIZE * 0.085, cy, bar_h / 2):
            color = col
        bx0 = px0 + SIZE * 0.17
        bx1 = px1 - SIZE * 0.07
        if rounded_rect(x, y, bx0, cy - bar_h / 2, bx1, cy + bar_h / 2, bar_h / 2):
            color = tuple(int(c * 0.55 + b * 0.45) for c, b in zip(col, PANEL))
    return (*color, 255)


def write_png(path):
    raw = bytearray()
    for y in range(SIZE):
        raw.append(0)
        for x in range(SIZE):
            raw.extend(pixel(x, y))

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", SIZE, SIZE, 8, 6, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)


if __name__ == "__main__":
    write_png(sys.argv[1] if len(sys.argv) > 1 else "icon_1024.png")
