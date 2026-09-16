from pathlib import Path
import re

p = Path("kitserver_module/menu_cards.cpp")
s = p.read_text(encoding="utf-8")

# The PES 2011 horizontal skin is still PES6's vertical menu underneath.
needle = "    constexpr DWORD LEFT_PRESSED = 0x40;\n    constexpr DWORD RIGHT_PRESSED = 0x80;\n"
if needle in s and "UP_PRESSED" not in s:
    s = s.replace(
        needle,
        "    constexpr DWORD UP_PRESSED = 0x10;\n    constexpr DWORD DOWN_PRESSED = 0x20;\n" + needle,
        1,
    )

# Logical PES6 button bits exposed by Kitserver's GetInputTable().
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

# State for nested menu depth plus pad debouncing. GetInputTable already contains
# PRESSED events, so we must not run our own old dirEdge/funcEdge filter on top.
state_needle = "    int g_prevIndex = 0;\n    ULONGLONG g_transitionStart = 0;\n"
if "g_menuDepth" not in s:
    if state_needle not in s:
        raise SystemExit("state insertion point not found")
    s = s.replace(
        state_needle,
        "    int g_prevIndex = 0;\n"
        "    int g_menuDepth = 0;\n"
        "    ULONGLONG g_lastMenuActionAt = 0;\n"
        "    ULONGLONG g_lastPadNavAt = 0;\n"
        "    ULONGLONG g_lastPadFuncAt = 0;\n"
        "    ULONGLONG g_transitionStart = 0;\n",
        1,
    )

# Only the very first main-menu BIN detection auto-shows. Submenus can request
# those same assets, so later detections must never show the overlay by themselves.
asset_pattern = re.compile(
    r'''        if \(!g_seenMainMenuAssets\)\n            Log\("main menu asset detected: afs=%lu file=%lu", afsId, localId\);\n        g_seenMainMenuAssets = true;\n        if \(g_autoMainMenu\)\n        \{\n            g_visible = true;\n            g_hiddenByEnter = false;\n            g_transitionStart = GetTickCount64\(\);\n        \}'''
)
asset_replacement = '''        if (!g_seenMainMenuAssets)\n        {\n            Log("main menu asset detected: afs=%lu file=%lu", afsId, localId);\n            g_seenMainMenuAssets = true;\n            if (g_autoMainMenu)\n            {\n                g_visible = true;\n                g_hiddenByEnter = false;\n                g_menuDepth = 0;\n                g_transitionStart = GetTickCount64();\n            }\n        }'''
s, count = asset_pattern.subn(asset_replacement, s, count=1)
if count != 1:
    raise SystemExit("main menu asset visibility block not found")

# V10 input handling:
# - keyboard keeps the already-working direct Windows path;
# - joystick reads Kitserver's PRESSED table exactly like original Kitserver modules;
# - no extra edge-filtering, which was swallowing pad input;
# - confirm/cancel update a depth counter so the card stays hidden in submenus and
#   comes back automatically once the user cancels back to the main menu.
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

        const ULONGLONG now = GetTickCount64();
        bool keyboardNav = false;

        // Keyboard navigation: this horizontal skin still uses PES6's UP/DOWN list.
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
            const ULONGLONG t = GetTickCount64();
            if (t - g_lastMenuActionAt < 100) return;
            g_lastMenuActionAt = t;

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
            const ULONGLONG t = GetTickCount64();
            if (t - g_lastMenuActionAt < 100) return;
            g_lastMenuActionAt = t;

            if (!g_visible && g_hiddenByEnter)
            {
                if (g_menuDepth > 0) --g_menuDepth;
                Log("submenu cancel: depth=%d", g_menuDepth);
                if (g_menuDepth == 0)
                {
                    g_visible = true;
                    g_hiddenByEnter = false;
                    g_transitionStart = t;
                    Log("show main menu again: index=%d", g_index);
                }
            }
        };

        if (confirmKeyboard) confirmAction();
        if (cancelKeyboard) cancelAction();

        // Read Kitserver's real PES input snapshot. It already stores PRESSED events,
        // one DWORD per controller. This is the same access pattern used by original
        // Kitserver modules, and works for d-pad / mapped analog navigation too.
        if (!g_getInputTable) return;
        DWORD* table = g_getInputTable();
        if (!table) return;

        bool padDown = false;
        bool padUp = false;
        bool padConfirm = false;
        bool padCancel = false;
        DWORD seenDir = 0;
        DWORD seenFunc = 0;

        for (int n = 0; n < 8; ++n)
        {
            const DWORD dir = table[DIRECTIONAL_PRESSED + n];
            const DWORD func = table[FUNCTIONAL + n];
            seenDir |= dir;
            seenFunc |= func;

            if (dir & DOWN_PRESSED) padDown = true;
            if (dir & UP_PRESSED) padUp = true;
            if (func & CROSS_PRESSED) padConfirm = true;
            if (func & (TRIANGLE_PRESSED | CIRCLE_PRESSED)) padCancel = true;
        }

        if (seenDir || seenFunc)
            Log("pad snapshot dir=%08lx func=%08lx depth=%d visible=%d",
                (unsigned long)seenDir, (unsigned long)seenFunc,
                g_menuDepth, g_visible ? 1 : 0);

        if (g_autoMainMenu && g_visible && !keyboardNav && now - g_lastPadNavAt >= 110)
        {
            if (padDown)
            {
                g_lastPadNavAt = now;
                TriggerIndex(g_index + 1);
            }
            else if (padUp)
            {
                g_lastPadNavAt = now;
                TriggerIndex(g_index - 1);
            }
        }

        if (now - g_lastPadFuncAt >= 110)
        {
            if (padConfirm)
            {
                g_lastPadFuncAt = now;
                confirmAction();
            }
            else if (padCancel)
            {
                g_lastPadFuncAt = now;
                cancelAction();
            }
        }
    }

    void DrawCard'''
s, count = pattern.subn(replacement, s, count=1)
if count != 1:
    raise SystemExit("HandleInput block not found")

p.write_text(s, encoding="utf-8")
print("Patched menu_cards.cpp for V10: real pad input + reliable return")
