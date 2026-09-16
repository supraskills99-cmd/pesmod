// Animated PES 6 main-menu card prototype loaded as a Kitserver module.
//
// Important: this does NOT patch Direct3DCreate8 itself. It registers a
// callback with Kitserver's already-installed hk_D3D_Present chain, the same
// mechanism used by official Kitserver 6 modules. This keeps PESMod.asi out of
// the rendering path and avoids the startup crash seen with the direct D3D8
// experiment.

#include <windows.h>
#include <wincodec.h>
#include <d3d8.h>

#include <array>
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>

namespace
{
    constexpr int HK_D3D_PRESENT = 3; // hook.h: hk_D3D_Present

    using HookFunctionFn   = void (__cdecl*)(int, DWORD);
    using UnhookFunctionFn = void (__cdecl*)(int, DWORD);

    HMODULE g_self = nullptr;
    HookFunctionFn g_hookFunction = nullptr;
    UnhookFunctionFn g_unhookFunction = nullptr;
    bool g_hooked = false;

    bool g_visible = true;
    int g_index = 0;
    int g_prevIndex = 0;
    ULONGLONG g_transitionStart = 0;
    ULONGLONG g_lastInputAt = 0;

    float g_anchorX = 0.250f;
    float g_anchorY = 0.875f;
    float g_cardW = 0.145f;
    float g_cardH = 0.430f;
    float g_animMs = 260.0f;
    float g_reflection = 0.30f;

    struct TextureSlot
    {
        IDirect3DTexture8* tex = nullptr;
        UINT width = 0;
        UINT height = 0;
    };

    std::array<TextureSlot, 11> g_textures = {};
    IDirect3DDevice8* g_textureDevice = nullptr;

    constexpr std::array<const char*, 11> kAssetNames = {
        "partido.png",
        "liga_master.png",
        "liga.png",
        "copa.png",
        "entrenamiento.png",
        "editar.png",
        "opciones.png",
        "partido_internacional.png",
        "seleccion_azar.png",
        "red.png",
        "salir.png"
    };

    struct Vertex
    {
        float x, y, z, rhw;
        D3DCOLOR color;
        float u, v;
    };

    constexpr DWORD kFvf = D3DFVF_XYZRHW | D3DFVF_DIFFUSE | D3DFVF_TEX1;

    std::string ModuleDir()
    {
        char path[MAX_PATH] = {};
        GetModuleFileNameA(g_self, path, MAX_PATH);
        std::string s(path);
        const size_t slash = s.find_last_of("\\/");
        if (slash != std::string::npos) s.resize(slash);
        return s;
    }

    std::string IniPath()
    {
        return ModuleDir() + "\\menu_cards.ini";
    }

    std::string AssetPath(const char* name)
    {
        return ModuleDir() + "\\menu_cards\\" + name;
    }

