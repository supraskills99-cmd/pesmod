from pathlib import Path
import re

p = Path("kitserver_module/menu_cards.cpp")
s = p.read_text(encoding="utf-8")

# -----------------------------------------------------------------------------
# V11: stop polling Kitserver's GetInputTable from Present.
#
# Important discovery: Kitserver only installs its own HookGameInput while the
# uniform/kit-selection flow is active (NewBeginUniSelect -> NewEndUniSelect).
# Therefore GetInputTable is NOT a global main-menu input source. That is why
# keyboard worked through GetAsyncKeyState while the joystick never followed the
# main menu.
#
# We install the same tiny input-table capture hook globally, using the official
# PES6/1.10/WE2007 addresses from Kitserver 6. This captures the actual logical
# PES input BEFORE the game clears it, so keyboard, d-pad and mapped analog pad
# all go through the same path. Kitserver can temporarily replace this hook in
# kit selection; when it unhooks, it restores our bytes because they were the
# bytes present when Kitserver installed its temporary hook.
# -----------------------------------------------------------------------------

# The PES 2011 horizontal skin is still PES6's vertical menu underneath.
needle = "    constexpr DWORD LEFT_PRESSED = 0x40;\n    constexpr DWORD RIGHT_PRESSED = 0x80;\n"
if needle in s and "UP_PRESSED" not in s:
    s = s.replace(
        needle,
        "    constexpr DWORD UP_PRESSED = 0x10;\n"
        "    constexpr DWORD DOWN_PRESSED = 0x20;\n" + needle,
        1,
    )

# Logical PES6 functional bits.
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

# Minimal GetPESInfo ABI. GameVersion is after seven pointers on x86.
type_needle = "    using GetInputTableFn = DWORD* (__cdecl*)();\n"
if type_needle not in s:
    raise SystemExit("GetInputTableFn insertion point not found")
if "GetPESInfoFn" not in s:
    s = s.replace(
        type_needle,
        type_needle +
        "    struct PESINFO_MIN\n"
        "    {\n"
        "        char* mydir;\n"
        "        char* pesdir;\n"
        "        char* processfile;\n"
        "        char* shortProcessfile;\n"
        "        char* shortProcessfileNoExt;\n"
        "        char* logName;\n"
        "        char* gdbDir;\n"
        "        int GameVersion;\n"
        "    };\n"
        "    using GetPESInfoFn = PESINFO_MIN* (__cdecl*)();\n",
        1,
    )

# Global capture state.
global_needle = "    GetInputTableFn g_getInputTable = nullptr;\n"
if global_needle not in s:
    raise SystemExit("global GetInputTable insertion point not found")
if "g_globalInputInstalled" not in s:
    s = s.replace(
        global_needle,
        global_needle +
        "    GetPESInfoFn g_getPesInfo = nullptr;\n"
        "    DWORD* g_liveInputTable = nullptr;\n"
        "    BYTE* g_cleanInputHook = nullptr;\n"
        "    BYTE g_cleanInputOriginal[10] = {};\n"
        "    bool g_globalInputInstalled = false;\n"
        "    volatile LONG g_inputGeneration = 0;\n"
        "    LONG g_lastProcessedGeneration = 0;\n"
        "    std::array<DWORD,24> g_inputSnapshot = {};\n",
        1,
    )

# State for menu stack tracking.
state_needle = "    int g_prevIndex = 0;\n    ULONGLONG g_transitionStart = 0;\n"
if "g_menuDepth" not in s:
    if state_needle not in s:
        raise SystemExit("state insertion point not found")
    s = s.replace(
        state_needle,
        "    int g_prevIndex = 0;\n"
        "    int g_menuDepth = 0;\n"
        "    ULONGLONG g_lastMenuActionAt = 0;\n"
        "    ULONGLONG g_transitionStart = 0;\n",
        1,
    )

# Main-menu BINs may be requested by submenus too. Only first detection shows.
asset_pattern = re.compile(
    r'''        if \(!g_seenMainMenuAssets\)\n            Log\("main menu asset detected: afs=%lu file=%lu", afsId, localId\);\n        g_seenMainMenuAssets = true;\n        if \(g_autoMainMenu\)\n        \{\n            g_visible = true;\n            g_hiddenByEnter = false;\n            g_transitionStart = GetTickCount64\(\);\n        \}'''
)
asset_replacement = '''        if (!g_seenMainMenuAssets)\n        {\n            Log("main menu asset detected: afs=%lu file=%lu", afsId, localId);\n            g_seenMainMenuAssets = true;\n            if (g_autoMainMenu)\n            {\n                g_visible = true;\n                g_hiddenByEnter = false;\n                g_menuDepth = 0;\n                g_transitionStart = GetTickCount64();\n            }\n        }'''
s, count = asset_pattern.subn(asset_replacement, s, count=1)
if count != 1:
    raise SystemExit("main menu asset visibility block not found")

