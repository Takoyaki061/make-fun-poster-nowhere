#!/usr/bin/env python3
"""CINDERLOOM — a travel poster for a place that does not exist.

Draws a 1024x1024 poster with the Python standard library ONLY (no PIL:
the grader runs `python3 -P -s /bot/main.py` in a stock python:3.13
image, so any third-party import exits 1). A lighthouse of stacked
glass bricks that never had a sea, sweeping its beam across a desert
of black sand. Writes to $MAKEFUN_OUTPUT_DIR/entry.png
(default /output/entry.png).

The picture is painted into an RGB bytearray with small scanline
helpers, and the PNG is encoded by hand (zlib + struct). The place
name is set with an embedded 5x7 bitmap font, scaled up.

Deterministic: no randomness except a fixed-seed star field; the same
bytes are produced on every run.
"""
import math
import os
import random
import struct
import zlib

W = H = 1024
INK = (16, 24, 32)          # deep night ink
DUSK = (58, 44, 48)         # dusky mauve above the horizon
EMBER = (228, 87, 46)       # lighthouse beam / sunset ember
EMBER_SOFT = (214, 122, 74)
BONE = (241, 233, 218)      # pale dune highlight / type
SAND_DARK = (10, 15, 20)
SAND_MID = (22, 30, 38)
SAND_LIT = (38, 48, 56)
GLASS_A = (233, 196, 138)
GLASS_B = (201, 148, 92)
GLASS_C = (244, 224, 178)

# ---------------------------------------------------------------- raster

# One RGB bytearray, row-major. All fills clip to the canvas.
buf = bytearray(W * H * 3)
for _y in range(H):
    buf[_y * W * 3:(_y + 1) * W * 3] = bytes(INK) * W


def fill_row(y, x0, x1, color):
    """Fill inclusive span [x0, x1] of row y with an RGB tuple."""
    if y < 0 or y >= H:
        return
    x0 = max(0, x0)
    x1 = min(W - 1, x1)
    if x1 < x0:
        return
    n = x1 - x0 + 1
    buf[y * W * 3 + x0 * 3:y * W * 3 + (x1 + 1) * 3] = bytes(color) * n


def fill_rect(x0, y0, x1, y1, color):
    for y in range(max(0, y0), min(H - 1, y1) + 1):
        fill_row(y, x0, x1, color)


def blend_row(y, x0, x1, color, alpha):
    """Alpha-blend inclusive span [x0, x1] of row y (alpha 0..255)."""
    if y < 0 or y >= H or alpha <= 0:
        return
    x0 = max(0, x0)
    x1 = min(W - 1, x1)
    if x1 < x0:
        return
    ia = 255 - alpha
    base = y * W * 3 + x0 * 3
    r, g, b = color
    for x in range(x0, x1 + 1):
        i = base + (x - x0) * 3
        buf[i] = (r * alpha + buf[i] * ia) // 255
        buf[i + 1] = (g * alpha + buf[i + 1] * ia) // 255
        buf[i + 2] = (b * alpha + buf[i + 2] * ia) // 255


def fill_ellipse(cx, cy, rx, ry, color):
    for dy in range(-ry, ry + 1):
        y = cy + dy
        if y < 0 or y >= H:
            continue
        dx = int(rx * math.sqrt(max(0.0, 1.0 - (dy * dy) / (ry * ry))))
        fill_row(y, cx - dx, cx + dx, color)


def blend_ellipse(cx, cy, rx, ry, color, alpha):
    for dy in range(-ry, ry + 1):
        y = cy + dy
        if y < 0 or y >= H:
            continue
        dx = int(rx * math.sqrt(max(0.0, 1.0 - (dy * dy) / (ry * ry))))
        blend_row(y, cx - dx, cx + dx, color, alpha)


def _scanline_spans(pts, y):
    """Even-odd fill spans for polygon pts on row y (inclusive x pairs)."""
    xs = []
    n = len(pts)
    for i in range(n):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % n]
        if y0 == y1:
            continue
        if (y0 <= y < y1) or (y1 <= y < y0):
            xs.append(x0 + (y - y0) * (x1 - x0) / (y1 - y0))
    xs.sort()
    spans = []
    for i in range(0, len(xs) - 1, 2):
        spans.append((int(math.ceil(xs[i])), int(math.floor(xs[i + 1]))))
    return spans


def fill_polygon(pts, color):
    min_y = max(0, min(y for _, y in pts))
    max_y = min(H - 1, max(y for _, y in pts))
    for y in range(min_y, max_y + 1):
        for x0, x1 in _scanline_spans(pts, y):
            fill_row(y, x0, x1, color)


def blend_polygon(pts, color, alpha):
    min_y = max(0, min(y for _, y in pts))
    max_y = min(H - 1, max(y for _, y in pts))
    for y in range(min_y, max_y + 1):
        for x0, x1 in _scanline_spans(pts, y):
            blend_row(y, x0, x1, color, alpha)


