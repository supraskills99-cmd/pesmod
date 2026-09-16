# SPDX-License-Identifier: GPL-3.0-or-later
"""Generate the placeholder card PNGs used by the animated-menu prototype.

Run from the repository root:
    python tools/generate_menu_cards.py

Requires Pillow:
    python -m pip install pillow

The PNGs are deliberately external runtime assets. Replace them freely later
without recompiling PESMod, keeping the same filenames.
"""

from pathlib import Path
import math

from PIL import Image, ImageDraw, ImageFont, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "menu_cards"
OUT.mkdir(parents=True, exist_ok=True)

FONT_CANDIDATES = [
    Path("C:/Windows/Fonts/arialbd.ttf"),
    Path("C:/Windows/Fonts/arial.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf"),
]


def font(size):
    for p in FONT_CANDIDATES:
        if p.exists():
            return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


FONT_BIG = font(30)
FONT_SMALL = font(22)
FONT_TINY = font(14)

ITEMS = [
    ("partido.png", "PARTIDO", "ball"),
    ("liga_master.png", "LIGA MÁSTER", "shield"),
    ("liga.png", "LIGA", "league"),
    ("copa.png", "COPA", "worldcup"),
    ("entrenamiento.png", "ENTRENAMIENTO", "training"),
    ("editar.png", "EDITAR", "edit"),
    ("opciones.png", "OPCIONES", "gear"),
    ("partido_internacional.png", "PARTIDO\nINTERNACIONAL", "globe"),
    ("seleccion_azar.png", "SELECCIÓN\nAL AZAR", "dice"),
    ("red.png", "RED", "network"),
    ("salir.png", "SALIR", "exit"),
]


def draw_world_cup_silhouette(d, cx, cy, fill):
    """Generic white world-cup silhouette: globe + rising body + broad base."""
    d.ellipse((cx - 25, cy - 70, cx + 25, cy - 20), fill=fill)
    d.polygon([
        (cx - 26, cy - 48), (cx - 15, cy - 17), (cx - 12, cy + 18),
        (cx - 25, cy + 46), (cx - 35, cy + 58), (cx - 13, cy + 58),
        (cx - 2, cy + 30), (cx, cy - 3),
    ], fill=fill)
    d.polygon([
        (cx + 26, cy - 48), (cx + 15, cy - 17), (cx + 12, cy + 18),
        (cx + 25, cy + 46), (cx + 35, cy + 58), (cx + 13, cy + 58),
        (cx + 2, cy + 30), (cx, cy - 3),
    ], fill=fill)
    d.rectangle((cx - 36, cy + 57, cx + 36, cy + 70), fill=fill)
    d.rectangle((cx - 43, cy + 70, cx + 43, cy + 82), fill=fill)


