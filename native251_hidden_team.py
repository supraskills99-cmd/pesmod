from pathlib import Path


def replace_once(path, old, new, label):
    p = Path(path)
    s = p.read_text(encoding='utf-8')
    n = s.count(old)
    if n != 1:
        raise SystemExit(f'{label}: expected exactly 1 match in {path}, got {n}')
    p.write_text(s.replace(old, new, 1), encoding='utf-8')

# -----------------------------------------------------------------------------
# 1) Team 251 is NOT a PESMod out-of-range/custom runtime team anymore.
#    It is the real hidden stock PES6 team Maccingami FC, reused as Racing.
#    Never route it through FormationVirtual/backing team 203.
# -----------------------------------------------------------------------------
replace_once(
    'src/hooks/club_hooks_kit_data.cpp',
    '''    if (teamID > 0xCB && teamID != 0x110 && teamID != 0x111 &&\n        teamID != 0x126 && teamID != 0x127)\n''',
    '''    if (teamID > 0xCB && teamID != 251 && teamID != 0x110 && teamID != 0x111 &&\n        teamID != 0x126 && teamID != 0x127)\n''',
    'exclude native hidden 251 from FormationVirtual')

# Native kit descriptors for hidden stock 251. This is the exact identity
# Kitserver needs: kserv sees team 251, not backing 203 or a synthetic kit.
for fn in ('GetTeamKitData', 'GetTeamKitDataB', 'GetTeamKitDataC'):
    api = 'RE_' + fn
    old = f'''    // Racing 251 uses normal club 203 as its native Edit/Option-File\n    // storage. Returning the backing pointer makes PES6's stock kit editor\n    // modify data that the game already knows how to save and reload.\n    if (teamID == 251) {{\n        if (uint8_t* edited = {api}(0xCB, variant))\n            return edited;\n    }}\n\n'''
    new = f'''    // Racing reuses PES6's REAL hidden stock team 251. Keep the native\n    // descriptor and identity intact so Kitserver maps GDB directly to 251.\n    if (teamID == 251)\n        return {api}(251, variant);\n\n'''
    replace_once('src/hooks/club_hooks_kit_data.cpp', old, new,
                 f'native 251 {fn}')

# -----------------------------------------------------------------------------
# 2) Squad/formation access for 251 must also stay on the native stock record.
#    Do not load squad/251.ini for this team and do not touch backing 203.
#    This lets Edit Data operate on the same team PES6 already owns.
# -----------------------------------------------------------------------------
replace_once(
    'src/hooks/club_hooks_squad_data.cpp',
    '''    // Racing 251 is a visual/custom identity backed by normal club 203 for\n    // Edit Data. Reads from 251 therefore use the native, persistent roster.\n    if (teamID == RACING_EDIT_REAL_TEAM) {\n        if (EnsureRacingEditProxyReady())\n            return orig_GetTeamPlayerID(RACING_EDIT_BACKING_TEAM, slotIdx, mode);\n    }\n\n''',
    '''    // Team 251 is a real hidden PES6 team. Use its stock roster table directly.\n    if (teamID == 251u)\n        return orig_GetTeamPlayerID(teamID, slotIdx, mode);\n\n''',
    'native 251 GetTeamPlayerID')

replace_once(
    'src/hooks/club_hooks_squad_data.cpp',
    '''    if (teamID == RACING_EDIT_REAL_TEAM) {\n        if (EnsureRacingEditProxyReady())\n            return orig_GetTeamPlayerAttr(RACING_EDIT_BACKING_TEAM, slotIdx, mode);\n    }\n''',
    '''    if (teamID == 251u)\n        return orig_GetTeamPlayerAttr(teamID, slotIdx, mode);\n''',
    'native 251 GetTeamPlayerAttr')

replace_once(
    'src/hooks/club_hooks_squad_data.cpp',
    '''    if (teamID == RACING_EDIT_REAL_TEAM) {\n        EnsureRacingEditProxyReady();\n        orig_SetTeamPlayerAttr(RACING_EDIT_BACKING_TEAM, slotIdx, mode, value);\n        return;\n    }\n''',
    '''    if (teamID == 251u) {\n        orig_SetTeamPlayerAttr(teamID, slotIdx, mode, value);\n        return;\n    }\n''',
    'native 251 SetTeamPlayerAttr')

replace_once(
    'src/hooks/club_hooks_squad_data.cpp',
    '''    if (teamID == RACING_EDIT_REAL_TEAM) {\n        EnsureRacingEditProxyReady();\n        orig_SetTeamPlayerID(RACING_EDIT_BACKING_TEAM, slotIdx, playerID);\n        return;\n    }\n''',
    '''    if (teamID == 251u) {\n        orig_SetTeamPlayerID(teamID, slotIdx, playerID);\n        return;\n    }\n''',
    'native 251 SetTeamPlayerID')

# If some future code accidentally asks to virtualize 251 through 203, reject the
# proxy path instead of mutating 203. The normal 251 loader above is the only path.
replace_once(
    'src/hooks/club_hooks_squad_data.cpp',
    '''    // Racing uses the backing as persistent native storage. Do not redirect\n    // 203 reads back into the INI cache or re-seed a saved edit on every load.\n    if (realTeamID == RACING_EDIT_REAL_TEAM && backingTeamID == RACING_EDIT_BACKING_TEAM)\n        return EnsureRacingEditProxyReady();\n\n''',
    '''    // Native hidden team 251 must never borrow/overwrite team 203.\n    if (realTeamID == 251u)\n        return false;\n\n''',
    'disable 251 backing sync')

# -----------------------------------------------------------------------------
# 3) Emblem/edit-slot hooks: remove the old 251->203 remap. 251 may still use
#    teams/251.png through the existing custom-emblem route, but never 203.
# -----------------------------------------------------------------------------
replace_once(
    'src/hooks/custom_team_loader.cpp',
    '''    if (teamId == RACING_EDIT_REAL_TEAM) {\n        SeedRacingProxyIdentityOnce();\n        return orig_GetTeamEditSlotIdx\n            ? orig_GetTeamEditSlotIdx(RACING_EDIT_BACKING_TEAM) : 0x1CA;\n    }\n''',
    '''    // Team 251 is the real hidden stock team; do not remap its edit slot to 203.\n''',
    'remove 251 edit-slot backing remap')

replace_once(
    'src/hooks/custom_team_loader.cpp',
    '''    if (teamId == RACING_EDIT_REAL_TEAM) {\n        SeedRacingProxyIdentityOnce();\n        return orig_GetTeamEmblemPalette\n            ? orig_GetTeamEmblemPalette(RACING_EDIT_BACKING_TEAM) : nullptr;\n    }\n''',
    '''    // Native hidden 251 is handled by its own/custom-emblem data path below.\n''',
    'remove 251 emblem palette backing remap')

replace_once(
    'src/hooks/custom_team_loader.cpp',
    '''    if (teamId == RACING_EDIT_REAL_TEAM) {\n        SeedRacingProxyIdentityOnce();\n        return orig_GetTeamEmblemPixels\n            ? orig_GetTeamEmblemPixels(RACING_EDIT_BACKING_TEAM) : nullptr;\n    }\n''',
    '''    // Native hidden 251 is handled by its own/custom-emblem data path below.\n''',
    'remove 251 emblem pixels backing remap')

print('Native hidden team 251 mode applied: no 251->203 proxy, native kit/squad/edit identity preserved')
