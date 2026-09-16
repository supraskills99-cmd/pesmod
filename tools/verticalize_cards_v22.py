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


def verticalize(src: Image.Image, phase: float) -> Image.Image:
    src = src.convert('RGBA')

    # V23: the user's existing PES2011 horizontal menu is the real selector bar.
    # We only draw the upper selected-panel extension. The lower 128x128 area is
    # deliberately transparent so the module never paints over/replaces the bar.
    out = Image.new('RGBA', (W, H), (0, 0, 0, 0))

    # Upper media/reflection panel above the selected option.
    crop = src.crop((24, 36, 152, 152)).resize((150, 136), Image.Resampling.LANCZOS)
    crop = ImageEnhance.Contrast(crop).enhance(1.10)
    crop = ImageEnhance.Brightness(crop).enhance(0.72)

    # Soft ambience behind the sharp visual, limited strictly to the upper panel.
    bg = crop.resize((W, TOP), Image.Resampling.BICUBIC).filter(ImageFilter.GaussianBlur(10))
    tint = Image.new('RGBA', (W, TOP), (29, 13, 52, 92))
    bg = Image.alpha_composite(bg, tint)
    out.alpha_composite(bg, (0, 0))

    # Main animated visual. This is the part that rises above the normal PES2011 bar.
    x = -11 + int(5 * phase)
    y = 20 - int(4 * phase)
    out.alpha_composite(crop, (x, y))

    # Subtle light/reflection sweep in the upper panel only.
    fx = Image.new('RGBA', (W, TOP), (0, 0, 0, 0))
    d = ImageDraw.Draw(fx)
    orb_x = int(-18 + phase * (W + 36))
    d.ellipse((orb_x - 34, -8, orb_x + 34, 60), fill=(124, 70, 190, 64))
    d.polygon([(orb_x - 16, 0), (orb_x + 7, 0), (orb_x + 52, TOP), (orb_x + 24, TOP)],
              fill=(255, 255, 255, 25))
    fx = fx.filter(ImageFilter.GaussianBlur(9))
    out.alpha_composite(fx, (0, 0))

    # A very thin join at the top edge of the existing selected tile. Nothing is
    # drawn below TOP, so the original menu, icons, reflections and movement remain intact.
    d = ImageDraw.Draw(out)
    d.line((4, TOP - 1, W - 5, TOP - 1), fill=(240, 240, 246, 105), width=1)

    return out


for stem in ITEMS:
    for i in range(FRAMES):
        p = OUT / f'{stem}_f{i}.png'
        if not p.exists():
            continue
        im = verticalize(Image.open(p), i / max(1, FRAMES - 1))
        im.save(p)
    base = OUT / f'{stem}.png'
    f0 = OUT / f'{stem}_f0.png'
    if f0.exists():
        Image.open(f0).save(base)

print('V23: upper PES2011 panel only; original horizontal menu bar remains untouched')
