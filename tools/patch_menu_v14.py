from pathlib import Path

p = Path("kitserver_module/menu_cards.cpp")
s = p.read_text(encoding="utf-8")

# V14
# 1) keep card order perfectly circular in both directions, matching PES6 menu wrap
# 2) remember navigation direction so reverse movement animates in reverse
# 3) make the PES2011-style collapse/rise transition much more visible

# Track direction next to menu state.
needle = "    int g_prevIndex = 0;\n"
if "g_navDirection" not in s:
    if needle not in s:
        raise SystemExit("g_prevIndex marker missing")
    s = s.replace(needle, needle + "    int g_navDirection = 1;\n", 1)

# Replace clamped TriggerIndex with circular ordering and direction tracking.
old_trigger = '''    void TriggerIndex(int newIndex)
    {
        newIndex = std::max(0, std::min(10, newIndex));
        if (newIndex == g_index) return;
        g_prevIndex = g_index;
        g_index = newIndex;
        g_transitionStart = GetTickCount64();
        Log("index -> %d", g_index);
    }
'''
new_trigger = '''    void TriggerIndex(int newIndex)
    {
        // PES6 main menu wraps. Keep the card list on the exact same 0..10 ring.
        while (newIndex < 0) newIndex += 11;
        while (newIndex >= 11) newIndex -= 11;
        if (newIndex == g_index) return;

        const int oldIndex = g_index;
        if (newIndex == ((oldIndex + 1) % 11)) g_navDirection = 1;
        else if (newIndex == ((oldIndex + 10) % 11)) g_navDirection = -1;
        else g_navDirection = (newIndex > oldIndex) ? 1 : -1;

        g_prevIndex = oldIndex;
        g_index = newIndex;
        g_transitionStart = GetTickCount64();
        Log("index %d -> %d dir=%d", g_prevIndex, g_index, g_navDirection);
    }
'''
if old_trigger not in s:
    raise SystemExit("TriggerIndex block not found")
s = s.replace(old_trigger, new_trigger, 1)

# Strengthen V13 visual motion. The old card clearly folds into the icon, then
# the new one grows from a small footprint and settles with a visible overshoot.
repls = {
    '        constexpr float c1 = 1.05f, c3 = c1 + 1.0f;\n':
    '        constexpr float c1 = 1.42f, c3 = c1 + 1.0f;\n',

    '        const float oldT = switching ? Saturate(raw / 0.58f) : 1.0f;\n':
    '        const float oldT = switching ? Saturate(raw / 0.46f) : 1.0f;\n',

    '        const float newRaw = switching ? Saturate((raw - 0.16f) / 0.84f) : raw;\n':
    '        const float newRaw = switching ? Saturate((raw - 0.24f) / 0.76f) : raw;\n',

    '        const float newWidth = 0.68f + 0.32f * EaseOutCubic(newRaw);\n':
    '        const float newWidth = 0.24f + 0.76f * EaseOutCubic(newRaw);\n',

    '        const float newHeight = 0.045f + 0.955f * newGrow;\n':
    '        const float newHeight = 0.055f + 0.945f * newGrow;\n',

    '        const float newAlpha = Saturate(newRaw * 1.75f);\n':
    '        const float newAlpha = Saturate(newRaw * 1.45f);\n',

    '        const float newReflection = Saturate((newRaw - 0.42f) / 0.58f);\n':
    '        const float newReflection = Saturate((newRaw - 0.52f) / 0.48f);\n',

    '            const float oldWidth = 1.0f - 0.34f * oldEase;\n':
    '            const float oldWidth = 1.0f - 0.80f * oldEase;\n',

    '            const float oldHeight = std::max(0.045f, 1.0f - 0.955f * oldEase);\n':
    '            const float oldHeight = std::max(0.055f, 1.0f - 0.945f * oldEase);\n',

    '            const float oldBottom = bottomY + fullH * 0.030f * oldEase;\n':
    '            const float oldBottom = bottomY + fullH * 0.095f * oldEase;\n',

    '                     centerX, oldBottom, fullW, fullH,\n':
    '                     centerX - g_navDirection * fullW * 0.055f * oldEase, oldBottom, fullW, fullH,\n',

    '        const float newBottom = bottomY + fullH * 0.026f * (1.0f - EaseOutCubic(newRaw));\n':
    '        const float newBottom = bottomY + fullH * 0.115f * (1.0f - EaseOutCubic(newRaw));\n',

    '                 centerX, newBottom, fullW * breathe, fullH * breathe,\n':
    '                 centerX + g_navDirection * fullW * 0.060f * (1.0f - EaseOutCubic(newRaw)),\n                 newBottom, fullW * breathe, fullH * breathe,\n',
}

for old, new in repls.items():
    if old not in s:
        raise SystemExit(f"V13 animation marker missing: {old.strip()}")
    s = s.replace(old, new, 1)

p.write_text(s, encoding="utf-8")
print("Patched menu_cards.cpp for V14: circular order + obvious reverse-aware PES2011 animation")