    std::string LogPath()
    {
        return ModuleDir() + "\\menu_cards.log";
    }

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
        char buf[64] = {};
        char defBuf[64] = {};
        std::snprintf(defBuf, sizeof(defBuf), "%.4f", def);
        GetPrivateProfileStringA("menu_cards", key, defBuf, buf, sizeof(buf), IniPath().c_str());
        return std::strtof(buf, nullptr);
    }

    void ReadConfig()
    {
        g_visible = GetPrivateProfileIntA("menu_cards", "start_visible", 1, IniPath().c_str()) != 0;
        g_anchorX = ReadFloat("anchor_x", 0.250f);
        g_anchorY = ReadFloat("anchor_y", 0.875f);
        g_cardW = ReadFloat("card_width", 0.145f);
        g_cardH = ReadFloat("card_height", 0.430f);
        g_animMs = ReadFloat("animation_ms", 260.0f);
        g_reflection = ReadFloat("reflection_alpha", 0.30f);
    }

    void ReleaseTextures()
    {
        for (auto& slot : g_textures)
        {
            if (slot.tex) slot.tex->Release();
            slot = {};
        }
        g_textureDevice = nullptr;
    }

    bool LoadPng(IDirect3DDevice8* device, const std::string& path, TextureSlot& out)
    {
        out = {};
        if (!device) return false;

        HRESULT initHr = CoInitializeEx(nullptr, COINIT_MULTITHREADED);
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

            IDirect3DTexture8* tex = nullptr;
            hr = device->CreateTexture(w, h, 1, 0, D3DFMT_A8R8G8B8, D3DPOOL_MANAGED, &tex);
            if (FAILED(hr) || !tex) goto cleanup;

            D3DLOCKED_RECT lock = {};
            hr = tex->LockRect(0, &lock, nullptr, 0);
            if (FAILED(hr)) { tex->Release(); goto cleanup; }

            const UINT stride = w * 4;
            const size_t bytes = static_cast<size_t>(stride) * h;
            BYTE* pixels = new BYTE[bytes];
            hr = converter->CopyPixels(nullptr, stride, static_cast<UINT>(bytes), pixels);
            if (SUCCEEDED(hr))
            {
                for (UINT y = 0; y < h; ++y)
                    std::memcpy(static_cast<BYTE*>(lock.pBits) + y * lock.Pitch,
                                pixels + static_cast<size_t>(y) * stride, stride);
            }
            delete[] pixels;
            tex->UnlockRect(0);

            if (FAILED(hr)) { tex->Release(); goto cleanup; }
            out.tex = tex;
            out.width = w;
            out.height = h;
        }

    cleanup:
        if (converter) converter->Release();
        if (frame) frame->Release();
        if (decoder) decoder->Release();
        if (factory) factory->Release();
        if (doUninit) CoUninitialize();
        return SUCCEEDED(hr) && out.tex != nullptr;
    }

    void EnsureTextures(IDirect3DDevice8* device)
    {
        if (!device) return;
        if (g_textureDevice == device && g_textures[0].tex) return;

        ReleaseTextures();
        g_textureDevice = device;
        int loaded = 0;
        for (size_t i = 0; i < kAssetNames.size(); ++i)
        {
            if (LoadPng(device, AssetPath(kAssetNames[i]), g_textures[i]))
                ++loaded;
            else
                Log("asset failed: %s", AssetPath(kAssetNames[i]).c_str());
        }
        Log("loaded %d/11 textures", loaded);
    }

    float Saturate(float v)
    {
        return std::max(0.0f, std::min(1.0f, v));
    }

    float EaseOutBack(float t)
    {
        t = Saturate(t);
        constexpr float c1 = 1.70158f;
        constexpr float c3 = c1 + 1.0f;
        const float x = t - 1.0f;
        return 1.0f + c3 * x * x * x + c1 * x * x;
    }

    void DrawQuad(IDirect3DDevice8* dev, IDirect3DTexture8* tex,
                  float x0, float y0, float x1, float y1,
                  D3DCOLOR topColor, D3DCOLOR bottomColor,
                  float u0 = 0.0f, float v0 = 0.0f,
                  float u1 = 1.0f, float v1 = 1.0f)
    {
        Vertex v[4] = {
            {x0, y0, 0.0f, 1.0f, topColor,    u0, v0},
            {x1, y0, 0.0f, 1.0f, topColor,    u1, v0},
            {x0, y1, 0.0f, 1.0f, bottomColor, u0, v1},
            {x1, y1, 0.0f, 1.0f, bottomColor, u1, v1},
        };
        dev->SetTexture(0, tex);
        dev->DrawPrimitiveUP(D3DPT_TRIANGLESTRIP, 2, v, sizeof(Vertex));
    }

    void SetupState(IDirect3DDevice8* dev)
    {
        dev->SetVertexShader(kFvf);
        dev->SetRenderState(D3DRS_ZENABLE, FALSE);
        dev->SetRenderState(D3DRS_ZWRITEENABLE, FALSE);
        dev->SetRenderState(D3DRS_ALPHABLENDENABLE, TRUE);
        dev->SetRenderState(D3DRS_SRCBLEND, D3DBLEND_SRCALPHA);
        dev->SetRenderState(D3DRS_DESTBLEND, D3DBLEND_INVSRCALPHA);
        dev->SetRenderState(D3DRS_CULLMODE, D3DCULL_NONE);
        dev->SetRenderState(D3DRS_LIGHTING, FALSE);

        dev->SetTextureStageState(0, D3DTSS_COLOROP, D3DTOP_MODULATE);
        dev->SetTextureStageState(0, D3DTSS_COLORARG1, D3DTA_TEXTURE);
        dev->SetTextureStageState(0, D3DTSS_COLORARG2, D3DTA_DIFFUSE);
        dev->SetTextureStageState(0, D3DTSS_ALPHAOP, D3DTOP_MODULATE);
        dev->SetTextureStageState(0, D3DTSS_ALPHAARG1, D3DTA_TEXTURE);
        dev->SetTextureStageState(0, D3DTSS_ALPHAARG2, D3DTA_DIFFUSE);
        dev->SetTextureStageState(0, D3DTSS_MINFILTER, D3DTEXF_LINEAR);
        dev->SetTextureStageState(0, D3DTSS_MAGFILTER, D3DTEXF_LINEAR);
    }

    void TriggerIndex(int newIndex)
    {
        if (newIndex == g_index) return;
        g_prevIndex = g_index;
        g_index = newIndex;
        g_transitionStart = GetTickCount64();
        Log("index -> %d", g_index);
    }

    void HandleKeys()
    {
        if (GetAsyncKeyState(VK_F9) & 1)
        {
            g_visible = !g_visible;
            g_transitionStart = GetTickCount64();
            Log("visible = %d", g_visible ? 1 : 0);
        }
        if (GetAsyncKeyState(VK_F10) & 1)
        {
            ReleaseTextures();
            ReadConfig();
            Log("reload requested");
        }

        if (!g_visible) return;
        const ULONGLONG now = GetTickCount64();
        if (now - g_lastInputAt < 90) return;

        if (GetAsyncKeyState(VK_RIGHT) & 1)
        {
            TriggerIndex((g_index + 1) % 11);
            g_lastInputAt = now;
        }
        else if (GetAsyncKeyState(VK_LEFT) & 1)
        {
            TriggerIndex((g_index + 10) % 11);
            g_lastInputAt = now;
        }
    }

    void DrawCard(IDirect3DDevice8* dev, IDirect3DTexture8* tex,
                  float centerX, float bottomY, float fullW, float fullH,
                  float openness, float alpha, bool reflection)
    {
        if (!tex || openness <= 0.001f || alpha <= 0.001f) return;
        const float curH = std::max(2.0f, fullH * openness);
        const float x0 = centerX - fullW * 0.5f;
        const float x1 = centerX + fullW * 0.5f;
        const float y0 = bottomY - curH;
        const float y1 = bottomY;
        const BYTE a = static_cast<BYTE>(255.0f * Saturate(alpha));
        const D3DCOLOR white = D3DCOLOR_ARGB(a, 255, 255, 255);
        DrawQuad(dev, tex, x0, y0, x1, y1, white, white);

        if (reflection)
        {
            const float rh = fullH * 0.24f * openness;
            const BYTE ra = static_cast<BYTE>(255.0f * Saturate(alpha * g_reflection));
            DrawQuad(dev, tex, x0, bottomY + 2.0f, x1, bottomY + 2.0f + rh,
                     D3DCOLOR_ARGB(ra, 255, 255, 255),
                     D3DCOLOR_ARGB(0, 255, 255, 255),
                     0.0f, 1.0f, 1.0f, 0.76f);
        }
    }

    void Render(IDirect3DDevice8* dev)
    {
        if (!g_visible || !dev) return;
        EnsureTextures(dev);

        D3DVIEWPORT8 vp = {};
        if (FAILED(dev->GetViewport(&vp)) || vp.Width == 0 || vp.Height == 0) return;

        const float W = static_cast<float>(vp.Width);
        const float H = static_cast<float>(vp.Height);
        const float centerX = W * g_anchorX;
        const float bottomY = H * g_anchorY;
        const float fullW = W * g_cardW;
        const float fullH = H * g_cardH;

        const ULONGLONG now = GetTickCount64();
        const float raw = Saturate(static_cast<float>(now - g_transitionStart) / std::max(1.0f, g_animMs));
        const float inP = EaseOutBack(raw);
        const float outP = 1.0f - raw;
        const float breathe = 1.0f + 0.006f * std::sin(static_cast<float>(now) * 0.004f);

        DWORD state = 0;
        const bool haveState = SUCCEEDED(dev->CreateStateBlock(D3DSBT_ALL, &state));
        if (FAILED(dev->BeginScene()))
        {
            if (haveState) dev->DeleteStateBlock(state);
            return;
        }

        SetupState(dev);

        if (raw < 1.0f && g_prevIndex != g_index)
        {
            DrawCard(dev, g_textures[static_cast<size_t>(g_prevIndex)].tex,
                     centerX, bottomY, fullW, fullH,
                     std::max(0.08f, outP), outP, true);
        }

        DrawCard(dev, g_textures[static_cast<size_t>(g_index)].tex,
                 centerX, bottomY, fullW * breathe, fullH * breathe,
                 std::max(0.05f, inP), Saturate(raw * 1.35f), true);

        // Very subtle white sweep over the selected card.
        dev->SetTexture(0, nullptr);
        dev->SetTextureStageState(0, D3DTSS_COLOROP, D3DTOP_SELECTARG1);
        dev->SetTextureStageState(0, D3DTSS_COLORARG1, D3DTA_DIFFUSE);
        dev->SetTextureStageState(0, D3DTSS_ALPHAOP, D3DTOP_SELECTARG1);
        dev->SetTextureStageState(0, D3DTSS_ALPHAARG1, D3DTA_DIFFUSE);
        const float sweep = std::fmod(static_cast<float>(now) * 0.00024f, 1.28f) - 0.14f;
        const float sx0 = centerX - fullW * 0.5f + fullW * sweep;
        const float sx1 = sx0 + fullW * 0.08f;
        const float y0 = bottomY - fullH * 0.96f;
        const D3DCOLOR swTop = D3DCOLOR_ARGB(18, 255, 255, 255);
        const D3DCOLOR swBot = D3DCOLOR_ARGB(4, 255, 255, 255);
        DrawQuad(dev, nullptr, sx0, y0, sx1, bottomY - 4.0f, swTop, swBot);

        dev->EndScene();
        if (haveState)
        {
            dev->ApplyStateBlock(state);
            dev->DeleteStateBlock(state);
        }
    }

    void __cdecl OnPresent(IDirect3DDevice8* self, const RECT*, const RECT*, HWND, LPVOID)
    {
        HandleKeys();
        Render(self);
    }

    bool InstallKitserverHook()
    {
        HMODULE kload = GetModuleHandleA("kload.dll");
        if (!kload)
        {
            Log("kload.dll not loaded");
            return false;
        }
        g_hookFunction = reinterpret_cast<HookFunctionFn>(GetProcAddress(kload, "HookFunction"));
        g_unhookFunction = reinterpret_cast<UnhookFunctionFn>(GetProcAddress(kload, "UnhookFunction"));
        if (!g_hookFunction)
        {
            Log("HookFunction export not found");
            return false;
        }
        g_hookFunction(HK_D3D_PRESENT, reinterpret_cast<DWORD>(&OnPresent));
        g_hooked = true;
        Log("registered with Kitserver hk_D3D_Present");
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
        InstallKitserverHook();
    }
    else if (reason == DLL_PROCESS_DETACH)
    {
        if (g_hooked && g_unhookFunction)
            g_unhookFunction(HK_D3D_PRESENT, reinterpret_cast<DWORD>(&OnPresent));
        ReleaseTextures();
    }
    return TRUE;
}
