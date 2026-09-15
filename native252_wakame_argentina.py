from pathlib import Path


def replace_once(path, old, new, label):
    p = Path(path)
    s = p.read_text(encoding='utf-8')
    n = s.count(old)
    if n != 1:
        raise SystemExit(f'{label}: expected exactly 1 match in {path}, got {n}')
    p.write_text(s.replace(old, new, 1), encoding='utf-8')

# -----------------------------------------------------------------------------
# Wakame '73 native hidden-team test.
# Goal:
#   - keep team 252 as PES6's ORIGINAL Wakame '73 identity/data
#   - place it in the user's Liga Argentina (league slot 17)
#   - replace the existing Racing custom team 251 if present; otherwise append
#   - keep 252 out of PESMod custom/proxy paths so Kitserver sees the real ID 252
# -----------------------------------------------------------------------------

# 1) Kit path: 252 is a real hidden stock team, just like 251 in the previous
# native test. Exempt it from FormationVirtual/custom backing routing.
replace_once(
    'src/hooks/club_hooks_kit_data.cpp',
    '''    if (teamID > 0xCB && teamID != 251 && teamID != 0x110 && teamID != 0x111 &&\n        teamID != 0x126 && teamID != 0x127)\n''',
    '''    if (teamID > 0xCB && teamID != 251 && teamID != 252 && teamID != 0x110 && teamID != 0x111 &&\n        teamID != 0x126 && teamID != 0x127)\n''',
    'exclude native hidden 252 from FormationVirtual kit path')

# 2) Squad path: force team 252 straight through the original PES6 accessors.
p = Path('src/hooks/club_hooks_squad_data.cpp')
s = p.read_text(encoding='utf-8')

hooks = [
    ('''uint32_t __cdecl hook_GetTeamPlayerID(uint32_t teamID, uint8_t slotIdx,\n                                        int mode)\n{\n''',
     '''    if (teamID == 252u)\n        return orig_GetTeamPlayerID(teamID, slotIdx, mode);\n\n''',
     'GetTeamPlayerID 252 native'),
    ('''uint8_t __cdecl hook_GetTeamPlayerAttr(uint32_t teamID, uint32_t slotIdx,\n                                         int mode)\n{\n''',
     '''    if (teamID == 252u)\n        return orig_GetTeamPlayerAttr(teamID, slotIdx, mode);\n\n''',
     'GetTeamPlayerAttr 252 native'),
    ('''void __cdecl hook_SetTeamPlayerAttr(uint32_t teamID, uint32_t slotIdx,\n                                      int mode, uint32_t value)\n{\n''',
     '''    if (teamID == 252u) {\n        orig_SetTeamPlayerAttr(teamID, slotIdx, mode, value);\n        return;\n    }\n\n''',
     'SetTeamPlayerAttr 252 native'),
    ('''void __cdecl hook_SetTeamPlayerID(uint32_t teamID, uint8_t slotIdx,\n                                    uint16_t playerID)\n{\n''',
     '''    if (teamID == 252u) {\n        orig_SetTeamPlayerID(teamID, slotIdx, playerID);\n        return;\n    }\n\n''',
     'SetTeamPlayerID 252 native'),
]
for signature, body, label in hooks:
    if signature not in s:
        raise SystemExit(f'{label}: signature not found')
    s = s.replace(signature, signature + body, 1)
p.write_text(s, encoding='utf-8')

# 3) Identity/emblem path: never treat 252 as a PESMod custom team even if a
# stray teams/252.ini or teams/252.png exists. Forward to stock PES6 data.
p = Path('src/hooks/custom_team_loader.cpp')
s = p.read_text(encoding='utf-8')

needle = '''const CustomTeam* GetCustomTeam(int teamId)\n{\n'''
if needle not in s:
    raise SystemExit('GetCustomTeam signature not found')
s = s.replace(needle, needle + '''    if (teamId == 252)\n        return nullptr;\n''', 1)

needle = '''char* __cdecl hook_GetTeamName(uint16_t teamId, int nameType, int param3)\n{\n'''
if needle not in s:
    raise SystemExit('hook_GetTeamName signature not found')
s = s.replace(needle, needle + '''    if (teamId == 252)\n        return orig_GetTeamName ? orig_GetTeamName(teamId, nameType, param3) : nullptr;\n\n''', 1)

