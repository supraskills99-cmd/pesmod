from pathlib import Path

p = Path("kitserver_module/menu_cards.cpp")
s = p.read_text(encoding="utf-8")

# V15: keep V13 rendering (V14 caused a runtime crash) and fix the real
# navigation desync: the same physical pad press can arrive once through the
# direct XInput/WinMM path and again a frame later through PES's logical table.
# Prefer the direct-pad edge for a short window so one menu step == one card step.

# Track the last physical-pad event time.
marker = "    bool g_directPadPrevCancel = false;\n"
if marker not in s:
    raise SystemExit("direct pad global marker missing")
if "g_lastDirectPadEventAt" not in s:
    s = s.replace(marker, marker + "    ULONGLONG g_lastDirectPadEventAt = 0;\n", 1)

# Stamp physical pad edges.
old = '''        const bool padCancelEdge = pad.cancel && !g_directPadPrevCancel;
        g_directPadPrevUp = pad.up;
        g_directPadPrevDown = pad.down;
        g_directPadPrevConfirm = pad.confirm;
        g_directPadPrevCancel = pad.cancel;
'''
new = '''        const bool padCancelEdge = pad.cancel && !g_directPadPrevCancel;
        g_directPadPrevUp = pad.up;
        g_directPadPrevDown = pad.down;
        g_directPadPrevConfirm = pad.confirm;
        g_directPadPrevCancel = pad.cancel;

        const bool directPadEdge = padUpEdge || padDownEdge || padConfirmEdge || padCancelEdge;
        if (directPadEdge)
            g_lastDirectPadEventAt = GetTickCount64();
'''
if old not in s:
    raise SystemExit("direct pad edge block missing")
s = s.replace(old, new, 1)

# Replace the final merged dispatch. PES logical input remains available for
# keyboard and as a fallback, but is ignored briefly after a direct pad event.
old_dispatch = '''        if (g_autoMainMenu && g_visible)
        {
            if ((seenDir & DOWN_PRESSED) || padDownEdge) TriggerIndex(g_index + 1);
            else if ((seenDir & UP_PRESSED) || padUpEdge) TriggerIndex(g_index - 1);
        }

        if ((seenFunc & CROSS_PRESSED) || padConfirmEdge) confirmAction();
        if ((seenFunc & (TRIANGLE_PRESSED | CIRCLE_PRESSED)) || padCancelEdge) cancelAction();
'''
new_dispatch = '''        const ULONGLONG inputNow = GetTickCount64();
        const bool allowLogicalInput = (inputNow - g_lastDirectPadEventAt) > 140;

        if (g_autoMainMenu && g_visible)
        {
            // One physical menu move must advance exactly one card. Direct pad
            // wins; PES logical input is only a keyboard/fallback source here.
            if (padDownEdge) TriggerIndex(g_index + 1);
            else if (padUpEdge) TriggerIndex(g_index - 1);
            else if (allowLogicalInput && (seenDir & DOWN_PRESSED)) TriggerIndex(g_index + 1);
            else if (allowLogicalInput && (seenDir & UP_PRESSED)) TriggerIndex(g_index - 1);
        }

        if (padConfirmEdge) confirmAction();
        else if (allowLogicalInput && (seenFunc & CROSS_PRESSED)) confirmAction();

        if (padCancelEdge) cancelAction();
        else if (allowLogicalInput && (seenFunc & (TRIANGLE_PRESSED | CIRCLE_PRESSED))) cancelAction();
'''
if old_dispatch not in s:
    raise SystemExit("V12 merged dispatch block missing")
s = s.replace(old_dispatch, new_dispatch, 1)

p.write_text(s, encoding="utf-8")
print("Patched menu_cards.cpp for V15: safe one-press/one-card input arbitration")
