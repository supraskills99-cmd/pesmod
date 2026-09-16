from pathlib import Path
import re

p = Path("kitserver_module/menu_cards.cpp")
s = p.read_text(encoding="utf-8")

# V18: draw our own PES2011-style horizontal icon strip under the selected card.
# IMPORTANT: input/navigation/lifecycle from V15 stays untouched. This patch only
# adds icon textures + rendering, so the working joystick behavior is preserved.

# ---------------------------------------------------------------------------
# Config / globals
# ---------------------------------------------------------------------------
marker = "    float g_frameMs = 75.0f;\n"
if marker not in s:
    raise SystemExit("V16 frame timing marker missing")
if "g_iconStripY" not in s:
    s = s.replace(
        marker,
        marker
        + "    bool g_customIconStrip = true;\n"
        + "    float g_iconStripY = 0.895f;\n"
        + "    float g_iconSize = 0.052f;\n"
        + "    float g_iconGap = 0.064f;\n"
        + "    int g_iconMaskAlpha = 218;\n",
        1,
    )

marker = "    std::array<std::array<TextureSlot, kCardAnimFrames>, 11> g_animTextures = {};\n"
if marker not in s:
    raise SystemExit("V16 animated texture marker missing")
if "g_iconTextures" not in s:
    s = s.replace(marker, marker + "    std::array<TextureSlot, 11> g_iconTextures = {};\n", 1)

# Add icon filenames after the existing card filename table.
if "kIconAssetNames" not in s:
    m = re.search(
        r'(    constexpr std::array<const char\*, 11> kAssetNames = \{.*?\n    \};\n)',
        s,
        flags=re.S,
    )
    if not m:
        raise SystemExit("card filename table not found")
    icon_table = r'''

    constexpr std::array<const char*, 11> kIconAssetNames = {
        "icon_partido.png", "icon_liga_master.png", "icon_liga.png", "icon_copa.png",
        "icon_entrenamiento.png", "icon_editar.png", "icon_opciones.png",
        "icon_partido_internacional.png", "icon_seleccion_azar.png", "icon_red.png", "icon_salir.png"
    };
'''
    s = s[:m.end()] + icon_table + s[m.end():]

# Read icon-strip settings.
marker = "        g_frameMs = ReadFloat(\"frame_ms\", 75.0f);\n"
if marker not in s:
    raise SystemExit("V16 ReadConfig frame marker missing")
if "custom_icon_strip" not in s:
    s = s.replace(
        marker,
        marker
        + "        g_customIconStrip = GetPrivateProfileIntA(\"menu_cards\", \"custom_icon_strip\", 1, IniPath().c_str()) != 0;\n"
        + "        g_iconStripY = ReadFloat(\"icon_y\", 0.895f);\n"
        + "        g_iconSize = ReadFloat(\"icon_size\", 0.052f);\n"
        + "        g_iconGap = ReadFloat(\"icon_gap\", 0.064f);\n"
        + "        g_iconMaskAlpha = std::max(0, std::min(255, GetPrivateProfileIntA(\"menu_cards\", \"icon_mask_alpha\", 218, IniPath().c_str())));\n",
        1,
    )

# Release icon textures with the rest.
release_marker = '''        for (auto& cardFrames : g_animTextures)
        {
            for (auto& slot : cardFrames)
            {
                if (slot.tex) ComRelease(slot.tex);
                slot = {};
            }
        }
        g_textureDevice = nullptr;
'''
if release_marker not in s:
    raise SystemExit("V16 ReleaseTextures block not found")
if "for (auto& slot : g_iconTextures)" not in s:
    s = s.replace(
        release_marker,
        '''        for (auto& cardFrames : g_animTextures)
        {
            for (auto& slot : cardFrames)
            {
                if (slot.tex) ComRelease(slot.tex);
                slot = {};
            }
        }
        for (auto& slot : g_iconTextures)
        {
            if (slot.tex) ComRelease(slot.tex);
            slot = {};
        }
        g_textureDevice = nullptr;
''',
        1,
    )

# Load icon textures after cards/frames.
load_marker = '''        Log("loaded %d/11 base textures + %d animated frames", loaded, loadedFrames);
    }

    void* AnimatedCardTexture'''
if load_marker not in s:
    raise SystemExit("V16 EnsureTextures tail not found")