needle = '''int __cdecl hook_CrestResolve(int scratchId, uint16_t teamId, int p3, int p4)\n{\n'''
if needle not in s:
    raise SystemExit('hook_CrestResolve signature not found')
s = s.replace(needle, needle + '''    if (teamId == 252)\n        return orig_CrestResolve ? orig_CrestResolve(scratchId, teamId, p3, p4) : 0;\n''', 1)

needle = '''bool DrawCustomBadge(int nodeStruct, int teamIdRaw)\n{\n    const int teamId = teamIdRaw & 0xFFFF;\n'''
if needle not in s:
    raise SystemExit('DrawCustomBadge signature not found')
s = s.replace(needle, needle + '''    if (teamId == 252)\n        return false;\n''', 1)

for signature, body, label in [
    ('int __cdecl hook_GetTeamEditSlotIdx(uint16_t teamId)\n{\n',
     '    if (teamId == 252) return orig_GetTeamEditSlotIdx ? orig_GetTeamEditSlotIdx(teamId) : 0x1CA;\n',
     'edit slot 252'),
    ('uint8_t* __cdecl hook_GetTeamEmblemPalette(uint16_t teamId)\n{\n',
     '    if (teamId == 252) return orig_GetTeamEmblemPalette ? orig_GetTeamEmblemPalette(teamId) : nullptr;\n',
     'emblem palette 252'),
    ('uint8_t* __cdecl hook_GetTeamEmblemPixels(uint16_t teamId)\n{\n',
     '    if (teamId == 252) return orig_GetTeamEmblemPixels ? orig_GetTeamEmblemPixels(teamId) : nullptr;\n',
     'emblem pixels 252'),
]:
    if signature not in s:
        raise SystemExit(f'{label}: signature not found')
    s = s.replace(signature, signature + body, 1)
p.write_text(s, encoding='utf-8')

p = Path('src/hooks/custom_logo_loader.cpp')
s = p.read_text(encoding='utf-8')
for signature, body, label in [
    ('int RegisterCustomCrest(int scratchId, int teamId)\n{\n',
     '    if (teamId == 252) return 0;\n', 'crest 252 stock'),
    ('int GetCustomEmblemNode(int teamId)\n{\n',
     '    if (teamId == 252) return 0;\n', 'emblem node 252 stock'),
    ('int GetCustomNativeEmblemSlot(int teamId)\n{\n',
     '    if (teamId == 252) return -1;\n', 'native emblem slot 252 stock'),
]:
    if signature not in s:
        raise SystemExit(f'{label}: signature not found')
    s = s.replace(signature, signature + body, 1)
p.write_text(s, encoding='utf-8')

# 4) Liga Argentina: when leagues/17.ini is loaded, replace team 251 with
# native Wakame '73 (252). If 251 is not present, append 252 to the first free
# team slot. This keeps the user's league name/logo/order otherwise unchanged.
p = Path('src/hooks/club_hooks_leagues.cpp')
s = p.read_text(encoding='utf-8')
needle = '''        if (!LoadOneLeagueIni(slot, buf)) continue;\n'''
if s.count(needle) != 1:
    raise SystemExit(f'ApplyLeagueIniOverrides insertion point count={s.count(needle)}')
insert = needle + '''\n        if (slot == 17) {\n            bool placed = false;\n            for (int i = 0; i < TEAM_SLOT_COUNT; ++i) {\n                if (buf.teamIDs[i] == 251) {\n                    buf.teamIDs[i] = 252;\n                    placed = true;\n                    Logger::Log("[Native252Test] Liga Argentina: replaced team 251 with original Wakame '73 (252) at index %d", i);\n                    break;\n                }\n            }\n            if (!placed) {\n                for (int i = 0; i < TEAM_SLOT_COUNT; ++i) {\n                    if (buf.teamIDs[i] == CLUB_NULL_ID) {\n                        buf.teamIDs[i] = 252;\n                        placed = true;\n                        Logger::Log("[Native252Test] Liga Argentina: appended original Wakame '73 (252) at index %d", i);\n                        break;\n                    }\n                }\n            }\n        }\n'''
s = s.replace(needle, insert, 1)
p.write_text(s, encoding='utf-8')

print("Native Wakame '73 252 test applied: stock data, Liga Argentina slot 17, no 251/custom proxy")
