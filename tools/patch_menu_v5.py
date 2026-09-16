from pathlib import Path
import re

p = Path("kitserver_module/menu_cards.cpp")
s = p.read_text(encoding="utf-8")

# Aggregate all controller slots as a fallback.
old_poll = """        const DWORD dir = table[DIRECTIONAL_PRESSED];
        const DWORD func = table[FUNCTIONAL];
        const DWORD dirEdge = dir & ~g_lastDirectional;
        const DWORD funcEdge = func & ~g_lastFunctional;
        g_lastDirectional = dir;
        g_lastFunctional = func;
"""
new_poll = """        DWORD dir = 0;
        DWORD func = 0;
        for (int n = 0; n < 8; ++n)
        {
            dir |= table[DIRECTIONAL_PRESSED + n];
            func |= table[FUNCTIONAL + n];
        }
        const DWORD dirEdge = dir & ~g_lastDirectional;
        const DWORD funcEdge = func & ~g_lastFunctional;
        g_lastDirectional = dir;
        g_lastFunctional = func;
"""
if old_poll in s:
    s = s.replace(old_poll, new_poll, 1)

# Direction bits used by the horizontal PES 2011 menu are actually UP/DOWN.
needle = "    constexpr DWORD LEFT_PRESSED = 0x40;\n    constexpr DWORD RIGHT_PRESSED = 0x80;\n"
if needle in s and "UP_PRESSED" not in s:
    s = s.replace(
        needle,
        "    constexpr DWORD UP_PRESSED = 0x10;\n    constexpr DWORD DOWN_PRESSED = 0x20;\n" + needle,
        1,
    )

# hk_Input is index 20 in Kitserver 6 hook.h.
needle = "    constexpr int HK_D3D_PRESENT = 3;\n"
if "HK_INPUT" not in s:
    if needle not in s:
        raise SystemExit("HK_D3D_PRESENT constant not found")
    s = s.replace(needle, needle + "    constexpr int HK_INPUT = 20;\n", 1)

if "g_inputHooked" not in s:
    needle = "    bool g_createHooked = false;\n    bool g_afsHooked = false;\n"
    if needle not in s:
        raise SystemExit("hook flags block not found")
    s = s.replace(needle, "    bool g_createHooked = false;\n    bool g_inputHooked = false;\n    bool g_afsHooked = false;\n", 1)

# Do not re-show the card every time the main-menu BINs are requested again.
# That was the reason MATCH leaked into team-select and other submenus.
asset_pattern = re.compile(
    r'''        if \(!g_seenMainMenuAssets\)\n            Log\("main menu asset detected: afs=%lu file=%lu", afsId, localId\);\n        g_seenMainMenuAssets = true;\n        if \(g_autoMainMenu\)\n        \{\n            g_visible = true;\n            g_hiddenByEnter = false;\n            g_transitionStart = GetTickCount64\(\);\n        \}'''
)
asset_replacement = '''        if (!g_seenMainMenuAssets)\n        {\n            Log("main menu asset detected: afs=%lu file=%lu", afsId, localId);\n            g_seenMainMenuAssets = true;\n            if (g_autoMainMenu)\n            {\n                g_visible = true;\n                g_hiddenByEnter = false;\n                g_transitionStart = GetTickCount64();\n            }\n        }'''
s, count = asset_pattern.subn(asset_replacement, s, count=1)
if count != 1:
    raise SystemExit("main menu asset visibility block not found")

