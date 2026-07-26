"""
cpu_data.py: CPU Generation Data
"""

import enum


class CPUGen(enum.IntEnum):
    pentium_4     = 0
    yonah         = 1
    conroe        = 2
    penryn        = 3
    nehalem       = 4    # (Westmere included)
    sandy_bridge  = 5    # 2000
    ivy_bridge    = 6    # 3000
    haswell       = 7    # 4000
    broadwell     = 8    # 5000
    skylake       = 9    # 6000
    kaby_lake     = 10   # 7000
    coffee_lake   = 11   # 8000/9000/10000
    comet_lake    = 12   # 10000
    ice_lake      = 13   # 10000

    apple_dtk     = 100  # A12
    apple_silicon = 101  # A14 and newer (not tracked beyond this point)

    # Not supported for Mac (intel 11000-13000) Support for hackintosh
    rocket_lake   = 14   # 11000
    alder_lake    = 15   # 12000
    raptor_lake   = 16   # 13000
    arrow_lake    = 17

    #AMD
    zen          = 17
    zen2         = 18
    zen3         = 19
    zen4         = 20
    
class CPUMODEL(enum.Enum):
    penryn        = [23]
    nehalem       = [26,30]    
    westmere      = [37]
    sandy_bridge  = [42] 
    sandy_bridge_e  = [45]   
    ivy_bridge      = [58]
    ivy_bridge_e    = [62] 
    haswell       = [60,70]
    haswell_e     = [63] 
    broadwell     = [61]  
    skylake       = [78,94]    
    kaby_lake     = [142,158]
    coffee_lake   = [142,158] 
    comet_lake    = [165,166]  
    ice_lake      = [126]
    rocket_lake   = [167]              # 0xA7
    alder_lake    = [151,154]          # 0x97 (S), 0x9A (L/P)
    raptor_lake   = [183,186,191]      # 0xB7, 0xBA (P), 0xBF (S)
    meteor_lake   = [172,170]          # 0xAC, 0xAA (L)
    arrow_lake    = [197,198,181]      # 0xC5 (H), 0xC6, 0xB5 (U)
    all_intel_ids = [23,26,30,37,42,45,58,62,60,70,63,61,78,94,142,158,165,166,126,
                     167,151,154,183,186,191,172,170,197,198,181]


class CPUGenWin(enum.IntEnum):
    """Maps CPUID display model (Family 6) to CPU generation for Windows detection."""
    # Gen 1 - Nehalem/Westmere
    nehalem       = 26   # 0x1A
    nehalem_2     = 30   # 0x1E
    westmere      = 37   # 0x25
    # Gen 2 - Sandy Bridge
    sandy_bridge   = 42  # 0x2A
    sandy_bridge_e = 45  # 0x2D
    # Gen 3 - Ivy Bridge
    ivy_bridge     = 58  # 0x3A
    ivy_bridge_e   = 62  # 0x3E
    # Gen 4 - Haswell
    haswell       = 60   # 0x3C
    haswell_2     = 70   # 0x46
    haswell_e     = 63   # 0x3F
    # Gen 5 - Broadwell
    broadwell     = 61   # 0x3D
    # Gen 6 - Skylake
    skylake       = 78   # 0x4E
    skylake_2     = 94   # 0x5E
    # Gen 7 - Kaby Lake
    kaby_lake     = 142  # 0x8E
    kaby_lake_2   = 158  # 0x9E
    # Gen 10 - Comet Lake / Ice Lake
    comet_lake    = 165  # 0xA5
    comet_lake_l  = 166  # 0xA6
    ice_lake      = 125  # 0x7D
    ice_lake_l    = 126  # 0x7E
    # Gen 11 - Rocket Lake / Tiger Lake
    rocket_lake   = 167  # 0xA7
    tiger_lake_l  = 140  # 0x8C
    tiger_lake    = 141  # 0x8D
    # Gen 12 - Alder Lake
    alder_lake    = 151  # 0x97
    alder_lake_l  = 154  # 0x9A
    alder_lake_n  = 190  # 0xBE
    # Gen 13 - Raptor Lake (also covers 14th gen refresh)
    raptor_lake   = 183  # 0xB7
    raptor_lake_p = 186  # 0xBA
    raptor_lake_s = 191  # 0xBF
    # Gen 14 - Meteor Lake
    meteor_lake   = 172  # 0xAC
    meteor_lake_l = 170  # 0xAA
    # Gen 15 - Arrow Lake / Lunar Lake
    arrow_lake_h  = 197  # 0xC5
    arrow_lake    = 198  # 0xC6
    arrow_lake_u  = 181  # 0xB5
    lunar_lake_m  = 189  # 0xBD


