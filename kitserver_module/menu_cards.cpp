// PES 6 animated main-menu card prototype for Kitserver 6.
// V3: follows PES/Kitserver's real input table (keyboard + gamepad),
// auto-shows when the horizontal main-menu assets are loaded, and
// auto-hides/re-shows when entering/leaving a main-menu option.

#define NOMINMAX
#include <windows.h>
#include <wincodec.h>

#include <array>
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <cstdarg>
#include <string>

namespace
{
    // ------------------------------------------------------------------
    // Minimal Direct3D 8 ABI bridge. We call the live device through its
    // COM vtable so this can compile with a modern Windows SDK.
    // ------------------------------------------------------------------
    using D3DCOLOR = DWORD;

    struct D3DVIEWPORT8_MIN { DWORD X, Y, Width, Height; float MinZ, MaxZ; };
    struct D3DLOCKED_RECT_MIN { INT Pitch; void* pBits; };

    constexpr DWORD D3DFMT_A8R8G8B8_ = 21;
    constexpr DWORD D3DPOOL_MANAGED_ = 1;
    constexpr DWORD D3DSBT_ALL_ = 1;
    constexpr DWORD D3DPT_TRIANGLESTRIP_ = 5;

    constexpr DWORD D3DRS_ZENABLE_ = 7;
    constexpr DWORD D3DRS_ZWRITEENABLE_ = 14;
    constexpr DWORD D3DRS_SRCBLEND_ = 19;
    constexpr DWORD D3DRS_DESTBLEND_ = 20;
    constexpr DWORD D3DRS_CULLMODE_ = 22;
    constexpr DWORD D3DRS_ALPHABLENDENABLE_ = 27;
    constexpr DWORD D3DRS_LIGHTING_ = 137;

    constexpr DWORD D3DBLEND_SRCALPHA_ = 5;
    constexpr DWORD D3DBLEND_INVSRCALPHA_ = 6;
    constexpr DWORD D3DCULL_NONE_ = 1;

    constexpr DWORD D3DTSS_COLOROP_ = 1;
    constexpr DWORD D3DTSS_COLORARG1_ = 2;
    constexpr DWORD D3DTSS_COLORARG2_ = 3;
    constexpr DWORD D3DTSS_ALPHAOP_ = 4;
    constexpr DWORD D3DTSS_ALPHAARG1_ = 5;
    constexpr DWORD D3DTSS_ALPHAARG2_ = 6;
    constexpr DWORD D3DTSS_MAGFILTER_ = 16;
    constexpr DWORD D3DTSS_MINFILTER_ = 17;

    constexpr DWORD D3DTOP_SELECTARG1_ = 2;
    constexpr DWORD D3DTOP_MODULATE_ = 4;
    constexpr DWORD D3DTA_DIFFUSE_ = 0x00000000;
    constexpr DWORD D3DTA_TEXTURE_ = 0x00000002;
    constexpr DWORD D3DTEXF_LINEAR_ = 2;

    constexpr DWORD D3DFVF_XYZRHW_ = 0x004;
    constexpr DWORD D3DFVF_DIFFUSE_ = 0x040;
    constexpr DWORD D3DFVF_TEX1_ = 0x100;
    constexpr DWORD kFvf = D3DFVF_XYZRHW_ | D3DFVF_DIFFUSE_ | D3DFVF_TEX1_;

    inline D3DCOLOR Argb(BYTE a, BYTE r, BYTE g, BYTE b)
    {
        return (static_cast<DWORD>(a) << 24) |
               (static_cast<DWORD>(r) << 16) |
               (static_cast<DWORD>(g) << 8) |
               static_cast<DWORD>(b);
    }

    template<typename Fn>
    Fn VMethod(void* obj, size_t index)
    {
        return reinterpret_cast<Fn>((*reinterpret_cast<void***>(obj))[index]);
    }

    ULONG ComRelease(void* obj)
    {
        using Fn = ULONG (__stdcall*)(void*);
        return obj ? VMethod<Fn>(obj, 2)(obj) : 0;
    }

