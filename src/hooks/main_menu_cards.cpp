// SPDX-License-Identifier: GPL-3.0-or-later
//
// Animated main-menu card prototype for PES 6.
// PES 6 renders through Direct3D 8, so this module hooks IDirect3DDevice8::EndScene.
// The horizontal PES 6 menu remains underneath; this draws only the animated card.

#include "main_menu_cards.h"
#include "../utils/config.h"
#include "../utils/logger.h"
#include "MinHook/include/MinHook.h"

#include <windows.h>
#include <wincodec.h>

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <string>

namespace
{
    // -------------------------------------------------------------------------
    // Minimal Direct3D 8 declarations. Modern Windows SDKs no longer ship the
    // old d3d8 headers/libraries consistently, so we call COM vtables directly.
    // -------------------------------------------------------------------------
    constexpr UINT  D3D8_SDK_VERSION = 220;
    constexpr DWORD D3DADAPTER_DEFAULT_8 = 0;
    constexpr DWORD D3DDEVTYPE_HAL_8 = 1;
    constexpr DWORD D3DDEVTYPE_REF_8 = 2;
    constexpr DWORD D3DCREATE_SOFTWARE_VERTEXPROCESSING_8 = 0x20;
    constexpr DWORD D3DFMT_UNKNOWN_8 = 0;
    constexpr DWORD D3DFMT_A8R8G8B8_8 = 21;
    constexpr DWORD D3DPOOL_MANAGED_8 = 1;
    constexpr DWORD D3DSWAPEFFECT_DISCARD_8 = 1;

    constexpr DWORD D3DFVF_XYZRHW_8 = 0x004;
    constexpr DWORD D3DFVF_DIFFUSE_8 = 0x040;
    constexpr DWORD D3DFVF_TEX1_8 = 0x100;
    constexpr DWORD kFvf = D3DFVF_XYZRHW_8 | D3DFVF_DIFFUSE_8 | D3DFVF_TEX1_8;

    constexpr DWORD D3DPT_TRIANGLESTRIP_8 = 5;

    constexpr DWORD D3DRS_ZENABLE_8 = 7;
    constexpr DWORD D3DRS_ZWRITEENABLE_8 = 14;
    constexpr DWORD D3DRS_ALPHABLENDENABLE_8 = 27;
    constexpr DWORD D3DRS_SRCBLEND_8 = 19;
    constexpr DWORD D3DRS_DESTBLEND_8 = 20;
    constexpr DWORD D3DRS_CULLMODE_8 = 22;
    constexpr DWORD D3DRS_LIGHTING_8 = 137;

    constexpr DWORD D3DBLEND_SRCALPHA_8 = 5;
    constexpr DWORD D3DBLEND_INVSRCALPHA_8 = 6;
    constexpr DWORD D3DCULL_NONE_8 = 1;

    constexpr DWORD D3DTSS_COLOROP_8 = 1;
    constexpr DWORD D3DTSS_COLORARG1_8 = 2;
    constexpr DWORD D3DTSS_COLORARG2_8 = 3;
    constexpr DWORD D3DTSS_ALPHAOP_8 = 4;
    constexpr DWORD D3DTSS_ALPHAARG1_8 = 5;
    constexpr DWORD D3DTSS_ALPHAARG2_8 = 6;
    constexpr DWORD D3DTSS_MAGFILTER_8 = 16;
    constexpr DWORD D3DTSS_MINFILTER_8 = 17;

    constexpr DWORD D3DTOP_SELECTARG1_8 = 2;
    constexpr DWORD D3DTOP_MODULATE_8 = 4;
    constexpr DWORD D3DTA_DIFFUSE_8 = 0;
    constexpr DWORD D3DTA_TEXTURE_8 = 2;
    constexpr DWORD D3DTEXF_LINEAR_8 = 2;
    constexpr DWORD D3DSBT_ALL_8 = 1;

