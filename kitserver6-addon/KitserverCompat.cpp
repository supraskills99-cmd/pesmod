#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <cstdint>
#include <cstdio>
#include <cstring>

#include "MinHook.h"

namespace {

constexpr uintptr_t ADDR_GET_KIT   = 0x00865240;
constexpr uintptr_t ADDR_GET_KIT_B = 0x00865380;
constexpr uintptr_t ADDR_GET_KIT_C = 0x00865430;

#define KIT_NATIONAL_TABLE_PTR     (*reinterpret_cast<uint8_t**>(0x0113200c))
#define KIT_CLUB_TABLE_PTR         (*reinterpret_cast<uint8_t**>(0x01132010))
#define KIT_SPECIAL_NATIONAL_PTR   (*reinterpret_cast<uint8_t**>(0x01132064))
#define KIT_NATIONAL_FALLBACK_PTR  (*reinterpret_cast<uint8_t**>(0x01132068))
#define KIT_SPECIAL_CLUB_PTR       (*reinterpret_cast<uint8_t**>(0x0113206c))
#define KIT_ALIAS_PTR_126          (*reinterpret_cast<uint8_t**>(0x00c97334))
#define KIT_ALIAS_PTR_127          (*reinterpret_cast<uint8_t**>(0x00c97338))
#define EDIT_TEAM_KIT_BASE         reinterpret_cast<uint8_t*>(0x01132098)
#define ML_TEAM_KIT_BASE           reinterpret_cast<uint8_t*>(0x011324d8)
#define KIT_FALLBACK_BUFFER        reinterpret_cast<uint8_t*>(0x00c97340)

using FN_GetTeamKitData = uint8_t* (__cdecl*)(uint16_t, int);
FN_GetTeamKitData g_prevGetKit   = nullptr;
FN_GetTeamKitData g_prevGetKitB  = nullptr;
FN_GetTeamKitData g_prevGetKitC  = nullptr;

HMODULE g_self = nullptr;
HANDLE g_log = INVALID_HANDLE_VALUE;

void OpenLog()
{
    char p[MAX_PATH] = {};
    GetModuleFileNameA(g_self, p, MAX_PATH);
    char* s = strrchr(p, '\\');
    if (!s) s = strrchr(p, '/');
    if (s) *(s + 1) = 0; else p[0] = 0;
    strncat_s(p, "PESModKitserverCompat.log", _TRUNCATE);
    g_log = CreateFileA(p, GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE,
                        nullptr, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
}

void Log(const char* fmt, ...)
{
    if (g_log == INVALID_HANDLE_VALUE) return;
    char b[1024];
    va_list ap; va_start(ap, fmt);
    _vsnprintf_s(b, sizeof(b), _TRUNCATE, fmt, ap);
    va_end(ap);
    DWORD w = 0;
    WriteFile(g_log, b, static_cast<DWORD>(strlen(b)), &w, nullptr);
    WriteFile(g_log, "\r\n", 2, &w, nullptr);
    FlushFileBuffers(g_log);
}

bool IsReadable(const void* p, size_t bytes)
{
    if (!p || bytes == 0) return false;
    MEMORY_BASIC_INFORMATION mbi{};
    if (VirtualQuery(p, &mbi, sizeof(mbi)) != sizeof(mbi)) return false;
    if (mbi.State != MEM_COMMIT || (mbi.Protect & PAGE_GUARD) || (mbi.Protect & PAGE_NOACCESS)) return false;
    uintptr_t start = reinterpret_cast<uintptr_t>(p);
    uintptr_t end = reinterpret_cast<uintptr_t>(mbi.BaseAddress) + mbi.RegionSize;
    return start + bytes <= end;
}

uint8_t* GetAlias(uint16_t id)
{
    if (id == 0x126) return KIT_ALIAS_PTR_126;
    if (id == 0x127) return KIT_ALIAS_PTR_127;
    return nullptr;
}

int GetType(uint16_t id)
{
    for (int i = 0; i < 8; ++i) {
        if (id < 0x39)  return 0;
        if (id < 0x40)  return 2;
        if (id < 0xCC)  return 3;
        if (id < 0xDD)  return 0;
        if (id < 0x126) return 3;
        if (id == 0x126 || id == 0x127) {
            uint8_t* a = GetAlias(id);
            if (!a || !IsReadable(a + 0x170, sizeof(uint16_t))) return 3;
            uint16_t r = *reinterpret_cast<uint16_t*>(a + 0x170);
            if (r == 0x126 || r == 0x127) return 3;
            id = r;
            continue;
        }
        return 0;
    }
    return 3;
}

uint8_t* GetClubBase(uint16_t id)
{
    if (id == 0x126 || id == 0x127) {
        uint8_t* a = GetAlias(id);
        if (a && IsReadable(a, sizeof(int))) {
            int base = *reinterpret_cast<int*>(a);
            if (base + 0x58 != 0) return reinterpret_cast<uint8_t*>(base + 0x58);
        }
    }
    if (id >= 0x40 && id < 0xCC && KIT_CLUB_TABLE_PTR)
        return KIT_CLUB_TABLE_PTR + (id - 0x40) * 0x220;
    if (id >= 0xDD && id < 0xFE && KIT_SPECIAL_CLUB_PTR)
        return KIT_SPECIAL_CLUB_PTR + (id - 0xDD) * 0x220;
    if (id >= 0x10E && id <= 0x10F)
        return EDIT_TEAM_KIT_BASE + (id - 0x10E) * 0x220;
    return nullptr;
}

uint8_t* GetNationalBase(uint16_t id)
{
    if (id == 0x126 || id == 0x127) {
        uint8_t* a = GetAlias(id);
        if (a && IsReadable(a, sizeof(int))) {
            int base = *reinterpret_cast<int*>(a);
            if (base + 0x58 != 0) return reinterpret_cast<uint8_t*>(base + 0x58);
        }
    }
    if (id < 0x40 && KIT_NATIONAL_TABLE_PTR)
        return KIT_NATIONAL_TABLE_PTR + static_cast<uint32_t>(id) * 0x160;
    if (id >= 0xCC && id < 0xDD && KIT_SPECIAL_NATIONAL_PTR)
        return KIT_SPECIAL_NATIONAL_PTR + (id - 0xCC) * 0x160;
    if (id >= 0xFE && id <= 0x10D && KIT_NATIONAL_FALLBACK_PTR)
        return KIT_NATIONAL_FALLBACK_PTR + (id - 0xFE) * 0x160;
    return KIT_FALLBACK_BUFFER;
}

uint8_t* NativeGetKit(uint16_t id, int variant)
{
    if (variant < 0 || variant >= 4) return nullptr;
    int type = GetType(id);
    bool special = (id >= 0xFE && id <= 0x10D);
    if (!special && type == 3) {
        uint8_t* base = GetClubBase(id);
        if (base && IsReadable(base + variant * 0x3E, 0x3E))
            return base + variant * 0x3E;
        if (id >= 0x110 && id <= 0x111) {
            uint8_t* p = ML_TEAM_KIT_BASE + (id - 0x110) * 0xF8 + variant * 0x3E;
            return IsReadable(p, 0x3E) ? p : nullptr;
        }
        return nullptr;
    }
    uint8_t* base = GetNationalBase(id);
    if (!base || base == KIT_FALLBACK_BUFFER) return nullptr;
    uint8_t* p = base + variant * 0x3E;
    return IsReadable(p, 0x3E) ? p : nullptr;
}

uint8_t* NativeGetKitB(uint16_t id, int variant)
{
    if (variant < 0 || variant >= 4) return nullptr;
    int type = GetType(id);
    bool special = (id >= 0xFE && id <= 0x10D);
    if (!special && type == 3) {
        uint8_t* base = GetClubBase(id);
        if (!base) return nullptr;
        uint8_t* p = base + variant * 0x18 + 0x100;
        return IsReadable(p, 0x18) ? p : nullptr;
    }
    uint8_t* base = GetNationalBase(id);
    if (!base || base == KIT_FALLBACK_BUFFER) return nullptr;
    uint8_t* p = base + variant * 0x18 + 0x100;
    return IsReadable(p, 0x18) ? p : nullptr;
}

uint8_t* NativeGetKitC(uint16_t id, int variant)
{
    if (variant < 0 || variant >= 4) return nullptr;
    int type = GetType(id);
    bool special = (id >= 0xFE && id <= 0x10D);
    if (!special && type == 3) {
        uint8_t* base = GetClubBase(id);
        if (!base) return nullptr;
        uint8_t* p = base + variant * 0x30 + 0x160;
        return IsReadable(p, 0x30) ? p : nullptr;
    }
    return nullptr;
}

bool KitserverLoaded()
{
    return GetModuleHandleA("kserv.dll") != nullptr;
}

bool ShouldUseNative(uint16_t id)
{
    // The exact PES6 club band that contains PESMod's custom Racing 251.
    // Keep this deliberately narrow so all other PESMod behaviour stays intact.
    return id >= 0xDD && id < 0xFE;
}

uint8_t* __cdecl HookGetKit(uint16_t id, int variant)
{
    if (KitserverLoaded() && ShouldUseNative(id)) {
        if (uint8_t* p = NativeGetKit(id, variant)) return p;
    }
    return g_prevGetKit ? g_prevGetKit(id, variant) : nullptr;
}

uint8_t* __cdecl HookGetKitB(uint16_t id, int variant)
{
    if (KitserverLoaded() && ShouldUseNative(id)) {
        if (uint8_t* p = NativeGetKitB(id, variant)) return p;
    }
    return g_prevGetKitB ? g_prevGetKitB(id, variant) : nullptr;
}

uint8_t* __cdecl HookGetKitC(uint16_t id, int variant)
{
    if (KitserverLoaded() && ShouldUseNative(id)) {
        if (uint8_t* p = NativeGetKitC(id, variant)) return p;
    }
    return g_prevGetKitC ? g_prevGetKitC(id, variant) : nullptr;
}

void* ResolveCurrentDetour(uintptr_t address)
{
    uint8_t* p = reinterpret_cast<uint8_t*>(address);
    __try {
        if (p[0] != 0xE9) return nullptr;
        int32_t rel = *reinterpret_cast<int32_t*>(p + 1);
        return p + 5 + rel;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return nullptr;
    }
}

bool HookExistingDetour(uintptr_t gameAddr, void* replacement, void** previous, const char* name)
{
    void* current = ResolveCurrentDetour(gameAddr);
    if (!current) {
        Log("[%s] PESMod detour not found at 0x%08X", name, static_cast<unsigned>(gameAddr));
        return false;
    }

    MH_STATUS s = MH_CreateHook(current, replacement, previous);
    if (s != MH_OK && s != MH_ERROR_ALREADY_CREATED) {
        Log("[%s] MH_CreateHook failed=%d current=%p", name, static_cast<int>(s), current);
        return false;
    }
    s = MH_EnableHook(current);
    if (s != MH_OK && s != MH_ERROR_ENABLED) {
        Log("[%s] MH_EnableHook failed=%d", name, static_cast<int>(s));
        return false;
    }
    Log("[%s] wrapped PESMod detour %p", name, current);
    return true;
}

DWORD WINAPI Worker(void*)
{
    OpenLog();
    Log("PESModKitserverCompat starting");

    for (int i = 0; i < 600; ++i) {
        bool pesmod = GetModuleHandleA("PESMod.asi") != nullptr ||
                      GetModuleHandleA("PESMod(8).asi") != nullptr;
        bool hooked = ResolveCurrentDetour(ADDR_GET_KIT) &&
                      ResolveCurrentDetour(ADDR_GET_KIT_B) &&
                      ResolveCurrentDetour(ADDR_GET_KIT_C);
        if (pesmod && hooked) break;
        Sleep(100);
    }

    MH_STATUS init = MH_Initialize();
    if (init != MH_OK && init != MH_ERROR_ALREADY_INITIALIZED) {
        Log("MH_Initialize failed=%d", static_cast<int>(init));
        return 0;
    }

    bool a = HookExistingDetour(ADDR_GET_KIT,   reinterpret_cast<void*>(&HookGetKit),
                                reinterpret_cast<void**>(&g_prevGetKit), "GetTeamKitData");
    bool b = HookExistingDetour(ADDR_GET_KIT_B, reinterpret_cast<void*>(&HookGetKitB),
                                reinterpret_cast<void**>(&g_prevGetKitB), "GetTeamKitDataB");
    bool c = HookExistingDetour(ADDR_GET_KIT_C, reinterpret_cast<void*>(&HookGetKitC),
                                reinterpret_cast<void**>(&g_prevGetKitC), "GetTeamKitDataC");

    Log("install complete a=%d b=%d c=%d kserv=%d", a?1:0, b?1:0, c?1:0, KitserverLoaded()?1:0);
    return 0;
}

} // namespace

BOOL APIENTRY DllMain(HMODULE hModule, DWORD reason, LPVOID)
{
    if (reason == DLL_PROCESS_ATTACH) {
        g_self = hModule;
        DisableThreadLibraryCalls(hModule);
        HANDLE th = CreateThread(nullptr, 0, Worker, nullptr, 0, nullptr);
        if (th) CloseHandle(th);
    } else if (reason == DLL_PROCESS_DETACH) {
        if (g_log != INVALID_HANDLE_VALUE) {
            CloseHandle(g_log);
            g_log = INVALID_HANDLE_VALUE;
        }
    }
    return TRUE;
}