    HRESULT DevCreateTexture(void* dev, UINT w, UINT h, void** outTex)
    {
        using Fn = HRESULT (__stdcall*)(void*, UINT, UINT, UINT, DWORD, DWORD, DWORD, void**);
        return VMethod<Fn>(dev, 20)(dev, w, h, 1, 0, D3DFMT_A8R8G8B8_, D3DPOOL_MANAGED_, outTex);
    }
    HRESULT DevBeginScene(void* dev) { using Fn = HRESULT (__stdcall*)(void*); return VMethod<Fn>(dev, 34)(dev); }
    HRESULT DevEndScene(void* dev) { using Fn = HRESULT (__stdcall*)(void*); return VMethod<Fn>(dev, 35)(dev); }
    HRESULT DevGetViewport(void* dev, D3DVIEWPORT8_MIN* vp) { using Fn = HRESULT (__stdcall*)(void*, D3DVIEWPORT8_MIN*); return VMethod<Fn>(dev, 41)(dev, vp); }
    HRESULT DevSetRenderState(void* dev, DWORD s, DWORD v) { using Fn = HRESULT (__stdcall*)(void*, DWORD, DWORD); return VMethod<Fn>(dev, 50)(dev, s, v); }
    HRESULT DevApplyStateBlock(void* dev, DWORD token) { using Fn = HRESULT (__stdcall*)(void*, DWORD); return VMethod<Fn>(dev, 54)(dev, token); }
    HRESULT DevDeleteStateBlock(void* dev, DWORD token) { using Fn = HRESULT (__stdcall*)(void*, DWORD); return VMethod<Fn>(dev, 56)(dev, token); }
    HRESULT DevCreateStateBlock(void* dev, DWORD* token) { using Fn = HRESULT (__stdcall*)(void*, DWORD, DWORD*); return VMethod<Fn>(dev, 57)(dev, D3DSBT_ALL_, token); }
    HRESULT DevSetTexture(void* dev, DWORD stage, void* tex) { using Fn = HRESULT (__stdcall*)(void*, DWORD, void*); return VMethod<Fn>(dev, 61)(dev, stage, tex); }
    HRESULT DevSetTextureStageState(void* dev, DWORD stage, DWORD type, DWORD value) { using Fn = HRESULT (__stdcall*)(void*, DWORD, DWORD, DWORD); return VMethod<Fn>(dev, 63)(dev, stage, type, value); }
    HRESULT DevDrawPrimitiveUP(void* dev, DWORD type, UINT count, const void* data, UINT stride) { using Fn = HRESULT (__stdcall*)(void*, DWORD, UINT, const void*, UINT); return VMethod<Fn>(dev, 72)(dev, type, count, data, stride); }
    HRESULT DevSetVertexShader(void* dev, DWORD shader) { using Fn = HRESULT (__stdcall*)(void*, DWORD); return VMethod<Fn>(dev, 76)(dev, shader); }
    HRESULT DevSetPixelShader(void* dev, DWORD shader) { using Fn = HRESULT (__stdcall*)(void*, DWORD); return VMethod<Fn>(dev, 88)(dev, shader); }
    HRESULT TexLockRect(void* tex, D3DLOCKED_RECT_MIN* locked) { using Fn = HRESULT (__stdcall*)(void*, UINT, D3DLOCKED_RECT_MIN*, const RECT*, DWORD); return VMethod<Fn>(tex, 16)(tex, 0, locked, nullptr, 0); }
    HRESULT TexUnlockRect(void* tex) { using Fn = HRESULT (__stdcall*)(void*, UINT); return VMethod<Fn>(tex, 17)(tex, 0); }

    // ------------------------------------------------------------------
    // Kitserver bridge
    // ------------------------------------------------------------------
    constexpr int HK_D3D_CREATE = 0;
    constexpr int HK_D3D_PRESENT = 3;

    using HookFunctionFn = void (__cdecl*)(int, DWORD);
    using UnhookFunctionFn = void (__cdecl*)(int, DWORD);
    using GetInputTableFn = DWORD* (__cdecl*)();
    using RegisterAfsReplaceCallbackFn = void (__cdecl*)(void*, void*, void*);
    using SplitFileIdFn = DWORD (__cdecl*)(DWORD, DWORD*);