def draw_icon(d, kind, cx, cy):
    white = (245, 245, 245, 255)

    if kind == "ball":
        d.ellipse((cx - 55, cy - 55, cx + 55, cy + 55), outline=white, width=7)
        d.regular_polygon((cx, cy, 24), 5, rotation=18, fill=white)
        for a in range(0, 360, 72):
            x = cx + 42 * math.cos(math.radians(a - 90))
            y = cy + 42 * math.sin(math.radians(a - 90))
            d.line((cx, cy, x, y), fill=white, width=5)

    elif kind == "shield":
        pts = [(cx - 58, cy - 58), (cx + 58, cy - 58),
               (cx + 48, cy + 30), (cx, cy + 72), (cx - 48, cy + 30)]
        d.line(pts + [pts[0]], fill=white, width=7)
        f = font(48)
        box = d.textbbox((0, 0), "ML", font=f)
        d.text((cx - (box[2] - box[0]) / 2, cy - 30), "ML", font=f, fill=white)

    elif kind == "league":
        d.ellipse((cx - 48, cy - 48, cx + 48, cy + 48), outline=white, width=7)
        d.arc((cx - 66, cy - 30, cx + 66, cy + 82), 20, 160, fill=white, width=6)
        d.arc((cx - 66, cy - 82, cx + 66, cy + 30), 200, 340, fill=white, width=6)

    elif kind == "worldcup":
        draw_world_cup_silhouette(d, cx, cy, white)

    elif kind == "training":
        for dx in (-45, 0, 45):
            d.polygon([(cx + dx, cy - 45), (cx + dx - 24, cy + 50),
                       (cx + dx + 24, cy + 50)], outline=white)
            d.line((cx + dx - 24, cy + 50, cx + dx + 24, cy + 50), fill=white, width=7)
        d.line((cx - 72, cy + 58, cx + 72, cy + 58), fill=white, width=7)

    elif kind == "edit":
        for ox, oy in [(-55, -55), (5, -55), (-55, 5), (5, 5)]:
            d.rounded_rectangle((cx + ox, cy + oy, cx + ox + 52, cy + oy + 52),
                                8, fill=white)

    elif kind == "gear":
        d.ellipse((cx - 55, cy - 55, cx + 55, cy + 55), outline=white, width=10)
        d.ellipse((cx - 18, cy - 18, cx + 18, cy + 18), fill=white)
        for a in range(0, 360, 45):
            x = cx + 70 * math.cos(math.radians(a))
            y = cy + 70 * math.sin(math.radians(a))
            d.rectangle((x - 9, y - 18, x + 9, y + 18), fill=white)

    elif kind == "globe":
        d.ellipse((cx - 60, cy - 60, cx + 60, cy + 60), outline=white, width=7)
        d.arc((cx - 30, cy - 60, cx + 30, cy + 60), 90, 270, fill=white, width=5)
        d.arc((cx - 30, cy - 60, cx + 30, cy + 60), 270, 90, fill=white, width=5)
        d.line((cx - 58, cy, cx + 58, cy), fill=white, width=5)

    elif kind == "dice":
        d.rounded_rectangle((cx - 58, cy - 58, cx + 58, cy + 58),
                            16, outline=white, width=8)
        for dx, dy in [(-28, -28), (28, -28), (0, 0), (-28, 28), (28, 28)]:
            d.ellipse((cx + dx - 7, cy + dy - 7, cx + dx + 7, cy + dy + 7), fill=white)

    elif kind == "network":
        pts = [(cx - 58, cy + 28), (cx, cy - 45), (cx + 58, cy + 28)]
        for x, y in pts:
            d.ellipse((x - 16, y - 16, x + 16, y + 16), fill=white)
        d.line((*pts[0], *pts[1]), fill=white, width=7)
        d.line((*pts[1], *pts[2]), fill=white, width=7)
        d.line((*pts[0], *pts[2]), fill=white, width=7)

    elif kind == "exit":
        d.rectangle((cx - 55, cy - 65, cx + 28, cy + 65), outline=white, width=8)
        d.polygon([(cx - 5, cy), (cx + 65, cy - 45), (cx + 65, cy - 18),
                   (cx + 90, cy - 18), (cx + 90, cy + 18), (cx + 65, cy + 18),
                   (cx + 65, cy + 45)], fill=white)


def make_card(label, kind):
    w, h = 256, 384
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)

    for y in range(h):
        p = y / (h - 1)
        r = int(42 * (1 - p) + 15 * p)
        g = int(25 * (1 - p) + 13 * p)
        b = int(59 * (1 - p) + 27 * p)
        d.line((0, y, w, y), fill=(r, g, b, 245))

    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((25, -70, 230, 150), fill=(80, 130, 170, 60))
    glow = glow.filter(ImageFilter.GaussianBlur(35))
    im = Image.alpha_composite(im, glow)
    d = ImageDraw.Draw(im)

    d.rounded_rectangle((5, 5, w - 6, h - 6), 16,
                        outline=(92, 255, 147, 255), width=5)
    d.rounded_rectangle((11, 11, w - 12, h - 12), 13,
                        outline=(240, 255, 245, 65), width=2)
    d.line((24, 282, w - 24, 282), fill=(255, 255, 255, 60), width=2)

    draw_icon(d, kind, w // 2, 170)

    lines = label.split("\n")
    f = FONT_SMALL if max(len(x) for x in lines) > 12 else FONT_BIG
    heights = [d.textbbox((0, 0), line, font=f)[3] for line in lines]
    yy = 315 - (sum(heights) + 4 * (len(lines) - 1)) / 2
    for line, th in zip(lines, heights):
        box = d.textbbox((0, 0), line, font=f)
        tw = box[2] - box[0]
        d.text(((w - tw) / 2, yy), line, font=f, fill=(248, 248, 248, 255))
        yy += th + 4

    d.text((24, 355), "PES 6", font=FONT_TINY, fill=(180, 180, 190, 190))
    return im


def main():
    for filename, label, icon in ITEMS:
        make_card(label, icon).save(OUT / filename, optimize=True)
    print(f"Generated {len(ITEMS)} cards in {OUT}")


if __name__ == "__main__":
    main()
