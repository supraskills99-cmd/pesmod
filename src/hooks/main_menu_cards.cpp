// SPDX-License-Identifier: GPL-3.0-or-later
//
// Experimental animated main-menu cards for PES 6.
// This first version is intentionally isolated behind its own config section.
// It renders an animated card above the horizontal menu selection using a
// Direct3D9 EndScene hook. F9 toggles the overlay; LEFT/RIGHT keep the card
// index in sync for the initial test build; F10 reloads PNG assets.
//
// Once the native PES 6 main-menu selection variable is identified, the same
// renderer can read that index directly and debug_hotkeys can be disabled.

#include "main_menu_cards.h"
#include "../utils/config.h"
#include "../utils/logger.h"
#include "MinHook/include/MinHook.h"

#include <windows.h>
#include <d3d9.h>
#include <wincodec.h>

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <string>

namespace
{
    using EndSceneFn = HRESULT (WINAPI*)(IDirect3DDevice9*);
    using ResetFn    = HRESULT (WINAPI*)(IDirect3DDevice9*, D3DPRESENT_PARAMETERS*);

    EndSceneFn g_origEndScene = nullptr;
    ResetFn    g_origReset    = nullptr;

    bool g_registered = false;
    bool g_visible = false;
    bool g_debugHotkeys = true;
    int  g_index = 0;

    float g_anchorX = 0.247f;
    float g_anchorY = 0.785f;
    float g_cardW   = 0.145f;
    float g_cardH   = 0.445f;
    float g_gap     = 0.014f;
    float g_animMs  = 240.0f;
    float g_reflection = 0.28f;

    ULONGLONG g_animStart = 0;

    std::array<IDirect3DTexture9*, 11> g_textures = {};
    IDirect3DDevice9* g_assetDevice = nullptr;

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

    std::string GameDir()
    {
        char buf[MAX_PATH] = {};
        GetModuleFileNameA(nullptr, buf, MAX_PATH);
        std::string path(buf);
        const size_t slash = path.find_last_of("\\/");
        if (slash != std::string::npos)
            path.resize(slash);
        return path;
    }

    std::string AssetPath(const char* name)
    {
        return GameDir() + "\\PESMod\\menu_cards\\" + name;
    }

    void ReleaseTextures()
    {
        for (auto*& tex : g_textures)
        {
            if (tex)
            {
                tex->Release();
                tex = nullptr;
            }
        }
        g_assetDevice = nullptr;
    }

    bool LoadPngTexture(IDirect3DDevice9* device, const std::string& path,
                        IDirect3DTexture9** outTex)
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

        hr = CoCreateInstance(CLSID_WICImagingFactory, nullptr,
                              CLSCTX_INPROC_SERVER,
                              IID_PPV_ARGS(&factory));
        if (FAILED(hr)) goto done;