def rect_outline(x0, y0, x1, y1, color, width):
    for w in range(width):
        fill_rect(x0 + w, y0 + w, x1 - w, y0 + w, color)
        fill_rect(x0 + w, y1 - w, x1 - w, y1 - w, color)
        fill_rect(x0 + w, y0 + w, x0 + w, y1 - w, color)
        fill_rect(x1 - w, y0 + w, x1 - w, y1 - w, color)


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


# ------------------------------------------------------------- bitmap font
# Classic 5x7 glyphs, one byte per row, bit 4 = leftmost column.
FONT_5X7 = {
    "A": (0x0E, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11),
    "B": (0x1E, 0x11, 0x11, 0x1E, 0x11, 0x11, 0x1E),
    "C": (0x0E, 0x11, 0x10, 0x10, 0x10, 0x11, 0x0E),
    "D": (0x1E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x1E),
    "E": (0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x1F),
    "F": (0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x10),
    "G": (0x0E, 0x11, 0x10, 0x17, 0x11, 0x11, 0x0F),
    "H": (0x11, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11),
    "I": (0x0E, 0x04, 0x04, 0x04, 0x04, 0x04, 0x0E),
    "J": (0x07, 0x02, 0x02, 0x02, 0x02, 0x12, 0x0C),
    "K": (0x11, 0x12, 0x14, 0x18, 0x14, 0x12, 0x11),
    "L": (0x10, 0x10, 0x10, 0x10, 0x10, 0x10, 0x1F),
    "M": (0x11, 0x1B, 0x15, 0x15, 0x11, 0x11, 0x11),
    "N": (0x11, 0x19, 0x15, 0x13, 0x11, 0x11, 0x11),
    "O": (0x0E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E),
    "P": (0x1E, 0x11, 0x11, 0x1E, 0x10, 0x10, 0x10),
    "Q": (0x0E, 0x11, 0x11, 0x11, 0x15, 0x12, 0x0D),
    "R": (0x1E, 0x11, 0x11, 0x1E, 0x14, 0x12, 0x11),
    "S": (0x0F, 0x10, 0x10, 0x0E, 0x01, 0x01, 0x1E),
    "T": (0x1F, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04),
    "U": (0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E),
    "V": (0x11, 0x11, 0x11, 0x11, 0x11, 0x0A, 0x04),
    "W": (0x11, 0x11, 0x11, 0x15, 0x15, 0x1B, 0x11),
    "X": (0x11, 0x11, 0x0A, 0x04, 0x0A, 0x11, 0x11),
    "Y": (0x11, 0x11, 0x0A, 0x04, 0x04, 0x04, 0x04),
    "Z": (0x1F, 0x01, 0x02, 0x04, 0x08, 0x10, 0x1F),
}


def draw_text(text, x, y, scale, gap, color):
    """Draw uppercase text with the embedded font; returns total width."""
    cx = x
    for ch in text:
        glyph = FONT_5X7.get(ch)
        if glyph is None:
            cx += 5 * scale + gap
            continue
        for row, bits in enumerate(glyph):
            for col in range(5):
                if bits & (0x10 >> col):
                    fill_rect(cx + col * scale, y + row * scale,
                              cx + col * scale + scale - 1,
                              y + row * scale + scale - 1, color)
        cx += 5 * scale + gap
    return cx - x - gap


# ------------------------------------------------------------------ scene

def draw_sky():
    horizon = 640
    for y in range(horizon):
        t = y / horizon
        # ink at the top, warming to dusk ember near the horizon
        if t < 0.55:
            col = lerp((11, 17, 23), INK, t / 0.55)
        else:
            col = lerp(INK, DUSK, (t - 0.55) / 0.45)
        fill_row(y, 0, W - 1, col)
    # ember glow band hugging the horizon
    for i, y in enumerate(range(horizon - 90, horizon)):
        t = i / 90.0
        fill_row(y, 0, W - 1, lerp(DUSK, EMBER_SOFT, t * t))


def draw_stars():
    rng = random.Random(20261121)
    for _ in range(140):
        x = rng.randint(0, W - 1)
        y = rng.randint(0, 420)
        r = rng.choice([1, 1, 1, 2])
        rng.randint(120, 235)  # brightness was unused in the original too
        fill_ellipse(x, y, r, r, BONE)


def draw_sun():
    cx, cy, r = 190, 648, 58
    # soft halo
    for rad, col in ((104, (228, 87, 46)), (82, (228, 110, 60))):
        fill_ellipse(cx, cy, rad, rad, col)
    fill_ellipse(cx, cy, r, r, (244, 164, 96))


def draw_beam():
    # lamp room sits near the top of the tower (tower top ~ y=300)
    ox, oy = 668, 286
    # wide sweeping beam down to the left, landing on the dunes
    blend_polygon([(ox, oy - 22), (ox, oy + 22), (400, 760), (400, 600)],
                  (228, 87, 46), 78)
    blend_polygon([(ox, oy - 10), (ox, oy + 10), (400, 720), (400, 640)],
                  (244, 180, 110), 110)


