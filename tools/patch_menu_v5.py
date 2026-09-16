from pathlib import Path
import re

p = Path("kitserver_module/menu_cards.cpp")
s = p.read_text(encoding="utf-8")

# The horizontal PES 2011 skin is still PES6's vertical menu underneath.
# So NEXT/PREV are DOWN/UP, not RIGHT/LEFT.
needle = "    constexpr DWORD LEFT_PRESSED = 0x40;\n    constexpr DWORD RIGHT_PRESSED = 0x80;\n"
if needle in s and "UP_PRESSED" not in s:
    s = s.replace(
        needle,
        "    constexpr DWORD UP_PRESSED = 0x10;\n    constexpr DWORD DOWN_PRESSED = 0x20;\n" + needle,
        1,
    )

# Main-menu BINs can be requested again while entering other screens.
# Only the FIRST detection is allowed to auto-show the card.
asset_pattern = re.compile(
    r'''        if \(!g_seenMainMenuAssets\)\n            Log\("main menu asset detected: afs=%lu file=%lu", afsId, localId\);\n        g_seenMainMenuAssets = true;\n        if \(g_autoMainMenu\)\n        \{\n            g_visible = true;\n            g_hiddenByEnter = false;\n            g_transitionStart = GetTickCount64\(\);\n        \}'''
)
asset_replacement = '''        if (!g_seenMainMenuAssets)\n        {\n            Log("main menu asset detected: afs=%lu file=%lu", afsId, localId);\n            g_seenMainMenuAssets = true;\n            if (g_autoMainMenu)\n            {\n                g_visible = true;\n                g_hiddenByEnter = false;\n                g_transitionStart = GetTickCount64();\n            }\n        }'''
s, count = asset_pattern.subn(asset_replacement, s, count=1)
if count != 1:
    raise SystemExit("main menu asset visibility block not found")

# Replace the old input logic completely.
# Keyboard is read directly from Windows here because that path is already proven
# reliable in this module (F9 and the early manual card tests worked this way).
# PES/Kitserver's input table remains only as gamepad fallback.
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

        bool keyboardNav = false;

        if (g_autoMainMenu && g_visible)
        {
            // The horizontal skin is only visual: PES6 still navigates the list vertically.
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

            // Hide immediately when the user ENTERS an option.
            // X is the usual PES6 confirm key; Enter/Space cover alternate keyboard setups.
            const bool confirmKeyboard =
                (GetAsyncKeyState('X') & 1) ||
                (GetAsyncKeyState(VK_RETURN) & 1) ||
                (GetAsyncKeyState(VK_SPACE) & 1);
            if (confirmKeyboard)
            {
                g_visible = false;
                g_hiddenByEnter = true;
                Log("keyboard hide: left main menu index=%d", g_index);
                return;
            }
        }
        else if (g_autoMainMenu && !g_visible && g_hiddenByEnter)
        {
            // When backing out of the first screen opened from the main menu,
            // restore the card immediately. This fixes the old 'returns with no card' bug.
            const bool cancelKeyboard =
                (GetAsyncKeyState('Z') & 1) ||
                (GetAsyncKeyState(VK_ESCAPE) & 1) ||
                (GetAsyncKeyState(VK_BACK) & 1);
            if (cancelKeyboard)
            {
                g_visible = true;
                g_hiddenByEnter = false;
                g_transitionStart = GetTickCount64();
                Log("keyboard show: returned to main menu index=%d", g_index);
                return;
            }
        }

        // Gamepad fallback. Do not process keyboard navigation twice in the same frame.
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

        if (g_autoMainMenu && g_visible)
        {
            if (!keyboardNav)
            {
                if (dirEdge & DOWN_PRESSED) TriggerIndex(g_index + 1);
                else if (dirEdge & UP_PRESSED) TriggerIndex(g_index - 1);
            }

            if (funcEdge & CROSS_PRESSED)
            {
                g_visible = false;
                g_hiddenByEnter = true;
                Log("pad hide: left main menu index=%d", g_index);
                return;
            }
        }
        else if (g_autoMainMenu && !g_visible && g_hiddenByEnter && (funcEdge & CIRCLE_PRESSED))
        {
            g_visible = true;
            g_hiddenByEnter = false;
            g_transitionStart = GetTickCount64();
            Log("pad show: returned to main menu index=%d", g_index);
        }
    }

    void DrawCard'''
s, count = pattern.subn(replacement, s, count=1)
if count != 1:
    raise SystemExit("HandleInput block not found")

p.write_text(s, encoding="utf-8")
print("Patched menu_cards.cpp for V7")
