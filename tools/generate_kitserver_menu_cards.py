from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import math

OUT = Path('build_menu_cards')
OUT.mkdir(exist_ok=True)

# Final PES2011-inspired card set for the 11 PES6 main-menu entries.
# The DLL still reads the same filenames, so V15 input/navigation remains untouched.
ITEMS = [
    ('partido.png', 'PARTIDO', 'match'),
    ('liga_master.png', 'LIGA MÁSTER', 'master'),
    ('liga.png', 'LIGA', 'league'),
    ('copa.png', 'COPA', 'cup'),
    ('entrenamiento.png', 'ENTRENAMIENTO', 'training'),
    ('editar.png', 'EDITAR', 'edit'),
    ('opciones.png', 'OPCIONES', 'options'),
    ('partido_internacional.png', 'PARTIDO INTERNACIONAL', 'international'),
    ('seleccion_azar.png', 'SELECCIÓN AL AZAR', 'random'),
    ('red.png', 'RED', 'network'),
    ('salir.png', 'SALIR', 'exit'),
]

FRAMES = 10
W = H = 176
FONT_BOLD = r'C:\Windows\Fonts\arialbd.ttf'
FONT_REG = r'C:\Windows\Fonts\arial.ttf'

BG = (15, 8, 29, 250)
BG2 = (7, 7, 13, 230)
GREEN = (104, 255, 154, 255)
GREEN_SOFT = (104, 255, 154, 105)
LILAC = (211, 189, 255, 180)
WHITE = (248, 248, 250, 250)
MUTED = (205, 203, 217, 220)


def font(size, bold=False):
    path = FONT_BOLD if bold else FONT_REG
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


def fit_font(draw, text, max_width, start=18, minimum=10):
    size = start
    while size > minimum:
        f = font(size, True)
        if draw.textbbox((0, 0), text, font=f)[2] <= max_width:
            return f
        size -= 1
    return font(minimum, True)