    struct D3DPRESENT_PARAMETERS8_MIN
    {
        UINT BackBufferWidth;
        UINT BackBufferHeight;
        DWORD BackBufferFormat;
        UINT BackBufferCount;
        DWORD MultiSampleType;
        DWORD SwapEffect;
        HWND hDeviceWindow;
        BOOL Windowed;
        BOOL EnableAutoDepthStencil;
        DWORD AutoDepthStencilFormat;
        DWORD Flags;
        UINT FullScreen_RefreshRateInHz;
        UINT FullScreen_PresentationInterval;
    };

    struct D3DVIEWPORT8_MIN
    {
        DWORD X, Y, Width, Height;
        float MinZ, MaxZ;
    };

    struct D3DLOCKED_RECT8_MIN
    {
        INT Pitch;
        void* pBits;
    };

    template <typename T>
    T VCall(void* obj, size_t index)
    {
        return reinterpret_cast<T>((*reinterpret_cast<void***>(obj))[index]);
    }

    using EndSceneFn = HRESULT (WINAPI*)(void*);
    using ResetFn = HRESULT (WINAPI*)(void*, D3DPRESENT_PARAMETERS8_MIN*);

    EndSceneFn g_origEndScene = nullptr;
    ResetFn g_origReset = nullptr;

    bool g_registered = false;
    bool g_visible = true;
    bool g_debugHotkeys = true;
    int g_index = 0;

    float g_anchorX = 0.247f;
    float g_anchorY = 0.785f;
    float g_cardW = 0.145f;
    float g_cardH = 0.445f;
    float g_gap = 0.014f;
    float g_animMs = 240.0f;
    float g_reflection = 0.28f;

    ULONGLONG g_animStart = 0;