# Insert the global PES input capture immediately before HandleInput.
handle_marker = "    void HandleInput()\n"
if handle_marker not in s:
    raise SystemExit("HandleInput marker not found")
if "CaptureAndCleanPesInput" not in s:
    capture_block = r'''    void __cdecl CaptureAndCleanPesInput()
    {
        if (!g_liveInputTable) return;
        std::memcpy(g_inputSnapshot.data(), g_liveInputTable, sizeof(DWORD) * 24);
        std::memset(g_liveInputTable, 0, sizeof(DWORD) * 24);
        InterlockedIncrement(&g_inputGeneration);
    }

    bool OurInputPatchIsActive()
    {
        if (!g_cleanInputHook) return false;
        if (g_cleanInputHook[0] != 0xE8 || g_cleanInputHook[5] != 0xC3) return false;
        const DWORD rel = *reinterpret_cast<DWORD*>(g_cleanInputHook + 1);
        const DWORD dest = reinterpret_cast<DWORD>(g_cleanInputHook + 5) + rel;
        return dest == reinterpret_cast<DWORD>(&CaptureAndCleanPesInput);
    }

    bool InstallGlobalInputCapture()
    {
        if (g_globalInputInstalled) return true;
        if (!g_getPesInfo)
        {
            Log("global input: GetPESInfo export missing");
            return false;
        }

        PESINFO_MIN* info = g_getPesInfo();
        if (!info || info->GameVersion < 0 || info->GameVersion > 2)
        {
            Log("global input: unsupported game version");
            return false;
        }

        // Addresses are the same values used by Kitserver 6 input.cpp/hook.cpp.
        static const DWORD kCleanHook[3] = { 0x009CD4F2, 0x009CD682, 0x009CDCE2 };
        static const DWORD kInputTable[3] = { 0x03A71254, 0x03A72254, 0x03A6BCD4 };

        const int v = info->GameVersion;
        g_cleanInputHook = reinterpret_cast<BYTE*>(kCleanHook[v]);
        g_liveInputTable = reinterpret_cast<DWORD*>(kInputTable[v]);

        DWORD oldProtect = 0;
        if (!VirtualProtect(g_cleanInputHook, 32, PAGE_EXECUTE_READWRITE, &oldProtect))
        {
            Log("global input: VirtualProtect failed err=%lu", GetLastError());
            g_cleanInputHook = nullptr;
            g_liveInputTable = nullptr;
            return false;
        }

        std::memcpy(g_cleanInputOriginal, g_cleanInputHook, 10);
        g_cleanInputHook[0] = 0xE8;
        *reinterpret_cast<DWORD*>(g_cleanInputHook + 1) =
            reinterpret_cast<DWORD>(&CaptureAndCleanPesInput) -
            reinterpret_cast<DWORD>(g_cleanInputHook + 5);
        g_cleanInputHook[5] = 0xC3;
        g_cleanInputHook[6] = 0x90;
        g_cleanInputHook[7] = 0x90;
        g_cleanInputHook[8] = 0x90;
        g_cleanInputHook[9] = 0x90;
        FlushInstructionCache(GetCurrentProcess(), g_cleanInputHook, 10);

        DWORD dummy = 0;
        VirtualProtect(g_cleanInputHook, 32, oldProtect, &dummy);
        g_globalInputInstalled = true;
        Log("global input capture installed: version=%d hook=%08lx table=%08lx",
            v, (unsigned long)kCleanHook[v], (unsigned long)kInputTable[v]);
        return true;
    }

    void RestoreGlobalInputCapture()
    {
        if (!g_globalInputInstalled || !g_cleanInputHook) return;
        // If Kitserver currently owns the clean-input hook (kit selection), do not
        // overwrite its temporary patch during detach.
        if (OurInputPatchIsActive())
        {
            DWORD oldProtect = 0;
            if (VirtualProtect(g_cleanInputHook, 32, PAGE_EXECUTE_READWRITE, &oldProtect))
            {
                std::memcpy(g_cleanInputHook, g_cleanInputOriginal, 10);
                FlushInstructionCache(GetCurrentProcess(), g_cleanInputHook, 10);
                DWORD dummy = 0;
                VirtualProtect(g_cleanInputHook, 32, oldProtect, &dummy);
            }
        }
        g_globalInputInstalled = false;
    }

'''
    s = s.replace(handle_marker, capture_block + handle_marker, 1)