def composite_blur(im, painter, radius=10):
    layer = Image.new('RGBA', im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    painter(d)
    return Image.alpha_composite(im, layer.filter(ImageFilter.GaussianBlur(radius)))


def line_glow(im, xy, fill=GREEN, width=2, blur=5, glow_alpha=90):
    glow = Image.new('RGBA', im.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    c = (fill[0], fill[1], fill[2], glow_alpha)
    gd.line(xy, fill=c, width=max(3, width + 3))
    glow = glow.filter(ImageFilter.GaussianBlur(blur))
    im = Image.alpha_composite(im, glow)
    ImageDraw.Draw(im).line(xy, fill=fill, width=width)
    return im


def ball(draw, cx, cy, r=20, alpha=245):
    white = (245, 245, 248, alpha)
    dark = (26, 21, 38, alpha)
    draw.ellipse((cx-r, cy-r, cx+r, cy+r), fill=white)
    # simple readable football pattern
    pent = []
    for k in range(5):
        a = -math.pi/2 + k * 2*math.pi/5
        pent.append((cx + math.cos(a)*r*0.34, cy + math.sin(a)*r*0.34))
    draw.polygon(pent, fill=dark)
    for k in range(5):
        a = -math.pi/2 + k * 2*math.pi/5
        x = cx + math.cos(a)*r*0.34
        y = cy + math.sin(a)*r*0.34
        ex = cx + math.cos(a)*r*0.86
        ey = cy + math.sin(a)*r*0.86
        draw.line((x, y, ex, ey), fill=dark, width=2)


def world_cup(draw, cx, cy, glow=False):
    # recognizable white world-cup silhouette, kept white as requested.
    c = WHITE if not glow else (255, 255, 255, 255)
    draw.ellipse((cx-13, cy-42, cx+13, cy-18), fill=c)
    draw.ellipse((cx-10, cy-31, cx+10, cy-8), fill=c)
    draw.polygon([(cx-9,cy-15),(cx+9,cy-15),(cx+5,cy+8),(cx-5,cy+8)], fill=c)
    draw.rounded_rectangle((cx-5,cy+3,cx+5,cy+24), radius=3, fill=c)
    draw.ellipse((cx-16,cy+18,cx+16,cy+30), fill=c)
    draw.rectangle((cx-11,cy+26,cx+11,cy+34), fill=c)


def shield(draw, cx, cy, scale=1.0):
    pts = [
        (cx-27*scale, cy-29*scale), (cx+27*scale, cy-29*scale),
        (cx+23*scale, cy+8*scale), (cx, cy+34*scale),
        (cx-23*scale, cy+8*scale)
    ]
    draw.polygon(pts, fill=(32, 24, 51, 245), outline=GREEN)
    draw.line((cx-17*scale,cy-13*scale,cx+17*scale,cy-13*scale), fill=LILAC, width=2)
    f = font(max(13, int(22*scale)), True)
    text = 'ML'
    box = draw.textbbox((0,0), text, font=f)
    draw.text((cx-(box[2]-box[0])/2, cy-5*scale-(box[3]-box[1])/2), text, font=f, fill=WHITE)


def cone(draw, x, y, s=1.0):
    draw.polygon([(x, y-17*s), (x-11*s, y+12*s), (x+11*s, y+12*s)], fill=(245,245,248,245))
    draw.rectangle((x-15*s, y+10*s, x+15*s, y+15*s), fill=GREEN)
    draw.line((x-8*s,y+2*s,x+8*s,y+2*s), fill=(35,28,49,255), width=max(1,int(3*s)))


def pencil(draw, cx, cy, angle=0.0):
    L, T = 58, 13
    ca, sa = math.cos(angle), math.sin(angle)
    def rot(x, y):
        return (cx + x*ca-y*sa, cy+x*sa+y*ca)
    body = [rot(-L/2,-T/2), rot(L/2-12,-T/2), rot(L/2-12,T/2), rot(-L/2,T/2)]
    tip = [rot(L/2-12,-T/2), rot(L/2+10,0), rot(L/2-12,T/2)]
    draw.polygon(body, fill=WHITE)
    draw.polygon(tip, fill=GREEN)
    draw.line((body[0], body[3]), fill=LILAC, width=3)


def gear(draw, cx, cy, phase=0.0):
    pts = []
    teeth = 12
    for i in range(teeth*2):
        a = phase + i*math.pi/teeth
        r = 33 if i % 2 == 0 else 27
        pts.append((cx+math.cos(a)*r, cy+math.sin(a)*r))
    draw.polygon(pts, fill=(232,232,238,245))
    draw.ellipse((cx-18,cy-18,cx+18,cy+18), fill=(18,12,30,255), outline=GREEN, width=3)
    draw.ellipse((cx-6,cy-6,cx+6,cy+6), fill=GREEN)


def globe(draw, cx, cy, phase=0.0):
    draw.ellipse((cx-33,cy-33,cx+33,cy+33), outline=WHITE, width=3)
    draw.arc((cx-20,cy-33,cx+20,cy+33), 90, 270, fill=LILAC, width=2)
    draw.arc((cx-20,cy-33,cx+20,cy+33), -90, 90, fill=LILAC, width=2)
    yoff = int(math.sin(phase)*3)
    draw.line((cx-31,cy+yoff,cx+31,cy+yoff), fill=GREEN, width=2)
    draw.arc((cx-31,cy-18,cx+31,cy+18), 0, 180, fill=MUTED, width=2)
    draw.arc((cx-31,cy-18,cx+31,cy+18), 180, 360, fill=MUTED, width=2)


def shuffle(draw, cx, cy, shift=0):
    y1, y2 = cy-17, cy+17
    draw.line((cx-35,y1,cx-10+shift,y1,cx+18,y2,cx+31,y2), fill=WHITE, width=4)
    draw.line((cx-35,y2,cx-10-shift,y2,cx+18,y1,cx+31,y1), fill=GREEN, width=4)
    draw.polygon([(cx+31,y2),(cx+21,y2-7),(cx+21,y2+7)], fill=WHITE)
    draw.polygon([(cx+31,y1),(cx+21,y1-7),(cx+21,y1+7)], fill=GREEN)


def network(draw, cx, cy, pulse=0.0):
    nodes = [(cx,cy-31),(cx-31,cy+17),(cx+31,cy+17),(cx,cy+30)]
    for a,b in [(0,1),(0,2),(1,3),(2,3),(1,2)]:
        draw.line((nodes[a],nodes[b]), fill=(210,205,230,210), width=2)
    for i,(x,y) in enumerate(nodes):
        rr = 7 + (2 if i == int(pulse*4)%4 else 0)
        draw.ellipse((x-rr,y-rr,x+rr,y+rr), fill=GREEN if i%2==0 else WHITE)


def power(draw, cx, cy, glow=0):
    draw.arc((cx-31,cy-31,cx+31,cy+31), -48, 228, fill=WHITE, width=6)
    draw.line((cx,cy-36,cx,cy-2), fill=GREEN, width=7)
    if glow:
        draw.ellipse((cx-5,cy-5,cx+5,cy+5), fill=(104,255,154,180))


def background(phase, kind):
    im = Image.new('RGBA', (W,H), BG)

    # broad purple ambience
    def purple_glow(d):
        x = 88 + math.sin(phase*2*math.pi) * 8
        d.ellipse((x-62, 12, x+62, 136), fill=(105, 76, 164, 56))
    im = composite_blur(im, purple_glow, 20)
    d = ImageDraw.Draw(im)

    # panel body / outlines
    d.rounded_rectangle((2,2,W-3,H-3), radius=11, fill=(19,10,34,245), outline=GREEN, width=3)
    d.rounded_rectangle((6,6,W-7,H-7), radius=9, outline=(218,193,255,150), width=2)
    d.rounded_rectangle((10,10,W-11,H-11), radius=7, fill=BG2)

    # PES2011-ish diagonal depth lines
    offset = int((phase*26) % 26)
    for x in range(-35, W+45, 30):
        d.line((x+offset,H-18,x+50+offset,18), fill=(104,255,154,33), width=2)

    # moving bottom energy bar
    bar_x = int(14 + phase*(W-50))
    d.rounded_rectangle((14,H-19,W-15,H-13), radius=3, fill=(255,255,255,18))
    d.rounded_rectangle((bar_x,H-20,min(W-14,bar_x+34),H-12), radius=4, fill=(104,255,154,115))

    return im


def draw_title(im, title):
    d = ImageDraw.Draw(im)
    f = fit_font(d, title, W-26, start=16, minimum=9)
    box = d.textbbox((0,0), title, font=f)
    tw = box[2]-box[0]
    d.text(((W-tw)/2, 17), title, font=f, fill=WHITE)
    d.line((27,42,W-28,42), fill=(104,255,154,125), width=1)


def draw_icon(im, kind, phase):
    d = ImageDraw.Draw(im)
    cx, cy = W//2, 96
    wave = math.sin(phase*2*math.pi)

    # icon-local glow
    glow = Image.new('RGBA', (W,H), (0,0,0,0))
    gd = ImageDraw.Draw(glow)
    rr = int(34 + 4*(0.5+0.5*wave))
    gd.ellipse((cx-rr,cy-rr,cx+rr,cy+rr), fill=(104,255,154,38))
    im.alpha_composite(glow.filter(ImageFilter.GaussianBlur(12)))
    d = ImageDraw.Draw(im)

    if kind == 'match':
        y = cy + int(wave*4)
        ball(d,cx,y,20)
        d.polygon([(cx-48,cy),(cx-34,cy-11),(cx-34,cy+11)], fill=GREEN)
        d.polygon([(cx+48,cy),(cx+34,cy-11),(cx+34,cy+11)], fill=LILAC)
    elif kind == 'master':
        shield(d,cx,cy,1.0 + 0.025*wave)
    elif kind == 'league':
        heights = [25,42,31,52]
        for i,h in enumerate(heights):
            h2 = h + int(4*math.sin(phase*2*math.pi+i))
            x = cx-39+i*25
            d.rounded_rectangle((x,cy+29-h2,x+15,cy+29),radius=3,
                                fill=GREEN if i==3 else (240,240,244,235))
        d.line((cx-47,cy+31,cx+48,cy+31), fill=LILAC, width=2)
    elif kind == 'cup':
        world_cup(d,cx,cy+3,True)
    elif kind == 'training':
        cone(d,cx-26,cy+8,0.85)
        cone(d,cx+27,cy+8,0.85)
        ball(d,cx,cy-16+int(wave*3),13)
    elif kind == 'edit':
        pencil(d,cx,cy,angle=-0.65 + 0.05*wave)
        d.line((cx-34,cy+30,cx+34,cy+30),fill=GREEN,width=2)
    elif kind == 'options':
        gear(d,cx,cy,phase=phase*2*math.pi/10)
    elif kind == 'international':
        globe(d,cx,cy,phase*2*math.pi)
        ball(d,cx+29,cy+25,10)
    elif kind == 'random':
        shuffle(d,cx,cy,int(wave*5))
    elif kind == 'network':
        network(d,cx,cy,phase)
    elif kind == 'exit':
        power(d,cx,cy,int(phase*FRAMES)%2)


def add_sheen(im, phase):
    layer = Image.new('RGBA', (W,H), (0,0,0,0))
    d = ImageDraw.Draw(layer)
    x = int(-55 + (W+110)*phase)
    d.polygon([(x-20,10),(x+7,10),(x+52,H-12),(x+24,H-12)], fill=(255,255,255,42))
    layer = layer.filter(ImageFilter.GaussianBlur(7))
    return Image.alpha_composite(im, layer)


def make_frame(title, kind, frame_index):
    phase = frame_index / FRAMES
    im = background(phase, kind)
    draw_title(im, title)
    draw_icon(im, kind, phase)
    im = add_sheen(im, phase)
    return im


for filename, title, kind in ITEMS:
    stem = Path(filename).stem
    frames = []
    for i in range(FRAMES):
        frame = make_frame(title, kind, i)
        frame.save(OUT / f'{stem}_f{i}.png')
        frames.append(frame)
    # Base file doubles as safe fallback and matches frame 0.
    frames[0].save(OUT / filename)

print(f'Generated {len(ITEMS)} PES2011-style cards + {len(ITEMS)*FRAMES} animated frames in {OUT.resolve()}')
