from pathlib import Path

p = Path("kitserver_module/menu_cards.cpp")
s = p.read_text(encoding="utf-8")

old = '        g_iconMaskAlpha = std::max(0, std::min(255, GetPrivateProfileIntA("menu_cards", "icon_mask_alpha", 218, IniPath().c_str())));\n'
new = '        g_iconMaskAlpha = std::max(0, std::min(255, static_cast<int>(GetPrivateProfileIntA("menu_cards", "icon_mask_alpha", 218, IniPath().c_str()))));\n'

if old not in s:
    raise SystemExit("V18 icon mask config line not found")

s = s.replace(old, new, 1)
p.write_text(s, encoding="utf-8")
print("Applied V18 compile fix for icon_mask_alpha")
