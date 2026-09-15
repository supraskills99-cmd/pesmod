from pathlib import Path

p = Path('src/hooks/custom_team_loader.cpp')
s = p.read_text(encoding='utf-8')

def repl(old, new, label):
    global s
    n = s.count(old)
    if n != 1:
        raise SystemExit(f'{label}: expected exactly 1 match, got {n}')
    s = s.replace(old, new, 1)

repl(r'''void SeedRacingProxyIdentityOnce()
{
    if (g_racingProxyIdentitySeeded) return;
    g_racingProxyIdentitySeeded = true;

    const bool loadedFromNative = RacingEditProxyLoadedFromNativeSave();
    if (loadedFromNative) {
        Logger::Log("[EditProxy] Racing 251 identity preserved from native backing 203");
        return;
    }

    const CustomTeam* racing = GetCustomTeam(RACING_EDIT_REAL_TEAM);
    if (racing && orig_GetTeamName) {
        if (char* full = orig_GetTeamName(RACING_EDIT_BACKING_TEAM, 0, 0)) {
            std::strncpy(full, racing->fullName, 48);
            full[48] = '\0';
        }
        if (char* sh = orig_GetTeamName(RACING_EDIT_BACKING_TEAM, 1, 0)) {
            std::strncpy(sh, racing->shortName, 5);
            sh[5] = '\0';
        }
    }

    // Seed the editable emblem bank once from teams/251.png. After the first
    // native save, the original 203 buffers become authoritative.
    if (orig_GetTeamEditSlotIdx && orig_GetEmblemPaletteBySlot && orig_GetEmblemPixelsBySlot) {
        const int slot = orig_GetTeamEditSlotIdx(RACING_EDIT_BACKING_TEAM);
        const uint8_t* srcPal = nullptr;
        const uint8_t* srcPix = nullptr;
        if (slot >= 0 && GetCustomNativeEmblemData(RACING_EDIT_REAL_TEAM, &srcPal, &srcPix)) {
            uint8_t* dstPal = orig_GetEmblemPaletteBySlot(slot);
            uint8_t* dstPix = orig_GetEmblemPixelsBySlot(slot);
            if (dstPal && srcPal) std::memcpy(dstPal, srcPal, 0x400);
            if (dstPix && srcPix) std::memcpy(dstPix, srcPix, 0x1000);
        }
    }
    Logger::Log("[EditProxy] Racing 251 identity seeded into native backing 203");
}
''', r'''void SeedRacingProxyIdentityOnce()
{
    if (g_racingProxyIdentitySeeded) return;
    g_racingProxyIdentitySeeded = true;

    // Never write through pointers returned by GetTeamName(): PES does not
    // guarantee those are writable or large enough. Keep Racing's visible
    // identity in PESMod and proxy only native editable team/squad/kit data.
    EnsureRacingEditProxyReady();
    Logger::Log("[EditProxy] Racing 251 native data proxy ready; custom identity preserved");
}
''', 'SeedRacingProxyIdentityOnce')

repl(r'''    if (teamId == RACING_EDIT_REAL_TEAM || teamId == RACING_EDIT_BACKING_TEAM) {
        SeedRacingProxyIdentityOnce();
        return orig_GetTeamName
            ? orig_GetTeamName(RACING_EDIT_BACKING_TEAM, nameType, param3)
            : nullptr;
    }

''', r'''    if (teamId == RACING_EDIT_REAL_TEAM) {
        SeedRacingProxyIdentityOnce();
        const CustomTeam* racing = GetCustomTeam(teamId);
        if (racing) {
            if (nameType == 0) return const_cast<char*>(racing->fullName);
            if (nameType == 1) return const_cast<char*>(racing->shortName);
        }
    }

''', 'GetTeamName Racing identity')

repl(r'''    if (teamId == RACING_EDIT_REAL_TEAM) {
        SeedRacingProxyIdentityOnce();
        return orig_CrestResolve
            ? orig_CrestResolve(scratchId, RACING_EDIT_BACKING_TEAM, p3, p4)
            : 0;
    }

''', '', 'CrestResolve Racing remap')

repl(r'''    if ((teamId & 0xFFFF) == RACING_EDIT_REAL_TEAM) {
        SeedRacingProxyIdentityOnce();
        if (orig_BadgeRenderCdecl)
            orig_BadgeRenderCdecl(nodeStruct, RACING_EDIT_BACKING_TEAM);
        return;
    }
''', '', 'BadgeRenderCdecl Racing remap')

repl(r'''        cmp  cx, 0FBh
        jne  not_racing_proxy
        mov  ecx, 0CBh
        jmp  dword ptr [orig_BadgeRender]
    not_racing_proxy:
''', '', 'BadgeRender naked Racing remap')

repl(r'''    if (teamId == RACING_EDIT_REAL_TEAM) {
        SeedRacingProxyIdentityOnce();
        teamId = RACING_EDIT_BACKING_TEAM;
    }
''', '', 'ComputeBadgeSlot Racing remap')

p.write_text(s, encoding='utf-8')
print('Racing EditProxy crash fix applied safely')
