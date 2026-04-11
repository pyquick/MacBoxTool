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