# CPUID model -> generation number (Intel Core iX-NXXX "N"th gen)
CPUID_MODEL_TO_GEN: dict[int, int] = {
    # Gen 1
    26: 1, 30: 1, 37: 1,
    # Gen 2
    42: 2, 45: 2,
    # Gen 3
    58: 3, 62: 3,
    # Gen 4
    60: 4, 70: 4, 63: 4,
    # Gen 5
    61: 5,
    # Gen 6
    78: 6, 94: 6,
    # Gen 7/8 (Kaby Lake / Coffee Lake share model IDs 142, 158)
    142: 7, 158: 7,
    # Gen 10
    165: 10, 166: 10, 125: 10, 126: 10,
    # Gen 11
    167: 11, 140: 11, 141: 11,
    # Gen 12
    151: 12, 154: 12, 190: 12,
    # Gen 13 (also covers 14th gen Raptor Lake refresh)
    183: 13, 186: 13, 191: 13,
    # Gen 14
    172: 14, 170: 14,
    # Gen 15
    197: 15, 198: 15, 181: 15, 189: 15,
}


# CPUID display model -> CPU microarchitecture. These IDs are shared by macOS
# machdep.cpu.model and Windows Win32_Processor.ProcessorId.
CPUID_MODEL_TO_ARCHITECTURE: dict[int, str] = {
    23: "penryn",
    26: "nehalem", 30: "nehalem", 37: "westmere",
    42: "sandy_bridge", 45: "sandy_bridge_e",
    58: "ivy_bridge", 62: "ivy_bridge_e",
    60: "haswell", 70: "haswell", 63: "haswell_e",
    61: "broadwell",
    78: "skylake", 94: "skylake",
    # Kaby Lake and Coffee Lake use the same display models, so the device ID
    # alone cannot distinguish them.
    142: "kaby_lake_or_coffee_lake", 158: "kaby_lake_or_coffee_lake",
    165: "comet_lake", 166: "comet_lake",
    125: "ice_lake", 126: "ice_lake",
    167: "rocket_lake",
    140: "tiger_lake", 141: "tiger_lake",
    151: "alder_lake", 154: "alder_lake", 190: "alder_lake",
    183: "raptor_lake", 186: "raptor_lake", 191: "raptor_lake",
    172: "meteor_lake", 170: "meteor_lake",
    197: "arrow_lake", 198: "arrow_lake", 181: "arrow_lake",
    189: "lunar_lake",
}

_INTEL_VENDOR_IDS = {"genuineintel", "intel", "intel corporation"}


def architecture_from_device_id(device_id: int | None, vendor_id: str | None = None) -> str | None:
    """Return a CPU microarchitecture for a CPUID display model."""
    if device_id is None:
        return None
    if vendor_id and vendor_id.strip().lower() not in _INTEL_VENDOR_IDS:
        return None
    return CPUID_MODEL_TO_ARCHITECTURE.get(device_id)


# ---------------------------------------------------------------------------
# IGPU PCI device ID tables — used to identify CPU architecture via the
# integrated GPU's PCI device ID.  This disambiguates cases where CPUID
# model alone is not enough (e.g. Kaby Lake vs Coffee Lake both use
# CPUID models 142 / 158 but have different IGPU device IDs).
#
# Intel device IDs are always 4-digit hex (e.g. 0x4668).
# AMD device IDs are also 4-digit hex (e.g. 0x1638).
# ---------------------------------------------------------------------------


