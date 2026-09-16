from pathlib import Path

p = Path("kitserver_module/menu_cards.cpp")
s = p.read_text(encoding="utf-8")

# V19: align the custom strip with the original PES2011 horizontal menu zone.
# Keep V15 input/lifecycle untouched. This only changes visual geometry/masking.
repls = {
    "    float g_iconStripY = 0.895f;\n": "    float g_iconStripY = 0.715f;\n",
    "    float g_iconSize = 0.052f;\n": "    float g_iconSize = 0.050f;\n",
    "    float g_iconGap = 0.064f;\n": "    float g_iconGap = 0.100f;\n",
    "    int g_iconMaskAlpha = 218;\n": "    int g_iconMaskAlpha = 228;\n",
    "        g_iconStripY = ReadFloat(\"icon_y\", 0.895f);\n": "        g_iconStripY = ReadFloat(\"icon_y\", 0.715f);\n",
    "        g_iconSize = ReadFloat(\"icon_size\", 0.052f);\n": "        g_iconSize = ReadFloat(\"icon_size\", 0.050f);\n",
    "        g_iconGap = ReadFloat(\"icon_gap\", 0.064f);\n": "        g_iconGap = ReadFloat(\"icon_gap\", 0.100f);\n",
    "        g_iconMaskAlpha = std::max(0, std::min(255, static_cast<int>(GetPrivateProfileIntA(\"menu_cards\", \"icon_mask_alpha\", 218, IniPath().c_str()))));\n": "        g_iconMaskAlpha = std::max(0, std::min(255, static_cast<int>(GetPrivateProfileIntA(\"menu_cards\", \"icon_mask_alpha\", 228, IniPath().c_str()))));\n",
    "                 0.0f, stripY - baseSize * 0.80f,\n                 W, stripY + baseSize * 0.76f,\n": "                 0.0f, stripY - baseSize * 1.55f,\n                 W, stripY + baseSize * 1.05f,\n",
}

for old, new in repls.items():
    if old not in s:
        raise SystemExit(f"V19 marker missing: {old!r}")
    s = s.replace(old, new, 1)

# Make distant icons fade progressively, closer to the PES2011 carousel feel.
old = '''            const float centerDistance = std::fabs((x - centerX) / gap);
            const float selected = 1.0f - Saturate(centerDistance);
            const float size = baseSize * (0.78f + 0.30f * selected);
            const float y = stripY - baseSize * 0.10f * selected;
            const BYTE a = static_cast<BYTE>(120.0f + 135.0f * selected);
'''
new = '''            const float centerDistance = std::fabs((x - centerX) / gap);
            const float selected = 1.0f - Saturate(centerDistance);
            const float nearFade = 1.0f - Saturate(centerDistance / 4.8f);
            const float size = baseSize * (0.76f + 0.30f * selected + 0.08f * nearFade);
            const float y = stripY - baseSize * 0.10f * selected;
            const float alphaF = 72.0f + 183.0f * std::max(selected, nearFade * 0.82f);
            const BYTE a = static_cast<BYTE>(std::max(0.0f, std::min(255.0f, alphaF)));
'''
if old not in s:
    raise SystemExit("V19 icon fade marker missing")
s = s.replace(old, new, 1)

p.write_text(s, encoding="utf-8")
print("Patched menu_cards.cpp for V19: aligned PES2011 icon strip and cleaned original menu zone")
