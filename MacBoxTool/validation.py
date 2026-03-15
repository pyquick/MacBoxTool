"""
validation.py: Hardware compatibility validation for EFI building
"""


def _is_laptop(computer) -> bool:
    """Check if computer is a laptop"""
    if not computer or not computer.real_model:
        return False
    model = computer.real_model.upper()
    return "MACBOOK" in model or computer.internal_keyboard_type is not None


def _detect_cpu_generation(cpu_name: str) -> str:
    """Detect CPU generation from name"""
    name_upper = cpu_name.upper()

    if "12TH GEN" in name_upper or "ALDER" in name_upper:
        return "alder_lake"
    if "11TH GEN" in name_upper or "ROCKET" in name_upper:
        return "rocket_lake"
    if "10TH GEN" in name_upper or "COMET" in name_upper:
        return "comet_lake"
    if "9TH GEN" in name_upper or "8TH GEN" in name_upper or "COFFEE" in name_upper:
        return "coffee_lake"
    if "7TH GEN" in name_upper or "KABY" in name_upper:
        return "kaby_lake"
    if "6TH GEN" in name_upper or "SKYLAKE" in name_upper:
        return "skylake"
    if "5TH GEN" in name_upper or "BROADWELL" in name_upper:
        return "broadwell"
    if "4TH GEN" in name_upper or "HASWELL" in name_upper:
        return "haswell"
    if "3RD GEN" in name_upper or "IVY" in name_upper:
        return "ivy_bridge"
    if "2ND GEN" in name_upper or "SANDY" in name_upper:
        return "sandy_bridge"
    if "PENRYN" in name_upper or "CORE 2" in name_upper:
        return "penryn"

    return "unknown"


def validate_cpu(constants, target_macos_version: int) -> tuple[bool, str]:
    """Validate CPU compatibility for target macOS version"""
    if not constants.computer or not constants.computer.cpu:
        return False, "CPU detection failed"

    cpu_gen = _detect_cpu_generation(constants.computer.cpu.name)

    # Block pre-Haswell for macOS 13+ (requires AVX2)
    if target_macos_version >= 13:
        pre_avx2 = ["penryn", "conroe", "yonah", "sandy_bridge", "ivy_bridge"]
        if cpu_gen in pre_avx2:
            return False, f"macOS 13+ requires AVX2 (Haswell+). Current: {cpu_gen}"

    # Block AMD laptop CPUs
    if "AMD" in constants.computer.cpu.name and _is_laptop(constants.computer):
        return False, "AMD laptop CPUs not supported"

    return True, ""


def validate_gpu(constants) -> tuple[bool, str]:
    """Validate GPU compatibility"""
    if not constants.computer or not constants.computer.gpus:
        return False, ""

    warnings = []
    for gpu in constants.computer.gpus:
        name = gpu.name.upper()

        if any(x in name for x in ["RTX 20", "RTX 30", "RTX 40"]):
            warnings.append(f"{gpu.name}: No macOS driver")
        elif any(x in name for x in ["GTX 9", "GTX 10"]):
            warnings.append(f"{gpu.name}: Max macOS 10.14")
        elif "ARC" in name:
            warnings.append(f"{gpu.name}: No driver")

    if _is_laptop(constants.computer) and len(constants.computer.gpus) > 1:
        warnings.append("Laptop dGPU: 90% incompatible")

    return (True, "\n".join(warnings)) if warnings else (False, "")


def validate_storage(constants) -> tuple[bool, str]:
    """Validate storage device compatibility"""
    if not constants.computer or not constants.computer.storage:
        return False, ""

    problematic = ["PM981", "PM991", "2200S"]
    warnings = []

    for storage in constants.computer.storage:
        name = storage.name if hasattr(storage, 'name') else str(storage)
        for model in problematic:
            if model in name:
                warnings.append(f"{name}: Kernel panic risk. Use NVMeFix or replace")
                break

    return (True, "\n".join(warnings)) if warnings else (False, "")


def validate_network(constants) -> tuple[bool, str]:
    """Validate network card and provide kext info"""
    if not constants.computer:
        return False, ""

    info = []

    if hasattr(constants.computer, 'wifi') and constants.computer.wifi:
        wifi = str(constants.computer.wifi)
        if "Intel" in wifi:
            info.append("Intel WiFi: Needs AirportItlwm + IntelBluetoothFirmware")

    if hasattr(constants.computer, 'ethernet') and constants.computer.ethernet:
        eth = str(constants.computer.ethernet)
        if "I225" in eth:
            info.append("Intel I225-V: Needs device-id spoof")

    return (True, "\n".join(info)) if info else (False, "")
