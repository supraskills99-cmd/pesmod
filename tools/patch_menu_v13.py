from pathlib import Path
import re

p = Path("kitserver_module/menu_cards.cpp")
s = p.read_text(encoding="utf-8")

# V13: make the selected card animate much closer to PES 2011:
# - old card retracts down into the selected icon
# - new card grows upward from the icon with a soft overshoot
# - reflection appears slightly after the card itself
# - subtle base flash and sheen during the transition
# Input/lifecycle logic from V11/V12 is intentionally left untouched.

# Add easing helpers after the existing EaseOutBack helper.
marker = '''    float EaseOutBack(float t)\n    {\n        t = Saturate(t);\n        constexpr float c1 = 1.70158f, c3 = c1 + 1.0f;\n        const float x = t - 1.0f;\n        return 1.0f + c3*x*x*x + c1*x*x;\n    }\n'''
if marker not in s:
    raise SystemExit("EaseOutBack marker not found")
if "EaseOutBackSoft" not in s:
    replacement = marker + '''\n    float EaseOutCubic(float t)\n    {\n        t = Saturate(t);\n        const float x = 1.0f - t;\n        return 1.0f - x*x*x;\n    }\n\n    float EaseInCubic(float t)\n    {\n        t = Saturate(t);\n        return t*t*t;\n    }\n\n    float EaseOutBackSoft(float t)\n    {\n        t = Saturate(t);\n        constexpr float c1 = 1.05f, c3 = c1 + 1.0f;\n        const float x = t - 1.0f;\n        return 1.0f + c3*x*x*x + c1*x*x;\n    }\n'''
    s = s.replace(marker, replacement, 1)

# When returning to the main menu, reopen only the current card instead of briefly
# drawing a stale previous card from the last selection transition.
return_old = '''                    g_visible = true;\n                    g_hiddenByEnter = false;\n                    g_transitionStart = t;\n                    Log("returned to main menu: index=%d", g_index);\n'''
return_new = '''                    g_visible = true;\n                    g_hiddenByEnter = false;\n                    g_prevIndex = g_index;\n                    g_transitionStart = t;\n                    Log("returned to main menu: index=%d", g_index);\n'''
if return_old in s:
    s = s.replace(return_old, return_new, 1)

# Replace the old simple vertical scale with a PES2011-style staged transition.
pattern = re.compile(
    r'''    void DrawCard\(void\* dev, void\* tex, float centerX, float bottomY,\n'''
    r'''                  float fullW, float fullH, float openness, float alpha, bool reflection\)\n'''
    r'''    \{.*?\n    \}\n\n'''
    r'''    void Render\(void\* dev\)\n'''
    r'''    \{.*?\n    \}\n\n'''
    r'''    void __cdecl OnPresent''',
    re.S,
)

