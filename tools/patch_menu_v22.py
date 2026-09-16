from pathlib import Path

p = Path("kitserver_module/menu_cards.cpp")
s = p.read_text(encoding="utf-8")

# V22: match the supplied PES 2011 video more literally.
# The selected item is a fixed square tile plus an upper panel that reveals
# upward. The old upper panel snaps shut, the carousel slides, then the new
# upper panel opens. Input/navigation/lifecycle remains untouched.

# 1) Crop/reveal the texture vertically instead of squashing the whole card.
old = '''        const float curW = std::max(2.0f, fullW * widthScale);
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
'''
new = '''        constexpr float kTileFraction = 128.0f / 292.0f;
        const float reveal = std::max(kTileFraction, std::min(1.0f, heightScale));
        const float curW = std::max(2.0f, fullW * widthScale);
        const float curH = std::max(2.0f, fullH * reveal);
        const float x0 = centerX - curW * 0.5f;
        const float x1 = centerX + curW * 0.5f;
        const float y0 = bottomY - curH;
        const float v0 = 1.0f - reveal;
        const BYTE a = static_cast<BYTE>(255.0f * Saturate(alpha));

        // PES2011 does not vertically squeeze the panel: it reveals it upward
        // from the square selected tile. UV cropping reproduces that behavior.
        DrawQuad(dev, tex, x0, y0, x1, bottomY,
                 Argb(a,255,255,255), Argb(a,255,255,255), 0,v0,1,1);

        if (reflectionAlpha > 0.001f)
        {
            // Reflect only the lower square tile, like the original menu video.
            const float rh = fullW * 0.28f;
            const BYTE ra = static_cast<BYTE>(255.0f * Saturate(alpha * reflectionAlpha * g_reflection));
            DrawQuad(dev, tex, x0, bottomY + 2.0f, x1, bottomY + 2.0f + rh,
                     Argb(ra,255,255,255), Argb(0,255,255,255),
                     0,1,1,1.0f-kTileFraction);
        }
'''
if old not in s:
    raise SystemExit("V22 DrawCard marker missing")
s = s.replace(old, new, 1)

# 2) Match the timing measured from the supplied PES2011 clip (~350ms total).
old = '''        const float stripRaw = switching ? Saturate((transitionRaw - 0.10f) / 0.60f) : 1.0f;
'''
new = '''        const float stripRaw = switching ? Saturate((transitionRaw - 0.10f) / 0.42f) : 1.0f;
'''
if old not in s:
    raise SystemExit("V22 strip timing marker missing")
s = s.replace(old, new, 1)

# 3) The old panel closes almost immediately; incoming panel starts only after
# the new square tile has reached the selected slot.
old = '''        const float oldT = switching ? Saturate(raw / 0.30f) : 1.0f;
        const float oldEase = EaseInCubic(oldT);
        const float newRaw = switching ? Saturate((raw - 0.58f) / 0.42f) : raw;
        const float newGrow = EaseOutBackSoft(newRaw);
        const float newWidth = 0.74f + 0.26f * EaseOutCubic(newRaw);
        const float newHeight = 0.028f + 0.972f * newGrow;
        const float newAlpha = Saturate(newRaw * 2.25f);
        const float newReflection = Saturate((newRaw - 0.48f) / 0.52f);
        const float breathe = 1.0f + 0.0018f * std::sin(static_cast<float>(now) * 0.0032f);
'''
new = '''        constexpr float kTileFraction = 128.0f / 292.0f;
        const float oldT = switching ? Saturate(raw / 0.15f) : 1.0f;
        const float oldEase = EaseInCubic(oldT);
        const float newRaw = switching ? Saturate((raw - 0.46f) / 0.54f) : raw;
        const float newGrow = EaseOutCubic(newRaw);
        const float newWidth = 1.0f;
        const float newHeight = kTileFraction + (1.0f-kTileFraction) * newGrow;
        const float newAlpha = switching ? Saturate(newRaw * 7.0f) : Saturate(raw * 5.0f);
        const float newReflection = Saturate((newRaw - 0.60f) / 0.40f);
        const float breathe = 1.0f;
'''
if old not in s:
    raise SystemExit("V22 card timing marker missing")
s = s.replace(old, new, 1)

# 4) Old panel retracts to the square tile with no horizontal shrinking, then
# disappears so the moving carousel icon takes over seamlessly.
old = '''            const float oldWidth = 1.0f - 0.26f * oldEase;
            const float oldHeight = std::max(0.028f, 1.0f - 0.972f * oldEase);
            const float oldAlpha = 1.0f - Saturate(oldT * 1.32f);
            const float oldBottom = bottomY + fullH * 0.018f * oldEase;
            const float oldReflection = 1.0f - Saturate(oldT * 1.75f);
'''
new = '''            constexpr float kTileFraction = 128.0f / 292.0f;
            const float oldWidth = 1.0f;
            const float oldHeight = 1.0f - (1.0f-kTileFraction) * oldEase;
            const float oldAlpha = 1.0f - Saturate((oldT - 0.82f) / 0.18f);
            const float oldBottom = bottomY;
            const float oldReflection = 1.0f - Saturate(oldT * 3.0f);
'''
if old not in s:
    raise SystemExit("V22 outgoing marker missing")
s = s.replace(old, new, 1)

# 5) No vertical bounce of the whole card; the reveal itself is the motion.
old = '''        const float newBottom = bottomY + fullH * 0.014f * (1.0f - EaseOutCubic(newRaw));
'''
new = '''        const float newBottom = bottomY;
'''
if old not in s:
    raise SystemExit("V22 newBottom marker missing")
s = s.replace(old, new, 1)

p.write_text(s, encoding="utf-8")
print("Patched menu_cards.cpp for V22: PES2011 square-tile + upward panel reveal")