    std::array<void*, 11> g_textures = {};
    void* g_assetDevice = nullptr;

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
        DWORD color;
        float u, v;
    };

    DWORD Argb(uint8_t a, uint8_t r, uint8_t g, uint8_t b)
    {
        return (static_cast<DWORD>(a) << 24)
             | (static_cast<DWORD>(r) << 16)
             | (static_cast<DWORD>(g) << 8)
             | static_cast<DWORD>(b);
    }

    std::string GameDir()
    {
        char buf[MAX_PATH] = {};
        GetModuleFileNameA(nullptr, buf, MAX_PATH);
        std::string path(buf);
        const size_t slash = path.find_last_of("\\/");
        if (slash != std::string::npos) path.resize(slash);
        return path;
    }

    std::string AssetPath(const char* name)
    {
        return GameDir() + "\\PESMod\\menu_cards\\" + name;
    }

    ULONG ReleaseCom(void* obj)
    {
        if (!obj) return 0;
        using Fn = ULONG (WINAPI*)(void*);
        return VCall<Fn>(obj, 2)(obj);
    }

    void ReleaseTextures()
    {
        for (auto*& tex : g_textures)
        {
            if (tex)
            {
                ReleaseCom(tex);
                tex = nullptr;
            }
        }
        g_assetDevice = nullptr;
    }

    bool DeviceCreateTexture(void* device, UINT width, UINT height, void** outTex)
    {
        using Fn = HRESULT (WINAPI*)(void*, UINT, UINT, UINT, DWORD, DWORD, DWORD, void**);
        return SUCCEEDED(VCall<Fn>(device, 20)(device, width, height, 1, 0,
                                               D3DFMT_A8R8G8B8_8,
                                               D3DPOOL_MANAGED_8, outTex));
    }

    bool TextureLock(void* tex, D3DLOCKED_RECT8_MIN* locked)
    {
        using Fn = HRESULT (WINAPI*)(void*, UINT, D3DLOCKED_RECT8_MIN*, const RECT*, DWORD);
        return SUCCEEDED(VCall<Fn>(tex, 16)(tex, 0, locked, nullptr, 0));
    }

    void TextureUnlock(void* tex)
    {
        using Fn = HRESULT (WINAPI*)(void*, UINT);
        VCall<Fn>(tex, 17)(tex, 0);
    }

    bool LoadPngTexture(void* device, const std::string& path, void** outTex)
    {
        if (!device || !outTex) return false;
        *outTex = nullptr;

        HRESULT co = CoInitializeEx(nullptr, COINIT_MULTITHREADED);
        const bool uninit = SUCCEEDED(co);

        IWICImagingFactory* factory = nullptr;
        IWICBitmapDecoder* decoder = nullptr;
        IWICBitmapFrameDecode* frame = nullptr;
        IWICFormatConverter* converter = nullptr;
        HRESULT hr = E_FAIL;

        hr = CoCreateInstance(CLSID_WICImagingFactory, nullptr, CLSCTX_INPROC_SERVER,
                              IID_PPV_ARGS(&factory));
        if (FAILED(hr)) goto done;

        {
            int wideLen = MultiByteToWideChar(CP_UTF8, 0, path.c_str(), -1, nullptr, 0);
            if (wideLen <= 0) { hr = E_FAIL; goto done; }
            std::wstring wide(static_cast<size_t>(wideLen), L'\0');
            MultiByteToWideChar(CP_UTF8, 0, path.c_str(), -1, wide.data(), wideLen);
            hr = factory->CreateDecoderFromFilename(wide.c_str(), nullptr, GENERIC_READ,
                                                     WICDecodeMetadataCacheOnDemand,
                                                     &decoder);
            if (FAILED(hr)) goto done;
        }

        hr = decoder->GetFrame(0, &frame);
        if (FAILED(hr)) goto done;
        hr = factory->CreateFormatConverter(&converter);
        if (FAILED(hr)) goto done;
        hr = converter->Initialize(frame, GUID_WICPixelFormat32bppBGRA,
                                   WICBitmapDitherTypeNone, nullptr, 0.0,
                                   WICBitmapPaletteTypeCustom);
        if (FAILED(hr)) goto done;

        {
            UINT width = 0, height = 0;
            hr = converter->GetSize(&width, &height);
            if (FAILED(hr) || width == 0 || height == 0) goto done;

            void* tex = nullptr;
            if (!DeviceCreateTexture(device, width, height, &tex) || !tex)
            {
                hr = E_FAIL;
                goto done;
            }

            D3DLOCKED_RECT8_MIN locked = {};
            if (!TextureLock(tex, &locked))
            {
                ReleaseCom(tex);
                hr = E_FAIL;
                goto done;
            }

            const UINT stride = width * 4;
            auto* pixels = new BYTE[static_cast<size_t>(stride) * height];
            hr = converter->CopyPixels(nullptr, stride, stride * height, pixels);
            if (SUCCEEDED(hr))
            {
                for (UINT y = 0; y < height; ++y)
                {
                    memcpy(static_cast<BYTE*>(locked.pBits) + y * locked.Pitch,
                           pixels + y * stride, stride);
                }
            }
            delete[] pixels;
            TextureUnlock(tex);

            if (FAILED(hr))
            {
                ReleaseCom(tex);
                goto done;
            }
            *outTex = tex;
        }

    done:
        if (converter) converter->Release();
        if (frame) frame->Release();
        if (decoder) decoder->Release();
        if (factory) factory->Release();
        if (uninit) CoUninitialize();
        return SUCCEEDED(hr) && *outTex != nullptr;
    }

    void EnsureTextures(void* device)
    {
        if (!device) return;
        if (g_assetDevice == device && g_textures[0] != nullptr) return;

        ReleaseTextures();
        g_assetDevice = device;
        int loaded = 0;
        for (size_t i = 0; i < kAssetNames.size(); ++i)
        {
            if (LoadPngTexture(device, AssetPath(kAssetNames[i]), &g_textures[i]))
                ++loaded;
            else
                Logger::Log("[MainMenuCards] Asset missing/unreadable: %s",
                            AssetPath(kAssetNames[i]).c_str());
        }
        Logger::Log("[MainMenuCards] Loaded %d/%d Direct3D8 card textures.",
                    loaded, static_cast<int>(kAssetNames.size()));
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

    bool GetViewport(void* device, D3DVIEWPORT8_MIN* vp)
    {
        using Fn = HRESULT (WINAPI*)(void*, D3DVIEWPORT8_MIN*);
        return SUCCEEDED(VCall<Fn>(device, 41)(device, vp));
    }

    void SetRenderState(void* device, DWORD state, DWORD value)
    {
        using Fn = HRESULT (WINAPI*)(void*, DWORD, DWORD);
        VCall<Fn>(device, 50)(device, state, value);
    }

    void SetTexture(void* device, DWORD stage, void* tex)
    {
        using Fn = HRESULT (WINAPI*)(void*, DWORD, void*);
        VCall<Fn>(device, 61)(device, stage, tex);
    }

    void SetTextureStageState(void* device, DWORD stage, DWORD type, DWORD value)
    {
        using Fn = HRESULT (WINAPI*)(void*, DWORD, DWORD, DWORD);
        VCall<Fn>(device, 63)(device, stage, type, value);
    }

    void SetVertexShader(void* device, DWORD handle)
    {
        using Fn = HRESULT (WINAPI*)(void*, DWORD);
        VCall<Fn>(device, 76)(device, handle);
    }

    void SetPixelShader(void* device, DWORD handle)
    {
        using Fn = HRESULT (WINAPI*)(void*, DWORD);
        VCall<Fn>(device, 88)(device, handle);
    }

    void DrawPrimitiveUP(void* device, DWORD primitiveType, UINT primitiveCount,
                         const void* data, UINT stride)
    {
        using Fn = HRESULT (WINAPI*)(void*, DWORD, UINT, const void*, UINT);
        VCall<Fn>(device, 72)(device, primitiveType, primitiveCount, data, stride);
    }

    bool CreateStateBlock(void* device, DWORD* token)
    {
        using Fn = HRESULT (WINAPI*)(void*, DWORD, DWORD*);
        return SUCCEEDED(VCall<Fn>(device, 57)(device, D3DSBT_ALL_8, token));
    }

    void ApplyStateBlock(void* device, DWORD token)
    {
        using Fn = HRESULT (WINAPI*)(void*, DWORD);
        VCall<Fn>(device, 54)(device, token);
    }

    void DeleteStateBlock(void* device, DWORD token)
    {
        using Fn = HRESULT (WINAPI*)(void*, DWORD);
        VCall<Fn>(device, 56)(device, token);
    }

    void SetupOverlayState(void* device)
    {
        SetVertexShader(device, kFvf);
        SetPixelShader(device, 0);
        SetRenderState(device, D3DRS_ZENABLE_8, FALSE);
        SetRenderState(device, D3DRS_ZWRITEENABLE_8, FALSE);
        SetRenderState(device, D3DRS_ALPHABLENDENABLE_8, TRUE);
        SetRenderState(device, D3DRS_SRCBLEND_8, D3DBLEND_SRCALPHA_8);
        SetRenderState(device, D3DRS_DESTBLEND_8, D3DBLEND_INVSRCALPHA_8);
        SetRenderState(device, D3DRS_CULLMODE_8, D3DCULL_NONE_8);
        SetRenderState(device, D3DRS_LIGHTING_8, FALSE);
        SetTextureStageState(device, 0, D3DTSS_MINFILTER_8, D3DTEXF_LINEAR_8);
        SetTextureStageState(device, 0, D3DTSS_MAGFILTER_8, D3DTEXF_LINEAR_8);
    }

    void DrawQuad(void* device, void* tex,
                  float x0, float y0, float x1, float y1,
                  DWORD color,
                  float u0 = 0.0f, float v0 = 0.0f,
                  float u1 = 1.0f, float v1 = 1.0f)
    {
        Vertex v[4] = {
            {x0, y0, 0.0f, 1.0f, color, u0, v0},
            {x1, y0, 0.0f, 1.0f, color, u1, v0},
            {x0, y1, 0.0f, 1.0f, color, u0, v1},
            {x1, y1, 0.0f, 1.0f, color, u1, v1},
        };

        SetTexture(device, 0, tex);
        if (tex)
        {
            SetTextureStageState(device, 0, D3DTSS_COLOROP_8, D3DTOP_MODULATE_8);
            SetTextureStageState(device, 0, D3DTSS_COLORARG1_8, D3DTA_TEXTURE_8);
            SetTextureStageState(device, 0, D3DTSS_COLORARG2_8, D3DTA_DIFFUSE_8);
            SetTextureStageState(device, 0, D3DTSS_ALPHAOP_8, D3DTOP_MODULATE_8);
            SetTextureStageState(device, 0, D3DTSS_ALPHAARG1_8, D3DTA_TEXTURE_8);
            SetTextureStageState(device, 0, D3DTSS_ALPHAARG2_8, D3DTA_DIFFUSE_8);
        }
        else
        {
            SetTextureStageState(device, 0, D3DTSS_COLOROP_8, D3DTOP_SELECTARG1_8);
            SetTextureStageState(device, 0, D3DTSS_COLORARG1_8, D3DTA_DIFFUSE_8);
            SetTextureStageState(device, 0, D3DTSS_ALPHAOP_8, D3DTOP_SELECTARG1_8);
            SetTextureStageState(device, 0, D3DTSS_ALPHAARG1_8, D3DTA_DIFFUSE_8);
        }
        DrawPrimitiveUP(device, D3DPT_TRIANGLESTRIP_8, 2, v, sizeof(Vertex));
    }

    void HandleInput()
    {
        if (GetAsyncKeyState(VK_F9) & 1)
        {
            g_visible = !g_visible;
            g_animStart = GetTickCount64();
            Logger::Log("[MainMenuCards] Overlay %s.", g_visible ? "ON" : "OFF");
        }
        if (!g_visible || !g_debugHotkeys) return;

        int newIndex = g_index;
        if (GetAsyncKeyState(VK_RIGHT) & 1)
            newIndex = (newIndex + 1) % static_cast<int>(kAssetNames.size());
        if (GetAsyncKeyState(VK_LEFT) & 1)
            newIndex = (newIndex + static_cast<int>(kAssetNames.size()) - 1)
                     % static_cast<int>(kAssetNames.size());
        if (newIndex != g_index)
        {
            g_index = newIndex;
            g_animStart = GetTickCount64();
        }
        if (GetAsyncKeyState(VK_F10) & 1)
            ReleaseTextures();
    }

    void RenderCard(void* device)
    {
        if (!g_visible || !device) return;

        D3DVIEWPORT8_MIN vp = {};
        if (!GetViewport(device, &vp) || vp.Width == 0 || vp.Height == 0)
            return;

        EnsureTextures(device);
        void* tex = g_textures[static_cast<size_t>(g_index)];

        DWORD stateToken = 0;
        const bool haveState = CreateStateBlock(device, &stateToken);
        SetupOverlayState(device);

        const float W = static_cast<float>(vp.Width);
        const float H = static_cast<float>(vp.Height);
        const float anchorX = W * g_anchorX;
        const float iconTop = H * g_anchorY;
        const float gap = H * g_gap;

        const ULONGLONG now = GetTickCount64();
        const float elapsed = static_cast<float>(now - g_animStart);
        const float t = Saturate(elapsed / std::max(1.0f, g_animMs));
        const float p = EaseOutBack(t);
        const float breathe = 1.0f + 0.0075f * std::sin(static_cast<float>(now) * 0.0042f);

        const float fullW = W * g_cardW * breathe;
        const float fullH = H * g_cardH * breathe;
        const float curH = std::max(3.0f, fullH * std::max(0.05f, p));
        const float x0 = std::floor(anchorX - fullW * 0.5f) + 0.5f;
        const float x1 = std::floor(anchorX + fullW * 0.5f) + 0.5f;
        const float bottom = std::floor(iconTop - gap) + 0.5f;
        const float y0 = std::floor(bottom - curH) + 0.5f;
        const float y1 = bottom;
        const uint8_t alpha = static_cast<uint8_t>(255.0f * Saturate(t * 1.35f));

        if (tex)
        {
            DrawQuad(device, tex, x0, y0, x1, y1, Argb(alpha, 255, 255, 255));

            constexpr int strips = 12;
            const float reflH = fullH * 0.27f * Saturate(t);
            for (int i = 0; i < strips; ++i)
            {
                const float s0 = static_cast<float>(i) / strips;
                const float s1 = static_cast<float>(i + 1) / strips;
                const float ry0 = bottom + 3.0f + reflH * s0;
                const float ry1 = bottom + 3.0f + reflH * s1;
                const float v0 = 1.0f - 0.27f * s0;
                const float v1 = 1.0f - 0.27f * s1;
                const uint8_t ra = static_cast<uint8_t>(255.0f * (1.0f - s0)
                                  * g_reflection * Saturate(t));
                DrawQuad(device, tex, x0, ry0, x1, ry1,
                         Argb(ra, 255, 255, 255), 0.0f, v0, 1.0f, v1);
            }
        }
        else
        {
            DrawQuad(device, nullptr, x0, y0, x1, y1, Argb(alpha, 26, 17, 38));
        }

        if (haveState)
        {
            ApplyStateBlock(device, stateToken);
            DeleteStateBlock(device, stateToken);
        }
    }

    HRESULT WINAPI HookEndScene(void* device)
    {
        HandleInput();
        RenderCard(device);
        return g_origEndScene ? g_origEndScene(device) : S_OK;
    }

    HRESULT WINAPI HookReset(void* device, D3DPRESENT_PARAMETERS8_MIN* pp)
    {
        ReleaseTextures();
        return g_origReset ? g_origReset(device, pp) : S_OK;
    }

    LRESULT CALLBACK DummyWndProc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp)
    {
        return DefWindowProcA(hwnd, msg, wp, lp);
    }

    bool ResolveD3D8Vtable(void** outEndScene, void** outReset)
    {
        if (!outEndScene || !outReset) return false;
        *outEndScene = nullptr;
        *outReset = nullptr;

        HMODULE d3d8 = GetModuleHandleA("d3d8.dll");
        if (!d3d8) d3d8 = LoadLibraryA("d3d8.dll");
        if (!d3d8)
        {
            Logger::Log("[MainMenuCards] d3d8.dll not available.");
            return false;
        }

        using Direct3DCreate8Fn = void* (WINAPI*)(UINT);
        auto create8 = reinterpret_cast<Direct3DCreate8Fn>(
            GetProcAddress(d3d8, "Direct3DCreate8"));
        if (!create8) return false;

        const char* cls = "PESMod_D3D8_Probe";
        WNDCLASSEXA wc = {};
        wc.cbSize = sizeof(wc);
        wc.lpfnWndProc = DummyWndProc;
        wc.hInstance = GetModuleHandleA(nullptr);
        wc.lpszClassName = cls;
        RegisterClassExA(&wc);

        HWND hwnd = CreateWindowExA(0, cls, cls, WS_OVERLAPPEDWINDOW,
                                    0, 0, 64, 64, nullptr, nullptr,
                                    wc.hInstance, nullptr);
        if (!hwnd)
        {
            UnregisterClassA(cls, wc.hInstance);
            return false;
        }

        void* d3d = create8(D3D8_SDK_VERSION);
        if (!d3d)
        {
            DestroyWindow(hwnd);
            UnregisterClassA(cls, wc.hInstance);
            return false;
        }

        D3DPRESENT_PARAMETERS8_MIN pp = {};
        pp.Windowed = TRUE;
        pp.SwapEffect = D3DSWAPEFFECT_DISCARD_8;
        pp.hDeviceWindow = hwnd;
        pp.BackBufferFormat = D3DFMT_UNKNOWN_8;

        using CreateDeviceFn = HRESULT (WINAPI*)(void*, UINT, DWORD, HWND, DWORD,
                                                  D3DPRESENT_PARAMETERS8_MIN*, void**);
        auto createDevice = VCall<CreateDeviceFn>(d3d, 15);
        void* device = nullptr;
        HRESULT hr = createDevice(d3d, D3DADAPTER_DEFAULT_8, D3DDEVTYPE_HAL_8,
                                  hwnd, D3DCREATE_SOFTWARE_VERTEXPROCESSING_8,
                                  &pp, &device);
        if (FAILED(hr))
        {
            hr = createDevice(d3d, D3DADAPTER_DEFAULT_8, D3DDEVTYPE_REF_8,
                              hwnd, D3DCREATE_SOFTWARE_VERTEXPROCESSING_8,
                              &pp, &device);
        }

        bool ok = false;
        if (SUCCEEDED(hr) && device)
        {
            void** vtbl = *reinterpret_cast<void***>(device);
            *outReset = vtbl[14];
            *outEndScene = vtbl[35];
            ok = (*outReset != nullptr && *outEndScene != nullptr);
            ReleaseCom(device);
        }

        ReleaseCom(d3d);
        DestroyWindow(hwnd);
        UnregisterClassA(cls, wc.hInstance);
        return ok;
    }
}

