from pathlib import Path

p = Path("kitserver_module/menu_cards.cpp")
s = p.read_text(encoding="utf-8")

# V16: animated-card frame engine.
# IMPORTANT: do not touch V15 input/navigation/lifecycle. This patch only changes
# texture loading + rendering so each selected card can behave like a small
# animated PES2011 panel instead of a single static PNG.

# Config/global frame timing.
needle = "    float g_reflection = 0.26f;\n"
if needle not in s:
    raise SystemExit("reflection global marker missing")
if "g_frameMs" not in s:
    s = s.replace(needle, needle + "    float g_frameMs = 75.0f;\n", 1)

# Animated texture storage next to the existing static textures.
needle = "    std::array<TextureSlot, 11> g_textures = {};\n"
if needle not in s:
    raise SystemExit("texture array marker missing")
if "g_animTextures" not in s:
    s = s.replace(
        needle,
        "    constexpr int kCardAnimFrames = 10;\n"
        + needle
        + "    std::array<std::array<TextureSlot, kCardAnimFrames>, 11> g_animTextures = {};\n",
        1,
    )

# Read frame duration from ini.
needle = "        g_reflection = ReadFloat(\"reflection_alpha\", 0.26f);\n"
if needle not in s:
    raise SystemExit("ReadConfig reflection marker missing")
if "frame_ms" not in s:
    s = s.replace(
        needle,
        needle + "        g_frameMs = ReadFloat(\"frame_ms\", 75.0f);\n",
        1,
    )

# Release animated frames together with the static textures.
old = '''    void ReleaseTextures()
    {
        for (auto& slot : g_textures)
        {
            if (slot.tex) ComRelease(slot.tex);
            slot = {};
        }
        g_textureDevice = nullptr;
    }
'''
new = '''    void ReleaseTextures()
    {
        for (auto& slot : g_textures)
        {
            if (slot.tex) ComRelease(slot.tex);
            slot = {};
        }
        for (auto& cardFrames : g_animTextures)
        {
            for (auto& slot : cardFrames)
            {
                if (slot.tex) ComRelease(slot.tex);
                slot = {};
            }
        }
        g_textureDevice = nullptr;
    }
'''
if old not in s:
    raise SystemExit("ReleaseTextures block missing")
s = s.replace(old, new, 1)

# Load filename_f0.png ... filename_f9.png for every card. Static PNG remains
# the fallback, so custom packs can omit frames and still work.
old = '''        int loaded = 0;
        for (size_t i = 0; i < kAssetNames.size(); ++i)
        {
            if (LoadPng(device, AssetPath(kAssetNames[i]), g_textures[i])) ++loaded;
            else Log("asset failed: %s", AssetPath(kAssetNames[i]).c_str());
        }
        Log("loaded %d/11 textures", loaded);
    }
'''
new = '''        int loaded = 0;
        int loadedFrames = 0;
        for (size_t i = 0; i < kAssetNames.size(); ++i)
        {
            if (LoadPng(device, AssetPath(kAssetNames[i]), g_textures[i])) ++loaded;
            else Log("asset failed: %s", AssetPath(kAssetNames[i]).c_str());

            std::string baseName = kAssetNames[i];
            const size_t dot = baseName.rfind(".png");
            if (dot != std::string::npos) baseName.resize(dot);
            for (int f = 0; f < kCardAnimFrames; ++f)
            {
                const std::string frameName = baseName + "_f" + std::to_string(f) + ".png";
                if (LoadPng(device, AssetPath(frameName.c_str()), g_animTextures[i][static_cast<size_t>(f)]))
                    ++loadedFrames;
            }
        }
        Log("loaded %d/11 base textures + %d animated frames", loaded, loadedFrames);
    }

    void* AnimatedCardTexture(size_t index, ULONGLONG now)
    {
        if (index >= g_animTextures.size()) return nullptr;
        const ULONGLONG frameDuration = static_cast<ULONGLONG>(std::max(30.0f, g_frameMs));
        const size_t frame = static_cast<size_t>((now / frameDuration) % kCardAnimFrames);
        void* tex = g_animTextures[index][frame].tex;
        return tex ? tex : g_textures[index].tex;
    }
'''
if old not in s:
    raise SystemExit("EnsureTextures tail missing")
s = s.replace(old, new, 1)

# Render the current card using its live animation frame. The outgoing card stays
# on its base image, which keeps the close/reopen transition clean.
old = '''        DrawCard(dev, g_textures[static_cast<size_t>(g_index)].tex,
                 centerX, newBottom, fullW * breathe, fullH * breathe,
                 newWidth, std::max(0.045f, newHeight), newAlpha, newReflection);
'''
new = '''        DrawCard(dev, AnimatedCardTexture(static_cast<size_t>(g_index), now),
                 centerX, newBottom, fullW * breathe, fullH * breathe,
                 newWidth, std::max(0.045f, newHeight), newAlpha, newReflection);
'''
if old not in s:
    raise SystemExit("current DrawCard call missing")
s = s.replace(old, new, 1)

p.write_text(s, encoding="utf-8")
print("Patched menu_cards.cpp for V16: animated card frame engine (input untouched)")
