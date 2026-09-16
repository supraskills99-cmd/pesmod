from pathlib import Path

p = Path("kitserver_module/menu_cards.cpp")
s = p.read_text(encoding="utf-8")

# V20: clean the remaining PES6 graphics out of the carousel zone and make
# our replacement icon strip read as one coherent PES2011-style navigation bar.
# Input/lifecycle logic stays untouched.

repls = {
    "    float g_iconSize = 0.050f;\n": "    float g_iconSize = 0.058f;\n",
    "    int g_iconMaskAlpha = 228;\n": "    int g_iconMaskAlpha = 250;\n",
    "        g_iconSize = ReadFloat(\"icon_size\", 0.050f);\n": "        g_iconSize = ReadFloat(\"icon_size\", 0.058f);\n",
    "        g_iconMaskAlpha = std::max(0, std::min(255, static_cast<int>(GetPrivateProfileIntA(\"menu_cards\", \"icon_mask_alpha\", 228, IniPath().c_str()))));\n": "        g_iconMaskAlpha = std::max(0, std::min(255, static_cast<int>(GetPrivateProfileIntA(\"menu_cards\", \"icon_mask_alpha\", 250, IniPath().c_str()))));\n",
}
for old, new in repls.items():
    if old not in s:
        raise SystemExit(f"V20 marker missing: {old!r}")
    s = s.replace(old, new, 1)

old = '''        const BYTE ma = static_cast<BYTE>(g_iconMaskAlpha);
        DrawQuad(dev, nullptr,
                 0.0f, stripY - baseSize * 1.55f,
                 W, stripY + baseSize * 1.05f,
                 Argb(static_cast<BYTE>(ma * 0.72f), 8,5,16),
                 Argb(ma, 15,8,27));
'''
new = '''        const BYTE ma = static_cast<BYTE>(g_iconMaskAlpha);
        const float maskTop = stripY - baseSize * 1.82f;
        const float maskCoreTop = stripY - baseSize * 1.50f;
        const float maskCoreBottom = stripY + baseSize * 1.18f;
        const float maskBottom = stripY + baseSize * 1.48f;

        // Feathered opaque replacement band. The core is deliberately almost
        // opaque so PES6's original arrows, labels and icons cannot bleed through.
        DrawQuad(dev, nullptr,
                 0.0f, maskTop, W, maskCoreTop,
                 Argb(0, 8,5,16), Argb(ma, 11,6,20));
        DrawQuad(dev, nullptr,
                 0.0f, maskCoreTop, W, maskCoreBottom,
                 Argb(ma, 11,6,20), Argb(ma, 15,8,27));
        DrawQuad(dev, nullptr,
                 0.0f, maskCoreBottom, W, maskBottom,
                 Argb(ma, 15,8,27), Argb(0, 15,8,27));
'''
if old not in s:
    raise SystemExit("V20 V19 mask block missing")
s = s.replace(old, new, 1)

# Give the selected position a slightly stronger PES2011 pedestal so the
# fixed card and the moving carousel visually belong to the same control.
old = '''        const float pulse = 0.5f + 0.5f * std::sin(static_cast<float>(now) * 0.006f);
        const BYTE glowA = static_cast<BYTE>(38.0f + pulse * 30.0f);
        DrawQuad(dev, nullptr,
                 centerX - baseSize * 0.58f, stripY + baseSize * 0.47f,
                 centerX + baseSize * 0.58f, stripY + baseSize * 0.55f,
                 Argb(glowA,104,255,154), Argb(0,104,255,154));
'''
new = '''        const float pulse = 0.5f + 0.5f * std::sin(static_cast<float>(now) * 0.006f);
        const BYTE glowA = static_cast<BYTE>(52.0f + pulse * 42.0f);
        DrawQuad(dev, nullptr,
                 centerX - baseSize * 0.72f, stripY + baseSize * 0.48f,
                 centerX + baseSize * 0.72f, stripY + baseSize * 0.56f,
                 Argb(glowA,104,255,154), Argb(0,104,255,154));
        DrawQuad(dev, nullptr,
                 centerX - baseSize * 0.48f, stripY + baseSize * 0.40f,
                 centerX + baseSize * 0.48f, stripY + baseSize * 0.44f,
                 Argb(static_cast<BYTE>(glowA * 0.70f),211,189,255),
                 Argb(0,211,189,255));
'''
if old not in s:
    raise SystemExit("V20 pedestal block missing")
s = s.replace(old, new, 1)

# Slightly stronger selected scaling and less tiny neighboring icons.
old = '''            const float size = baseSize * (0.76f + 0.30f * selected + 0.08f * nearFade);
            const float y = stripY - baseSize * 0.10f * selected;
'''
new = '''            const float size = baseSize * (0.80f + 0.34f * selected + 0.08f * nearFade);
            const float y = stripY - baseSize * 0.12f * selected;
'''
if old not in s:
    raise SystemExit("V20 icon sizing marker missing")
s = s.replace(old, new, 1)

p.write_text(s, encoding="utf-8")
print("Patched menu_cards.cpp for V20: clean original PES6 carousel and strengthen PES2011 strip")
