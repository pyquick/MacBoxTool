"""
smbios_selector.py: SMBIOS model selection logic for EFI building
"""

from ...datasets.smbios_data import smbios_dictionary


def _is_laptop(computer) -> bool:
    """Check if computer is a laptop"""
    if not computer or not computer.real_model:
        return False
    model = computer.real_model.upper()
    return "MACBOOK" in model or computer.internal_keyboard_type is not None


def _detect_cpu_gen(cpu_name: str) -> str:
    """Detect CPU generation from name"""
    name = cpu_name.upper()
    if "12TH" in name or "ALDER" in name: return "alder_lake"
    if "11TH" in name or "ROCKET" in name: return "rocket_lake"
    if "10TH" in name or "COMET" in name: return "comet_lake"
    if "9TH" in name or "8TH" in name or "COFFEE" in name: return "coffee_lake"
    if "7TH" in name or "KABY" in name: return "kaby_lake"
    if "6TH" in name or "SKYLAKE" in name: return "skylake"
    if "5TH" in name or "BROADWELL" in name: return "broadwell"
    if "4TH" in name or "HASWELL" in name: return "haswell"
    if "3RD" in name or "IVY" in name: return "ivy_bridge"
    return "unknown"


def select_smbios(constants, target_macos_version: int) -> str:
    """Select appropriate SMBIOS model based on hardware"""
    if not constants.computer or not constants.computer.cpu:
        return "iMac19,1"

    cpu_gen = _detect_cpu_gen(constants.computer.cpu.name)
    has_igpu = constants.computer.igpu is not None
    is_laptop = _is_laptop(constants.computer)

    # Laptop SMBIOS
    if is_laptop:
        laptop_map = {
            "ivy_bridge": "MacBookPro10,1",
            "haswell": "MacBookPro11,1",
            "broadwell": "MacBookPro12,1",
            "skylake": "MacBookPro13,1",
            "kaby_lake": "MacBookPro14,1",
            "coffee_lake": "MacBookPro15,1",
            "comet_lake": "MacBookPro16,1",
        }
        return laptop_map.get(cpu_gen, "MacBookPro15,1")

    # Desktop without iGPU
    if not has_igpu:
        return "iMacPro1,1"

    # Desktop with iGPU
    desktop_map = {
        "ivy_bridge": "iMac13,1",
        "haswell": "iMac15,1",
        "broadwell": "iMac16,1",
        "skylake": "iMac17,1",
        "kaby_lake": "iMac18,2",
        "coffee_lake": "iMac19,1",
        "comet_lake": "iMac20,1",
    }
    return desktop_map.get(cpu_gen, "iMac19,1")


def get_smbios_info(smbios_model: str) -> dict:
    """Get SMBIOS information from smbios_dictionary"""
    return smbios_dictionary.get(smbios_model, {})


def get_smbios_explanation(smbios_model: str, constants) -> str:
    """Generate explanation for why this SMBIOS was chosen"""
    info = get_smbios_info(smbios_model)
    if not info:
        return f"Selected {smbios_model} (default)"

    cpu_gen = _detect_cpu_gen(constants.computer.cpu.name) if constants.computer else "unknown"
    has_igpu = constants.computer.igpu is not None if constants.computer else False
    is_laptop = _is_laptop(constants.computer) if constants.computer else False

    explanation = f"Selected {smbios_model}\n"
    explanation += f"Reason: "

    if is_laptop:
        explanation += f"Laptop with {cpu_gen} CPU"
    elif not has_igpu:
        explanation += f"Desktop without iGPU (requires iMacPro/MacPro SMBIOS)"
    else:
        explanation += f"Desktop with {cpu_gen} CPU and iGPU"

    if "Max OS Supported" in info:
        explanation += f"\nMax macOS: {info['Max OS Supported']}"

    return explanation