    struct GETFILEINFO_MIN
    {
        DWORD uniqueId;
        bool isProcessed;
        DWORD fileId;
        DWORD oldFileId;
        void* replaceBuf;
        DWORD replaceSize;
        DWORD firstPage;
        char fileName[0x200];
        bool needsUnpack;
    };

    HMODULE g_self = nullptr;
    HookFunctionFn g_hookFunction = nullptr;
    UnhookFunctionFn g_unhookFunction = nullptr;
    GetInputTableFn g_getInputTable = nullptr;
    RegisterAfsReplaceCallbackFn g_registerAfs = nullptr;
    SplitFileIdFn g_splitFileId = nullptr;

    bool g_presentHooked = false;
    bool g_createHooked = false;
    bool g_afsHooked = false;

    bool g_visible = false;
    bool g_autoMainMenu = true;
    bool g_hiddenByEnter = false;
    bool g_seenMainMenuAssets = false;
    int g_index = 0;
    int g_prevIndex = 0;
    ULONGLONG g_transitionStart = 0;
    DWORD g_lastDirectional = 0;
    DWORD g_lastFunctional = 0;

    float g_anchorX = 0.251f;
    float g_anchorY = 0.783f;
    float g_cardW = 0.116f;
    float g_cardH = 0.188f;
    float g_animMs = 235.0f;
    float g_reflection = 0.26f;

    // Kitserver input.h values.
    constexpr DWORD LEFT_PRESSED = 0x40;
    constexpr DWORD RIGHT_PRESSED = 0x80;
    constexpr DWORD CROSS_PRESSED = 0x01;
    constexpr DWORD CIRCLE_PRESSED = 0x08;
    constexpr int DIRECTIONAL_PRESSED = 0;
    constexpr int FUNCTIONAL = 16;

    struct TextureSlot { void* tex = nullptr; UINT width = 0; UINT height = 0; };
    std::array<TextureSlot, 11> g_textures = {};
    void* g_textureDevice = nullptr;

    constexpr std::array<const char*, 11> kAssetNames = {
        "partido.png", "liga_master.png", "liga.png", "copa.png",
        "entrenamiento.png", "editar.png", "opciones.png",
        "partido_internacional.png", "seleccion_azar.png", "red.png", "salir.png"
    };

    struct Vertex { float x, y, z, rhw; D3DCOLOR color; float u, v; };

    std::string ModuleDir()
    {
        char path[MAX_PATH] = {};
        GetModuleFileNameA(g_self, path, MAX_PATH);
        std::string s(path);
        const size_t slash = s.find_last_of("\\/");
        if (slash != std::string::npos) s.resize(slash);
        return s;
    }

    std::string IniPath() { return ModuleDir() + "\\menu_cards.ini"; }
    std::string LogPath() { return ModuleDir() + "\\menu_cards.log"; }
    std::string AssetPath(const char* name) { return ModuleDir() + "\\menu_cards\\" + name; }

    void Log(const char* fmt, ...)
    {
        FILE* f = nullptr;
        fopen_s(&f, LogPath().c_str(), "a");
        if (!f) return;
        SYSTEMTIME st = {};
        GetLocalTime(&st);
        std::fprintf(f, "[%02u:%02u:%02u] ", st.wHour, st.wMinute, st.wSecond);
        va_list ap;
        va_start(ap, fmt);
        std::vfprintf(f, fmt, ap);
        va_end(ap);
        std::fputc('\n', f);
        std::fclose(f);
    }

    float ReadFloat(const char* key, float def)
    {
        char buf[64] = {}, defBuf[64] = {};
        std::snprintf(defBuf, sizeof(defBuf), "%.4f", def);
        GetPrivateProfileStringA("menu_cards", key, defBuf, buf, sizeof(buf), IniPath().c_str());
        return std::strtof(buf, nullptr);
    }

