from pathlib import Path

p = Path("kitserver_module/menu_cards.cpp")
s = p.read_text(encoding="utf-8")

# V23: the user's existing PES2011 horizontal menu is authoritative.
# Keep all V15 input/lifecycle and V22 upper-panel animation, but make the
# custom V18 strip opt-in only so it can never cover the normal menu by default.

old = "    bool g_customIconStrip = true;\n"
new = "    bool g_customIconStrip = false;\n"
if old in s:
    s = s.replace(old, new, 1)

old = '        g_customIconStrip = GetPrivateProfileIntA("menu_cards", "custom_icon_strip", 1, IniPath().c_str()) != 0;\n'
new = '        g_customIconStrip = GetPrivateProfileIntA("menu_cards", "custom_icon_strip", 0, IniPath().c_str()) != 0;\n'
if old in s:
    s = s.replace(old, new, 1)

p.write_text(s, encoding="utf-8")
print("Patched menu_cards.cpp for V23: original PES2011 bar stays untouched")
