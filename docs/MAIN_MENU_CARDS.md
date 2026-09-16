# Animated PES 6 main-menu cards

This branch adds the first runnable prototype of the PES 2011-style animated
card requested for the horizontal PES 6 main menu.

## What it does

- Keeps the existing PES 6 horizontal menu underneath.
- Draws one vertical card directly **above the selected icon axis**.
- The card grows upward from the icon with a short ease-out animation.
- Adds a mirrored, fading reflection under the card.
- Adds a subtle moving light sweep and idle breathing.
- Uses the PES 6 option order:
  1. Partido
  2. Liga Master
  3. Liga
  4. Copa
  5. Entrenamiento
  6. Editar
  7. Opciones
  8. Partido Internacional
  9. Partido de Seleccion al Azar
  10. Red
  11. Salir

The Copa card uses the normal tall World-Cup-style trophy silhouette requested
during the design pass, not the colorful themed logo.

## First test controls

This is the visual integration pass. It deliberately does not replace PES 6's
menu logic.

- **F9**: show/hide animated card overlay.
- **Left / Right**: move the card index in the same 11-item order.
- **F10**: reload PNG card assets from disk.

The next reverse-engineering step is to replace the temporary Left/Right sync
with the game's native selected-main-menu index, so controller navigation and
the overlay are always synchronized automatically.

## Runtime assets

The plugin looks for:

`PESMod\menu_cards\*.png`

next to the game executable.

Run `python tools/generate_menu_cards.py` once to create the supplied 256x384
placeholder PNGs (requires Pillow). The CI build does this automatically. The
PNGs can then be replaced without recompiling PESMod as long as filenames stay
the same.

## Configuration

See `[main_menu_cards]` in `PESMod.ini`.

`anchor_x` and `anchor_y` are screen-relative values, so the card should remain
anchored correctly at different resolutions. The defaults target the selected
column position in the supplied horizontal-menu mapping.

The branch has a Win32 GitHub Actions build so each renderer change is compiled
before handing the test package over for in-game testing.