    void ReadConfig()
    {
        g_autoMainMenu = GetPrivateProfileIntA("menu_cards", "auto_main_menu", 1, IniPath().c_str()) != 0;
        if (!g_autoMainMenu)
            g_visible = GetPrivateProfileIntA("menu_cards", "start_visible", 0, IniPath().c_str()) != 0;
        g_anchorX = ReadFloat("anchor_x", 0.251f);
        g_anchorY = ReadFloat("anchor_y", 0.783f);
        g_cardW = ReadFloat("card_width", 0.116f);
        g_cardH = ReadFloat("card_height", 0.188f);
        g_animMs = ReadFloat("animation_ms", 235.0f);
        g_reflection = ReadFloat("reflection_alpha", 0.26f);
    }

    void ReleaseTextures()
    {
        for (auto& slot : g_textures)
        {
            if (slot.tex) ComRelease(slot.tex);
            slot = {};
        }
        g_textureDevice = nullptr;
    }

    bool LoadPng(void* device, const std::string& path, TextureSlot& out)
    {
        out = {};
        if (!device) return false;
        const HRESULT initHr = CoInitializeEx(nullptr, COINIT_MULTITHREADED);
        const bool doUninit = SUCCEEDED(initHr);
        IWICImagingFactory* factory = nullptr;
        IWICBitmapDecoder* decoder = nullptr;
        IWICBitmapFrameDecode* frame = nullptr;
        IWICFormatConverter* converter = nullptr;
        HRESULT hr = CoCreateInstance(CLSID_WICImagingFactory, nullptr, CLSCTX_INPROC_SERVER,
                                      IID_PPV_ARGS(&factory));
        if (FAILED(hr)) goto cleanup;

        {
            int n = MultiByteToWideChar(CP_ACP, 0, path.c_str(), -1, nullptr, 0);
            if (n <= 0) { hr = E_FAIL; goto cleanup; }
            std::wstring wide(static_cast<size_t>(n), L'\0');
            MultiByteToWideChar(CP_ACP, 0, path.c_str(), -1, wide.data(), n);
            hr = factory->CreateDecoderFromFilename(wide.c_str(), nullptr, GENERIC_READ,
                                                    WICDecodeMetadataCacheOnLoad, &decoder);
            if (FAILED(hr)) goto cleanup;
        }
        hr = decoder->GetFrame(0, &frame);
        if (FAILED(hr)) goto cleanup;
        hr = factory->CreateFormatConverter(&converter);
        if (FAILED(hr)) goto cleanup;
        hr = converter->Initialize(frame, GUID_WICPixelFormat32bppBGRA,
                                   WICBitmapDitherTypeNone, nullptr, 0.0,
                                   WICBitmapPaletteTypeCustom);
        if (FAILED(hr)) goto cleanup;

        {
            UINT w = 0, h = 0;
            hr = converter->GetSize(&w, &h);
            if (FAILED(hr) || w == 0 || h == 0) { hr = E_FAIL; goto cleanup; }
            void* tex = nullptr;
            hr = DevCreateTexture(device, w, h, &tex);
            if (FAILED(hr) || !tex) goto cleanup;

            D3DLOCKED_RECT_MIN lock = {};
            hr = TexLockRect(tex, &lock);
            if (FAILED(hr)) { ComRelease(tex); goto cleanup; }

            const UINT stride = w * 4;
            const size_t bytes = static_cast<size_t>(stride) * h;
            BYTE* pixels = new BYTE[bytes];
            hr = converter->CopyPixels(nullptr, stride, static_cast<UINT>(bytes), pixels);
            if (SUCCEEDED(hr))
            {
                for (UINT y = 0; y < h; ++y)
                    std::memcpy(static_cast<BYTE*>(lock.pBits) + static_cast<size_t>(y) * lock.Pitch,
                                pixels + static_cast<size_t>(y) * stride, stride);
            }
            delete[] pixels;
            TexUnlockRect(tex);
            if (FAILED(hr)) { ComRelease(tex); goto cleanup; }
            out.tex = tex; out.width = w; out.height = h;
        }

    cleanup:
        if (converter) converter->Release();
        if (frame) frame->Release();
        if (decoder) decoder->Release();
        if (factory) factory->Release();
        if (doUninit) CoUninitialize();
        return SUCCEEDED(hr) && out.tex != nullptr;
    }

