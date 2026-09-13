#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <cstdarg>

namespace {

constexpr uint32_t ADDR_GET_B = 0x00865380;
constexpr uint32_t ADDR_GET_C = 0x00865430;
constexpr uint16_t TARGET_TEAM = 251;
constexpr uint16_t SCAN_MAX_TEAM = 220;

using FN_GetExtra = uint8_t* (__cdecl*)(uint16_t, int);
const auto GetB = reinterpret_cast<FN_GetExtra>(ADDR_GET_B);
const auto GetC = reinterpret_cast<FN_GetExtra>(ADDR_GET_C);

HMODULE g_self = nullptr;
HANDLE g_log = INVALID_HANDLE_VALUE;

void Log(const char* fmt, ...)
{
    if (g_log == INVALID_HANDLE_VALUE) return;
    char b[1024];
    va_list ap; va_start(ap, fmt);
    _vsnprintf_s(b, sizeof(b), _TRUNCATE, fmt, ap);
    va_end(ap);
    DWORD w = 0;
    WriteFile(g_log, b, (DWORD)strlen(b), &w, nullptr);
    WriteFile(g_log, "\r\n", 2, &w, nullptr);
    FlushFileBuffers(g_log);
}

void OpenLog()
{
    char p[MAX_PATH] = {};
    GetModuleFileNameA(g_self, p, MAX_PATH);
    char* s = strrchr(p, '\\');
    if (!s) s = strrchr(p, '/');
    if (s) *(s + 1) = 0; else p[0] = 0;
    strncat_s(p, "PESModKitsAux.log", _TRUNCATE);
    g_log = CreateFileA(p, GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE,
                        nullptr, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
}

bool IsReadable(const void* p, size_t need)
{
    if (!p) return false;
    MEMORY_BASIC_INFORMATION mbi{};
    if (VirtualQuery(p, &mbi, sizeof(mbi)) != sizeof(mbi)) return false;
    if (mbi.State != MEM_COMMIT || (mbi.Protect & PAGE_GUARD) || (mbi.Protect & PAGE_NOACCESS)) return false;
    auto begin = reinterpret_cast<uintptr_t>(p);
    auto end = reinterpret_cast<uintptr_t>(mbi.BaseAddress) + mbi.RegionSize;
    return begin + need <= end;
}

bool IsWritable(void* p, size_t need)
{
    if (!IsReadable(p, need)) return false;
    MEMORY_BASIC_INFORMATION mbi{};
    VirtualQuery(p, &mbi, sizeof(mbi));
    DWORD rw = PAGE_READWRITE | PAGE_WRITECOPY | PAGE_EXECUTE_READWRITE | PAGE_EXECUTE_WRITECOPY;
    return (mbi.Protect & rw) != 0;
}

bool GetAll(uint16_t team, uint8_t* b[4], uint8_t* c[4])
{
    __try {
        for (int v = 0; v < 4; ++v) {
            b[v] = GetB(team, v);
            c[v] = GetC(team, v);
            if (!IsReadable(b[v], 0x18) || !IsReadable(c[v], 0x30)) return false;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
    return true;
}

int ScoreDonor(uint8_t* c[4])
{
    // pa.png is variant 1, so make a nonzero C+3 there mandatory/high priority.
    if (c[1][3] == 0) return -1;
    int score = 100;
    for (int v = 0; v < 4; ++v)
        if (c[v][3] != 0) ++score;
    return score;
}

bool PrimeOnce()
{
    uint8_t* dstB[4]{}; uint8_t* dstC[4]{};
    if (!GetAll(TARGET_TEAM, dstB, dstC)) return false;
    for (int v = 0; v < 4; ++v)
        if (!IsWritable(dstB[v], 0x18) || !IsWritable(dstC[v], 0x30)) return false;

    int bestScore = -1;
    int bestTeam = -1;
    uint8_t* bestB[4]{}; uint8_t* bestC[4]{};
    int candidatesLogged = 0;

    for (uint16_t donor = 0; donor <= SCAN_MAX_TEAM; ++donor) {
        if (donor == TARGET_TEAM) continue;
        uint8_t* srcB[4]{}; uint8_t* srcC[4]{};
        if (!GetAll(donor, srcB, srcC)) continue;

        const bool anyC3 = srcC[0][3] || srcC[1][3] || srcC[2][3] || srcC[3][3];
        if (anyC3 && candidatesLogged < 32) {
            Log("[AuxScan] team=%u B3=%02X/%02X/%02X/%02X C3=%02X/%02X/%02X/%02X",
                donor,
                srcB[0][3], srcB[1][3], srcB[2][3], srcB[3][3],
                srcC[0][3], srcC[1][3], srcC[2][3], srcC[3][3]);
            ++candidatesLogged;
        }

        int score = ScoreDonor(srcC);
        if (score > bestScore) {
            bestScore = score;
            bestTeam = donor;
            for (int v = 0; v < 4; ++v) { bestB[v] = srcB[v]; bestC[v] = srcC[v]; }
        }
    }

    if (bestTeam < 0) {
        Log("[AuxScan] NO DONOR FOUND with extraC[variant1][3] != 0 in team range 0..%u", SCAN_MAX_TEAM);
        return false;
    }

    Log("[AuxScan] SELECTED donor=%d score=%d C3=%02X/%02X/%02X/%02X",
        bestTeam, bestScore, bestC[0][3], bestC[1][3], bestC[2][3], bestC[3][3]);

    __try {
        for (int v = 0; v < 4; ++v) {
            Log("[AuxPrime] before dst team=%u v=%d B2=%02X B3=%02X C2=%02X C3=%02X | donor=%d B2=%02X B3=%02X C2=%02X C3=%02X",
                TARGET_TEAM, v, dstB[v][2], dstB[v][3], dstC[v][2], dstC[v][3],
                bestTeam, bestB[v][2], bestB[v][3], bestC[v][2], bestC[v][3]);
            memcpy(dstB[v], bestB[v], 0x18);
            memcpy(dstC[v], bestC[v], 0x30);
            Log("[AuxPrime] after  dst team=%u v=%d B2=%02X B3=%02X C2=%02X C3=%02X",
                TARGET_TEAM, v, dstB[v][2], dstB[v][3], dstC[v][2], dstC[v][3]);
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        Log("[AuxPrime] exception while copying donor=%d", bestTeam);
        return false;
    }

    Log("[AuxPrime] SUCCESS target=%u donor=%d. Only extraB/extraC were copied.", TARGET_TEAM, bestTeam);
    return true;
}

DWORD WINAPI Worker(void*)
{
    OpenLog();
    Log("PESModKitsAux v0.2 TEST5 starting - scanning stock teams for nonzero extraC+3");

    bool ready = false;
    for (int i = 0; i < 600; ++i) {
        HMODULE m = GetModuleHandleA("PESMod.asi");
        if (!m) m = GetModuleHandleA("PESMod(7).asi");
        __try {
            if (m && *reinterpret_cast<volatile uint8_t*>(0x00865240) == 0xE9 &&
                *reinterpret_cast<volatile uint8_t*>(0x00865380) == 0xE9 &&
                *reinterpret_cast<volatile uint8_t*>(0x00865430) == 0xE9) {
                ready = true; break;
            }
        } __except (EXCEPTION_EXECUTE_HANDLER) {}
        Sleep(100);
    }
    if (!ready) { Log("[AuxPrime] PESMod kit hooks not detected"); return 0; }

    for (int attempt = 1; attempt <= 240; ++attempt) {
        if (PrimeOnce()) return 0;
        if (attempt == 1 || attempt % 20 == 0)
            Log("[AuxPrime] waiting/scanning, attempt=%d", attempt);
        Sleep(250);
    }
    Log("[AuxPrime] FAILED: no usable graphical donor became available");
    return 0;
}

}

BOOL APIENTRY DllMain(HMODULE h, DWORD reason, LPVOID)
{
    if (reason == DLL_PROCESS_ATTACH) {
        g_self = h;
        DisableThreadLibraryCalls(h);
        HANDLE th = CreateThread(nullptr, 0, Worker, nullptr, 0, nullptr);
        if (th) CloseHandle(th);
    } else if (reason == DLL_PROCESS_DETACH) {
        if (g_log != INVALID_HANDLE_VALUE) { CloseHandle(g_log); g_log = INVALID_HANDLE_VALUE; }
    }
    return TRUE;
}
