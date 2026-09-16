from pathlib import Path

p = Path("kitserver_module/menu_cards.cpp")
s = p.read_text(encoding="utf-8")

# V21: focus only on reproducing the PES2011 transition rhythm.
# One shared timeline drives card close -> carousel travel -> card open.
# Do not touch V15 input/navigation/lifecycle.

# ---------------------------------------------------------------------------
# 1) Make the carousel wait for the outgoing card to start folding, then slide.
# ---------------------------------------------------------------------------
old = '''        const float slide = switching ? EaseOutCubic(transitionRaw) : 1.0f;
        const float transitionOffset = switching
            ? static_cast<float>(direction) * gap * (1.0f - slide)
            : 0.0f;
'''
new = '''        // PES2011 rhythm: the old panel starts folding first, then the icon row
        // travels. The incoming icon reaches the fixed slot before its card fully opens.
        const float stripRaw = switching ? Saturate((transitionRaw - 0.10f) / 0.60f) : 1.0f;
        const float slide = switching ? EaseOutCubic(stripRaw) : 1.0f;
        const float transitionOffset = switching
            ? static_cast<float>(direction) * gap * (1.0f - slide)
            : 0.0f;
'''
if old not in s:
    raise SystemExit("V21 carousel timing marker missing")
s = s.replace(old, new, 1)

# ---------------------------------------------------------------------------
# 2) Pedestal/glow only locks in as the arriving icon reaches the fixed slot.
# ---------------------------------------------------------------------------
old = '''        const float pulse = 0.5f + 0.5f * std::sin(static_cast<float>(now) * 0.006f);
        const BYTE glowA = static_cast<BYTE>(52.0f + pulse * 42.0f);
        DrawQuad(dev, nullptr,
                 centerX - baseSize * 0.72f, stripY + baseSize * 0.48f,
                 centerX + baseSize * 0.72f, stripY + baseSize * 0.56f,
                 Argb(glowA,104,255,154), Argb(0,104,255,154));
        DrawQuad(dev, nullptr,
                 centerX - baseSize * 0.48f, stripY + baseSize * 0.40f,
                 centerX + baseSize * 0.48f, stripY + baseSize * 0.44f,
                 Argb(static_cast<BYTE>(glowA * 0.70f),211,189,255),
                 Argb(0,211,189,255));
'''
new = '''        const float pulse = 0.5f + 0.5f * std::sin(static_cast<float>(now) * 0.006f);
        const float lockIn = switching ? Saturate((transitionRaw - 0.54f) / 0.32f) : 1.0f;
        const BYTE glowA = static_cast<BYTE>((52.0f + pulse * 42.0f) * lockIn);
        if (glowA > 0)
        {
            DrawQuad(dev, nullptr,
                     centerX - baseSize * 0.72f, stripY + baseSize * 0.48f,
                     centerX + baseSize * 0.72f, stripY + baseSize * 0.56f,
                     Argb(glowA,104,255,154), Argb(0,104,255,154));
            DrawQuad(dev, nullptr,
                     centerX - baseSize * 0.48f, stripY + baseSize * 0.40f,
                     centerX + baseSize * 0.48f, stripY + baseSize * 0.44f,
                     Argb(static_cast<BYTE>(glowA * 0.70f),211,189,255),
                     Argb(0,211,189,255));
        }
'''
if old not in s:
    raise SystemExit("V21 pedestal marker missing")
s = s.replace(old, new, 1)

