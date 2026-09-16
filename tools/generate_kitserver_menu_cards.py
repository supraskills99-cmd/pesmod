from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

OUT = Path('build_menu_cards')
OUT.mkdir(exist_ok=True)

items = [
    ('partido.png', 'MATCH'),
    ('liga_master.png', 'ML'),
    ('liga.png', 'LEAGUE'),
    ('copa.png', 'WORLD CUP'),
    ('entrenamiento.png', 'TRAINING'),
    ('editar.png', 'EDIT'),
    ('opciones.png', 'OPTIONS'),
    ('partido_internacional.png', 'INTL'),
    ('seleccion_azar.png', 'RANDOM'),
    ('red.png', 'NETWORK'),
    ('salir.png', 'EXIT'),
]

FONT = r'C:\Windows\Fonts\arialbd.ttf'
FRAMES = 10

def font(size):
    try:
        return ImageFont.truetype(FONT, size)
    except OSError:
        return ImageFont.load_default()

big = font(35)

def trophy(draw, cx, cy):
    draw.ellipse((cx-12, cy-42, cx+12, cy-18), fill='white')
    draw.polygon([(cx-9, cy-18), (cx+9, cy-18), (cx+5, cy+5), (cx-5, cy+5)], fill='white')
    draw.rounded_rectangle((cx-5, cy+2, cx+5, cy+23), radius=3, fill='white')
    draw.ellipse((cx-15, cy+18, cx+15, cy+29), fill='white')
    draw.rectangle((cx-11, cy+24, cx+11, cy+33), fill='white')

def make_card(filename, sub):
    W = H = 176
    im = Image.new('RGBA', (W,H), (22,10,34,248))
    d = ImageDraw.Draw(im)

    glow = Image.new('RGBA', (W,H), (0,0,0,0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((20,10,156,146), fill=(110,90,155,45))
    glow = glow.filter(ImageFilter.GaussianBlur(18))
    im = Image.alpha_composite(im, glow)
    d = ImageDraw.Draw(im)

    d.rounded_rectangle((2,2,W-3,H-3), radius=10, outline=(102,255,151,255), width=3)
    d.rounded_rectangle((6,6,W-7,H-7), radius=8, outline=(220,190,255,130), width=2)
    d.rounded_rectangle((10,10,W-11,H-11), radius=7, fill=(7,7,12,145))

    for k in range(5):
        x = 18 + k*33
        d.line((x,154,x+48,20), fill=(120,255,175,42), width=3)

    if filename == 'copa.png':
        trophy(d, W//2, 88)
    else:
        f = big
        while d.textbbox((0,0), sub, font=f)[2] > W-24 and getattr(f,'size',20) > 18:
            f = font(f.size-1)
        box = d.textbbox((0,0), sub, font=f)
        tw, th = box[2]-box[0], box[3]-box[1]
        d.text(((W-tw)//2, (H-th)//2-2), sub, font=f, fill=(248,248,248,245))

    im.save(OUT/filename)
    return im

def make_animated_frames(filename, base):
    W, H = base.size
    stem = Path(filename).stem

    for i in range(FRAMES):
        phase = i / FRAMES
        frame = base.copy()

        # Animated internal light sweep: this is deliberately visible in the
        # test pack so we can verify that the selected card is a live panel,
        # not a static PNG. Final artwork can replace these frame sequences.
        overlay = Image.new('RGBA', (W,H), (0,0,0,0))
        od = ImageDraw.Draw(overlay)
        x = int(-60 + (W + 120) * phase)
        od.polygon([
            (x-26, 8), (x+9, 8), (x+55, H-9), (x+19, H-9)
        ], fill=(235,255,245,72))
        overlay = overlay.filter(ImageFilter.GaussianBlur(8))
        frame = Image.alpha_composite(frame, overlay)

        # Soft green pulse at the lower edge, similar to a selected frontend tile.
        pulse = 0.5 + 0.5 * abs(1.0 - 2.0 * phase)
        accent = Image.new('RGBA', (W,H), (0,0,0,0))
        ad = ImageDraw.Draw(accent)
        a = int(24 + 42 * (1.0 - pulse))
        ad.rounded_rectangle((12, H-24, W-13, H-12), radius=6,
                             fill=(102,255,151,a))
        accent = accent.filter(ImageFilter.GaussianBlur(7))
        frame = Image.alpha_composite(frame, accent)

        frame.save(OUT / f'{stem}_f{i}.png')

for filename, sub in items:
    base = make_card(filename, sub)
    make_animated_frames(filename, base)

print(f'Generated {len(items)} cards + {len(items)*FRAMES} animation frames in {OUT.resolve()}')
