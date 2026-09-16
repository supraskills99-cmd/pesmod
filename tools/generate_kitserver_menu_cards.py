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

for filename, sub in items:
    make_card(filename, sub)

print(f'Generated {len(items)} square cards in {OUT.resolve()}')
