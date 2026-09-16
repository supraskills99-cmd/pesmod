from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance

OUT = Path('build_menu_cards')
ITEMS = [
    'partido','liga_master','liga','copa','entrenamiento','editar','opciones',
    'partido_internacional','seleccion_azar','red','salir'
]
FRAMES = 10
W = 128
BOTTOM = 128
TOP = 164
H = TOP + BOTTOM
GREEN = (104,255,154,255)
LILAC = (211,189,255,185)


def verticalize(src: Image.Image, phase: float) -> Image.Image:
    src = src.convert('RGBA')
    out = Image.new('RGBA', (W,H), (8,6,16,255))

    # Upper media panel: use the animated content of the existing card as a
    # blown-up, darker moving visual. This mimics the PES2011 tall media header.
    crop = src.crop((24, 36, 152, 152)).resize((150,136), Image.Resampling.LANCZOS)
    crop = ImageEnhance.Contrast(crop).enhance(1.10)
    crop = ImageEnhance.Brightness(crop).enhance(0.72)

    # Soft full-panel ambience behind the sharp emblem/image.
    bg = crop.resize((W,TOP), Image.Resampling.BICUBIC).filter(ImageFilter.GaussianBlur(10))
    tint = Image.new('RGBA',(W,TOP),(29,13,52,92))
    bg = Image.alpha_composite(bg, tint)
    out.alpha_composite(bg, (0,0))

    # Main animated visual, slightly oversized like the original PES2011 cards.
    x = -11 + int(5*phase)
    y = 20 - int(4*phase)
    out.alpha_composite(crop, (x,y))

    # Purple light sweep/orb that changes with the frame sequence.
    fx = Image.new('RGBA',(W,TOP),(0,0,0,0))
    d = ImageDraw.Draw(fx)
    orb_x = int(-18 + phase*(W+36))
    d.ellipse((orb_x-34, -8, orb_x+34, 60), fill=(124,70,190,64))
    d.polygon([(orb_x-16,0),(orb_x+7,0),(orb_x+52,TOP),(orb_x+24,TOP)], fill=(255,255,255,25))
    fx = fx.filter(ImageFilter.GaussianBlur(9))
    out.alpha_composite(fx,(0,0))

    # Lower square selected tile. Keep the original artwork readable, but make
    # it slightly darker/cleaner so it resembles the fixed PES2011 selector tile.
    tile = src.resize((BOTTOM,BOTTOM), Image.Resampling.LANCZOS)
    tile = ImageEnhance.Brightness(tile).enhance(0.93)
    out.alpha_composite(tile,(0,TOP))

    d = ImageDraw.Draw(out)
    # Divider and selected border are deliberately thin, like the video.
    d.line((4,TOP, W-5,TOP), fill=(240,240,246,150), width=1)
    d.rounded_rectangle((1,TOP+1,W-2,H-2), radius=5, outline=GREEN, width=2)
    d.rounded_rectangle((4,TOP+4,W-5,H-5), radius=4, outline=LILAC, width=1)
    d.line((2,1,W-3,1), fill=(255,255,255,38), width=1)
    return out


for stem in ITEMS:
    for i in range(FRAMES):
        p = OUT / f'{stem}_f{i}.png'
        if not p.exists():
            continue
        im = verticalize(Image.open(p), i/max(1,FRAMES-1))
        im.save(p)
    base = OUT / f'{stem}.png'
    f0 = OUT / f'{stem}_f0.png'
    if f0.exists():
        Image.open(f0).save(base)

print('V22: converted animated cards to 128x292 PES2011 vertical selector panels')
