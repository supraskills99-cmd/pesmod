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

# Read actual keyboard events from Kitserver's keyboard hook. Present-time polling
# can happen after Kitserver has already consumed/cleared the input table.
pattern = re.compile(r"    void HandleInput\(\)\n    \{.*?\n    \}\n\n    void DrawCard", re.S)
replacement = r'''    void HandleInput()
    {
        // Emergency test controls only.
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
    }

    void __cdecl OnInput(int code1, WPARAM wParam, LPARAM lParam)
    {
        if (code1 < 0) return;
        if ((code1 != HC_ACTION) || !(lParam & 0x80000000)) return; // key release
        if (!g_autoMainMenu) return;

        if (g_visible)
        {
            if (wParam == VK_RIGHT)
            {
                TriggerIndex(g_index + 1);
                return;
            }
            if (wParam == VK_LEFT)
            {
                TriggerIndex(g_index - 1);
                return;
            }
            if (wParam == VK_RETURN || wParam == VK_SPACE)
            {
                g_visible = false;
                g_hiddenByEnter = true;
                Log("keyboard hide: enter option index=%d key=%u", g_index, (unsigned)wParam);
                return;
            }
        }
        else if (g_hiddenByEnter && (wParam == VK_ESCAPE || wParam == VK_BACK))
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
print("Patched menu_cards.cpp for V5")