# ---------------------------------------------------------------------------
# 3) Replace V13's overlapping card timing with the PES2011 three-stage rhythm.
# ---------------------------------------------------------------------------
old = '''        // PES 2011 feel: the previous panel folds down first, while the new one
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
'''
new = '''        // PES2011-style shared timeline:
        //   0.00 -> 0.30 : current card collapses into the selected icon
        //   0.10 -> 0.70 : icon carousel travels beneath the fixed card slot
        //   0.58 -> 1.00 : arriving card unfolds upward and settles
        const float oldT = switching ? Saturate(raw / 0.30f) : 1.0f;
        const float oldEase = EaseInCubic(oldT);
        const float newRaw = switching ? Saturate((raw - 0.58f) / 0.42f) : raw;
        const float newGrow = EaseOutBackSoft(newRaw);
        const float newWidth = 0.74f + 0.26f * EaseOutCubic(newRaw);
        const float newHeight = 0.028f + 0.972f * newGrow;
        const float newAlpha = Saturate(newRaw * 2.25f);
        const float newReflection = Saturate((newRaw - 0.48f) / 0.52f);
        const float breathe = 1.0f + 0.0018f * std::sin(static_cast<float>(now) * 0.0032f);
'''
if old not in s:
    raise SystemExit("V21 card timing marker missing")
s = s.replace(old, new, 1)

# ---------------------------------------------------------------------------
# 4) Outgoing card should fold sharply downward, not slowly cross-fade.
# ---------------------------------------------------------------------------
old = '''            const float oldWidth = 1.0f - 0.34f * oldEase;
            const float oldHeight = std::max(0.045f, 1.0f - 0.955f * oldEase);
            const float oldAlpha = 1.0f - Saturate(oldT * 1.10f);
            const float oldBottom = bottomY + fullH * 0.030f * oldEase;
            const float oldReflection = 1.0f - Saturate(oldT * 1.45f);
'''
new = '''            const float oldWidth = 1.0f - 0.26f * oldEase;
            const float oldHeight = std::max(0.028f, 1.0f - 0.972f * oldEase);
            const float oldAlpha = 1.0f - Saturate(oldT * 1.32f);
            const float oldBottom = bottomY + fullH * 0.018f * oldEase;
            const float oldReflection = 1.0f - Saturate(oldT * 1.75f);
'''
if old not in s:
    raise SystemExit("V21 outgoing card marker missing")
s = s.replace(old, new, 1)

# ---------------------------------------------------------------------------
# 5) Incoming card starts almost flat at the icon and snaps into place.
# ---------------------------------------------------------------------------
old = '''        const float newBottom = bottomY + fullH * 0.026f * (1.0f - EaseOutCubic(newRaw));
'''
new = '''        const float newBottom = bottomY + fullH * 0.014f * (1.0f - EaseOutCubic(newRaw));
'''
if old not in s:
    raise SystemExit("V21 incoming card anchor marker missing")
s = s.replace(old, new, 1)

# ---------------------------------------------------------------------------
# 6) Base flash happens when the arriving icon/card lock together, not at t=0.
# ---------------------------------------------------------------------------
old = '''        if (newRaw < 1.0f)
        {
            const float flash = 1.0f - Saturate(newRaw * 1.35f);
            const float glowW = fullW * (0.22f + 0.55f * EaseOutCubic(newRaw));
            const BYTE ga = static_cast<BYTE>(52.0f * flash);
            DrawQuad(dev, nullptr,
                     centerX - glowW * 0.5f, bottomY - 2.0f,
                     centerX + glowW * 0.5f, bottomY + 2.0f,
                     Argb(ga,255,255,255), Argb(0,255,255,255));
        }
'''
new = '''        if (newRaw > 0.001f && newRaw < 1.0f)
        {
            const float flash = 1.0f - Saturate(newRaw * 1.55f);
            const float glowW = fullW * (0.30f + 0.50f * EaseOutCubic(newRaw));
            const BYTE ga = static_cast<BYTE>(64.0f * flash);
            DrawQuad(dev, nullptr,
                     centerX - glowW * 0.5f, bottomY - 2.0f,
                     centerX + glowW * 0.5f, bottomY + 2.0f,
                     Argb(ga,255,255,255), Argb(0,255,255,255));
        }
'''
if old not in s:
    raise SystemExit("V21 base flash marker missing")
s = s.replace(old, new, 1)

p.write_text(s, encoding="utf-8")
print("Patched menu_cards.cpp for V21: PES2011 synchronized card/carousel transition")