if "loadedIcons" not in s:
    s = s.replace(
        load_marker,
        '''        int loadedIcons = 0;
        for (size_t i = 0; i < kIconAssetNames.size(); ++i)
        {
            if (LoadPng(device, AssetPath(kIconAssetNames[i]), g_iconTextures[i])) ++loadedIcons;
            else Log("icon asset failed: %s", AssetPath(kIconAssetNames[i]).c_str());
        }
        Log("loaded %d/11 base textures + %d animated frames + %d/11 menu icons",
            loaded, loadedFrames, loadedIcons);
    }

    void* AnimatedCardTexture''',
        1,
    )

# ---------------------------------------------------------------------------
# Sliding strip renderer
# ---------------------------------------------------------------------------
render_marker = "    void Render(void* dev)\n"
if render_marker not in s:
    raise SystemExit("Render marker missing")
if "void DrawIconStrip" not in s:
    block = r'''    void DrawIconStrip(void* dev, float W, float H, float centerX,
                       float transitionRaw, bool switching, ULONGLONG now)
    {
        if (!g_customIconStrip) return;

        const float stripY = H * g_iconStripY;
        const float baseSize = W * g_iconSize;
        const float gap = std::max(8.0f, W * g_iconGap);

        // First cover the original PES6 horizontal selector so only our strip is
        // visible. This makes the whole lower navigation read as one PES2011 unit.
        DevSetTexture(dev, 0, nullptr);
        DevSetTextureStageState(dev,0,D3DTSS_COLOROP_,D3DTOP_SELECTARG1_);
        DevSetTextureStageState(dev,0,D3DTSS_COLORARG1_,D3DTA_DIFFUSE_);
        DevSetTextureStageState(dev,0,D3DTSS_ALPHAOP_,D3DTOP_SELECTARG1_);
        DevSetTextureStageState(dev,0,D3DTSS_ALPHAARG1_,D3DTA_DIFFUSE_);

        const BYTE ma = static_cast<BYTE>(g_iconMaskAlpha);
        DrawQuad(dev, nullptr,
                 0.0f, stripY - baseSize * 0.80f,
                 W, stripY + baseSize * 0.76f,
                 Argb(static_cast<BYTE>(ma * 0.72f), 8,5,16),
                 Argb(ma, 15,8,27));

        // Fixed selected pedestal directly under the card.
        const float pulse = 0.5f + 0.5f * std::sin(static_cast<float>(now) * 0.006f);
        const BYTE glowA = static_cast<BYTE>(38.0f + pulse * 30.0f);
        DrawQuad(dev, nullptr,
                 centerX - baseSize * 0.58f, stripY + baseSize * 0.47f,
                 centerX + baseSize * 0.58f, stripY + baseSize * 0.55f,
                 Argb(glowA,104,255,154), Argb(0,104,255,154));

        // Back to normal textured state for the icons.
        SetupState(dev);

        int direction = 0;
        if (switching)
            direction = (g_index > g_prevIndex) ? 1 : -1;

        const float slide = switching ? EaseOutCubic(transitionRaw) : 1.0f;
        const float transitionOffset = switching
            ? static_cast<float>(direction) * gap * (1.0f - slide)
            : 0.0f;

        for (int i = 0; i < 11; ++i)
        {
            void* tex = g_iconTextures[static_cast<size_t>(i)].tex;
            if (!tex) continue;

            const float logicalOffset = static_cast<float>(i - g_index);
            const float x = centerX + logicalOffset * gap + transitionOffset;
            if (x < -baseSize || x > W + baseSize) continue;

            const float centerDistance = std::fabs((x - centerX) / gap);
            const float selected = 1.0f - Saturate(centerDistance);
            const float size = baseSize * (0.78f + 0.30f * selected);
            const float y = stripY - baseSize * 0.10f * selected;
            const BYTE a = static_cast<BYTE>(120.0f + 135.0f * selected);

            DrawQuad(dev, tex,
                     x - size * 0.5f, y - size * 0.5f,
                     x + size * 0.5f, y + size * 0.5f,
                     Argb(a,255,255,255), Argb(a,255,255,255));
        }
    }

'''
    s = s.replace(render_marker, block + render_marker, 1)

# Call the strip renderer before the card itself, using the same transition clock.
call_marker = '''        SetupState(dev);

        if (switching && raw < 1.0f)
'''
if call_marker not in s:
    raise SystemExit("V13 Render setup marker missing")
if "DrawIconStrip(dev" not in s:
    s = s.replace(
        call_marker,
        '''        SetupState(dev);

        DrawIconStrip(dev, W, H, centerX, raw, switching, now);

        if (switching && raw < 1.0f)
''',
        1,
    )

p.write_text(s, encoding="utf-8")
print("Patched menu_cards.cpp for V18: PES2011 sliding custom icon strip (V15 input untouched)")
