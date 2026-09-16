from pathlib import Path
p = Path("kitserver_module/menu_cards.cpp")
s = p.read_text(encoding="utf-8")
s = s.replace('std::max(1, GetPrivateProfileIntA("menu_cards", "joy_confirm_button", 1, IniPath().c_str()))', 'std::max(1, static_cast<int>(GetPrivateProfileIntA("menu_cards", "joy_confirm_button", 1, IniPath().c_str())))')
s = s.replace('std::max(1, GetPrivateProfileIntA("menu_cards", "joy_cancel_button", 2, IniPath().c_str()))', 'std::max(1, static_cast<int>(GetPrivateProfileIntA("menu_cards", "joy_cancel_button", 2, IniPath().c_str())))')
p.write_text(s, encoding="utf-8")
print("Applied V12 compile fix")