        {
            int wideLen = MultiByteToWideChar(CP_UTF8, 0, path.c_str(), -1, nullptr, 0);
            if (wideLen <= 0) { hr = E_FAIL; goto done; }
            std::wstring wide(static_cast<size_t>(wideLen), L'\0');
            MultiByteToWideChar(CP_UTF8, 0, path.c_str(), -1, wide.data(), wideLen);

            hr = factory->CreateDecoderFromFilename(
                wide.c_str(), nullptr, GENERIC_READ,
                WICDecodeMetadataCacheOnDemand, &decoder);
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

            IDirect3DTexture9* tex = nullptr;
            hr = device->CreateTexture(width, height, 1, 0,
                                       D3DFMT_A8R8G8B8, D3DPOOL_MANAGED,
                                       &tex, nullptr);
            if (FAILED(hr)) goto done;

            D3DLOCKED_RECT locked = {};
            hr = tex->LockRect(0, &locked, nullptr, 0);
            if (FAILED(hr))
            {
                tex->Release();
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
            tex->UnlockRect(0);

            if (FAILED(hr))
            {
                tex->Release();
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

    void EnsureTextures(IDirect3DDevice9* device)
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

        Logger::Log("[MainMenuCards] Loaded %d/%d card textures.",
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

    void DrawQuad(IDirect3DDevice9* device, IDirect3DTexture9* tex,
                  float x0, float y0, float x1, float y1,
                  D3DCOLOR color,
                  float u0 = 0.0f, float v0 = 0.0f,
                  float u1 = 1.0f, float v1 = 1.0f)
    {
        Vertex v[4] = {
            { x0, y0, 0.0f, 1.0f, color, u0, v0 },
            { x1, y0, 0.0f, 1.0f, color, u1, v0 },
            { x0, y1, 0.0f, 1.0f, color, u0, v1 },
            { x1, y1, 0.0f, 1.0f, color, u1, v1 },
        };

        device->SetTexture(0, tex);
        if (tex)
        {
            device->SetTextureStageState(0, D3DTSS_COLOROP, D3DTOP_MODULATE);
            device->SetTextureStageState(0, D3DTSS_COLORARG1, D3DTA_TEXTURE);
            device->SetTextureStageState(0, D3DTSS_COLORARG2, D3DTA_DIFFUSE);
            device->SetTextureStageState(0, D3DTSS_ALPHAOP, D3DTOP_MODULATE);
            device->SetTextureStageState(0, D3DTSS_ALPHAARG1, D3DTA_TEXTURE);
            device->SetTextureStageState(0, D3DTSS_ALPHAARG2, D3DTA_DIFFUSE);
        }
        else
        {
            device->SetTextureStageState(0, D3DTSS_COLOROP, D3DTOP_SELECTARG1);
            device->SetTextureStageState(0, D3DTSS_COLORARG1, D3DTA_DIFFUSE);
            device->SetTextureStageState(0, D3DTSS_ALPHAOP, D3DTOP_SELECTARG1);
            device->SetTextureStageState(0, D3DTSS_ALPHAARG1, D3DTA_DIFFUSE);
        }
        device->DrawPrimitiveUP(D3DPT_TRIANGLESTRIP, 2, v, sizeof(Vertex));
    }

    void SetupOverlayState(IDirect3DDevice9* device)
    {
        device->SetVertexShader(nullptr);
        device->SetPixelShader(nullptr);
        device->SetFVF(kFvf);

        device->SetRenderState(D3DRS_ZENABLE, FALSE);
        device->SetRenderState(D3DRS_ZWRITEENABLE, FALSE);
        device->SetRenderState(D3DRS_ALPHABLENDENABLE, TRUE);
        device->SetRenderState(D3DRS_SRCBLEND, D3DBLEND_SRCALPHA);
        device->SetRenderState(D3DRS_DESTBLEND, D3DBLEND_INVSRCALPHA);
        device->SetRenderState(D3DRS_CULLMODE, D3DCULL_NONE);
        device->SetRenderState(D3DRS_LIGHTING, FALSE);
        device->SetSamplerState(0, D3DSAMP_MINFILTER, D3DTEXF_LINEAR);
        device->SetSamplerState(0, D3DSAMP_MAGFILTER, D3DTEXF_LINEAR);
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
            Logger::Log("[MainMenuCards] Selected card index = %d", g_index);
        }

        if (GetAsyncKeyState(VK_F10) & 1)
        {
            ReleaseTextures();
            Logger::Log("[MainMenuCards] Asset reload requested.");
        }
    }

    void RenderCard(IDirect3DDevice9* device)
    {
        if (!g_visible || !device) return;

        D3DVIEWPORT9 vp = {};
        if (FAILED(device->GetViewport(&vp)) || vp.Width == 0 || vp.Height == 0)
            return;

        EnsureTextures(device);
        IDirect3DTexture9* tex = g_textures[static_cast<size_t>(g_index)];

        IDirect3DStateBlock9* state = nullptr;
        if (FAILED(device->CreateStateBlock(D3DSBT_ALL, &state)) || !state)
            return;
        state->Capture();
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
        const float curH  = std::max(3.0f, fullH * std::max(0.05f, p));

        const float x0 = std::floor(anchorX - fullW * 0.5f) + 0.5f;
        const float x1 = std::floor(anchorX + fullW * 0.5f) + 0.5f;
        const float bottom = std::floor(iconTop - gap) + 0.5f;
        const float y0 = std::floor(bottom - curH) + 0.5f;
        const float y1 = bottom;

        const uint8_t alpha = static_cast<uint8_t>(255.0f * Saturate(t * 1.35f));

        if (tex)
        {
            DrawQuad(device, tex, x0, y0, x1, y1,
                     D3DCOLOR_ARGB(alpha, 255, 255, 255));

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
                const float fade = (1.0f - s0) * g_reflection * Saturate(t);
                const uint8_t ra = static_cast<uint8_t>(255.0f * fade);
                DrawQuad(device, tex, x0, ry0, x1, ry1,
                         D3DCOLOR_ARGB(ra, 255, 255, 255),
                         0.0f, v0, 1.0f, v1);
            }

            const float sweep = std::fmod(static_cast<float>(now) * 0.00022f, 1.35f) - 0.18f;
            const float sw = fullW * 0.12f;
            const float sx0 = x0 + sweep * fullW;
            DrawQuad(device, nullptr,
                     sx0, y0 + curH * 0.03f,
                     sx0 + sw, y1 - curH * 0.03f,
                     D3DCOLOR_ARGB(static_cast<uint8_t>(35 * Saturate(t)),
                                   220, 255, 235));
        }
        else
        {
            DrawQuad(device, nullptr, x0, y0, x1, y1,
                     D3DCOLOR_ARGB(alpha, 26, 17, 38));
            const float border = std::max(2.0f, W / 640.0f);
            const D3DCOLOR green = D3DCOLOR_ARGB(alpha, 92, 255, 147);
            DrawQuad(device, nullptr, x0, y0, x1, y0 + border, green);
            DrawQuad(device, nullptr, x0, y1 - border, x1, y1, green);
            DrawQuad(device, nullptr, x0, y0, x0 + border, y1, green);
            DrawQuad(device, nullptr, x1 - border, y0, x1, y1, green);
        }

        state->Apply();
        state->Release();
    }

    HRESULT WINAPI HookEndScene(IDirect3DDevice9* device)
    {
        HandleInput();
        RenderCard(device);
        return g_origEndScene ? g_origEndScene(device) : D3D_OK;
    }

    HRESULT WINAPI HookReset(IDirect3DDevice9* device, D3DPRESENT_PARAMETERS* pp)
    {
        ReleaseTextures();
        return g_origReset ? g_origReset(device, pp) : D3D_OK;
    }

    LRESULT CALLBACK DummyWndProc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp)
    {
        return DefWindowProcA(hwnd, msg, wp, lp);
    }

    bool ResolveD3D9Vtable(void** outEndScene, void** outReset)
    {
        if (!outEndScene || !outReset) return false;
        *outEndScene = nullptr;
        *outReset = nullptr;

        const char* cls = "PESMod_D3D9_Probe";
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

        IDirect3D9* d3d = Direct3DCreate9(D3D_SDK_VERSION);
        if (!d3d)
        {
            DestroyWindow(hwnd);
            UnregisterClassA(cls, wc.hInstance);
            return false;
        }

        D3DPRESENT_PARAMETERS pp = {};
        pp.Windowed = TRUE;
        pp.SwapEffect = D3DSWAPEFFECT_DISCARD;
        pp.hDeviceWindow = hwnd;
        pp.BackBufferFormat = D3DFMT_UNKNOWN;

        IDirect3DDevice9* device = nullptr;
        HRESULT hr = d3d->CreateDevice(
            D3DADAPTER_DEFAULT, D3DDEVTYPE_HAL, hwnd,
            D3DCREATE_SOFTWARE_VERTEXPROCESSING,
            &pp, &device);

        if (FAILED(hr))
        {
            hr = d3d->CreateDevice(
                D3DADAPTER_DEFAULT, D3DDEVTYPE_REF, hwnd,
                D3DCREATE_SOFTWARE_VERTEXPROCESSING,
                &pp, &device);
        }

        bool ok = false;
        if (SUCCEEDED(hr) && device)
        {
            void** vtbl = *reinterpret_cast<void***>(device);
            *outReset = vtbl[16];
            *outEndScene = vtbl[42];
            ok = (*outReset != nullptr && *outEndScene != nullptr);
            device->Release();
        }

        d3d->Release();
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

    g_visible       = Config::GetBool("main_menu_cards", "start_visible", false);
    g_debugHotkeys  = Config::GetBool("main_menu_cards", "debug_hotkeys", true);
    g_anchorX       = Config::GetFloat("main_menu_cards", "anchor_x", 0.247f);
    g_anchorY       = Config::GetFloat("main_menu_cards", "anchor_y", 0.785f);
    g_cardW         = Config::GetFloat("main_menu_cards", "card_width", 0.145f);
    g_cardH         = Config::GetFloat("main_menu_cards", "card_height", 0.445f);
    g_gap           = Config::GetFloat("main_menu_cards", "gap", 0.014f);
    g_animMs        = Config::GetFloat("main_menu_cards", "animation_ms", 240.0f);
    g_reflection    = Config::GetFloat("main_menu_cards", "reflection_alpha", 0.28f);
    g_index         = std::clamp(Config::GetInt("main_menu_cards", "initial_index", 0), 0, 10);
    g_animStart     = GetTickCount64();

    void* endScene = nullptr;
    void* reset = nullptr;
    if (!ResolveD3D9Vtable(&endScene, &reset))
    {
        Logger::Log("[MainMenuCards] Could not resolve Direct3D9 vtable.");
        return;
    }

    if (MH_CreateHook(endScene,
                      reinterpret_cast<void*>(&HookEndScene),
                      reinterpret_cast<void**>(&g_origEndScene)) != MH_OK)
    {
        Logger::Log("[MainMenuCards] MH_CreateHook(EndScene) failed.");
        return;
    }

    if (MH_CreateHook(reset,
                      reinterpret_cast<void*>(&HookReset),
                      reinterpret_cast<void**>(&g_origReset)) != MH_OK)
    {
        Logger::Log("[MainMenuCards] MH_CreateHook(Reset) failed.");
        MH_RemoveHook(endScene);
        return;
    }

    if (MH_EnableHook(endScene) != MH_OK || MH_EnableHook(reset) != MH_OK)
    {
        Logger::Log("[MainMenuCards] Enabling D3D9 hooks failed.");
        MH_RemoveHook(endScene);
        MH_RemoveHook(reset);
        return;
    }

    g_registered = true;
    Logger::Log("[MainMenuCards] Registered. F9 toggles overlay; LEFT/RIGHT change card; F10 reloads assets.");
}

void MainMenuCards::Shutdown()
{
    ReleaseTextures();
    g_registered = false;
}
