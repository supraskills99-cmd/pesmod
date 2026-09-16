from pathlib import Path
import importlib.util
from PIL import Image

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "generate_kitserver_menu_cards.py"

spec = importlib.util.spec_from_file_location("menu_card_generator", SOURCE)
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(mod)

# Reuse exactly the same icon drawing functions/colors as the V17 animated cards,
# but export transparent icon-only textures for the sliding bottom strip.
for filename, _title, kind in mod.ITEMS:
    canvas = Image.new('RGBA', (mod.W, mod.H), (0, 0, 0, 0))
    mod.draw_icon(canvas, kind, 0.0)

    # The source artwork is centered around (88,96). Crop tightly enough to make
    # the icon readable at ~65px on a 1280-wide game backbuffer while preserving
    # the soft glow around it.
    icon = canvas.crop((30, 38, 146, 154))
    stem = Path(filename).stem
    icon.save(mod.OUT / f"icon_{stem}.png")

print(f"Generated {len(mod.ITEMS)} transparent V18 menu-strip icons in {mod.OUT.resolve()}")
