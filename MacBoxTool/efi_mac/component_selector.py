"""
component_selector.py: Select ACPI/Kexts/Drivers for EFI building
"""

from pathlib import Path


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


def select_ssdts(constants, cpu_gen: str, is_laptop: bool = None) -> list[Path]:
    """Select required SSDT files based on platform"""
    if is_laptop is None:
        is_laptop = _is_laptop(constants.computer) if constants.computer else False

    if not cpu_gen or cpu_gen == "unknown":
        cpu_gen = _detect_cpu_gen(constants.computer.cpu.name) if constants.computer else "unknown"

    ssdts = []

    # CPU power management
    if cpu_gen in ["haswell", "broadwell", "skylake", "kaby_lake", "coffee_lake", "comet_lake"]:
        ssdts.append(constants.ssdt_plug_path)

    # EC + USB
    if cpu_gen in ["skylake", "kaby_lake", "coffee_lake", "comet_lake"]:
        ssdts.append(constants.ssdt_ec_usbx_laptop_path if is_laptop else constants.ssdt_ec_usbx_desktop_path)
    elif cpu_gen in ["haswell", "broadwell", "ivy_bridge"]:
        ssdts.append(constants.ssdt_ec_path)

    # AWAC
    if cpu_gen in ["kaby_lake", "coffee_lake", "comet_lake"]:
        ssdts.append(constants.ssdt_awac_path)

    # PMC
    if cpu_gen in ["kaby_lake", "coffee_lake"]:
        ssdts.append(constants.ssdt_pmc_path)

    # RHUB
    if cpu_gen == "comet_lake":
        ssdts.append(constants.ssdt_rhub_path)

    # Laptop SSDTs
    if is_laptop:
        ssdts.append(constants.ssdt_pnlf_path)
        ssdts.append(constants.ssdt_gpi0_path)

    return ssdts


def select_kexts(constants) -> list[Path]:
    """
    Select required kexts based on hardware

    Returns:
        List of Path objects to kext files
    """
    kexts = []

    # Base kexts (always required)
    kexts.append(constants.lilu_path)
    # Note: VirtualSMC path needs to be added to constants

    # Graphics
    kexts.append(constants.whatevergreen_path)

    # Audio
    if constants.set_alc_usage:
        kexts.append(constants.applealc_path)

    # Network
    if hasattr(constants.computer, 'wifi') and constants.computer.wifi:
        wifi = str(constants.computer.wifi)
        if "Intel" in wifi:
            # Intel WiFi kexts need to be added to constants
            pass

    # NVMe fix
    if constants.allow_nvme_fixing:
        kexts.append(constants.nvmefix_path)

    return kexts


def select_drivers(constants) -> list[Path]:
    """
    Select required UEFI drivers

    Returns:
        List of Path objects to driver files
    """
    drivers = []

    # Always required (paths need to be added to constants)
    # drivers.append(constants.hfsplus_driver_path)
    # drivers.append(constants.openruntime_driver_path)

    # Optional
    # if constants.showpicker:
    #     drivers.append(constants.opencanopy_driver_path)

    return drivers
