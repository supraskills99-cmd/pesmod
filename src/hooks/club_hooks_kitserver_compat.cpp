// SPDX-License-Identifier: GPL-3.0-or-later
//
// Kitserver 6 compatibility layer for PESMod.
//
// Kitserver 6 (kserv.dll) hooks the same PES6 kit pipeline that PESMod
// extends. PESMod's kits/<teamID>.ini loader normally has priority over the
// game's native kit descriptors. That is useful when PESMod owns the kit,
// but it prevents Kserv from seeing the native descriptor/kit-pack state it
// expects for GDB teams such as custom team 251.
//
// This translation unit compiles the existing implementation unchanged, but
// renames its three central kit-data hooks. We then expose compatibility-aware
// versions with the original public names:
//   - with kserv.dll loaded, prefer PES6 native kit data whenever the team ID
//     has a real native record (this includes the special club band 0xDD..0xFD,
//     so IDs 250/251 are covered);
//   - otherwise fall back to PESMod's existing INI-first safe implementation.
//
// Result: Kitserver owns graphical kits while PESMod keeps leagues, squads,
// emblems and its NULL/crash protection for truly unknown IDs. If Kitserver
// is not installed/loaded, behaviour is identical to the previous build.

#define hook_GetTeamKitData  hook_GetTeamKitData_PESModLegacy
#define hook_GetTeamKitDataB hook_GetTeamKitDataB_PESModLegacy
#define hook_GetTeamKitDataC hook_GetTeamKitDataC_PESModLegacy
#include "club_hooks_kit_data.cpp"
#undef hook_GetTeamKitData
#undef hook_GetTeamKitDataB
#undef hook_GetTeamKitDataC

namespace {

bool IsKitserver6Loaded()
{
    return GetModuleHandleA("kserv.dll") != nullptr;
}

void LogKitserverNativeOnce(uint16_t teamID)
{
    if (teamID >= 256)
        return;

    static bool logged[256] = {};
    if (logged[teamID])
        return;

    logged[teamID] = true;
    Logger::Log("[KitserverCompat] kserv.dll detected: team=%u uses native PES6 kit descriptors before PESMod INI overrides",
                static_cast<unsigned>(teamID));
}

} // namespace

uint8_t* __cdecl hook_GetTeamKitData(uint16_t teamID, int variant)
{
    if (IsKitserver6Loaded()) {
        if (uint8_t* native = RE_GetTeamKitData(teamID, variant)) {
            LogKitserverNativeOnce(teamID);
            return native;
        }
    }

    return hook_GetTeamKitData_PESModLegacy(teamID, variant);
}

uint8_t* __cdecl hook_GetTeamKitDataB(uint16_t teamID, int variant)
{
    if (IsKitserver6Loaded()) {
        if (uint8_t* native = RE_GetTeamKitDataB(teamID, variant)) {
            LogKitserverNativeOnce(teamID);
            return native;
        }
    }

    return hook_GetTeamKitDataB_PESModLegacy(teamID, variant);
}

uint8_t* __cdecl hook_GetTeamKitDataC(uint16_t teamID, int variant)
{
    if (IsKitserver6Loaded()) {
        if (uint8_t* native = RE_GetTeamKitDataC(teamID, variant)) {
            LogKitserverNativeOnce(teamID);
            return native;
        }
    }

    return hook_GetTeamKitDataC_PESModLegacy(teamID, variant);
}
