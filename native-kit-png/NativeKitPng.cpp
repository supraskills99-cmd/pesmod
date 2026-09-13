#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <cstdint>
#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <mutex>

#include "../include/MinHook/include/MinHook.h"

namespace {

// PES6 retail addresses verified against Kitserver 6.8.x source.
constexpr uint32_t ADDR_WRITE_KIT_INFO  = 0x00865380;
constexpr uint32_t ADDR_PROCESS_KIT     = 0x008D1A60;
constexpr uint32_t ADDR_REGISTER_TEX    = 0x00953660;
constexpr uint32_t ADDR_SETUP           = 0x00967EF0;
constexpr uint32_t CALL_SETUP[4]        = {0x00968051,0x00968073,0x00968091,0x009680AF};
constexpr uint32_t TEAM_ID_TABLE        = 0x03BE0940;
constexpr uint16_t TARGET_TEAM          = 251;

using FN_WriteKitInfo  = uint32_t (__cdecl*)(uint32_t,uint32_t);
using FN_ProcessKit    = uint32_t (__cdecl*)(uint32_t,uint32_t);
using FN_RegisterTex   = uint32_t* (__cdecl*)(uint32_t);
using FN_KitSetup      = void (__cdecl*)(uint32_t,uint32_t,uint32_t,uint32_t);

FN_WriteKitInfo g_origWriteKitInfo = nullptr;
FN_ProcessKit   g_origProcessKit = nullptr;
FN_RegisterTex  g_origRegisterTex = nullptr;
const auto g_nativeKitSetup = reinterpret_cast<FN_KitSetup>(ADDR_SETUP);

HMODULE g_self = nullptr;
HANDLE g_log = INVALID_HANDLE_VALUE;
std::mutex g_logMutex;
volatile LONG g_setupTeam = -1;
volatile LONG g_writeCount = 0;
volatile LONG g_processCount = 0;
volatile LONG g_registerCount = 0;

void OpenLog()
{
    char path[MAX_PATH] = {};
    if (!GetModuleFileNameA(g_self,path,MAX_PATH)) return;
    char* s = strrchr(path,'\\');
    if (!s) s = strrchr(path,'/');
    if (s) *(s+1)=0; else path[0]=0;
    strncat_s(path,"PESModKits.log",_TRUNCATE);
    g_log = CreateFileA(path,GENERIC_WRITE,FILE_SHARE_READ|FILE_SHARE_WRITE,nullptr,
                        CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);
}

void Log(const char* fmt,...)
{
    if (g_log == INVALID_HANDLE_VALUE) return;
    char buf[1400];
    va_list ap; va_start(ap,fmt);
    _vsnprintf_s(buf,sizeof(buf),_TRUNCATE,fmt,ap);
    va_end(ap);
    std::lock_guard<std::mutex> lock(g_logMutex);
    DWORD w=0;
    WriteFile(g_log,buf,(DWORD)strlen(buf),&w,nullptr);
    WriteFile(g_log,"\r\n",2,&w,nullptr);
    FlushFileBuffers(g_log);
}

bool IsReadable(const void* p,size_t need)
{
    if (!p) return false;
    MEMORY_BASIC_INFORMATION mbi{};
    if (VirtualQuery(p,&mbi,sizeof(mbi)) != sizeof(mbi)) return false;
    if (mbi.State != MEM_COMMIT || (mbi.Protect & PAGE_GUARD) || (mbi.Protect & PAGE_NOACCESS)) return false;
    const uintptr_t begin = reinterpret_cast<uintptr_t>(p);
    const uintptr_t end = reinterpret_cast<uintptr_t>(mbi.BaseAddress) + mbi.RegionSize;
    return begin + need <= end;
}

void GetCurrentTeams(uint16_t& home,uint16_t& away)
{
    home=away=0xFFFF;
    __try {
        auto* t = reinterpret_cast<volatile uint16_t*>(TEAM_ID_TABLE);
        home=t[0]; away=t[1];
    } __except(EXCEPTION_EXECUTE_HANDLER) {}
}

bool TargetOnScreen()
{
    uint16_t h,a; GetCurrentTeams(h,a);
    return h==TARGET_TEAM || a==TARGET_TEAM || g_setupTeam==TARGET_TEAM;
}

void Dump16(const void* p,char (&out)[80])
{
    out[0]=0;
    if (!IsReadable(p,16)) { strcpy_s(out,"<unreadable>"); return; }
    const uint8_t* b = reinterpret_cast<const uint8_t*>(p);
    size_t pos=0;
    for (int i=0;i<16 && pos+4<sizeof(out);++i) {
        int n=_snprintf_s(out+pos,sizeof(out)-pos,_TRUNCATE,"%02X%s",b[i],i==15?"":" ");
        if (n<0) break;
        pos += static_cast<size_t>(n);
    }
}

bool ValidateCall(uint32_t site,uint32_t expected)
{
    uint8_t* p=reinterpret_cast<uint8_t*>(site);
    __try {
        if (p[0]!=0xE8) return false;
        int32_t rel=*reinterpret_cast<int32_t*>(p+1);
        return reinterpret_cast<uint32_t>(p+5+rel)==expected;
    } __except(EXCEPTION_EXECUTE_HANDLER) { return false; }
}

bool PatchCall(uint32_t site,uint32_t expected,void* hook)
{
    if (!ValidateCall(site,expected)) {
        Log("[TRACE] setup callsite 0x%08X mismatch; leaving it untouched",site);
        return false;
    }
    uint8_t* p=reinterpret_cast<uint8_t*>(site);
    DWORD old=0;
    if (!VirtualProtect(p,5,PAGE_EXECUTE_READWRITE,&old)) return false;
    *reinterpret_cast<int32_t*>(p+1)=static_cast<int32_t>(reinterpret_cast<uint8_t*>(hook)-(p+5));
    DWORD dummy=0; VirtualProtect(p,5,old,&dummy);
    FlushInstructionCache(GetCurrentProcess(),p,5);
    return true;
}

void __cdecl KitSetupProxy(uint32_t team,uint32_t a2,uint32_t a3,uint32_t a4)
{
    LONG prev=g_setupTeam;
    g_setupTeam=(team<=0xFFFF)?static_cast<LONG>(team):-1;
    if ((team & 0xFFFF)==TARGET_TEAM)
        Log("[TRACE251] SETUP team=%u a2=%u a3=%u a4=%u",team,a2,a3,a4);
    g_nativeKitSetup(team,a2,a3,a4);
    g_setupTeam=prev;
}

uint32_t __cdecl HookWriteKitInfo(uint32_t teamId,uint32_t kitOrdinal)
{
    const uint16_t tid=static_cast<uint16_t>(teamId & 0xFFFF);
    uint16_t h,a; GetCurrentTeams(h,a);
    LONG n=InterlockedIncrement(&g_writeCount);
    const bool important=(tid==TARGET_TEAM || h==TARGET_TEAM || a==TARGET_TEAM || g_setupTeam==TARGET_TEAM);
    if (important || n<=80)
        Log("[%s] WRITEKIT #%ld rawTeam=0x%08X team=%u ordinal=%u current=%u/%u setup=%ld",
            important?"TRACE251":"TRACE",n,teamId,tid,kitOrdinal,h,a,g_setupTeam);

    uint32_t result=g_origWriteKitInfo?g_origWriteKitInfo(teamId,kitOrdinal):0;
    if (important) {
        char bytes[80];
        const void* probe = result>=0xF8 ? reinterpret_cast<const void*>(result-0xF8) : nullptr;
        Dump16(probe,bytes);
        Log("[TRACE251] WRITEKIT result=0x%08X probe(result-0xF8)=%s",result,bytes);
    }
    return result;
}

uint32_t __cdecl HookProcessKit(uint32_t dest,uint32_t src)
{
    uint16_t h,a; GetCurrentTeams(h,a);
    LONG n=InterlockedIncrement(&g_processCount);
    const bool important=TargetOnScreen();
    if (important || n<=120) {
        char sb[80]; Dump16(reinterpret_cast<const void*>(src),sb);
        Log("[%s] PROCESS #%ld dest=0x%08X src=0x%08X current=%u/%u setup=%ld src16=%s",
            important?"TRACE251":"TRACE",n,dest,src,h,a,g_setupTeam,sb);
    }
    uint32_t result=g_origProcessKit?g_origProcessKit(dest,src):0;
    if (important)
        Log("[TRACE251] PROCESS result=0x%08X",result);
    return result;
}

uint32_t* __cdecl HookRegisterTexture(uint32_t blob)
{
    LONG n=InterlockedIncrement(&g_registerCount);
    const bool important=TargetOnScreen();
    uint32_t magic=0,id=0,wh=0,size=0;
    __try {
        if (IsReadable(reinterpret_cast<void*>(blob),0x18)) {
            magic=*reinterpret_cast<uint32_t*>(blob+0x00);
            size =*reinterpret_cast<uint32_t*>(blob+0x08);
            id   =*reinterpret_cast<uint32_t*>(blob+0x0C);
            wh   =*reinterpret_cast<uint32_t*>(blob+0x14);
        }
    } __except(EXCEPTION_EXECUTE_HANDLER) {}
    if (important || n<=80) {
        uint16_t h,a; GetCurrentTeams(h,a);
        Log("[%s] REGTEX #%ld blob=0x%08X magic=0x%08X id=0x%08X size=0x%X wh=%ux%u current=%u/%u setup=%ld",
            important?"TRACE251":"TRACE",n,blob,magic,id,size,wh&0xFFFF,(wh>>16)&0xFFFF,h,a,g_setupTeam);
    }
    return g_origRegisterTex?g_origRegisterTex(blob):nullptr;
}

bool InstallHook(void* target,void* hook,void** orig,const char* name)
{
    MH_STATUS st=MH_CreateHook(target,hook,orig);
    if (st!=MH_OK && st!=MH_ERROR_ALREADY_CREATED) {
        Log("[TRACE] MH_CreateHook(%s)=%d",name,st); return false;
    }
    st=MH_EnableHook(target);
    if (st!=MH_OK && st!=MH_ERROR_ENABLED) {
        Log("[TRACE] MH_EnableHook(%s)=%d",name,st); return false;
    }
    Log("[TRACE] hooked %s at %p",name,target);
    return true;
}

bool Install()
{
    MH_STATUS st=MH_Initialize();
    if (st!=MH_OK && st!=MH_ERROR_ALREADY_INITIALIZED) {
        Log("[TRACE] MH_Initialize=%d",st); return false;
    }

    bool ok=true;
    ok &= InstallHook(reinterpret_cast<void*>(ADDR_WRITE_KIT_INFO),reinterpret_cast<void*>(&HookWriteKitInfo),reinterpret_cast<void**>(&g_origWriteKitInfo),"WriteKitInfo/0x865380");
    ok &= InstallHook(reinterpret_cast<void*>(ADDR_PROCESS_KIT),reinterpret_cast<void*>(&HookProcessKit),reinterpret_cast<void**>(&g_origProcessKit),"ProcessKit/0x8D1A60");
    ok &= InstallHook(reinterpret_cast<void*>(ADDR_REGISTER_TEX),reinterpret_cast<void*>(&HookRegisterTexture),reinterpret_cast<void**>(&g_origRegisterTex),"RegisterTexture/0x953660");

    for (uint32_t s:CALL_SETUP) {
        if (!PatchCall(s,ADDR_SETUP,reinterpret_cast<void*>(&KitSetupProxy)))
            Log("[TRACE] setup proxy not installed at 0x%08X",s);
    }

    Log("[TRACE] TEST6 installed ok=%d. Using Kitserver-verified WriteKitInfo + ProcessKit pipeline. PESMod.asi untouched.",ok?1:0);
    return ok;
}

DWORD WINAPI Worker(void*)
{
    OpenLog();
    Log("PESModKits TEST6 v0.4 starting");
    bool ready=false;
    for (int i=0;i<600;++i) {
        HMODULE m=GetModuleHandleA("PESMod.asi");
        if (!m) m=GetModuleHandleA("PESMod(7).asi");
        __try {
            if (m && *reinterpret_cast<volatile uint8_t*>(0x00865240)==0xE9) { ready=true; break; }
        } __except(EXCEPTION_EXECUTE_HANDLER) {}
        Sleep(100);
    }
    if (!ready) { Log("[TRACE] PESMod hook not detected; game untouched"); return 0; }
    Install();
    return 0;
}

} // namespace

BOOL APIENTRY DllMain(HMODULE h,DWORD reason,LPVOID)
{
    if (reason==DLL_PROCESS_ATTACH) {
        g_self=h; DisableThreadLibraryCalls(h);
        HANDLE th=CreateThread(nullptr,0,Worker,nullptr,0,nullptr);
        if (th) CloseHandle(th);
    } else if (reason==DLL_PROCESS_DETACH) {
        if (g_log!=INVALID_HANDLE_VALUE) { CloseHandle(g_log); g_log=INVALID_HANDLE_VALUE; }
    }
    return TRUE;
}
