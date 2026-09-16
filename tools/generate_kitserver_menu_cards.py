from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

OUT = Path('build_menu_cards')
OUT.mkdir(exist_ok=True)

items = [
    ('partido.png', 'PARTIDO', 'MATCH'),
    ('liga_master.png', 'LIGA MASTER', 'ML'),
    ('liga.png', 'LIGA', 'LEAGUE'),
    ('copa.png', 'COPA', 'WORLD CUP'),
    ('entrenamiento.png', 'ENTRENAMIENTO', 'TRAINING'),
    ('editar.png', 'EDITAR', 'EDIT'),
    ('opciones.png', 'OPCIONES', 'OPTIONS'),
    ('partido_internacional.png', 'PARTIDO INTERNACIONAL', 'INTL'),
    ('seleccion_azar.png', 'SELECCION AL AZAR', 'RANDOM'),
    ('red.png', 'RED', 'NETWORK'),
    ('salir.png', 'SALIR', 'EXIT'),
]

font_paths = [
    r'C:\Windows\Fonts\arialbd.ttf',
    r'C:\Windows\Fonts\arial.ttf',
]

def get_font(size, bold=False):
    candidates = [font_paths[0], font_paths[1]] if bold else [font_paths[1], font_paths[0]]
    for p in candidates:
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            pass
    return ImageFont.load_default()

font_title = get_font(22, True)
font_sub = get_font(16, False)
font_big = get_font(42, True)


def trophy(draw, cx, cy):
    # Normal tall World-Cup-style white silhouette, deliberately not the themed colored logo.
    draw.ellipse((cx-16, cy-58, cx+16, cy-26), fill='white')
    draw.polygon([(cx-12, cy-28), (cx+12, cy-28), (cx+7, cy+2), (cx-7, cy+2)], fill='white')
    draw.rounded_rectangle((cx-6, cy-2, cx+6, cy+28), radius=4, fill='white')
    draw.ellipse((cx-20, cy+20, cx+20, cy+34), fill='white')
    draw.rectangle((cx-15, cy+28, cx+15, cy+39), fill='white')


def make_card(label, sub, filename):
    W, H = 256, 384
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)

    # dark purple / graphite column similar to the user's horizontal PES 2011-style menu
    for y in range(H):
        t = y/(H-1)
        r = int(44*(1-t) + 19*t)
        g = int(18*(1-t) + 12*t)
        b = int(62*(1-t) + 35*t)
        d.line((0,y,W,y), fill=(r,g,b,246))

    # soft center light
    glow = Image.new('RGBA', (W,H), (0,0,0,0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((20, 10, 236, 210), fill=(110, 90, 155, 45))
    glow = glow.filter(ImageFilter.GaussianBlur(26))
    im = Image.alpha_composite(im, glow)
    d = ImageDraw.Draw(im)

    # PES-like pale green selected frame, no red
    d.rounded_rectangle((5,5,W-6,H-6), radius=12, outline=(102,255,151,245), width=4)
    d.rounded_rectangle((11,11,W-12,H-12), radius=10, outline=(235,255,240,80), width=1)

    # upper graphic area
    d.rounded_rectangle((18,22,W-19,214), radius=8, fill=(6,6,10,150))
    for k in range(6):
        x = 16 + k*45
        d.line((x,205,x+70,30), fill=(120,255,175,35), width=3)

    if filename == 'copa.png':
        trophy(d, W//2, 125)
    else:
        box = d.textbbox((0,0), sub, font=font_big)
        tw = box[2]-box[0]
        th = box[3]-box[1]
        d.text(((W-tw)//2, 118-th//2), sub, font=font_big, fill=(250,250,250,235))

    # title area
    y0 = 245
    # shrink long labels
    f = font_title
    while d.textbbox((0,0), label, font=f)[2] > W-28 and getattr(f, 'size', 16) > 13:
        f = get_font(f.size-1, True)
    tw = d.textbbox((0,0), label, font=f)[2]
    d.text(((W-tw)//2, y0), label, font=f, fill=(248,248,248,255))
    d.line((28, 292, W-28, 292), fill=(255,255,255,60), width=1)
    hint = 'SELECCIONADO'
    tw2 = d.textbbox((0,0), hint, font=font_sub)[2]
    d.text(((W-tw2)//2, 310), hint, font=font_sub, fill=(208,205,220,220))

    im.save(OUT/filename)

for filename, label, sub in items:
    make_card(label, sub, filename)

print(f'Generated {len(items)} cards in {OUT.resolve()}')
