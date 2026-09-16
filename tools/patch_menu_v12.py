from pathlib import Path
import re

p = Path("kitserver_module/menu_cards.cpp")
s = p.read_text(encoding="utf-8")

# V12: direct gamepad fallback for the PES6 main menu.
# V11 captures PES logical input globally. Some pads/drivers still bypass that
# table in the frontend, so add a second path that reads the physical controller
# directly: XInput first, WinMM joystick second. This only feeds our card state;
# PES itself continues receiving its input normally.

# WinMM joystick API.
if "#include <mmsystem.h>" not in s:
    s = s.replace("#include <windows.h>\n", "#include <windows.h>\n#include <mmsystem.h>\n", 1)

# Minimal XInput declarations without linking xinput.lib.
marker = "namespace\n{\n"
if marker not in s:
    raise SystemExit("namespace marker not found")
if "XINPUT_STATE_MIN" not in s:
    block = r'''namespace
{
    struct XINPUT_GAMEPAD_MIN
    {
        WORD wButtons;
        BYTE bLeftTrigger;
        BYTE bRightTrigger;
        SHORT sThumbLX;
        SHORT sThumbLY;
        SHORT sThumbRX;
        SHORT sThumbRY;
    };
    struct XINPUT_STATE_MIN
    {
        DWORD dwPacketNumber;
        XINPUT_GAMEPAD_MIN Gamepad;
    };
    using XInputGetStateFn = DWORD (WINAPI*)(DWORD, XINPUT_STATE_MIN*);

    constexpr WORD XI_DPAD_UP    = 0x0001;
    constexpr WORD XI_DPAD_DOWN  = 0x0002;
    constexpr WORD XI_A          = 0x1000;
    constexpr WORD XI_B          = 0x2000;

'''
    # Replace the original namespace opener with our declarations + same namespace.
    s = s.replace(marker, block, 1)

# Add direct pad state globals near the input snapshot globals.
global_marker = "    std::array<DWORD,24> g_inputSnapshot = {};\n"
if global_marker not in s:
    raise SystemExit("input snapshot global marker not found")
if "g_xinputGetState" not in s:
    s = s.replace(
        global_marker,
        global_marker +
        "    HMODULE g_xinputDll = nullptr;\n"
        "    XInputGetStateFn g_xinputGetState = nullptr;\n"
        "    bool g_directPadInitialized = false;\n"
        "    bool g_directPadPrevUp = false;\n"
        "    bool g_directPadPrevDown = false;\n"
        "    bool g_directPadPrevConfirm = false;\n"
        "    bool g_directPadPrevCancel = false;\n"
        "    int g_winmmConfirmButton = 1;\n"
        "    int g_winmmCancelButton = 2;\n",
        1,
    )

# Read optional generic-pad button mapping from menu_cards.ini (1-based buttons).
read_marker = "        g_reflection = ReadFloat(\"reflection_alpha\", 0.26f);\n"
if read_marker not in s:
    raise SystemExit("ReadConfig marker not found")
if "joy_confirm_button" not in s:
    s = s.replace(
        read_marker,
        read_marker +
        "        g_winmmConfirmButton = std::max(1, GetPrivateProfileIntA(\"menu_cards\", \"joy_confirm_button\", 1, IniPath().c_str()));\n"
        "        g_winmmCancelButton = std::max(1, GetPrivateProfileIntA(\"menu_cards\", \"joy_cancel_button\", 2, IniPath().c_str()));\n",
        1,
    )

# Insert direct controller polling before HandleInput.
handle_marker = "    void HandleInput()\n"
if handle_marker not in s:
    raise SystemExit("HandleInput marker not found")
