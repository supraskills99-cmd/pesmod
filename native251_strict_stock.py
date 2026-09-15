from pathlib import Path


def replace_once(path, old, new, label):
    p = Path(path)
    s = p.read_text(encoding='utf-8')
    n = s.count(old)
    if n != 1:
        raise SystemExit(f'{label}: expected exactly 1 match in {path}, got {n}')
    p.write_text(s.replace(old, new, 1), encoding='utf-8')

# -----------------------------------------------------------------------------
# Strict stock mode for hidden team 251.
# Previous build still let teams/251.ini and teams/251.png enter PESMod custom
# identity/emblem routes. The crash log ended exactly after that custom texture
# was registered. For this build, 251 must behave as a stock hidden PES6 team
# everywhere except for a safe static display-name override.
# -----------------------------------------------------------------------------

# 1) Never parse teams/251.ini. This prevents custom identity side-effects.
replace_once(
    'src/hooks/custom_team_loader.cpp',
    '''const CustomTeam* GetCustomTeam(int teamId)\n{\n    auto it = g_teams.find(teamId);\n''',
    '''const CustomTeam* GetCustomTeam(int teamId)\n{\n    if (teamId == 251)\n        return nullptr;\n    auto it = g_teams.find(teamId);\n''',
    'bypass teams/251.ini')

# 2) Give 251 a safe static Racing display name without touching stock buffers
#    or loading the custom-team INI.
replace_once(
    'src/hooks/custom_team_loader.cpp',
    '''char* __cdecl hook_GetTeamName(uint16_t teamId, int nameType, int param3)\n{\n    if (teamId == RACING_EDIT_REAL_TEAM) {\n        SeedRacingProxyIdentityOnce();\n        const CustomTeam* racing = GetCustomTeam(teamId);\n        if (racing) {\n            if (nameType == 0) return const_cast<char*>(racing->fullName);\n            if (nameType == 1) return const_cast<char*>(racing->shortName);\n        }\n    }\n\n''',
    '''char* __cdecl hook_GetTeamName(uint16_t teamId, int nameType, int param3)\n{\n    if (teamId == 251) {\n        static char racingFull[] = "Racing Club";\n        static char racingShort[] = "RAC";\n        if (nameType == 0) return racingFull;\n        if (nameType == 1) return racingShort;\n        return orig_GetTeamName ? orig_GetTeamName(teamId, nameType, param3) : nullptr;\n    }\n\n''',
    'static Racing name for stock 251')

# 3) 251 crest/badge must use the original PES6 routes. Do not decode/register
#    teams/251.png in the menu path.
replace_once(
    'src/hooks/custom_team_loader.cpp',
    '''int __cdecl hook_CrestResolve(int scratchId, uint16_t teamId, int p3, int p4)\n{\n    const int node = RegisterCustomCrest(scratchId, teamId);\n''',
    '''int __cdecl hook_CrestResolve(int scratchId, uint16_t teamId, int p3, int p4)\n{\n    if (teamId == 251)\n        return orig_CrestResolve ? orig_CrestResolve(scratchId, teamId, p3, p4) : 0;\n    const int node = RegisterCustomCrest(scratchId, teamId);\n''',
    'stock crest route for 251')

replace_once(
    'src/hooks/custom_team_loader.cpp',
    '''bool DrawCustomBadge(int nodeStruct, int teamIdRaw)\n{\n    const int teamId = teamIdRaw & 0xFFFF;\n    if (teamId == 0xFFFF || nodeStruct == 0)\n''',
    '''bool DrawCustomBadge(int nodeStruct, int teamIdRaw)\n{\n    const int teamId = teamIdRaw & 0xFFFF;\n    if (teamId == 251)\n        return false;\n    if (teamId == 0xFFFF || nodeStruct == 0)\n''',
    'stock badge route for 251')

# 4) Disable every custom emblem source for 251, including the lower-level
#    match-time native-emblem bridge. This guarantees no custom 251 texture can
#    claim slot 0x142 behind the stock team's back.
replace_once(
    'src/hooks/custom_logo_loader.cpp',
    '''int RegisterCustomCrest(int scratchId, int teamId)\n{\n    const CrestData* c = GetCrestData(teamId);\n''',
    '''int RegisterCustomCrest(int scratchId, int teamId)\n{\n    if (teamId == 251) return 0;\n    const CrestData* c = GetCrestData(teamId);\n''',
    'disable custom crest data for 251')

replace_once(
    'src/hooks/custom_logo_loader.cpp',
    '''int GetCustomEmblemNode(int teamId)\n{\n    const int emblemId = kEmblemIdBase + teamId;\n''',
    '''int GetCustomEmblemNode(int teamId)\n{\n    if (teamId == 251) return 0;\n    const int emblemId = kEmblemIdBase + teamId;\n''',
    'disable custom emblem node for 251')

# This function exists in the full source patch applied before this script.
p = Path('src/hooks/custom_logo_loader.cpp')
s = p.read_text(encoding='utf-8')
needle = '''int GetCustomNativeEmblemSlot(int teamId)\n{\n'''
if needle not in s:
    raise SystemExit('GetCustomNativeEmblemSlot not found after full source patch')
s = s.replace(needle, needle + '''    if (teamId == 251)\n        return -1;\n''', 1)
p.write_text(s, encoding='utf-8')

# 5) Lower-level emblem accessors must forward 251 straight to PES6 stock data.
p = Path('src/hooks/custom_team_loader.cpp')
s = p.read_text(encoding='utf-8')
for signature, body in [
    ('int __cdecl hook_GetTeamEditSlotIdx(uint16_t teamId)\n{\n',
     '    if (teamId == 251) return orig_GetTeamEditSlotIdx ? orig_GetTeamEditSlotIdx(teamId) : 0x1CA;\n'),
    ('uint8_t* __cdecl hook_GetTeamEmblemPalette(uint16_t teamId)\n{\n',
     '    if (teamId == 251) return orig_GetTeamEmblemPalette ? orig_GetTeamEmblemPalette(teamId) : nullptr;\n'),
    ('uint8_t* __cdecl hook_GetTeamEmblemPixels(uint16_t teamId)\n{\n',
     '    if (teamId == 251) return orig_GetTeamEmblemPixels ? orig_GetTeamEmblemPixels(teamId) : nullptr;\n'),
]:
    if signature not in s:
        raise SystemExit(f'missing accessor signature: {signature.strip()}')
    s = s.replace(signature, signature + body, 1)
p.write_text(s, encoding='utf-8')

print('Strict stock hidden team 251 applied: no custom INI/PNG/emblem route; static Racing name only')