    void EnsureTextures(void* device)
    {
        if (!device) return;
        if (g_textureDevice == device && g_textures[0].tex) return;
        ReleaseTextures();
        g_textureDevice = device;
        int loaded = 0;
        for (size_t i = 0; i < kAssetNames.size(); ++i)
        {
            if (LoadPng(device, AssetPath(kAssetNames[i]), g_textures[i])) ++loaded;
            else Log("asset failed: %s", AssetPath(kAssetNames[i]).c_str());
        }
        Log("loaded %d/11 textures", loaded);
    }

    float Saturate(float v) { return std::max(0.0f, std::min(1.0f, v)); }
    float EaseOutBack(float t)
    {
        t = Saturate(t);
        constexpr float c1 = 1.70158f, c3 = c1 + 1.0f;
        const float x = t - 1.0f;
        return 1.0f + c3*x*x*x + c1*x*x;
    }

    void DrawQuad(void* dev, void* tex, float x0, float y0, float x1, float y1,
                  D3DCOLOR topColor, D3DCOLOR bottomColor,
                  float u0=0.0f, float v0=0.0f, float u1=1.0f, float v1=1.0f)
    {
        Vertex v[4] = {
            {x0,y0,0,1,topColor,u0,v0}, {x1,y0,0,1,topColor,u1,v0},
            {x0,y1,0,1,bottomColor,u0,v1}, {x1,y1,0,1,bottomColor,u1,v1}
        };
        DevSetTexture(dev, 0, tex);
        DevDrawPrimitiveUP(dev, D3DPT_TRIANGLESTRIP_, 2, v, sizeof(Vertex));
    }

    void SetupState(void* dev)
    {
        DevSetVertexShader(dev, kFvf);
        DevSetPixelShader(dev, 0);
        DevSetRenderState(dev, D3DRS_ZENABLE_, FALSE);
        DevSetRenderState(dev, D3DRS_ZWRITEENABLE_, FALSE);
        DevSetRenderState(dev, D3DRS_ALPHABLENDENABLE_, TRUE);
        DevSetRenderState(dev, D3DRS_SRCBLEND_, D3DBLEND_SRCALPHA_);
        DevSetRenderState(dev, D3DRS_DESTBLEND_, D3DBLEND_INVSRCALPHA_);
        DevSetRenderState(dev, D3DRS_CULLMODE_, D3DCULL_NONE_);
        DevSetRenderState(dev, D3DRS_LIGHTING_, FALSE);
        DevSetTextureStageState(dev,0,D3DTSS_COLOROP_,D3DTOP_MODULATE_);
        DevSetTextureStageState(dev,0,D3DTSS_COLORARG1_,D3DTA_TEXTURE_);
        DevSetTextureStageState(dev,0,D3DTSS_COLORARG2_,D3DTA_DIFFUSE_);
        DevSetTextureStageState(dev,0,D3DTSS_ALPHAOP_,D3DTOP_MODULATE_);
        DevSetTextureStageState(dev,0,D3DTSS_ALPHAARG1_,D3DTA_TEXTURE_);
        DevSetTextureStageState(dev,0,D3DTSS_ALPHAARG2_,D3DTA_DIFFUSE_);
        DevSetTextureStageState(dev,0,D3DTSS_MINFILTER_,D3DTEXF_LINEAR_);
        DevSetTextureStageState(dev,0,D3DTSS_MAGFILTER_,D3DTEXF_LINEAR_);
    }

    void TriggerIndex(int newIndex)
    {
        newIndex = std::max(0, std::min(10, newIndex));
        if (newIndex == g_index) return;
        g_prevIndex = g_index;
        g_index = newIndex;
        g_transitionStart = GetTickCount64();
        Log("index -> %d", g_index);
    }