def draw_tower():
    base_y = 640
    top_y = 304
    # stacked glass bricks, tapering as they rise
    rows = 12
    for i in range(rows):
        t0 = i / rows
        t1 = (i + 1) / rows
        y0 = int(base_y - (base_y - top_y) * t1)
        y1 = int(base_y - (base_y - top_y) * t0)
        half_w0 = int(58 - 26 * t0)
        half_w1 = int(58 - 26 * t1)
        cx = 668
        col = [GLASS_A, GLASS_B, GLASS_C, (226, 178, 120)][i % 4]
        fill_polygon([(cx - half_w1, y0), (cx + half_w1, y0),
                      (cx + half_w0, y1), (cx - half_w0, y1)], col)
        # mortar line between bricks
        fill_rect(cx - half_w1, y0, cx + half_w1, y0 + 1, (60, 40, 30))
    # lamp room: bright glass cage on top
    fill_rect(636, 270, 700, 306, (250, 214, 150))
    rect_outline(636, 270, 700, 306, (60, 40, 30), 3)
    fill_rect(667, 270, 668, 306, (60, 40, 30))
    # cap and finial
    fill_polygon([(628, 270), (708, 270), (688, 246), (648, 246)],
                 (40, 26, 22))
    fill_ellipse(668, 238, 6, 6, EMBER)
    # glow around the lamp
    blend_ellipse(668, 300, 80, 80, (244, 180, 110), 60)


def draw_dunes():
    horizon = 640
    # far dune: a long rolling ridge
    pts = [(0, horizon + 24)]
    for x in range(0, W + 1, 8):
        y = horizon + 24 + int(34 * math.sin(x / 260.0)
                               + 18 * math.sin(x / 90.0 + 1.3))
        pts.append((x, y))
    pts += [(W, H), (0, H)]
    fill_polygon(pts, SAND_MID)
    # near dune sweeping up from the left
    pts = [(0, 790)]
    for x in range(0, W + 1, 8):
        y = 790 + int(110 * ((x / W) ** 1.5)) - int(52 * math.sin(x / 320.0))
        pts.append((x, y))
    pts += [(W, H), (0, H)]
    fill_polygon(pts, SAND_DARK)
    # pool of beam light where the beam lands on the sand
    blend_ellipse(430, 712, 110, 24, (228, 120, 60), 46)
    blend_ellipse(430, 712, 70, 14, (244, 180, 110), 70)


def draw_name():
    name = "CINDERLOOM"
    scale, gap = 12, 10
    total = len(name) * 5 * scale + (len(name) - 1) * gap
    x = (W - total) // 2
    y = 62
    # soft shadow for legibility against the sky
    draw_text(name, x + 4, y + 5, scale, gap, (8, 12, 16))
    draw_text(name, x, y, scale, gap, BONE)
    # ember rule under the name, centred, shorter than the name
    rule_w = int(total * 0.62)
    fill_rect((W - rule_w) // 2, y + 108,
              (W + rule_w) // 2, y + 113, EMBER)


# -------------------------------------------------------------- PNG writer

def _chunk(kind, data):
    c = struct.pack(">I", len(data)) + kind + data
    return c + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def _filtered_row(raw, prev, ftype):
    if ftype == 0:
        return b"\x00" + raw
    out = bytearray()
    out.append(ftype)
    if ftype == 1:  # Sub
        for i, v in enumerate(raw):
            left = raw[i - 3] if i >= 3 else 0
            out.append((v - left) & 0xFF)
    else:  # Up
        for i, v in enumerate(raw):
            out.append((v - prev[i]) & 0xFF)
    return bytes(out)


def _filter_score(frow):
    # Sum of absolute values of the signed filter bytes, sampled.
    s = 0
    for v in frow[1::8]:
        s += v if v < 128 else 256 - v
    return s


def write_png(path):
    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    data = bytearray()
    prev = bytes(W * 3)
    for y in range(H):
        raw = bytes(buf[y * W * 3:(y + 1) * W * 3])
        cands = []
        for ftype in (0, 1, 2):
            frow = _filtered_row(raw, prev, ftype)
            cands.append((_filter_score(frow), frow))
        data += min(cands, key=lambda t: t[0])[1]
        prev = raw
    png = (b"\x89PNG\r\n\x1a\n"
           + _chunk(b"IHDR", ihdr)
           + _chunk(b"IDAT", zlib.compress(bytes(data), 9))
           + _chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(png)


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    draw_sky()
    draw_stars()
    draw_sun()
    draw_beam()
    draw_tower()
    draw_dunes()
    draw_name()
    path = os.path.join(out_dir, "entry.png")
    write_png(path)
    print(f"wrote {path} ({os.path.getsize(path)} bytes)")


if __name__ == "__main__":
    main()
