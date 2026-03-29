"""
compatibility_data.py: Hardware compatibility database for EFI building
"""

# Unsupported CPU generations for different macOS versions
MACOS_CPU_REQUIREMENTS = {
    13: "haswell",  # macOS 13+ requires AVX2 (Haswell or newer)
    12: "ivy_bridge",
    11: "sandy_bridge",
}

# Problematic NVMe SSDs that cause kernel panics
PROBLEMATIC_NVME = [
    "Samsung PM981",
    "Samsung PM991",
    "Micron 2200S",
    "Intel Optane",
]

# GPU compatibility info
UNSUPPORTED_GPUS = {
    "nvidia_turing": {
        "models": ["RTX 20", "RTX 2060", "RTX 2070", "RTX 2080"],
        "max_macos": None,
        "message": "No macOS driver available"
    },
    "nvidia_ampere": {
        "models": ["RTX 30", "RTX 3060", "RTX 3070", "RTX 3080", "RTX 3090"],
        "max_macos": None,
        "message": "No macOS driver available"
    },
    "nvidia_ada": {
        "models": ["RTX 40", "RTX 4060", "RTX 4070", "RTX 4080", "RTX 4090"],
        "max_macos": None,
        "message": "No macOS driver available"
    },
    "nvidia_maxwell": {
        "models": ["GTX 9", "GTX 950", "GTX 960", "GTX 970", "GTX 980"],
        "max_macos": "10.14",
        "message": "Maximum macOS 10.14 Mojave"
    },
    "nvidia_pascal": {
        "models": ["GTX 10", "GTX 1050", "GTX 1060", "GTX 1070", "GTX 1080"],
        "max_macos": "10.14",
        "message": "Maximum macOS 10.14 Mojave"
    },
    "intel_arc": {
        "models": ["Arc", "A770", "A750", "A380"],
        "max_macos": None,
        "message": "No macOS driver available"
    },
}

# Network card workarounds
NETWORK_WORKAROUNDS = {
    "intel_i225v": {
        "needs_device_id_spoof": True,
        "kext": None,
        "message": "Requires device-id spoofing to F2150000"
    },
    "intel_wifi": {
        "needs_device_id_spoof": False,
        "kext": ["AirportItlwm", "IntelBluetoothFirmware"],
        "message": "Requires third-party kexts (non-native)"
    },
}

# ============================================================================
# NEW COMPATIBILITY DATABASE (Dortania-based)
# ============================================================================

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class CompatStatus(Enum):
    """Compatibility status levels"""
    SUPPORTED = "supported"
    PARTIAL = "partial"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


@dataclass
class CompatResult:
    """Result of a compatibility check"""
    status: CompatStatus
    message: str
    max_macos: Optional[str] = None
    min_macos: Optional[str] = None
    notes: list[str] = field(default_factory=list)
    kexts_needed: list[str] = field(default_factory=list)