replacement = r'''    void DrawCard(void* dev, void* tex, float centerX, float bottomY,
                  float fullW, float fullH, float widthScale, float heightScale,
                  float alpha, float reflectionAlpha)
    {
        if (!tex || widthScale <= 0.001f || heightScale <= 0.001f || alpha <= 0.001f) return;

        const float curW = std::max(2.0f, fullW * widthScale);
        const float curH = std::max(2.0f, fullH * heightScale);
        const float x0 = centerX - curW * 0.5f;
        const float x1 = centerX + curW * 0.5f;
        const float y0 = bottomY - curH;
        const BYTE a = static_cast<BYTE>(255.0f * Saturate(alpha));

        DrawQuad(dev, tex, x0, y0, x1, bottomY,
                 Argb(a,255,255,255), Argb(a,255,255,255));

        if (reflectionAlpha > 0.001f)
        {
            const float rh = fullH * 0.22f * std::min(1.08f, heightScale);
            const BYTE ra = static_cast<BYTE>(255.0f * Saturate(alpha * reflectionAlpha * g_reflection));
            DrawQuad(dev, tex, x0, bottomY + 2.0f, x1, bottomY + 2.0f + rh,
                     Argb(ra,255,255,255), Argb(0,255,255,255), 0,1,1,0.77f);
        }
    }

    void Render(void* dev)
    {
        if (!g_visible || !dev) return;
        EnsureTextures(dev);
        D3DVIEWPORT8_MIN vp = {};
        if (FAILED(DevGetViewport(dev, &vp)) || vp.Width == 0 || vp.Height == 0) return;

        const float W = static_cast<float>(vp.Width), H = static_cast<float>(vp.Height);
        const float centerX = W * g_anchorX;
        const float bottomY = H * g_anchorY;
        const float fullW = W * g_cardW;
        const float fullH = H * g_cardH;
        const ULONGLONG now = GetTickCount64();
        const float raw = Saturate(static_cast<float>(now - g_transitionStart) / std::max(1.0f, g_animMs));
        const bool switching = (g_prevIndex != g_index);

        // PES 2011 feel: the previous panel folds down first, while the new one
        // starts rising a moment later from the same icon anchor.
        const float oldT = switching ? Saturate(raw / 0.58f) : 1.0f;
        const float oldEase = EaseInCubic(oldT);
        const float newRaw = switching ? Saturate((raw - 0.16f) / 0.84f) : raw;
        const float newGrow = EaseOutBackSoft(newRaw);
        const float newWidth = 0.68f + 0.32f * EaseOutCubic(newRaw);
        const float newHeight = 0.045f + 0.955f * newGrow;
        const float newAlpha = Saturate(newRaw * 1.75f);
        const float newReflection = Saturate((newRaw - 0.42f) / 0.58f);
        const float breathe = 1.0f + 0.0025f * std::sin(static_cast<float>(now) * 0.0032f);

        DWORD state = 0;
        const bool haveState = SUCCEEDED(DevCreateStateBlock(dev, &state));
        if (FAILED(DevBeginScene(dev)))
        {
            if (haveState) DevDeleteStateBlock(dev, state);
            return;
        }
        SetupState(dev);

        if (switching && raw < 1.0f)
        {
            const float oldWidth = 1.0f - 0.34f * oldEase;
            const float oldHeight = std::max(0.045f, 1.0f - 0.955f * oldEase);
            const float oldAlpha = 1.0f - Saturate(oldT * 1.10f);
            const float oldBottom = bottomY + fullH * 0.030f * oldEase;
            const float oldReflection = 1.0f - Saturate(oldT * 1.45f);

            DrawCard(dev, g_textures[static_cast<size_t>(g_prevIndex)].tex,
                     centerX, oldBottom, fullW, fullH,
                     oldWidth, oldHeight, oldAlpha, oldReflection);
        }

        // The new card grows upward from the icon. A tiny overshoot gives the
        // same snap/settle sensation as the PES 2011 frontend.
        const float newBottom = bottomY + fullH * 0.026f * (1.0f - EaseOutCubic(newRaw));
        DrawCard(dev, g_textures[static_cast<size_t>(g_index)].tex,
                 centerX, newBottom, fullW * breathe, fullH * breathe,
                 newWidth, std::max(0.045f, newHeight), newAlpha, newReflection);

        // Untextured transition accents: a quick base flash and a soft sheen.
        DevSetTexture(dev, 0, nullptr);
        DevSetTextureStageState(dev,0,D3DTSS_COLOROP_,D3DTOP_SELECTARG1_);
        DevSetTextureStageState(dev,0,D3DTSS_COLORARG1_,D3DTA_DIFFUSE_);
        DevSetTextureStageState(dev,0,D3DTSS_ALPHAOP_,D3DTOP_SELECTARG1_);
        DevSetTextureStageState(dev,0,D3DTSS_ALPHAARG1_,D3DTA_DIFFUSE_);

        if (newRaw < 1.0f)
        {
            const float flash = 1.0f - Saturate(newRaw * 1.35f);
            const float glowW = fullW * (0.22f + 0.55f * EaseOutCubic(newRaw));
            const BYTE ga = static_cast<BYTE>(52.0f * flash);
            DrawQuad(dev, nullptr,
                     centerX - glowW * 0.5f, bottomY - 2.0f,
                     centerX + glowW * 0.5f, bottomY + 2.0f,
                     Argb(ga,255,255,255), Argb(0,255,255,255));
        }

        const float sheenGate = switching ? Saturate((newRaw - 0.48f) / 0.52f) : Saturate(newRaw);
        if (sheenGate > 0.001f)
        {
            const float sweep = std::fmod(static_cast<float>(now) * 0.00022f, 1.32f) - 0.16f;
            const float sx0 = centerX - fullW * 0.5f + fullW * sweep;
            const BYTE sa = static_cast<BYTE>(18.0f * sheenGate);
            DrawQuad(dev, nullptr,
                     sx0, bottomY - fullH * 0.95f,
                     sx0 + fullW * 0.075f, bottomY - 4.0f,
                     Argb(sa,255,255,255), Argb(2,255,255,255));
        }

        DevEndScene(dev);
        if (haveState)
        {
            DevApplyStateBlock(dev, state);
            DevDeleteStateBlock(dev, state);
        }
    }

    void __cdecl OnPresent'''

s, count = pattern.subn(replacement, s, count=1)
if count != 1:
    raise SystemExit("DrawCard/Render block not found")

p.write_text(s, encoding="utf-8")
print("Patched menu_cards.cpp for V13: PES2011-style card transition")
