#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <wincodec.h>
#include <cstdint>
#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <vector>
#include <algorithm>
#include <mutex>

namespace {

constexpr uint32_t ADDR_BUILD_KIT_TEXTURE = 0x00954B80;
constexpr uint32_t ADDR_SETUP             = 0x00967EF0;
constexpr uint32_t ADDR_REGISTER_TEXTURE  = 0x00953660;
constexpr uint32_t ADDR_RESOLVE_TEXTURE   = 0x00953630;
constexpr uint32_t ADDR_GAME_ALLOC        = 0x0045BC00;
constexpr uint32_t ADDR_GAME_FREE         = 0x0045BC50;

constexpr uint32_t CALL_BUILD_VARIANT = 0x009671DD;
constexpr uint32_t CALL_SETUP[4] = {0x00968051,0x00968073,0x00968091,0x009680AF};

constexpr int KIT_W = 512;
constexpr int KIT_H = 256;
constexpr uint32_t SYNTH_BASE = 0x00E20000;

HMODULE g_self = nullptr;
HANDLE g_log = INVALID_HANDLE_VALUE;
std::mutex g_logMutex;
volatile LONG g_activeTeam = -1;

using FN_BuildKitTexture = uint32_t (__cdecl*)(uint32_t,uint32_t,uint32_t,uint32_t,uint32_t);
using FN_KitSetup        = void (__cdecl*)(uint32_t,uint32_t,uint32_t,uint32_t);
using FN_RegisterTexture = uint32_t* (__cdecl*)(uint32_t);
using FN_ResolveTexture  = uint32_t* (__cdecl*)(int);
using FN_GameAlloc       = uint32_t* (__cdecl*)(int,int);
using FN_GameFree        = void (__cdecl*)(uint32_t*);

const auto g_nativeBuildKitTexture = reinterpret_cast<FN_BuildKitTexture>(ADDR_BUILD_KIT_TEXTURE);
const auto g_nativeKitSetup        = reinterpret_cast<FN_KitSetup>(ADDR_SETUP);
const auto RegisterTexture         = reinterpret_cast<FN_RegisterTexture>(ADDR_REGISTER_TEXTURE);
const auto ResolveTexture          = reinterpret_cast<FN_ResolveTexture>(ADDR_RESOLVE_TEXTURE);
const auto GameAlloc               = reinterpret_cast<FN_GameAlloc>(ADDR_GAME_ALLOC);
const auto GameFree                = reinterpret_cast<FN_GameFree>(ADDR_GAME_FREE);

struct RGBA { uint8_t r,g,b,a; };

const wchar_t* VariantName(int v)
{
    static const wchar_t* n[4] = {L"ga",L"pa",L"gb",L"pb"};
    return (v >= 0 && v < 4) ? n[v] : L"";
}

void OpenLog()
{
    char p[MAX_PATH] = {};
    if (!GetModuleFileNameA(g_self,p,MAX_PATH)) return;
    char* s = strrchr(p,'\\');
    if (!s) s = strrchr(p,'/');
    if (s) *(s+1)=0; else p[0]=0;
    strncat_s(p,"PESModKits.log",_TRUNCATE);
    g_log = CreateFileA(p,GENERIC_WRITE,FILE_SHARE_READ|FILE_SHARE_WRITE,nullptr,
                        CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);
}

void Log(const char* f,...)
{
    if (g_log == INVALID_HANDLE_VALUE) return;
    char b[1024];
    va_list a; va_start(a,f);
    _vsnprintf_s(b,sizeof(b),_TRUNCATE,f,a);
    va_end(a);
    std::lock_guard<std::mutex> lock(g_logMutex);
    DWORD w=0;
    WriteFile(g_log,b,(DWORD)strlen(b),&w,nullptr);
    WriteFile(g_log,"\r\n",2,&w,nullptr);
    FlushFileBuffers(g_log);
}

void GetBaseDir(wchar_t (&out)[MAX_PATH])
{
    out[0]=0;
    if (!GetModuleFileNameW(g_self,out,MAX_PATH)) return;
    wchar_t* s = wcsrchr(out,L'\\');
    if (!s) s = wcsrchr(out,L'/');
    if (s) *(s+1)=0; else out[0]=0;
}

void MakeKitPath(uint16_t team, int variant, wchar_t (&out)[MAX_PATH])
{
    wchar_t base[MAX_PATH]; GetBaseDir(base);
    _snwprintf_s(out,MAX_PATH,_TRUNCATE,L"%skits\\%u\\%s.png",
                 base,(unsigned)team,VariantName(variant));
}

bool FileExists(const wchar_t* p)
{
    DWORD a = GetFileAttributesW(p);
    return a != INVALID_FILE_ATTRIBUTES && !(a & FILE_ATTRIBUTE_DIRECTORY);
}

bool HasVariantPng(uint16_t team,int variant)
{
    wchar_t p[MAX_PATH]; MakeKitPath(team,variant,p);
    return FileExists(p);
}

bool HasAnyKitPng(uint16_t team)
{
    for (int v=0;v<4;++v) if (HasVariantPng(team,v)) return true;
    return false;
}

inline int SwzIndex(int x,int y,int w)
{
    const int block=(y&~0xf)*w+(x&~0xf)*2;
    const int swap=(((y+2)>>2)&1)*4;
    const int ypos=(((y&~3)>>1)+(y&1))&7;
    const int col=ypos*w*2+((x+swap)&7)*4;
    return block+col+((y>>1)&1)+((x>>2)&2);
}

void ClutSwap(uint8_t* p)
{
    for(int b=0;b<256;b+=32)
        for(int k=0;k<8;++k)
            for(int c=0;c<4;++c)
                std::swap(p[(b+8+k)*4+c],p[(b+16+k)*4+c]);
}

void MedianCut(const std::vector<RGBA>& px,
               std::vector<RGBA>& pal,
               std::vector<uint8_t>& idx)
{
    std::vector<std::vector<int>> boxes(1);
    boxes[0].resize(px.size());
    for(size_t i=0;i<px.size();++i) boxes[0][i]=(int)i;

    auto range=[&](const std::vector<int>& box,int& axis)->int {
        uint8_t mn[4]={255,255,255,255}, mx[4]={0,0,0,0};
        for(int i:box){
            const uint8_t* v=&px[i].r;
            for(int c=0;c<4;++c){mn[c]=std::min(mn[c],v[c]);mx[c]=std::max(mx[c],v[c]);}
        }
        int best=0; axis=0;
        for(int c=0;c<4;++c){int r=mx[c]-mn[c];if(r>best){best=r;axis=c;}}
        return best;
    };

    while(boxes.size()<256){
        int bi=-1,br=-1,ba=0;
        for(size_t k=0;k<boxes.size();++k){
            if(boxes[k].size()<2) continue;
            int a=0,r=range(boxes[k],a);
            if(r>br){br=r;bi=(int)k;ba=a;}
        }
        if(bi<0) break;
        auto box=std::move(boxes[bi]);
        boxes.erase(boxes.begin()+bi);
        std::sort(box.begin(),box.end(),[&](int a,int b){
            return (&px[a].r)[ba] < (&px[b].r)[ba];
        });
        size_t m=box.size()/2;
        boxes.emplace_back(box.begin(),box.begin()+m);
        boxes.emplace_back(box.begin()+m,box.end());
    }

    pal.assign(256,RGBA{0,0,0,0});
    idx.assign(px.size(),0);
    for(size_t k=0;k<boxes.size() && k<256;++k){
        const auto& box=boxes[k];
        if(box.empty()) continue;
        uint64_t s[4]={0,0,0,0};
        for(int i:box){s[0]+=px[i].r;s[1]+=px[i].g;s[2]+=px[i].b;s[3]+=px[i].a;}
        uint64_t n=box.size();
        pal[k]=RGBA{(uint8_t)(s[0]/n),(uint8_t)(s[1]/n),
                    (uint8_t)(s[2]/n),(uint8_t)(s[3]/n)};
        for(int i:box) idx[i]=(uint8_t)k;
    }
}

bool DecodeKitPng(const wchar_t* path,std::vector<RGBA>& out)
{
    HRESULT init=CoInitializeEx(nullptr,COINIT_MULTITHREADED);
    bool did=SUCCEEDED(init);
    IWICImagingFactory* f=nullptr;
    IWICBitmapDecoder* d=nullptr;
    IWICBitmapFrameDecode* fr=nullptr;
    IWICFormatConverter* c=nullptr;
    bool ok=false;

    do {
        if(FAILED(CoCreateInstance(CLSID_WICImagingFactory,nullptr,CLSCTX_INPROC_SERVER,
                                   IID_PPV_ARGS(&f)))) break;
        if(FAILED(f->CreateDecoderFromFilename(path,nullptr,GENERIC_READ,
                                               WICDecodeMetadataCacheOnDemand,&d))) break;
        if(FAILED(d->GetFrame(0,&fr))) break;
        UINT w=0,h=0;
        if(FAILED(fr->GetSize(&w,&h))) break;
        if(w!=KIT_W || h!=KIT_H){
            Log("[CustomKitPNG] rejected PNG: expected 512x256, got %ux%u",w,h);
            break;
        }
        if(FAILED(f->CreateFormatConverter(&c))) break;
        if(FAILED(c->Initialize(fr,GUID_WICPixelFormat32bppRGBA,
                                WICBitmapDitherTypeNone,nullptr,0.0,
                                WICBitmapPaletteTypeCustom))) break;
        out.resize((size_t)KIT_W*KIT_H);
        if(FAILED(c->CopyPixels(nullptr,KIT_W*4,(UINT)out.size()*4,
                                reinterpret_cast<BYTE*>(out.data())))) break;
        ok=true;
    } while(false);

    if(c)c->Release();
    if(fr)fr->Release();
    if(d)d->Release();
    if(f)f->Release();
    if(did)CoUninitialize();
    return ok;
}

uint32_t BuildAndRegister(uint16_t team,int variant)
{
    wchar_t path[MAX_PATH]; MakeKitPath(team,variant,path);
    if(!FileExists(path)) return 0;

    const int displayId=(int)(SYNTH_BASE + (uint32_t)team*4u + (uint32_t)variant);
    if(uint32_t* existing=ResolveTexture(displayId)){
        Log("[CustomKitPNG] reuse team=%u variant=%d display=0x%X node=%p",
            team,variant,displayId,existing);
        return reinterpret_cast<uint32_t>(existing);
    }

    std::vector<RGBA> rgba;
    if(!DecodeKitPng(path,rgba)){
        Log("[CustomKitPNG] decode failed team=%u variant=%d",team,variant);
        return 0;
    }

    std::vector<RGBA> pal;
    std::vector<uint8_t> idx;
    MedianCut(rgba,pal,idx);

    const int blobSize=0x80+1024+KIT_W*KIT_H;
    uint8_t* blob=reinterpret_cast<uint8_t*>(GameAlloc(1,blobSize));
    if(!blob){
        Log("[CustomKitPNG] allocation failed team=%u variant=%d",team,variant);
        return 0;
    }
    memset(blob,0,blobSize);

    auto W32=[&](int off,uint32_t v){*reinterpret_cast<uint32_t*>(blob+off)=v;};
    W32(0x00,0x29857294);
    W32(0x04,1);
    W32(0x08,(uint32_t)blobSize);
    W32(0x0C,(uint32_t)displayId);
    W32(0x10,0x00800480);
    W32(0x14,(uint32_t)KIT_W | ((uint32_t)KIT_H<<16));
    blob[0x18]=0x02;
    blob[0x19]=0x13;
    blob[0x1A]=9;
    blob[0x1B]=8;
    W32(0x1C,0x10100001);
    W32(0x20,(uint32_t)((KIT_W*KIT_H)/16));
    W32(0x24,0x40);
    W32(0x28,(uint32_t)(KIT_W/2) | ((uint32_t)(KIT_H/2)<<16));
    const uint32_t lo2c=(KIT_W>>7)?(uint32_t)(KIT_W>>7):1u;
    const uint32_t hi2c=((KIT_W*KIT_H)>>13)?(uint32_t)((KIT_W*KIT_H)>>13):1u;
    W32(0x2C,lo2c | (hi2c<<16));

    uint8_t* ppal=blob+0x80;
    for(int i=0;i<256;++i){
        RGBA q=pal[i];
        int a=(q.a+1)/2; if(a>128)a=128;
        ppal[i*4+0]=q.r;
        ppal[i*4+1]=q.g;
        ppal[i*4+2]=q.b;
        ppal[i*4+3]=(uint8_t)a;
    }
    ClutSwap(ppal);

    uint8_t* pix=blob+0x480;
    for(int y=0;y<KIT_H;++y)
        for(int x=0;x<KIT_W;++x)
            pix[SwzIndex(x,y,KIT_W)] = idx[y*KIT_W+x];

    uint32_t* node=RegisterTexture(reinterpret_cast<uint32_t>(blob));
    if(!node){
        node=ResolveTexture(displayId);
        if(!node) GameFree(reinterpret_cast<uint32_t*>(blob));
    }

    Log("[CustomKitPNG] register team=%u variant=%d file=%ls display=0x%X node=%p",
        team,variant,path,displayId,node);
    return reinterpret_cast<uint32_t>(node);
}

bool ValidateCall(uint32_t site,uint32_t expected)
{
    uint8_t* p=reinterpret_cast<uint8_t*>(site);
    __try{
        if(p[0]!=0xE8) return false;
        int32_t rel=*reinterpret_cast<int32_t*>(p+1);
        return (uint32_t)(p+5+rel)==expected;
    }__except(EXCEPTION_EXECUTE_HANDLER){
        return false;
    }
}

bool PatchCall(uint32_t site,uint32_t expected,void* hook)
{
    if(!ValidateCall(site,expected)){
        Log("[CustomKitPNG] ERROR callsite 0x%08X mismatch",site);
        return false;
    }
    uint8_t* p=reinterpret_cast<uint8_t*>(site);
    DWORD old=0;
    if(!VirtualProtect(p,5,PAGE_EXECUTE_READWRITE,&old)) return false;
    *reinterpret_cast<int32_t*>(p+1)=
        (int32_t)(reinterpret_cast<uint8_t*>(hook)-(p+5));
    DWORD dummy=0;
    VirtualProtect(p,5,old,&dummy);
    FlushInstructionCache(GetCurrentProcess(),p,5);
    return true;
}

uint32_t __cdecl BuildVariantProxy(uint32_t token,uint32_t a2,uint32_t a3,uint32_t a4,uint32_t a5)
{
    LONG t=g_activeTeam;
    if(t>=0 && t<=0xFFFF && token>=0x733E && token<=0x7341){
        int variant=(int)(token-0x733E);
        if(HasVariantPng((uint16_t)t,variant)){
            uint32_t node=BuildAndRegister((uint16_t)t,variant);
            if(node){
                Log("[CustomKitPNG] APPLIED team=%ld variant=%d (%ls) -> node=0x%08X",
                    t,variant,VariantName(variant),node);
                return node;
            }
            Log("[CustomKitPNG] custom build failed team=%ld variant=%d; stock fallback",
                t,variant);
        }
    }
    return g_nativeBuildKitTexture(token,a2,a3,a4,a5);
}

void __cdecl KitSetupProxy(uint32_t team,uint32_t a2,uint32_t a3,uint32_t a4)
{
    LONG prev=g_activeTeam;
    if(team<=0xFFFF && HasAnyKitPng((uint16_t)team)){
        g_activeTeam=(LONG)team;
        Log("[CustomKitPNG] setup team=%u a2=%u a3=%u a4=%u",team,a2,a3,a4);
    } else {
        g_activeTeam=-1;
    }

    g_nativeKitSetup(team,a2,a3,a4);
    g_activeTeam=prev;
}

bool Install()
{
    for(uint32_t s:CALL_SETUP){
        if(!ValidateCall(s,ADDR_SETUP)){
            Log("[CustomKitPNG] ERROR setup call 0x%08X validation; untouched",s);
            return false;
        }
    }
    if(!ValidateCall(CALL_BUILD_VARIANT,ADDR_BUILD_KIT_TEXTURE)){
        Log("[CustomKitPNG] ERROR build call validation; untouched");
        return false;
    }

    if(!PatchCall(CALL_BUILD_VARIANT,ADDR_BUILD_KIT_TEXTURE,
                  reinterpret_cast<void*>(&BuildVariantProxy))) return false;

    for(uint32_t s:CALL_SETUP){
        if(!PatchCall(s,ADDR_SETUP,reinterpret_cast<void*>(&KitSetupProxy))) return false;
    }

    Log("[CustomKitPNG] v0.2 installed. Direct PNG->texture path active. PESMod.asi untouched.");
    return true;
}

DWORD WINAPI Worker(void*)
{
    OpenLog();
    Log("PESModKits v0.2 starting");

    bool ready=false;
    for(int i=0;i<600;++i){
        HMODULE m=GetModuleHandleA("PESMod.asi");
        if(!m) m=GetModuleHandleA("PESMod(7).asi");
        __try{
            if(m && *reinterpret_cast<volatile uint8_t*>(0x00865240)==0xE9){
                ready=true;
                break;
            }
        }__except(EXCEPTION_EXECUTE_HANDLER){}
        Sleep(100);
    }

    if(!ready){
        Log("[CustomKitPNG] ERROR PESMod hook not detected; game untouched");
        return 0;
    }

    Install();
    return 0;
}

} // namespace

BOOL APIENTRY DllMain(HMODULE h,DWORD reason,LPVOID)
{
    if(reason==DLL_PROCESS_ATTACH){
        g_self=h;
        DisableThreadLibraryCalls(h);
        HANDLE th=CreateThread(nullptr,0,Worker,nullptr,0,nullptr);
        if(th) CloseHandle(th);
    } else if(reason==DLL_PROCESS_DETACH){
        if(g_log!=INVALID_HANDLE_VALUE){
            CloseHandle(g_log);
            g_log=INVALID_HANDLE_VALUE;
        }
    }
    return TRUE;
}
