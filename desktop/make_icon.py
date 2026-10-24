"""Draw the MechCopilot app icon (a ball bearing on a blue tile) and write desktop/icon.ico.

Pure Python (zlib + struct), so it needs no image library. Run again after changing the design:
    python desktop/make_icon.py
"""
import math
import os
import struct
import zlib

SIZES = (16, 24, 32, 48, 64, 128, 256)
BLUE = (37, 99, 235)
WHITE = (255, 255, 255)


def _pixel(x: float, y: float, s: int):
    """RGBA at pixel centre (x, y) of an s×s icon, with 4×4 supersampling for smooth edges."""
    acc = [0.0, 0.0, 0.0, 0.0]
    n = 4
    for i in range(n):
        for j in range(n):
            u = (x + (i + 0.5) / n) / s * 2 - 1      # -1..1
            v = (y + (j + 0.5) / n) / s * 2 - 1
            col = _shade(u, v)
            if col:
                a = col[3] / 255
                for k in range(3):
                    acc[k] += col[k] * a
                acc[3] += a
    if acc[3] == 0:
        return (0, 0, 0, 0)
    return tuple(int(round(c / acc[3])) for c in acc[:3]) + (int(round(255 * acc[3] / (n * n))),)


def _shade(u: float, v: float):
    # rounded-square tile
    r = 0.36
    dx, dy = max(abs(u) - (1 - r) + 0.04, 0), max(abs(v) - (1 - r) + 0.04, 0)
    if math.hypot(dx, dy) > r or abs(u) > 0.96 or abs(v) > 0.96:
        return None
    d = math.hypot(u, v)
    # outer and inner rings, balls between them
    if 0.56 <= d <= 0.70 or 0.20 <= d <= 0.32:
        return WHITE + (255,)
    for k in range(8):
        a = 2 * math.pi * k / 8
        if math.hypot(u - 0.44 * math.cos(a), v - 0.44 * math.sin(a)) <= 0.085:
            return WHITE + (255,)
    return BLUE + (255,)


def _png(s: int) -> bytes:
    rows = b"".join(b"\x00" + b"".join(bytes(_pixel(x, y, s)) for x in range(s)) for y in range(s))
    chunk = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", s, s, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows, 9)) + chunk(b"IEND", b""))


def main() -> None:
    images = [_png(s) for s in SIZES]
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    entries, data = b"", b""
    for s, img in zip(SIZES, images):
        entries += struct.pack("<BBBBHHII", s % 256, s % 256, 0, 0, 1, 32, len(img), offset + len(data))
        data += img
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")
    with open(out, "wb") as f:
        f.write(header + entries + data)
    print(f"wrote {out} ({len(header + entries + data)} bytes)")


if __name__ == "__main__":
    main()