void MainMenuCards::Register()
{
    if (g_registered) return;
    if (!Config::GetBool("main_menu_cards", "enabled", true))
    {
        Logger::Log("[MainMenuCards] Disabled by config.");
        return;
    }

    g_visible = Config::GetBool("main_menu_cards", "start_visible", true);
    g_debugHotkeys = Config::GetBool("main_menu_cards", "debug_hotkeys", true);
    g_anchorX = Config::GetFloat("main_menu_cards", "anchor_x", 0.247f);
    g_anchorY = Config::GetFloat("main_menu_cards", "anchor_y", 0.785f);
    g_cardW = Config::GetFloat("main_menu_cards", "card_width", 0.145f);
    g_cardH = Config::GetFloat("main_menu_cards", "card_height", 0.445f);
    g_gap = Config::GetFloat("main_menu_cards", "gap", 0.014f);
    g_animMs = Config::GetFloat("main_menu_cards", "animation_ms", 240.0f);
    g_reflection = Config::GetFloat("main_menu_cards", "reflection_alpha", 0.28f);
    g_index = std::clamp(Config::GetInt("main_menu_cards", "initial_index", 0), 0, 10);
    g_animStart = GetTickCount64();

    void* endScene = nullptr;
    void* reset = nullptr;
    if (!ResolveD3D8Vtable(&endScene, &reset))
    {
        Logger::Log("[MainMenuCards] Could not resolve Direct3D8 vtable.");
        return;
    }

    if (MH_CreateHook(endScene, reinterpret_cast<void*>(&HookEndScene),
                      reinterpret_cast<void**>(&g_origEndScene)) != MH_OK)
    {
        Logger::Log("[MainMenuCards] MH_CreateHook(D3D8 EndScene) failed.");
        return;
    }

    if (MH_CreateHook(reset, reinterpret_cast<void*>(&HookReset),
                      reinterpret_cast<void**>(&g_origReset)) != MH_OK)
    {
        Logger::Log("[MainMenuCards] MH_CreateHook(D3D8 Reset) failed.");
        MH_RemoveHook(endScene);
        return;
    }

    if (MH_EnableHook(endScene) != MH_OK || MH_EnableHook(reset) != MH_OK)
    {
        Logger::Log("[MainMenuCards] Enabling Direct3D8 hooks failed.");
        MH_RemoveHook(endScene);
        MH_RemoveHook(reset);
        return;
    }

    g_registered = true;
    Logger::Log("[MainMenuCards] Direct3D8 overlay registered. F9 toggle; LEFT/RIGHT card; F10 reload.");
}

void MainMenuCards::Shutdown()
{
    ReleaseTextures();
    g_registered = false;
}