if "PollDirectPad" not in s:
    direct_block = r'''    struct DirectPadSample
    {
        bool connected = false;
        bool up = false;
        bool down = false;
        bool confirm = false;
        bool cancel = false;
        const char* source = "none";
        DWORD rawButtons = 0;
    };

    void InitDirectPad()
    {
        if (g_directPadInitialized) return;
        g_directPadInitialized = true;

        const char* dlls[] = { "xinput1_4.dll", "xinput1_3.dll", "xinput9_1_0.dll" };
        for (const char* dll : dlls)
        {
            HMODULE mod = LoadLibraryA(dll);
            if (!mod) continue;
            auto fn = reinterpret_cast<XInputGetStateFn>(GetProcAddress(mod, "XInputGetState"));
            if (fn)
            {
                g_xinputDll = mod;
                g_xinputGetState = fn;
                Log("direct pad: XInput loaded from %s", dll);
                return;
            }
            FreeLibrary(mod);
        }
        Log("direct pad: XInput unavailable, WinMM fallback enabled");
    }

    DirectPadSample PollDirectPad()
    {
        InitDirectPad();
        DirectPadSample out;

        // Prefer XInput when any controller is connected. This covers Xbox pads
        // and PlayStation pads exposed through DS4Windows/Steam Input.
        if (g_xinputGetState)
        {
            for (DWORD i = 0; i < 4; ++i)
            {
                XINPUT_STATE_MIN st = {};
                if (g_xinputGetState(i, &st) != ERROR_SUCCESS) continue;
                out.connected = true;
                out.source = "xinput";
                out.rawButtons = st.Gamepad.wButtons;
                const bool stickUp = st.Gamepad.sThumbLY > 18000;
                const bool stickDown = st.Gamepad.sThumbLY < -18000;
                out.up = (st.Gamepad.wButtons & XI_DPAD_UP) != 0 || stickUp;
                out.down = (st.Gamepad.wButtons & XI_DPAD_DOWN) != 0 || stickDown;
                out.confirm = (st.Gamepad.wButtons & XI_A) != 0;
                out.cancel = (st.Gamepad.wButtons & XI_B) != 0;
                return out;
            }
        }

        // Generic/old DirectInput-style pads are usually visible through WinMM.
        for (UINT id = 0; id < 16; ++id)
        {
            JOYINFOEX ji = {};
            ji.dwSize = sizeof(ji);
            ji.dwFlags = JOY_RETURNALL;
            if (joyGetPosEx(id, &ji) != JOYERR_NOERROR) continue;

            out.connected = true;
            out.source = "winmm";
            out.rawButtons = ji.dwButtons;

            bool povUp = false, povDown = false;
            if (ji.dwPOV != JOY_POVCENTERED)
            {
                const DWORD p = ji.dwPOV % 36000;
                povUp = (p >= 31500 || p <= 4500);
                povDown = (p >= 13500 && p <= 22500);
            }
            // Most WinMM pads use the full 0..65535 range for Y.
            const bool axisUp = ji.dwYpos < 18000;
            const bool axisDown = ji.dwYpos > 47500;
            out.up = povUp || axisUp;
            out.down = povDown || axisDown;

            const DWORD confirmMask = 1u << static_cast<DWORD>(std::min(31, g_winmmConfirmButton - 1));
            const DWORD cancelMask = 1u << static_cast<DWORD>(std::min(31, g_winmmCancelButton - 1));
            out.confirm = (ji.dwButtons & confirmMask) != 0;
            out.cancel = (ji.dwButtons & cancelMask) != 0;
            return out;
        }

        return out;
    }

'''
    s = s.replace(handle_marker, direct_block + handle_marker, 1)

# Merge physical-pad edges into the existing V11 logical input inside HandleInput.
needle = '''        DWORD seenDir = 0;
        DWORD seenFunc = 0;
        for (int n = 0; n < 8; ++n)
        {
            seenDir |= g_inputSnapshot[static_cast<size_t>(DIRECTIONAL_PRESSED + n)];
            seenFunc |= g_inputSnapshot[static_cast<size_t>(FUNCTIONAL + n)];
        }

        if (!seenDir && !seenFunc) return;
        Log("PES input dir=%08lx func=%08lx depth=%d visible=%d",
            (unsigned long)seenDir, (unsigned long)seenFunc,
            g_menuDepth, g_visible ? 1 : 0);
'''
if needle not in s:
    raise SystemExit("V11 seenDir block not found")
