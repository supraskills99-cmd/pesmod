from pathlib import Path
import re

p = Path("kitserver_module/menu_cards.cpp")
s = p.read_text(encoding="utf-8")

# The horizontal PES 2011 skin is still PES6's vertical menu underneath.
needle = "    constexpr DWORD LEFT_PRESSED = 0x40;\n    constexpr DWORD RIGHT_PRESSED = 0x80;\n"
if needle in s and "UP_PRESSED" not in s:
    s = s.replace(
        needle,
        "    constexpr DWORD UP_PRESSED = 0x10;\n    constexpr DWORD DOWN_PRESSED = 0x20;\n" + needle,
        1,
    )

# PES6 menu cancel can arrive as TRIANGLE or CIRCLE depending on the
# active keyboard/pad mapping. Keep both so returning to the main menu
# is detected reliably.
func_needle = "    constexpr DWORD CROSS_PRESSED = 0x01;\n    constexpr DWORD CIRCLE_PRESSED = 0x08;\n"
if func_needle in s and "TRIANGLE_PRESSED" not in s:
    s = s.replace(
        func_needle,
        "    constexpr DWORD CROSS_PRESSED = 0x01;\n"
        "    constexpr DWORD TRIANGLE_PRESSED = 0x02;\n"
        "    constexpr DWORD SQUARE_PRESSED = 0x04;\n"
        "    constexpr DWORD CIRCLE_PRESSED = 0x08;\n",
        1,
    )

# Track how deep we are after leaving the main menu. This lets us keep the
# overlay hidden through nested screens and only restore it after enough
# CANCEL actions return us to depth 0.
state_needle = "    int g_prevIndex = 0;\n    ULONGLONG g_transitionStart = 0;\n"
if "g_menuDepth" not in s:
    if state_needle not in s:
        raise SystemExit("state insertion point not found")
    s = s.replace(
        state_needle,
        "    int g_prevIndex = 0;\n    int g_menuDepth = 0;\n    ULONGLONG g_lastMenuActionAt = 0;\n    ULONGLONG g_transitionStart = 0;\n",
        1,
    )

# Main-menu BINs can be requested again while entering other screens.
# Only the FIRST detection may auto-show the overlay.
asset_pattern = re.compile(
    r'''        if \(!g_seenMainMenuAssets\)\n            Log\("main menu asset detected: afs=%lu file=%lu", afsId, localId\);\n        g_seenMainMenuAssets = true;\n        if \(g_autoMainMenu\)\n        \{\n            g_visible = true;\n            g_hiddenByEnter = false;\n            g_transitionStart = GetTickCount64\(\);\n        \}'''
)
asset_replacement = '''        if (!g_seenMainMenuAssets)\n        {\n            Log("main menu asset detected: afs=%lu file=%lu", afsId, localId);\n            g_seenMainMenuAssets = true;\n            if (g_autoMainMenu)\n            {\n                g_visible = true;\n                g_hiddenByEnter = false;\n                g_menuDepth = 0;\n                g_transitionStart = GetTickCount64();\n            }\n        }'''
s, count = asset_pattern.subn(asset_replacement, s, count=1)
if count != 1:
    raise SystemExit("main menu asset visibility block not found")

# Replace input handling. The horizontal skin still navigates using UP/DOWN.
# We keep a depth counter while hidden. Most importantly, CANCEL is accepted
# from all common PES6 paths: keyboard D/Z/Esc/Backspace and pad TRIANGLE/CIRCLE.
pattern = re.compile(r"    void HandleInput\(\)\n    \{.*?\n    \}\n\n    void DrawCard", re.S)
replacement = r'''    void HandleInput()
    {
        if (GetAsyncKeyState(VK_F9) & 1)
        {
            g_visible = !g_visible;
            g_hiddenByEnter = !g_visible;
            if (g_visible) g_menuDepth = 0;
            g_transitionStart = GetTickCount64();
            Log("F9 visible=%d depth=%d", g_visible ? 1 : 0, g_menuDepth);
        }
        if (GetAsyncKeyState(VK_F10) & 1)
        {
            ReleaseTextures();
            ReadConfig();
            Log("F10 reload");
        }

        bool keyboardNav = false;

        if (g_autoMainMenu && g_visible)
        {
            if (GetAsyncKeyState(VK_DOWN) & 1)
            {
                TriggerIndex(g_index + 1);
                keyboardNav = true;
            }
            else if (GetAsyncKeyState(VK_UP) & 1)
            {
                TriggerIndex(g_index - 1);
                keyboardNav = true;
            }
        }

        const bool confirmKeyboard =
            (GetAsyncKeyState('X') & 1) ||
            (GetAsyncKeyState(VK_RETURN) & 1) ||
            (GetAsyncKeyState(VK_SPACE) & 1);
        const bool cancelKeyboard =
            (GetAsyncKeyState('D') & 1) ||
            (GetAsyncKeyState('Z') & 1) ||
            (GetAsyncKeyState(VK_ESCAPE) & 1) ||
            (GetAsyncKeyState(VK_BACK) & 1);

        auto confirmAction = [&]()
        {
            const ULONGLONG now = GetTickCount64();
            if (now - g_lastMenuActionAt < 120) return;
            g_lastMenuActionAt = now;

            if (g_visible)
            {
                g_menuDepth = 1;
                g_visible = false;
                g_hiddenByEnter = true;
                Log("hide main menu: index=%d depth=%d", g_index, g_menuDepth);
            }
            else if (g_hiddenByEnter)
            {
                if (g_menuDepth < 16) ++g_menuDepth;
                Log("submenu confirm: depth=%d", g_menuDepth);
            }
        };

        auto cancelAction = [&]()
        {
            const ULONGLONG now = GetTickCount64();
            if (now - g_lastMenuActionAt < 120) return;
            g_lastMenuActionAt = now;

            if (!g_visible && g_hiddenByEnter)
            {
                if (g_menuDepth > 0) --g_menuDepth;
                Log("submenu cancel: depth=%d", g_menuDepth);
                if (g_menuDepth == 0)
                {
                    g_visible = true;
                    g_hiddenByEnter = false;
                    g_transitionStart = now;
                    Log("show main menu again: index=%d", g_index);
                }
            }
        };

        if (confirmKeyboard) confirmAction();
        if (cancelKeyboard) cancelAction();

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

        if (g_autoMainMenu && g_visible && !keyboardNav)
        {
            if (dirEdge & DOWN_PRESSED) TriggerIndex(g_index + 1);
            else if (dirEdge & UP_PRESSED) TriggerIndex(g_index - 1);
        }

        if (funcEdge & CROSS_PRESSED)
        {
            Log("pad confirm edge=%08lx", (unsigned long)funcEdge);
            confirmAction();
        }
        if (funcEdge & (TRIANGLE_PRESSED | CIRCLE_PRESSED))
        {
            Log("pad cancel edge=%08lx", (unsigned long)funcEdge);
            cancelAction();
        }
    }

    void DrawCard'''
s, count = pattern.subn(replacement, s, count=1)
if count != 1:
    raise SystemExit("HandleInput block not found")

p.write_text(s, encoding="utf-8")
print("Patched menu_cards.cpp for V9")