    void HandleInput()
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
            ReleaseTextures(); ReadConfig(); Log("F10 reload");
        }

        if (!g_getInputTable) return;
        DWORD* table = g_getInputTable();
        if (!table) return;

        const DWORD dir = table[DIRECTIONAL_PRESSED];
        const DWORD func = table[FUNCTIONAL];
        const DWORD dirEdge = dir & ~g_lastDirectional;
        const DWORD funcEdge = func & ~g_lastFunctional;
        g_lastDirectional = dir;
        g_lastFunctional = func;

        if (g_autoMainMenu && g_visible && (funcEdge & CROSS_PRESSED))
        {
            g_visible = false;
            g_hiddenByEnter = true;
            Log("auto hide: enter option index=%d", g_index);
            return;
        }
        if (g_autoMainMenu && !g_visible && g_hiddenByEnter && (funcEdge & CIRCLE_PRESSED))
        {
            g_visible = true;
            g_hiddenByEnter = false;
            g_transitionStart = GetTickCount64();
            Log("auto show: returned to main menu index=%d", g_index);
            return;
        }

        if (!g_visible) return;
        if (dirEdge & RIGHT_PRESSED) TriggerIndex(g_index + 1);
        else if (dirEdge & LEFT_PRESSED) TriggerIndex(g_index - 1);
    }

    void DrawCard(void* dev, void* tex, float centerX, float bottomY,
                  float fullW, float fullH, float openness, float alpha, bool reflection)
    {
        if (!tex || openness <= 0.001f || alpha <= 0.001f) return;
        const float curH = std::max(2.0f, fullH * openness);
        const float x0 = centerX - fullW*0.5f, x1 = centerX + fullW*0.5f;
        const float y0 = bottomY - curH;
        const BYTE a = static_cast<BYTE>(255.0f * Saturate(alpha));
        DrawQuad(dev, tex, x0, y0, x1, bottomY, Argb(a,255,255,255), Argb(a,255,255,255));

        if (reflection)
        {
            const float rh = fullH * 0.24f * openness;
            const BYTE ra = static_cast<BYTE>(255.0f * Saturate(alpha * g_reflection));
            DrawQuad(dev, tex, x0, bottomY+2.0f, x1, bottomY+2.0f+rh,
                     Argb(ra,255,255,255), Argb(0,255,255,255), 0,1,1,0.76f);
        }
    }

    void Render(void* dev)
    {
        if (!g_visible || !dev) return;
        EnsureTextures(dev);
        D3DVIEWPORT8_MIN vp = {};
        if (FAILED(DevGetViewport(dev, &vp)) || vp.Width == 0 || vp.Height == 0) return;

        const float W = static_cast<float>(vp.Width), H = static_cast<float>(vp.Height);
        const float centerX = W*g_anchorX, bottomY = H*g_anchorY;
        const float fullW = W*g_cardW, fullH = H*g_cardH;
        const ULONGLONG now = GetTickCount64();
        const float raw = Saturate(static_cast<float>(now-g_transitionStart) / std::max(1.0f,g_animMs));
        const float inP = EaseOutBack(raw), outP = 1.0f - raw;
        const float breathe = 1.0f + 0.006f*std::sin(static_cast<float>(now)*0.004f);

        DWORD state = 0;
        const bool haveState = SUCCEEDED(DevCreateStateBlock(dev, &state));
        if (FAILED(DevBeginScene(dev))) { if (haveState) DevDeleteStateBlock(dev,state); return; }
        SetupState(dev);

        if (raw < 1.0f && g_prevIndex != g_index)
            DrawCard(dev, g_textures[static_cast<size_t>(g_prevIndex)].tex,
                     centerX,bottomY,fullW,fullH,std::max(0.08f,outP),outP,true);

        DrawCard(dev, g_textures[static_cast<size_t>(g_index)].tex,
                 centerX,bottomY,fullW*breathe,fullH*breathe,
                 std::max(0.05f,inP),Saturate(raw*1.35f),true);

        DevSetTexture(dev,0,nullptr);
        DevSetTextureStageState(dev,0,D3DTSS_COLOROP_,D3DTOP_SELECTARG1_);
        DevSetTextureStageState(dev,0,D3DTSS_COLORARG1_,D3DTA_DIFFUSE_);
        DevSetTextureStageState(dev,0,D3DTSS_ALPHAOP_,D3DTOP_SELECTARG1_);
        DevSetTextureStageState(dev,0,D3DTSS_ALPHAARG1_,D3DTA_DIFFUSE_);
        const float sweep = std::fmod(static_cast<float>(now)*0.00024f,1.28f)-0.14f;
        const float sx0 = centerX-fullW*0.5f+fullW*sweep;
        DrawQuad(dev,nullptr,sx0,bottomY-fullH*0.96f,sx0+fullW*0.08f,bottomY-4.0f,
                 Argb(18,255,255,255),Argb(4,255,255,255));

        DevEndScene(dev);
        if (haveState) { DevApplyStateBlock(dev,state); DevDeleteStateBlock(dev,state); }
    }

    void __cdecl OnPresent(void* self, const RECT*, const RECT*, HWND, LPVOID)
    {
        HandleInput();
        Render(self);
    }

    void __cdecl OnAfsFile(GETFILEINFO_MIN* gfi)
    {
        if (!gfi || !g_splitFileId) return;
        DWORD afsId = 0;
        const DWORD localId = g_splitFileId(gfi->fileId, &afsId);
        const bool mainMenuAsset = (afsId == 3 && localId == 356) || (afsId == 1 && localId == 920);
        if (!mainMenuAsset) return;

        if (!g_seenMainMenuAssets)
            Log("main menu asset detected: afs=%lu file=%lu", afsId, localId);
        g_seenMainMenuAssets = true;
        if (g_autoMainMenu)
        {
            g_visible = true;
            g_hiddenByEnter = false;
            g_transitionStart = GetTickCount64();
        }
    }

    void __cdecl OnD3DCreate()
    {
        HMODULE kload = GetModuleHandleA("kload.dll");
        if (kload)
        {
            g_registerAfs = reinterpret_cast<RegisterAfsReplaceCallbackFn>(GetProcAddress(kload,"RegisterAfsReplaceCallback"));
            g_splitFileId = reinterpret_cast<SplitFileIdFn>(GetProcAddress(kload,"splitFileId"));
            if (g_registerAfs && g_splitFileId && !g_afsHooked)
            {
                g_registerAfs(reinterpret_cast<void*>(&OnAfsFile), nullptr, nullptr);
                g_afsHooked = true;
                Log("registered AFS observer for main-menu assets");
            }
            else Log("AFS observer exports unavailable");
        }
        if (g_createHooked && g_unhookFunction)
        {
            g_unhookFunction(HK_D3D_CREATE, reinterpret_cast<DWORD>(&OnD3DCreate));
            g_createHooked = false;
        }
    }

    bool InstallKitserverHooks()
    {
        HMODULE kload = GetModuleHandleA("kload.dll");
        if (!kload) { Log("kload.dll not loaded"); return false; }
        g_hookFunction = reinterpret_cast<HookFunctionFn>(GetProcAddress(kload,"HookFunction"));
        g_unhookFunction = reinterpret_cast<UnhookFunctionFn>(GetProcAddress(kload,"UnhookFunction"));
        g_getInputTable = reinterpret_cast<GetInputTableFn>(GetProcAddress(kload,"GetInputTable"));
        if (!g_hookFunction) { Log("HookFunction export not found"); return false; }

        g_hookFunction(HK_D3D_CREATE, reinterpret_cast<DWORD>(&OnD3DCreate));
        g_createHooked = true;
        g_hookFunction(HK_D3D_PRESENT, reinterpret_cast<DWORD>(&OnPresent));
        g_presentHooked = true;
        Log("registered hk_D3D_Create + hk_D3D_Present; input=%s", g_getInputTable ? "OK" : "missing");
        return true;
    }
}

BOOL WINAPI DllMain(HINSTANCE hinst, DWORD reason, LPVOID)
{
    if (reason == DLL_PROCESS_ATTACH)
    {
        g_self = hinst;
        DisableThreadLibraryCalls(hinst);
        DeleteFileA(LogPath().c_str());
        ReadConfig();
        g_transitionStart = GetTickCount64();
        InstallKitserverHooks();
    }
    else if (reason == DLL_PROCESS_DETACH)
    {
        if (g_presentHooked && g_unhookFunction)
            g_unhookFunction(HK_D3D_PRESENT, reinterpret_cast<DWORD>(&OnPresent));
        if (g_createHooked && g_unhookFunction)
            g_unhookFunction(HK_D3D_CREATE, reinterpret_cast<DWORD>(&OnD3DCreate));
        ReleaseTextures();
    }
    return TRUE;
}