# Use both the real Kitserver keyboard hook and controller polling.
# The horizontal skin visually moves left/right, but internally PES navigates it with UP/DOWN.
pattern = re.compile(r"    void HandleInput\(\)\n    \{.*?\n    \}\n\n    void DrawCard", re.S)
replacement = r'''    void HandleInput()
    {
        if (GetAsyncKeyState(VK_F9) & 1)
        {
            g_visible = !g_visible;
            g_hiddenByEnter = false;
            g_transitionStart = GetTickCount64();
            Log("F9 visible=%d", g_visible ? 1 : 0);
        }
        if (GetAsyncKeyState(VK_F10) & 1)
        {
            ReleaseTextures();
            ReadConfig();
            Log("F10 reload");
        }

        // Gamepad / PES input-table fallback.
        if (!g_getInputTable) return;
        DWORD* table = g_getInputTable();
        if (!table) return;

        DWORD dir = 0;
        DWORD func = 0;
        for (int n = 0; n < 8; ++n)
        {
            dir |= table[DIRECTIONAL_PRESSED + n];
            func |= table[FUNCTIONAL + n];
        }
        const DWORD dirEdge = dir & ~g_lastDirectional;
        const DWORD funcEdge = func & ~g_lastFunctional;
        g_lastDirectional = dir;
        g_lastFunctional = func;

        if (g_visible)
        {
            if (dirEdge & DOWN_PRESSED) TriggerIndex(g_index + 1);
            else if (dirEdge & UP_PRESSED) TriggerIndex(g_index - 1);

            if (funcEdge & CROSS_PRESSED)
            {
                g_visible = false;
                g_hiddenByEnter = true;
                Log("pad hide: enter option index=%d", g_index);
            }
        }
        else if (g_hiddenByEnter && (funcEdge & CIRCLE_PRESSED))
        {
            g_visible = true;
            g_hiddenByEnter = false;
            g_transitionStart = GetTickCount64();
            Log("pad show: returned to main menu index=%d", g_index);
        }
    }

    void __cdecl OnInput(int code1, WPARAM wParam, LPARAM lParam)
    {
        if (code1 < 0) return;
        if ((code1 != HC_ACTION) || !(lParam & 0x80000000)) return; // key release
        if (!g_autoMainMenu) return;

        if (g_visible)
        {
            // Important: this horizontal menu is still PES6's vertical menu underneath.
            // DOWN advances to the next card; UP returns to the previous one.
            if (wParam == VK_DOWN)
            {
                TriggerIndex(g_index + 1);
                return;
            }
            if (wParam == VK_UP)
            {
                TriggerIndex(g_index - 1);
                return;
            }

            // LEFT/RIGHT are used inside many submenus. Never change the main-menu card with them.
            if (wParam == VK_LEFT || wParam == VK_RIGHT || wParam == VK_F9 || wParam == VK_F10)
                return;
            if (wParam == VK_SHIFT || wParam == VK_CONTROL || wParam == VK_MENU)
                return;

            // Any other action key while the main card is visible means PES is leaving
            // or activating the main menu. Hide immediately so the overlay cannot leak
            // into team-select/options/etc. This also catches custom PES confirm keys.
            g_visible = false;
            g_hiddenByEnter = true;
            Log("keyboard hide: leaving main menu index=%d key=%u", g_index, (unsigned)wParam);
            return;
        }

        if (g_hiddenByEnter && (wParam == VK_ESCAPE || wParam == VK_BACK || wParam == 'Z'))
        {
            g_visible = true;
            g_hiddenByEnter = false;
            g_transitionStart = GetTickCount64();
            Log("keyboard show: returned to main menu index=%d key=%u", g_index, (unsigned)wParam);
        }
    }

    void DrawCard'''
s, count = pattern.subn(replacement, s, count=1)
if count != 1:
    raise SystemExit("HandleInput block not found")

reg_old = """        g_hookFunction(HK_D3D_PRESENT, reinterpret_cast<DWORD>(&OnPresent));
        g_presentHooked = true;
        Log("registered hk_D3D_Create + hk_D3D_Present; input=%s", g_getInputTable ? "OK" : "missing");
"""
reg_new = """        g_hookFunction(HK_D3D_PRESENT, reinterpret_cast<DWORD>(&OnPresent));
        g_presentHooked = true;
        g_hookFunction(HK_INPUT, reinterpret_cast<DWORD>(&OnInput));
        g_inputHooked = true;
        Log("registered hk_D3D_Create + hk_D3D_Present + hk_Input; table=%s", g_getInputTable ? "OK" : "missing");
"""
if reg_old not in s:
    raise SystemExit("registration block not found")
s = s.replace(reg_old, reg_new, 1)

detach_old = """        if (g_createHooked && g_unhookFunction)
            g_unhookFunction(HK_D3D_CREATE, reinterpret_cast<DWORD>(&OnD3DCreate));
        ReleaseTextures();
"""
detach_new = """        if (g_createHooked && g_unhookFunction)
            g_unhookFunction(HK_D3D_CREATE, reinterpret_cast<DWORD>(&OnD3DCreate));
        if (g_inputHooked && g_unhookFunction)
            g_unhookFunction(HK_INPUT, reinterpret_cast<DWORD>(&OnInput));
        ReleaseTextures();
"""
if detach_old not in s:
    raise SystemExit("detach block not found")
s = s.replace(detach_old, detach_new, 1)

p.write_text(s, encoding="utf-8")
print("Patched menu_cards.cpp for V6")