# CPU compatibility database (based on Dortania GPU Buyers Guide)
CPU_COMPAT = {
    # Intel Nehalem and later (all supported)
    "nehalem": {
        "max_macos": "10.15",
        "min_macos": "10.5",
        "notes": ["64-bit only", "No Metal support on 10.14+"],
        "kexts_needed": [],
    },
    "westmere": {
        "max_macos": "10.15",
        "min_macos": "10.6",
        "notes": ["64-bit only", "No Metal support on 10.14+"],
        "kexts_needed": [],
    },
    "sandy_bridge": {
        "max_macos": "12.6",
        "min_macos": "10.7",
        "notes": ["Supported up to Monterey", "Full Metal support"],
        "kexts_needed": [],
    },
    "ivy_bridge": {
        "max_macos": "13.6",
        "min_macos": "10.8",
        "notes": ["Supported up to Ventura", "Full Metal support"],
        "kexts_needed": [],
    },
    "haswell": {
        "max_macos": "14.6",
        "min_macos": "10.9",
        "notes": ["Supported up to Sonoma", "Full Metal support"],
        "kexts_needed": [],
    },
    "broadwell": {
        "max_macos": "14.6",
        "min_macos": "10.10",
        "notes": ["Supported up to Sonoma", "Full Metal support"],
        "kexts_needed": [],
    },
    "skylake": {
        "max_macos": "14.6",
        "min_macos": "10.11",
        "notes": ["Supported up to Sonoma", "Full Metal support"],
        "kexts_needed": [],
    },
    "kaby_lake": {
        "max_macos": "14.6",
        "min_macos": "10.12",
        "notes": ["Supported up to Sonoma", "Full Metal support"],
        "kexts_needed": [],
    },
    "coffee_lake": {
        "max_macos": "15.0",
        "min_macos": "10.13",
        "notes": ["Supported up to Sequoia", "Full Metal support"],
        "kexts_needed": [],
    },
    "whiskey_lake": {
        "max_macos": "15.0",
        "min_macos": "10.14",
        "notes": ["Supported up to Sequoia", "Full Metal support"],
        "kexts_needed": [],
    },
    "comet_lake": {
        "max_macos": "15.0",
        "min_macos": "10.15",
        "notes": ["Supported up to Sequoia", "Full Metal support"],
        "kexts_needed": [],
    },
    "ice_lake": {
        "max_macos": "15.0",
        "min_macos": "10.15",
        "notes": ["Supported up to Sequoia", "Full Metal support"],
        "kexts_needed": [],
    },
    "rocket_lake": {
        "max_macos": "15.0",
        "min_macos": "11.3",
        "notes": ["Supported up to Sequoia", "Full Metal support"],
        "kexts_needed": [],
    },
    "alder_lake": {
        "max_macos": "15.0",
        "min_macos": "12.0",
        "notes": ["Supported up to Sequoia", "Full Metal support", "Requires macOS 12+"],
        "kexts_needed": [],
    },
    "raptor_lake": {
        "max_macos": "15.0",
        "min_macos": "13.0",
        "notes": ["Supported up to Sequoia", "Full Metal support", "Requires macOS 13+"],
        "kexts_needed": [],
    },
    # Intel HEDT
    "ivy_bridge_e": {
        "max_macos": "12.6",
        "min_macos": "10.9",
        "notes": ["X79/X99 chipset", "Supported up to Monterey"],
        "kexts_needed": [],
    },
    "haswell_e": {
        "max_macos": "12.6",
        "min_macos": "10.10",
        "notes": ["X99 chipset", "Supported up to Monterey"],
        "kexts_needed": [],
    },
    "broadwell_e": {
        "max_macos": "13.6",
        "min_macos": "10.11",
        "notes": ["X99 chipset", "Supported up to Ventura"],
        "kexts_needed": [],
    },
    "skylake_x": {
        "max_macos": "14.6",
        "min_macos": "10.13",
        "notes": ["X299 chipset", "Supported up to Sonoma", "Requires -lilubetaall for early macOS"],
        "kexts_needed": [],
    },
    # AMD
    "bulldozer": {
        "max_macos": "10.15",
        "min_macos": "10.8",
        "notes": ["FX series", "Limited GPU acceleration", "Use AppleMCEReporterDisabler"],
        "kexts_needed": ["AppleMCEReporterDisabler"],
    },
    "piledriver": {
        "max_macos": "10.15",
        "min_macos": "10.8",
        "notes": ["FX series", "Limited GPU acceleration", "Use AppleMCEReporterDisabler"],
        "kexts_needed": ["AppleMCEReporterDisabler"],
    },
    "steamroller": {
        "max_macos": "10.15",
        "min_macos": "10.10",
        "notes": ["AMD A-series", "Limited GPU acceleration", "Use AppleMCEReporterDisabler"],
        "kexts_needed": ["AppleMCEReporterDisabler"],
    },
    "excavator": {
        "max_macos": "12.6",
        "min_macos": "10.11",
        "notes": ["AMD A-series", "Use AppleMCEReporterDisabler"],
        "kexts_needed": ["AppleMCEReporterDisabler"],
    },
    "zen": {
        "max_macos": "14.6",
        "min_macos": "10.13",
        "notes": ["Ryzen 1000/2000 series", "Full support", "SSDT-CPUR recommended for B550/A520"],
        "kexts_needed": ["AppleMCEReporterDisabler"],
    },
    "zen2": {
        "max_macos": "15.0",
        "min_macos": "10.15",
        "notes": ["Ryzen 3000/4000 series", "Full support", "SSDT-CPUR recommended for B550/A520"],
        "kexts_needed": ["AppleMCEReporterDisabler"],
    },
    "zen3": {
        "max_macos": "15.0",
        "min_macos": "11.3",
        "notes": ["Ryzen 5000 series", "Full support", "SSDT-CPUR recommended for B550/A520"],
        "kexts_needed": ["AppleMCEReporterDisabler"],
    },
    "zen4": {
        "max_macos": "15.0",
        "min_macos": "13.0",
        "notes": ["Ryzen 7000 series", "Full support", "Requires macOS 13+", "SSDT-CPUR recommended for B550/A520"],
        "kexts_needed": ["AppleMCEReporterDisabler"],
    },
}