# Replace input handling entirely. Snapshot generation is the edge: each PES
# clean-input cycle is processed exactly once, so no Present polling races and no
# extra home-made edge filter.
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

        // If Kitserver temporarily replaced our hook for kit selection, it restores
        // our bytes on NewEndUniSelect. No re-patching is normally necessary.
        const LONG generation = InterlockedCompareExchange(&g_inputGeneration, 0, 0);
        if (generation == g_lastProcessedGeneration) return;
        g_lastProcessedGeneration = generation;

        DWORD seenDir = 0;
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

        auto confirmAction = [&]()
        {
            const ULONGLONG t = GetTickCount64();
            if (t - g_lastMenuActionAt < 80) return;
            g_lastMenuActionAt = t;

            if (g_visible)
            {
                g_menuDepth = 1;
                g_visible = false;
                g_hiddenByEnter = true;
                Log("leave main menu: index=%d depth=%d", g_index, g_menuDepth);
            }
            else if (g_hiddenByEnter)
            {
                if (g_menuDepth < 16) ++g_menuDepth;
                Log("submenu confirm depth=%d", g_menuDepth);
            }
        };

        auto cancelAction = [&]()
        {
            const ULONGLONG t = GetTickCount64();
            if (t - g_lastMenuActionAt < 80) return;
            g_lastMenuActionAt = t;

            if (!g_visible && g_hiddenByEnter)
            {
                if (g_menuDepth > 0) --g_menuDepth;
                Log("submenu cancel depth=%d", g_menuDepth);
                if (g_menuDepth == 0)
                {
                    g_visible = true;
                    g_hiddenByEnter = false;
                    g_transitionStart = t;
                    Log("returned to main menu: index=%d", g_index);
                }
            }
        };

        // Main-menu visual navigation follows PES6's underlying vertical list.
        if (g_autoMainMenu && g_visible)
        {
            if (seenDir & DOWN_PRESSED) TriggerIndex(g_index + 1);
            else if (seenDir & UP_PRESSED) TriggerIndex(g_index - 1);
        }

        if (seenFunc & CROSS_PRESSED) confirmAction();
        if (seenFunc & (TRIANGLE_PRESSED | CIRCLE_PRESSED)) cancelAction();
    }

    void DrawCard'''
s, count = pattern.subn(replacement, s, count=1)
if count != 1:
    raise SystemExit("HandleInput block not found")

# Resolve GetPESInfo and install the global input capture at module init.
install_old = '''        g_hookFunction = reinterpret_cast<HookFunctionFn>(GetProcAddress(kload,"HookFunction"));
        g_unhookFunction = reinterpret_cast<UnhookFunctionFn>(GetProcAddress(kload,"UnhookFunction"));
        g_getInputTable = reinterpret_cast<GetInputTableFn>(GetProcAddress(kload,"GetInputTable"));
        if (!g_hookFunction) { Log("HookFunction export not found"); return false; }
'''
install_new = '''        g_hookFunction = reinterpret_cast<HookFunctionFn>(GetProcAddress(kload,"HookFunction"));
        g_unhookFunction = reinterpret_cast<UnhookFunctionFn>(GetProcAddress(kload,"UnhookFunction"));
        g_getInputTable = reinterpret_cast<GetInputTableFn>(GetProcAddress(kload,"GetInputTable"));
        g_getPesInfo = reinterpret_cast<GetPESInfoFn>(GetProcAddress(kload,"GetPESInfo"));
        if (!g_hookFunction) { Log("HookFunction export not found"); return false; }
        InstallGlobalInputCapture();
'''
if install_old not in s:
    raise SystemExit("InstallKitserverHooks export block not found")
s = s.replace(install_old, install_new, 1)

# Update startup log so the test log proves whether the global hook is active.
s = s.replace(
    '        Log("registered hk_D3D_Create + hk_D3D_Present; input=%s", g_getInputTable ? "OK" : "missing");\n',
    '        Log("registered D3D hooks; globalInput=%s kloadInput=%s",\n'
    '            g_globalInputInstalled ? "OK" : "FAILED",\n'
    '            g_getInputTable ? "OK" : "missing");\n',
    1,
)

# Restore our global patch on DLL detach when it is still ours.
detach_needle = '''        if (g_createHooked && g_unhookFunction)
            g_unhookFunction(HK_D3D_CREATE, reinterpret_cast<DWORD>(&OnD3DCreate));
        ReleaseTextures();
'''
if detach_needle not in s:
    raise SystemExit("detach block not found")
s = s.replace(
    detach_needle,
    '''        if (g_createHooked && g_unhookFunction)
            g_unhookFunction(HK_D3D_CREATE, reinterpret_cast<DWORD>(&OnD3DCreate));
        RestoreGlobalInputCapture();
        ReleaseTextures();
''',
    1,
)

p.write_text(s, encoding="utf-8")
print("Patched menu_cards.cpp for V11: global PES input capture (keyboard + joystick)")
