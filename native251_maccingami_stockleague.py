from pathlib import Path


def replace_once(path, old, new, label):
    p = Path(path)
    s = p.read_text(encoding='utf-8')
    n = s.count(old)
    if n != 1:
        raise SystemExit(f'{label}: expected exactly 1 match in {path}, got {n}')
    p.write_text(s.replace(old, new, 1), encoding='utf-8')

# -----------------------------------------------------------------------------
# Pure diagnostic build:
# - Team 251 stays the ORIGINAL PES6 hidden Maccingami FC.
# - No Racing name, no teams/251.ini, no teams/251.png, no squad/251.ini proxy.
# - We only expose native 251 in one ORIGINAL exhibition category (stock slot 15,
#   the 18-team Other Clubs C/Team A-R block) by appending it as team #19.
# - Kitserver can then map 251 to Racing's GDB kit independently of PESMod.
# -----------------------------------------------------------------------------

# 1) Undo the strict build's cosmetic Racing rename. Forward every 251 name
# lookup directly to PES6 so the menu must show the game's own Maccingami FC.
replace_once(
    'src/hooks/custom_team_loader.cpp',
    '''    if (teamId == 251) {\n        static char racingFull[] = "Racing Club";\n        static char racingShort[] = "RAC";\n        if (nameType == 0) return racingFull;\n        if (nameType == 1) return racingShort;\n        return orig_GetTeamName ? orig_GetTeamName(teamId, nameType, param3) : nullptr;\n    }\n\n''',
    '''    if (teamId == 251)\n        return orig_GetTeamName ? orig_GetTeamName(teamId, nameType, param3) : nullptr;\n\n''',
    'restore stock Maccingami name')

# 2) Append native team 251 to ORIGINAL stock league slot 15 during normal
# exhibition mode only. We do not replace the slot or its name/logo; the stock
# 18-team list remains intact and 251 becomes the 19th entry.
p = Path('src/hooks/club_hooks_slots.cpp')
s = p.read_text(encoding='utf-8')
needle = '''        // ── String / name lookup ──────────────────────────────────────────\n'''
if needle not in s:
    raise SystemExit('club slot insertion point not found')
insert = '''        // Diagnostic: expose PES6's ORIGINAL hidden Maccingami FC (team 251)\n        // inside stock league slot 15 in normal Exhibition mode. Nothing else\n        // about the team is virtualized or replaced by PESMod.\n        if (modeActive == 0 && leagueSlotIndex == 15 && fillCount < TEAM_SLOT_COUNT)\n        {\n            bool alreadyPresent = false;\n            for (int i = 0; i < fillCount; ++i)\n                if (teamSlots.teamIDs[i] == 251) { alreadyPresent = true; break; }\n\n            if (!alreadyPresent)\n            {\n                teamSlots.teamIDs[fillCount++] = 251;\n                Logger::Log("[Native251Test] Appended original Maccingami FC (251) to stock slot 15");\n            }\n        }\n\n'''
s = s.replace(needle, insert + needle, 1)
p.write_text(s, encoding='utf-8')

print('Pure native Maccingami 251 test applied: stock name/data, appended to original slot 15')
