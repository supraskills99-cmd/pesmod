// SPDX-License-Identifier: GPL-3.0-or-later
//
// Thin build wrapper around club_hooks_kit_data.cpp.
//
// The stock custom-kit loader intentionally synthesises Extra-B/Extra-C as
// zero-filled buffers. That is safe for unknown team IDs, but it is wrong for
// custom teams that still live inside PES6's native club-kit ranges (for
// example team 251 / 0xFB): those teams already have a real 0x220-byte native
// kit record whose Extra-C +0x03 byte selects the kit graphics resource.
// Replacing that descriptor with zero prevents the normal graphics/Kitserver
// path from seeing the native resource/layout.
//
// Keep the custom INI override for the colour/model block (GetTeamKitData),
// but for Extra-B/Extra-C prefer the native descriptor whenever the game's
// native resolver returns a genuinely readable block. Unknown/out-of-range
// custom teams still fall back to PESMod's synthetic zero buffers, preserving
// the existing NULL/crash protection.

#include <windows.h>
#include <cstdint>

// Compile the existing implementation in this translation unit, but rename
// only the two descriptor hooks so we can provide corrected public versions
// below without duplicating the large kit-data source file.
#define hook_GetTeamKitDataB hook_GetTeamKitDataB_ZeroExtraLegacy
#define hook_GetTeamKitDataC hook_GetTeamKitDataC_ZeroExtraLegacy
#include "club_hooks_kit_data.cpp"
#undef hook_GetTeamKitDataB
#undef hook_GetTeamKitDataC

namespace {

bool IsReadableKitDescriptor(const uint8_t* ptr, size_t bytes)
{
    if (!ptr || bytes == 0)
        return false;

    MEMORY_BASIC_INFORMATION mbi{};
    if (VirtualQuery(ptr, &mbi, sizeof(mbi)) != sizeof(mbi))
        return false;
    if (mbi.State != MEM_COMMIT)
        return false;

    const DWORD protect = mbi.Protect;
    if ((protect & PAGE_GUARD) != 0 || (protect & PAGE_NOACCESS) != 0)
        return false;

    const uintptr_t start = reinterpret_cast<uintptr_t>(ptr);
    const uintptr_t regionStart = reinterpret_cast<uintptr_t>(mbi.BaseAddress);
    const uintptr_t regionEnd = regionStart + mbi.RegionSize;
    if (start < regionStart || start > regionEnd)
        return false;
    if (bytes > regionEnd - start)
        return false;

    return true;
}

void LogNativeExtraCOnce(uint16_t teamID, int variant, uint8_t* ptr)
{
    if (teamID >= 256 || variant < 0 || variant >= 4 || !ptr)
        return;

    static bool logged[256][4] = {};
    if (logged[teamID][variant])
        return;
    logged[teamID][variant] = true;

    Logger::Log("[KitNativeDescriptor] team=%u variant=%d extraC=%p graphic=%u",
                static_cast<unsigned>(teamID), variant, ptr,
                static_cast<unsigned>(ptr[3]));
}

} // namespace

uint8_t* __cdecl hook_GetTeamKitDataB(uint16_t teamID, int variant)
{
    // A native team such as 251 already owns a valid Extra-B descriptor.
    // Preserve it even when kits/<id>.ini overrides the colour/model block.
    uint8_t* native = RE_GetTeamKitDataB(teamID, variant);
    if (IsReadableKitDescriptor(native, KIT_EXTRA_B_RECORD_SIZE))
        return native;

    // Truly custom/out-of-range IDs have no native descriptor. Retain the
    // existing synthetic buffer behaviour for those IDs so downstream hooks
    // still receive safe memory instead of a wild game pointer.
    return TryLoadCustomKitExtraB(teamID, variant);
}

uint8_t* __cdecl hook_GetTeamKitDataC(uint16_t teamID, int variant)
{
    // Extra-C +0x03 is the kit-graphics selector. For native-range custom
    // teams, this byte must come from PES6's real 0x220-byte team record so
    // the graphics/Kitserver pipeline keeps the correct resource and UV/layout.
    uint8_t* native = RE_GetTeamKitDataC(teamID, variant);
    if (IsReadableKitDescriptor(native, KIT_EXTRA_C_RECORD_SIZE)) {
        LogNativeExtraCOnce(teamID, variant, native);
        return native;
    }

    // Unknown IDs have no native Extra-C. Fall back to the original safe
    // zero-filled descriptor supplied by the custom-kit cache.
    return TryLoadCustomKitExtraC(teamID, variant);
}
