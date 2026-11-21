#!/usr/bin/env python3
"""CINDERLOOM — a travel poster for a place that does not exist.

Draws a 1024x1024 poster with PIL: a lighthouse of stacked glass bricks
that never had a sea, sweeping its beam across a desert of black sand.
Writes to $MAKEFUN_OUTPUT_DIR/entry.png (default /output/entry.png).

Deterministic: no randomness except a fixed-seed star field; the same
bytes are produced on every run.
"""
import os
import random
from PIL import Image, ImageDraw, ImageFont

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

FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
]


def load_font(size):
    for path in FONT_PATHS:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def draw_sky(img):
    d = ImageDraw.Draw(img)
    horizon = 640
    for y in range(horizon):
        t = y / horizon
        # ink at the top, warming to dusk ember near the horizon
        if t < 0.55:
            col = lerp((11, 17, 23), INK, t / 0.55)
        else:
            col = lerp(INK, DUSK, (t - 0.55) / 0.45)
        d.line([(0, y), (W, y)], fill=col)
    # ember glow band hugging the horizon
    for i, y in enumerate(range(horizon - 90, horizon)):
        t = i / 90.0
        col = lerp(DUSK, EMBER_SOFT, t * t)
        d.line([(0, y), (W, y)], fill=col)


def draw_stars(img):
    rng = random.Random(20261121)
    d = ImageDraw.Draw(img)
    for _ in range(140):
        x = rng.randint(0, W - 1)
        y = rng.randint(0, 420)
        r = rng.choice([1, 1, 1, 2])
        a = rng.randint(120, 235)
        d.ellipse([x - r, y - r, x + r, y + r], fill=(BONE[0], BONE[1], BONE[2]))


def draw_sun(img):
    d = ImageDraw.Draw(img)
    cx, cy, r = 190, 648, 58
    # soft halo
    for rad, col in ((104, (228, 87, 46)), (82, (228, 110, 60))):
        d.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], fill=col)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(244, 164, 96))


def draw_beam(img):
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    # lamp room sits near the top of the tower (tower top ~ y=300)
    ox, oy = 668, 286
    # wide sweeping beam down to the left, landing on the dunes
    d.polygon([(ox, oy - 22), (ox, oy + 22), (400, 760), (400, 600)],
              fill=(228, 87, 46, 78))
    d.polygon([(ox, oy - 10), (ox, oy + 10), (400, 720), (400, 640)],
              fill=(244, 180, 110, 110))
    img.alpha_composite(overlay)


def draw_tower(img):
    d = ImageDraw.Draw(img)
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
        d.polygon([(cx - half_w1, y0), (cx + half_w1, y0),
                   (cx + half_w0, y1), (cx - half_w0, y1)], fill=col)
        # mortar line between bricks
        d.line([(cx - half_w1, y0), (cx + half_w1, y0)], fill=(60, 40, 30), width=2)
    # lamp room: bright glass cage on top
    d.rectangle([636, 270, 700, 306], fill=(250, 214, 150))
    d.rectangle([636, 270, 700, 306], outline=(60, 40, 30), width=3)
    d.line([(668, 270), (668, 306)], fill=(60, 40, 30), width=2)
    # cap and finial
    d.polygon([(628, 270), (708, 270), (688, 246), (648, 246)], fill=(40, 26, 22))
    d.ellipse([662, 232, 674, 244], fill=EMBER)
    # glow around the lamp
    halo = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    hd = ImageDraw.Draw(halo)
    hd.ellipse([588, 220, 748, 380], fill=(244, 180, 110, 60))
    img.alpha_composite(halo)


def draw_dunes(img):
    import math
    d = ImageDraw.Draw(img)
    horizon = 640
    # far dune: a long rolling ridge
    pts = [(0, horizon + 24)]
    for x in range(0, W + 1, 8):
        y = horizon + 24 + int(34 * math.sin(x / 260.0) + 18 * math.sin(x / 90.0 + 1.3))
        pts.append((x, y))
    pts += [(W, H), (0, H)]
    d.polygon(pts, fill=SAND_MID)
    # near dune sweeping up from the left
    pts = [(0, 790)]
    for x in range(0, W + 1, 8):
        y = 790 + int(110 * ((x / W) ** 1.5)) - int(52 * math.sin(x / 320.0))
        pts.append((x, y))
    pts += [(W, H), (0, H)]
    d.polygon(pts, fill=SAND_DARK)
    # pool of beam light where the beam lands on the sand
    pool = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    pd = ImageDraw.Draw(pool)
    pd.ellipse([320, 688, 540, 736], fill=(228, 120, 60, 46))
    pd.ellipse([360, 698, 500, 726], fill=(244, 180, 110, 70))
    img.alpha_composite(pool)


def draw_name(img):
    d = ImageDraw.Draw(img)
    name = "CINDERLOOM"
    font = load_font(92)
    # letterspaced, centred, with margins
    widths = [d.textlength(ch, font=font) for ch in name]
    gap = 10
    total = sum(widths) + gap * (len(name) - 1)
    x = (W - total) // 2
    y = 62
    # soft shadow for legibility against the sky
    for ch, w in zip(name, widths):
        d.text((x + 4, y + 5), ch, font=font, fill=(8, 12, 16))
        x += w + gap
    x = (W - total) // 2
    for ch, w in zip(name, widths):
        d.text((x, y), ch, font=font, fill=BONE)
        x += w + gap
    # ember rule under the name, centred, shorter than the name
    rule_w = int(total * 0.62)
    d.rectangle([(W - rule_w) // 2, y + 108, (W + rule_w) // 2, y + 113],
                fill=EMBER)


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    img = Image.new("RGBA", (W, H), INK)
    draw_sky(img)
    draw_stars(img)
    draw_sun(img)
    draw_beam(img)
    draw_tower(img)
    draw_dunes(img)
    draw_name(img)
    img = img.convert("RGB")
    path = os.path.join(out_dir, "entry.png")
    img.save(path, format="PNG", optimize=True)
    print(f"wrote {path} ({os.path.getsize(path)} bytes)")


if __name__ == "__main__":
    main()