# GPU families database (based on Dortania GPU Buyers Guide)
GPU_FAMILIES = {
    # AMD GPU families
    "amd_tera_scale": {
        "max_macos": "10.14",
        "min_macos": "10.4",
        "notes": ["Radeon HD 2000-4000 series", "No Metal support on 10.14+"],
        "kexts_needed": [],
        "models": ["Radeon HD 2", "Radeon HD 3", "Radeon HD 4"],
    },
    "amd_tera_scale_2": {
        "max_macos": "10.15",
        "min_macos": "10.7",
        "notes": ["Radeon HD 5000-6000 series", "No Metal support on 10.15"],
        "kexts_needed": [],
        "models": ["Radeon HD 5", "Radeon HD 6"],
    },
    "amd_gcn_1": {
        "max_macos": "12.6",
        "min_macos": "10.10",
        "notes": ["Radeon HD 7000, R7, R9 200 series", "Pitcairn, Tahiti, Hawaii"],
        "kexts_needed": [],
        "models": ["Radeon HD 7", "R7 2", "R9 2"],
    },
    "amd_gcn_2": {
        "max_macos": "14.6",
        "min_macos": "10.11",
        "notes": ["R9 300 series, R9 Fury, R9 Nano", "Tonga, Fiji"],
        "kexts_needed": [],
        "models": ["R9 3", "R9 Fury", "R9 Nano"],
    },
    "amd_gcn_3": {
        "max_macos": "14.6",
        "min_macos": "10.12",
        "notes": ["RX 400/500 series, RX Vega", "Polaris"],
        "kexts_needed": [],
        "models": ["RX 4", "RX 5", "RX Vega"],
    },
    "amd_gcn_4": {
        "max_macos": "14.6",
        "min_macos": "10.13",
        "notes": ["RX 5500/5600/5700 series", "Navi"],
        "kexts_needed": [],
        "models": ["RX 55", "RX 56", "RX 57"],
    },
    "amd_rdn2": {
        "max_macos": "15.0",
        "min_macos": "12.0",
        "notes": ["RX 6600/6700/6800/6900 series", "RDNA2", "Requires macOS 12+"],
        "kexts_needed": [],
        "models": ["RX 66", "RX 67", "RX 68", "RX 69"],
    },
    "amd_rdn3": {
        "max_macos": "15.0",
        "min_macos": "14.0",
        "notes": ["RX 7600/7700/7800/7900 series", "RDNA3", "Requires macOS 14+"],
        "kexts_needed": [],
        "models": ["RX 76", "RX 77", "RX 78", "RX 79"],
    },
    # NVIDIA GPU families
    "nvidia_tesla": {
        "max_macos": "10.13",
        "min_macos": "10.4",
        "notes": ["GeForce 8000-9000 series", "No Metal support"],
        "kexts_needed": [],
        "models": ["GeForce 8", "GeForce 9"],
    },
    "nvidia_fermi": {
        "max_macos": "10.13",
        "min_macos": "10.6",
        "notes": ["GeForce 400-500 series", "No Metal support"],
        "kexts_needed": [],
        "models": ["GeForce 4", "GeForce 5"],
    },
    "nvidia_kepler": {
        "max_macos": "10.14",
        "min_macos": "10.8",
        "notes": ["GeForce 600-900 series", "Max Mojave", "Native driver"],
        "kexts_needed": [],
        "models": ["GeForce 6", "GeForce 7", "GeForce 8", "GeForce 9"],
    },
    "nvidia_maxwell": {
        "max_macos": "10.14",
        "min_macos": "10.11",
        "notes": ["GTX 900 series", "Max Mojave", "Web driver required"],
        "kexts_needed": ["GeForceWeb"],
        "models": ["GTX 9"],
    },
    "nvidia_pascal": {
        "max_macos": "10.14",
        "min_macos": "10.12",
        "notes": ["GTX 10 series", "Max Mojave", "Web driver required"],
        "kexts_needed": ["GeForceWeb"],
        "models": ["GTX 10"],
    },
    "nvidia_turing": {
        "max_macos": None,
        "min_macos": None,
        "notes": ["RTX 20 series", "No macOS support", "Requires eGPU or alternative"],
        "kexts_needed": [],
        "models": ["RTX 20"],
    },
    "nvidia_ampere": {
        "max_macos": None,
        "min_macos": None,
        "notes": ["RTX 30 series", "No macOS support", "Requires eGPU or alternative"],
        "kexts_needed": [],
        "models": ["RTX 30"],
    },
    "nvidia_ada": {
        "max_macos": None,
        "min_macos": None,
        "notes": ["RTX 40 series", "No macOS support", "Requires eGPU or alternative"],
        "kexts_needed": [],
        "models": ["RTX 40"],
    },
    # Intel iGPU
    "intel_hd": {
        "max_macos": "10.15",
        "min_macos": "10.6",
        "notes": ["HD Graphics 2000-4000", "Sandy/Ivy Bridge iGPU"],
        "kexts_needed": [],
        "models": ["HD Graphics 2", "HD Graphics 3"],
    },
    "intel_hd_5000": {
        "max_macos": "12.6",
        "min_macos": "10.9",
        "notes": ["HD Graphics 5000-6000", "Haswell/Broadwell iGPU"],
        "kexts_needed": [],
        "models": ["HD Graphics 5", "HD Graphics 6"],
    },
    "intel_hd_6000": {
        "max_macos": "13.6",
        "min_macos": "10.11",
        "notes": ["Iris Pro 6200", "Skylake iGPU"],
        "kexts_needed": [],
        "models": ["Iris Pro 6"],
    },
    "intel_uhd": {
        "max_macos": "14.6",
        "min_macos": "10.12",
        "notes": ["UHD Graphics 600-700", "Kaby Lake+ iGPU"],
        "kexts_needed": [],
        "models": ["UHD Graphics"],
    },
    "intel_iris_plus": {
        "max_macos": "14.6",
        "min_macos": "10.13",
        "notes": ["Iris Plus Graphics 640-655", "Kaby Lake iGPU"],
        "kexts_needed": [],
        "models": ["Iris Plus"],
    },
    "intel_iris_xe": {
        "max_macos": "15.0",
        "min_macos": "11.4",
        "notes": ["Iris Xe Graphics", "Tiger Lake iGPU", "Requires macOS 11.4+"],
        "kexts_needed": [],
        "models": ["Iris Xe"],
    },
    "intel_arc": {
        "max_macos": None,
        "min_macos": None,
        "notes": ["Intel Arc Graphics", "No macOS support", "Requires eGPU or alternative"],
        "kexts_needed": [],
        "models": ["Arc"],
    },
}