class IntelIGPUDeviceIDs:
    """IGPU PCI device IDs for Intel CPUs, grouped by microarchitecture."""

    sandy_bridge = [
        0x0102, 0x0106, 0x010A,
        0x0112, 0x0116, 0x0122, 0x0126,
    ]

    ivy_bridge = [
        0x0152, 0x0156, 0x015A,
        0x0162, 0x0166, 0x016A,
    ]

    haswell = [
        0x0402, 0x0406, 0x040A, 0x040B, 0x040E,
        0x0412, 0x0416, 0x041A, 0x041B, 0x041E,
        0x0422, 0x0426, 0x042A, 0x042B, 0x042E,
        0x0A02, 0x0A06, 0x0A0A, 0x0A0B, 0x0A0E,
        0x0A12, 0x0A16, 0x0A1A, 0x0A1B, 0x0A1E,
        0x0A22, 0x0A26, 0x0A2A, 0x0A2B, 0x0A2E,
        0x0D02, 0x0D06, 0x0D0A, 0x0D0B, 0x0D0E,
        0x0D12, 0x0D16, 0x0D1A, 0x0D1B, 0x0D1E,
        0x0D22, 0x0D26, 0x0D2A, 0x0D2B, 0x0D2E,
    ]

    broadwell = [
        0x1602, 0x1606, 0x160A, 0x160B, 0x160D, 0x160E,
        0x1612, 0x1616, 0x161A, 0x161B, 0x161D, 0x161E,
        0x1622, 0x1626, 0x162A, 0x162B, 0x162D, 0x162E,
        0x0BD1, 0x0BD2, 0x0BD3,
    ]

    skylake = [
        0x1902, 0x1906, 0x190A, 0x190B, 0x190E,
        0x1912, 0x1913, 0x1915, 0x1916, 0x1917, 0x191A, 0x191B, 0x191D, 0x191E,
        0x1921, 0x1923, 0x1926, 0x1927, 0x192A, 0x192B, 0x192D,
        0x1932, 0x193A, 0x193B, 0x193D,
    ]

    kaby_lake = [
        0x5902, 0x5906, 0x5908, 0x590A, 0x590B, 0x590E,
        0x5912, 0x5915, 0x5916, 0x5917, 0x591A, 0x591B, 0x591C, 0x591D, 0x591E,
        0x5921, 0x5923, 0x5926, 0x5927, 0x592A, 0x592B,
        0x87C0, 0x87CA,
    ]

    coffee_lake = [
        0x3E90, 0x3E91, 0x3E92, 0x3E93, 0x3E94,
        0x3E96, 0x3E98, 0x3E99, 0x3E9A, 0x3E9B, 0x3E9C,
        0x3EA0, 0x3EA1, 0x3EA2, 0x3EA3, 0x3EA4,
        0x3EA5, 0x3EA6, 0x3EA7, 0x3EA8, 0x3EA9,
        0x9B21, 0x9B41, 0x9BA0, 0x9BA2, 0x9BA4, 0x9BA5, 0x9BA8,
        0x9BAA, 0x9BAB, 0x9BAC,
    ]

    comet_lake = [
        0x9B21, 0x9B41, 0x9BA0, 0x9BA2, 0x9BA4, 0x9BA5, 0x9BA8,
        0x9BAA, 0x9BAB, 0x9BAC, 0x9BC4, 0x9BC5, 0x9BC8, 0x9BE6,
        0x9BF6,
    ]

    ice_lake = [
        0x8A50, 0x8A51, 0x8A52, 0x8A53, 0x8A54,
        0x8A56, 0x8A57, 0x8A58, 0x8A59, 0x8A5A, 0x8A5B, 0x8A5C, 0x8A5D,
        0x8A70, 0x8A71,
        0xFF05,
    ]

    tiger_lake = [
        0x9A40, 0x9A49, 0x9A59, 0x9A60, 0x9A68, 0x9A70, 0x9A78,
        0x9AC0, 0x9AC9, 0x9AD9, 0x9AF8,
    ]

    rocket_lake = [
        0x4C80, 0x4C8A, 0x4C90, 0x4C9A,
    ]

    alder_lake = [
        0x4680, 0x4682, 0x4688, 0x468A,
        0x4690, 0x4692, 0x4698, 0x469A,
        0x46A0, 0x46A1, 0x46A2, 0x46A3, 0x46A6, 0x46A8, 0x46AA,
        0x46B0, 0x46B1, 0x46B2, 0x46B3,
        0x46C0, 0x46C1, 0x46C2, 0x46C3,
        0x4626, 0x4628, 0x462A,
        0x46D0, 0x46D1, 0x46D2,
    ]

    raptor_lake = [
        0xA780, 0xA781, 0xA782, 0xA783,
        0xA788, 0xA789, 0xA78A, 0xA78B,
        0xA720, 0xA721, 0xA7A0, 0xA7A1, 0xA7A8, 0xA7A9,
    ]

    meteor_lake = [
        0x7D40, 0x7D45, 0x7D55, 0x7D60, 0x7DD5,
    ]

    arrow_lake = [
        0x7D41, 0x7D50, 0x7D67, 0x7D70, 0x7D71, 0x7D51,
    ]

    lunar_lake = [
        0xB080, 0xB081, 0xB082, 0xB083, 0xB084,
        0xB085, 0xB086, 0xB087, 0xB088, 0xB089, 0xB08A,
    ]


