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