class CompatibilityChecker:
    """Hardware compatibility checker based on Dortania guide"""

    # CPU generation patterns for detection
    CPU_PATTERNS = {
        "raptor_lake": ["raptor lake", "i9-13900", "i7-13700", "i5-13600", "i5-13400"],
        "alder_lake": ["alder lake", "i9-12900", "i7-12700", "i5-12600", "i5-12400"],
        "rocket_lake": ["rocket lake", "i9-11900", "i7-11700", "i5-11600", "i5-11400"],
        "ice_lake": ["ice lake", "i7-1065g7", "i5-1035g", "i3-1005g"],
        "comet_lake": ["comet lake", "i9-10900", "i7-10700", "i5-10400", "i3-10100"],
        "whiskey_lake": ["whiskey lake", "i7-8565u", "i5-8265u"],
        "coffee_lake": ["coffee lake", "i9-9900", "i7-9700", "i5-9600", "i5-9400", "i3-9100"],
        "kaby_lake": ["kaby lake", "i7-7700", "i5-7600", "i5-7500", "i3-7100"],
        "skylake": ["skylake", "i7-6700", "i5-6600", "i5-6500", "i3-6100"],
        "broadwell": ["broadwell", "i7-5775", "i5-5675", "i7-5700", "i5-5600"],
        "haswell": ["haswell", "i7-4790", "i5-4690", "i5-4590", "i3-4150"],
        "ivy_bridge": ["ivy bridge", "i7-3770", "i5-3570", "i5-3470", "i3-3220"],
        "sandy_bridge": ["sandy bridge", "i7-2600", "i5-2500", "i5-2400", "i3-2100"],
        "westmere": ["westmere", "i7-970", "i5-650", "i5-660"],
        "nehalem": ["nehalem", "i7-920", "i7-950", "i5-750"],
        # HEDT
        "skylake_x": ["skylake-x", "i9-7900", "i7-7800", "i7-7820"],
        "broadwell_e": ["broadwell-e", "i7-5960", "i7-6950"],
        "haswell_e": ["haswell-e", "i7-5960x", "i7-6950x"],
        "ivy_bridge_e": ["ivy bridge-e", "i7-4960", "i7-4930"],
        # AMD
        "zen4": ["zen 4", "ryzen 7 7700", "ryzen 5 7600", "ryzen 9 7900"],
        "zen3": ["zen 3", "ryzen 7 5800", "ryzen 5 5600", "ryzen 9 5900"],
        "zen2": ["zen 2", "ryzen 7 3800", "ryzen 5 3600", "ryzen 9 3900"],
        "zen": ["zen", "ryzen 7 2700", "ryzen 5 2600", "ryzen 7 1800"],
        "excavator": ["excavator", "a10-7890k", "a8-7670k"],
        "steamroller": ["steamroller", "a10-7850k", "a8-7600"],
        "piledriver": ["piledriver", "fx-8350", "fx-8370", "fx-6300"],
        "bulldozer": ["bulldozer", "fx-8120", "fx-8150", "fx-4100"],
    }

    # GPU family patterns for detection
    GPU_PATTERNS = {
        # AMD
        "amd_rdn3": ["rx 7600", "rx 7700", "rx 7800", "rx 7900", "radeon rx 7"],
        "amd_rdn2": ["rx 6600", "rx 6700", "rx 6800", "rx 6900", "radeon rx 6"],
        "amd_gcn_4": ["rx 5500", "rx 5600", "rx 5700", "radeon rx 5", "radeon vii"],
        "amd_gcn_3": ["rx 470", "rx 480", "rx 570", "rx 580", "rx 590", "rx vega"],
        "amd_gcn_2": ["r9 390", "r9 380", "r9 fury", "r9 nano", "fiji"],
        "amd_gcn_1": ["r9 290", "r9 280", "r7 370", "r7 360", "hd 7950", "hd 7970"],
        "amd_tera_scale_2": ["hd 5870", "hd 6970", "hd 6770", "hd 5870"],
        "amd_tera_scale": ["hd 4870", "hd 5850", "hd 4870", "hd 3850"],
        # NVIDIA
        "nvidia_ada": ["rtx 4060", "rtx 4070", "rtx 4080", "rtx 4090"],
        "nvidia_ampere": ["rtx 3060", "rtx 3070", "rtx 3080", "rtx 3090"],
        "nvidia_turing": ["rtx 2060", "rtx 2070", "rtx 2080", "gtx 1660", "gtx 1650"],
        "nvidia_pascal": ["gtx 1080", "gtx 1070", "gtx 1060", "gtx 1050"],
        "nvidia_maxwell": ["gtx 980", "gtx 970", "gtx 960", "gtx 950"],
        "nvidia_kepler": ["gtx 780", "gtx 770", "gtx 680", "gtx 670"],
        "nvidia_fermi": ["gtx 580", "gtx 570", "gtx 560", "gtx 480"],
        "nvidia_tesla": ["gtx 280", "gtx 260", "8800 gtx", "9800 gtx"],
        # Intel
        "intel_arc": ["arc a770", "arc a750", "arc a380", "intel arc", "arc b580", "arc b570", "battlemage", "intel arc b",
                      "a770", "a750", "a380", "b580", "b570"],
        "intel_iris_xe": ["iris xe", "xe graphics", "intel uhd graphics (12th"],
        "intel_iris_plus": ["iris plus", "iris 645", "iris 655"],
        "intel_uhd": ["uhd graphics 620", "uhd graphics 630", "intel uhd"],
        "intel_hd_6000": ["iris pro 6200", "hd graphics 530"],
        "intel_hd_5000": ["hd graphics 5000", "hd graphics 5500", "hd graphics 6000"],
        "intel_hd": ["hd graphics 3000", "hd graphics 4000", "hd graphics 2500"],
    }

    @classmethod
    def _detect_cpu_generation(cls, cpu_name: str, vendor: str = "intel") -> str:
        """Detect CPU generation from CPU name string"""
        if not cpu_name:
            return "unknown"

        cpu_lower = cpu_name.lower()

        # AMD detection
        if vendor.lower() == "amd":
            for gen, patterns in cls.CPU_PATTERNS.items():
                if any(p in cpu_lower for p in patterns):
                    return gen
            # Check for generic AMD patterns
            if "ryzen 7" in cpu_lower or "ryzen 9" in cpu_lower:
                return "zen"
            if "fx" in cpu_lower:
                return "bulldozer"
            return "unknown"

        # Intel detection
        for gen, patterns in cls.CPU_PATTERNS.items():
            if any(p in cpu_lower for p in patterns):
                return gen

        # Fallback: try to detect from name patterns
        if "i9" in cpu_name:
            if "13" in cpu_name or "14" in cpu_name:
                return "raptor_lake"
            if "12" in cpu_name:
                return "alder_lake"
            return "rocket_lake"
        if "i7" in cpu_name:
            if "12" in cpu_name:
                return "alder_lake"
            if "10" in cpu_name or "11" in cpu_name:
                return "rocket_lake"
            if "8" in cpu_name or "9" in cpu_name:
                return "coffee_lake"
        if "i5" in cpu_name:
            if "12" in cpu_name:
                return "alder_lake"
            if "10" in cpu_name or "11" in cpu_name:
                return "rocket_lake"
            if "8" in cpu_name or "9" in cpu_name:
                return "coffee_lake"
        if "i3" in cpu_name:
            if "10" in cpu_name or "11" in cpu_name or "12" in cpu_name:
                return "comet_lake"
            if "8" in cpu_name or "9" in cpu_name:
                return "coffee_lake"

        return "unknown"

    @classmethod
    def _detect_gpu_family(cls, gpu_name: str) -> str:
        """Detect GPU family from GPU name string"""
        if not gpu_name:
            return "unknown"

        gpu_lower = gpu_name.lower()

        # Intel Arc standalone model numbers (B580, B570, A770, A750, A380) - before vendor checks
        if any(x in gpu_lower for x in ["a770", "a750", "a380", "b580", "b570"]):
            return "intel_arc"

        for family, patterns in cls.GPU_PATTERNS.items():
            if any(p in gpu_lower for p in patterns):
                return family

        # Additional pattern matching for common GPUs
        if "amd" in gpu_lower or "radeon" in gpu_lower:
            if "rx 7" in gpu_lower:
                return "amd_rdn3"
            if "rx 6" in gpu_lower:
                return "amd_rdn2"
            if "rx 5" in gpu_lower:
                return "amd_gcn_4"
            if "rx vega" in gpu_lower or "vega" in gpu_lower:
                return "amd_gcn_3"
            if "fury" in gpu_lower or "fiji" in gpu_lower:
                return "amd_gcn_2"
            return "amd_gcn_1"

        if "nvidia" in gpu_lower or "geforce" in gpu_lower or "gtx" in gpu_lower:
            if "rtx 40" in gpu_lower:
                return "nvidia_ada"
            if "rtx 30" in gpu_lower:
                return "nvidia_ampere"
            if "rtx 20" in gpu_lower:
                return "nvidia_turing"
            if "gtx 10" in gpu_lower:
                return "nvidia_pascal"
            if "gtx 9" in gpu_lower:
                return "nvidia_maxwell"
            if "gtx 7" in gpu_lower or "gtx 6" in gpu_lower:
                return "nvidia_kepler"
            if "gtx 5" in gpu_lower:
                return "nvidia_fermi"

        if "intel" in gpu_lower:
            if "arc" in gpu_lower or any(x in gpu_lower for x in ["a770", "a750", "a380", "b580", "b570"]):
                return "intel_arc"
            if "xe" in gpu_lower or "iris xe" in gpu_lower:
                return "intel_iris_xe"
            if "iris plus" in gpu_lower:
                return "intel_iris_plus"
            if "uhd" in gpu_lower:
                return "intel_uhd"
            if "hd graphics" in gpu_lower:
                if any(x in gpu_lower for x in ["530", "630"]):
                    return "intel_hd_6000"
                if any(x in gpu_lower for x in ["4000", "5000", "5500"]):
                    return "intel_hd_5000"
                return "intel_hd"

        return "unknown"

    @classmethod
    def check_cpu(cls, cpu_info) -> CompatResult:
        """
        Check CPU compatibility

        Args:
            cpu_info: CpuInfo object with name, vendor, generation attributes

        Returns:
            CompatResult with compatibility information
        """
        cpu_name = getattr(cpu_info, "name", "") or ""
        vendor = getattr(cpu_info, "vendor", "intel") or "intel"
        generation = getattr(cpu_info, "generation", None)

        # Use provided generation or detect
        if not generation:
            generation = cls._detect_cpu_generation(cpu_name, vendor)

        if generation == "unknown" or generation not in CPU_COMPAT:
            return CompatResult(
                status=CompatStatus.UNKNOWN,
                message=f"Unknown CPU: {cpu_name}",
                max_macos=None,
                min_macos=None,
                notes=["CPU generation could not be determined"],
                kexts_needed=[],
            )

        cpu_data = CPU_COMPAT[generation]

        # Determine status based on max macOS
        max_macos = cpu_data.get("max_macos")
        if max_macos:
            status = CompatStatus.SUPPORTED
            message = f"CPU generation {generation} is supported (max macOS {max_macos})"
        else:
            status = CompatStatus.UNSUPPORTED
            message = f"CPU generation {generation} is not supported"

        return CompatResult(
            status=status,
            message=message,
            max_macos=max_macos,
            min_macos=cpu_data.get("min_macos"),
            notes=cpu_data.get("notes", []),
            kexts_needed=cpu_data.get("kexts_needed", []),
        )

    @classmethod
    def check_gpu(cls, gpu_info) -> CompatResult:
        """
        Check GPU compatibility

        Args:
            gpu_info: GpuInfo object with name attribute

        Returns:
            CompatResult with compatibility information
        """
        gpu_name = getattr(gpu_info, "name", "") or ""

        # Detect GPU family
        family = cls._detect_gpu_family(gpu_name)

        if family == "unknown" or family not in GPU_FAMILIES:
            return CompatResult(
                status=CompatStatus.UNKNOWN,
                message=f"Unknown GPU: {gpu_name}",
                max_macos=None,
                min_macos=None,
                notes=["GPU family could not be determined"],
                kexts_needed=[],
            )

        gpu_data = GPU_FAMILIES[family]

        # Determine status
        max_macos = gpu_data.get("max_macos")
        if max_macos is None:
            status = CompatStatus.UNSUPPORTED
            message = f"GPU family {family} has no macOS support"
        elif max_macos == "10.14":
            status = CompatStatus.PARTIAL
            message = f"GPU family {family} is partially supported (max macOS {max_macos})"
        else:
            status = CompatStatus.SUPPORTED
            message = f"GPU family {family} is supported (max macOS {max_macos})"

        return CompatResult(
            status=status,
            message=message,
            max_macos=max_macos,
            min_macos=gpu_data.get("min_macos"),
            notes=gpu_data.get("notes", []),
            kexts_needed=gpu_data.get("kexts_needed", []),
        )

    @classmethod
    def check_all(cls, hw_info) -> dict:
        """
        Check all hardware compatibility

        Args:
            hw_info: HardwareInfo object with cpu and gpu (list) attributes

        Returns:
            Dictionary with cpu and list of gpu compatibility results
        """
        results = {}

        if hasattr(hw_info, "cpu") and hw_info.cpu:
            cpu = hw_info.cpu
            if hasattr(cpu, "name") and cpu.name:
                results["cpu"] = cls.check_cpu(cpu)

        if hasattr(hw_info, "gpu") and hw_info.gpu:
            gpu_list = hw_info.gpu
            if gpu_list and len(gpu_list) > 0:
                # Check all GPUs in the list and return as a list
                gpu_results = []
                for gpu in gpu_list:
                    if hasattr(gpu, "name") and gpu.name:
                        gpu_results.append(cls.check_gpu(gpu))
                if gpu_results:
                    results["gpu"] = gpu_results

        return results