_INTEL_IGPU_TO_ARCH: dict[int, str] = {}
for _arch, _ids in [
    ("sandy_bridge",  IntelIGPUDeviceIDs.sandy_bridge),
    ("ivy_bridge",    IntelIGPUDeviceIDs.ivy_bridge),
    ("haswell",       IntelIGPUDeviceIDs.haswell),
    ("broadwell",     IntelIGPUDeviceIDs.broadwell),
    ("skylake",       IntelIGPUDeviceIDs.skylake),
    ("kaby_lake",     IntelIGPUDeviceIDs.kaby_lake),
    ("coffee_lake",   IntelIGPUDeviceIDs.coffee_lake),
    ("comet_lake",    IntelIGPUDeviceIDs.comet_lake),
    ("ice_lake",      IntelIGPUDeviceIDs.ice_lake),
    ("tiger_lake",    IntelIGPUDeviceIDs.tiger_lake),
    ("rocket_lake",   IntelIGPUDeviceIDs.rocket_lake),
    ("alder_lake",    IntelIGPUDeviceIDs.alder_lake),
    ("raptor_lake",   IntelIGPUDeviceIDs.raptor_lake),
    ("meteor_lake",   IntelIGPUDeviceIDs.meteor_lake),
    ("arrow_lake",    IntelIGPUDeviceIDs.arrow_lake),
    ("lunar_lake",    IntelIGPUDeviceIDs.lunar_lake),
]:
    for _id in _ids:
        _INTEL_IGPU_TO_ARCH[_id] = _arch


class AmdIGPUDeviceIDs:
    """IGPU PCI device IDs for AMD APUs, grouped by microarchitecture."""

    raven_ridge    = [0x15DD]            # Zen 1  (Ryzen 2000G)
    picasso        = [0x15D8]            # Zen+   (Ryzen 3000G)
    renoir         = [0x1636]            # Zen 2  (Ryzen 4000G)
    cezanne        = [0x1638, 0x1640]    # Zen 3  (Ryzen 5000G)
    rembrandt      = [0x1681]            # Zen 3+ (Ryzen 6000)
    mendocino      = [0x1506]            # Zen 2  (Ryzen 7020)
    phoenix        = [0x15BF]            # Zen 4  (Ryzen 7040/8000)
    dragon_range   = [0x164E]            # Zen 4  (Ryzen 7045)
    raphael        = [0x164E]            # Zen 4  (Ryzen 7000 desktop)
    strix_point    = [0x150E]            # Zen 5  (Ryzen AI 300)


_AMD_IGPU_TO_ARCH: dict[int, str] = {}
for _arch, _ids in [
    ("zen",           AmdIGPUDeviceIDs.raven_ridge),
    ("zen_plus",      AmdIGPUDeviceIDs.picasso),
    ("zen2",          AmdIGPUDeviceIDs.renoir),
    ("zen3",          AmdIGPUDeviceIDs.cezanne),
    ("zen3_plus",     AmdIGPUDeviceIDs.rembrandt),
    ("zen2",          AmdIGPUDeviceIDs.mendocino),
    ("zen4",          AmdIGPUDeviceIDs.phoenix),
    ("zen4",          AmdIGPUDeviceIDs.dragon_range),
    ("zen4",          AmdIGPUDeviceIDs.raphael),
    ("zen5",          AmdIGPUDeviceIDs.strix_point),
]:
    for _id in _ids:
        _AMD_IGPU_TO_ARCH[_id] = _arch


_INTEL_IGPU_VENDOR = "0x8086"
_AMD_IGPU_VENDOR  = "0x1002"


def architecture_from_igpu_device_id(igpu_device_id: int, vendor_id: str) -> str | None:
    """Return CPU microarchitecture inferred from the IGPU PCI device ID.

    Args:
        igpu_device_id: IGPU PCI device ID (16-bit integer).
        vendor_id: PCI vendor ID string (e.g. '0x8086' for Intel, '0x1002' for AMD).

    Returns:
        Microarchitecture string (e.g. 'alder_lake', 'zen3') or None.
    """
    if not igpu_device_id or not vendor_id:
        return None
    vid = vendor_id.strip().lower()
    if vid == _INTEL_IGPU_VENDOR:
        return _INTEL_IGPU_TO_ARCH.get(igpu_device_id)
    if vid == _AMD_IGPU_VENDOR:
        return _AMD_IGPU_TO_ARCH.get(igpu_device_id)
    return None