replacement = r'''        DWORD seenDir = 0;
        DWORD seenFunc = 0;
        for (int n = 0; n < 8; ++n)
        {
            seenDir |= g_inputSnapshot[static_cast<size_t>(DIRECTIONAL_PRESSED + n)];
            seenFunc |= g_inputSnapshot[static_cast<size_t>(FUNCTIONAL + n)];
        }

        const DirectPadSample pad = PollDirectPad();
        const bool padUpEdge = pad.up && !g_directPadPrevUp;
        const bool padDownEdge = pad.down && !g_directPadPrevDown;
        const bool padConfirmEdge = pad.confirm && !g_directPadPrevConfirm;
        const bool padCancelEdge = pad.cancel && !g_directPadPrevCancel;
        g_directPadPrevUp = pad.up;
        g_directPadPrevDown = pad.down;
        g_directPadPrevConfirm = pad.confirm;
        g_directPadPrevCancel = pad.cancel;

        if (!seenDir && !seenFunc && !padUpEdge && !padDownEdge && !padConfirmEdge && !padCancelEdge)
            return;

        if (seenDir || seenFunc)
            Log("PES input dir=%08lx func=%08lx depth=%d visible=%d",
                (unsigned long)seenDir, (unsigned long)seenFunc,
                g_menuDepth, g_visible ? 1 : 0);
        if (padUpEdge || padDownEdge || padConfirmEdge || padCancelEdge)
            Log("direct pad source=%s buttons=%08lx up=%d down=%d confirm=%d cancel=%d",
                pad.source, (unsigned long)pad.rawButtons,
                padUpEdge ? 1 : 0, padDownEdge ? 1 : 0,
                padConfirmEdge ? 1 : 0, padCancelEdge ? 1 : 0);
'''
s = s.replace(needle, replacement, 1)

nav_needle = '''        if (g_autoMainMenu && g_visible)
        {
            if (seenDir & DOWN_PRESSED) TriggerIndex(g_index + 1);
            else if (seenDir & UP_PRESSED) TriggerIndex(g_index - 1);
        }

        if (seenFunc & CROSS_PRESSED) confirmAction();
        if (seenFunc & (TRIANGLE_PRESSED | CIRCLE_PRESSED)) cancelAction();
'''
if nav_needle not in s:
    raise SystemExit("V11 nav/action block not found")
nav_replacement = '''        if (g_autoMainMenu && g_visible)
        {
            if ((seenDir & DOWN_PRESSED) || padDownEdge) TriggerIndex(g_index + 1);
            else if ((seenDir & UP_PRESSED) || padUpEdge) TriggerIndex(g_index - 1);
        }

        if ((seenFunc & CROSS_PRESSED) || padConfirmEdge) confirmAction();
        if ((seenFunc & (TRIANGLE_PRESSED | CIRCLE_PRESSED)) || padCancelEdge) cancelAction();
'''
s = s.replace(nav_needle, nav_replacement, 1)

# Free XInput DLL when our module unloads.
detach_marker = "        RestoreGlobalInputCapture();\n        ReleaseTextures();\n"
if detach_marker in s and "FreeLibrary(g_xinputDll)" not in s:
    s = s.replace(
        detach_marker,
        "        RestoreGlobalInputCapture();\n"
        "        if (g_xinputDll) { FreeLibrary(g_xinputDll); g_xinputDll = nullptr; g_xinputGetState = nullptr; }\n"
        "        ReleaseTextures();\n",
        1,
    )

p.write_text(s, encoding="utf-8")
print("Patched menu_cards.cpp for V12: direct XInput/WinMM joystick fallback")
