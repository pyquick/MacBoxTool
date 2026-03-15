"""
builder.py: Main Hackintosh EFI builder

Orchestrates all efi_hack sub-modules to build a complete OpenCore EFI
for arbitrary PC hardware based on detected hardware + user SMBIOS choice.

Reuses efi_mac.base.BaseGenerator for OpenCore extraction and
efi_mac.config.ConfigManager for plist manipulation.
"""

import logging
from datetime import date

from ..efi_mac.base import BaseGenerator
from ..efi_mac.config import ConfigManager

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# Hardware detection helpers
# --------------------------------------------------------------------------

def _detect_cpu_gen(cpu_name: str) -> str:
    """Detect CPU generation string from CPU name."""
    name = cpu_name.upper()
    # AMD Zen families
    if "ZEN 4" in name or "RYZEN 7000" in name or "RYZEN 9 7" in name: return "zen4"
    if "ZEN 3" in name or "RYZEN 5000" in name or "RYZEN 9 5" in name: return "zen3"
    if "ZEN 2" in name or "RYZEN 3000" in name or "RYZEN 9 3" in name: return "zen2"
    if "ZEN" in name or "RYZEN" in name or "THREADRIPPER" in name: return "zen"
    # Intel generations (newest first to avoid partial matches)
    if "13TH" in name or "RAPTOR" in name: return "raptor_lake"
    if "12TH" in name or "ALDER" in name: return "alder_lake"
    if "11TH" in name or "ROCKET" in name: return "rocket_lake"
    if "10TH" in name or "COMET" in name: return "comet_lake"
    if ("9TH" in name or "8TH" in name) and "COFFEE" not in name: return "coffee_lake"
    if "COFFEE" in name: return "coffee_lake"
    if "7TH" in name or "KABY" in name: return "kaby_lake"
    if "6TH" in name or "SKYLAKE" in name: return "skylake"
    if "5TH" in name or "BROADWELL" in name: return "broadwell"
    if "4TH" in name or "HASWELL" in name: return "haswell"
    if "3RD" in name or "IVY" in name: return "ivy_bridge"
    if "2ND" in name or "SANDY" in name: return "sandy_bridge"
    # HEDT
    if "EXTREME" in name or "X-SERIES" in name or "W-" in name:
        if "SKYLAKE" in name or "BROADWELL" in name or "CASCADE" in name:
            return "skylake_x"
        if "HASWELL" in name: return "haswell_e"
        if "IVY" in name: return "ivy_bridge_e"
    return "unknown"


def _detect_chipset(computer) -> str:
    """Extract chipset string from computer object."""
    if not computer:
        return ""
    # Prefer dedicated chipset attribute if present
    chipset = getattr(computer, "chipset", None)
    if chipset:
        return str(chipset)
    # Fall back to board name
    board = getattr(computer, "board_name", None)
    return str(board) if board else ""


def _detect_vendor(computer) -> str:
    """Extract motherboard/system vendor string."""
    if not computer:
        return ""
    vendor = getattr(computer, "board_vendor", None) or getattr(computer, "vendor", None)
    return str(vendor) if vendor else ""


def _detect_gpu_names(computer) -> list[str]:
    """Return list of GPU name strings from detected hardware."""
    if not computer:
        return []
    gpus = getattr(computer, "gpus", []) or []
    return [str(g.name).upper() for g in gpus if g and g.name]


def _is_laptop(computer) -> bool:
    """Return True if the detected system is a laptop."""
    if not computer:
        return False
    if getattr(computer, "laptop", False):
        return True
    model = getattr(computer, "real_model", "") or ""
    if "MACBOOK" in model.upper():
        return True
    return getattr(computer, "internal_keyboard_type", None) is not None


# --------------------------------------------------------------------------
# Builder
# --------------------------------------------------------------------------

class HackintoshBuilder:
    """Build OpenCore EFI for Hackintosh hardware."""

    @staticmethod
    def get_available_smbios(global_constants) -> dict:
        """
        Get available SMBIOS models based on hardware type.

        Returns:
            dict with 'type' (desktop/laptop) and 'models' (list of SMBIOS)
        """
        from ..datasets.smbios_data import smbios_dictionary

        computer = global_constants.computer
        is_laptop = _is_laptop(computer) if computer else False

        if is_laptop:
            # Laptop: MacBook series only
            models = [m for m in smbios_dictionary.keys()
                     if m.startswith(("MacBook", "MacBookPro", "MacBookAir"))]
            return {"type": "laptop", "models": sorted(models)}
        else:
            # Desktop: iMac, Mac mini, Mac Pro, iMac Pro
            models = [m for m in smbios_dictionary.keys()
                     if m.startswith(("iMac", "Macmini", "MacPro", "iMacPro"))]
            return {"type": "desktop", "models": sorted(models)}

    def __init__(self, smbios_model: str, global_constants):
        from ..efi_mac.security import SecurityValidator
        if not SecurityValidator.validate_model(smbios_model):
            raise ValueError(f"Invalid SMBIOS model: {smbios_model}")

        self.smbios_model = smbios_model
        self.constants = global_constants
        self.log_lines: list[str] = []

        # Derived hardware info
        computer = global_constants.computer
        self.cpu_gen = "unknown"
        self.is_laptop = _is_laptop(computer)
        self.chipset = _detect_chipset(computer)
        self.vendor = _detect_vendor(computer)
        self.gpu_names = _detect_gpu_names(computer)

        if computer and computer.cpu:
            self.cpu_gen = _detect_cpu_gen(computer.cpu.name)

        # OpenCore extraction + path map
        self.base_gen = BaseGenerator(smbios_model, global_constants)
        self.paths = self.base_gen.get_paths()

    def _log(self, msg: str):
        logger.info(msg)
        self.log_lines.append(msg)

    # ------------------------------------------------------------------
    # Public build entry point
    # ------------------------------------------------------------------

    def build(self) -> list[str]:
        """
        Run the full Hackintosh EFI build.

        Returns:
            Log lines from the build process.
        """
        self._log("=== Building Hackintosh EFI ===")
        self._log(f"SMBIOS    : {self.smbios_model}")
        self._log(f"CPU gen   : {self.cpu_gen}")
        self._log(f"Chipset   : {self.chipset}")
        self._log(f"Vendor    : {self.vendor}")
        self._log(f"Laptop    : {self.is_laptop}")
        self._log(f"GPUs      : {self.gpu_names}")
        self._log(f"Date      : {date.today()}")
        self._log(f"OC ver    : {self.constants.opencore_version}")
        self._log("")

        # Guard: SMBIOS must be known
        from ..datasets.smbios_data import smbios_dictionary
        if self.smbios_model not in smbios_dictionary:
            self._log(f"[ERROR] Unknown SMBIOS model: {self.smbios_model}")
            return self.log_lines

        # Step 1: Extract OpenCore + load config template
        self.config, logs = self.base_gen.generate()
        self.log_lines.extend(logs)

        config_mgr = ConfigManager(self.config, self.paths["plist_path"])

        # Step 2: ACPI / SSDT selection
        from .acpi import HackACPI
        acpi = HackACPI(
            self.config, self.constants, self.paths,
            self.cpu_gen, self.is_laptop,
            chipset=self.chipset, vendor=self.vendor,
        )
        self.log_lines.extend(acpi.apply())

        # Step 3: Kext selection
        from .kexts import HackKexts
        kexts = HackKexts(
            self.config, self.constants, self.paths,
            self.cpu_gen, self.is_laptop,
            chipset=self.chipset,
        )
        self.log_lines.extend(kexts.apply())

        # Step 4: UEFI drivers
        from .drivers import HackDrivers
        drivers = HackDrivers(self.config, self.constants, self.paths)
        self.log_lines.extend(drivers.apply())

        # Step 5: Booter / Kernel quirks
        from .quirks import HackQuirks
        quirks = HackQuirks(
            self.config, self.constants, self.paths,
            self.cpu_gen, self.is_laptop,
            vendor=self.vendor, chipset=self.chipset,
        )
        self.log_lines.extend(quirks.apply())

        # Step 6: NVRAM (boot-args, SIP, system variables)
        from .nvram import HackNVRAM
        nvram = HackNVRAM(
            self.config, self.constants, self.paths,
            cpu_gen=self.cpu_gen, gpu_names=self.gpu_names,
        )
        self.log_lines.extend(nvram.apply())

        # Step 7: PlatformInfo / SMBIOS
        from .platform_info import HackPlatformInfo
        pi = HackPlatformInfo(
            self.config, self.constants, self.paths,
            self.smbios_model, vendor=self.vendor,
        )
        self.log_lines.extend(pi.apply())

        # Step 8: Strip disabled entries
        self.log_lines.extend(config_mgr.cleanup())

        # Step 9: Write config.plist
        self.log_lines.extend(config_mgr.save())

        # Step 10: Sanity-check referenced files
        self._validate()

        self._log("")
        self._log(f"[DONE] EFI at: {self.paths['oc_build']}")
        return self.log_lines

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate(self):
        """Check that all referenced kexts and drivers exist on disk."""
        self._log("[STEP] Validating EFI")
        errors = 0

        plist_path = self.paths["plist_path"]
        kexts_path = self.paths["kexts_path"]
        drivers_path = self.paths["drivers_path"]

        if not plist_path.exists():
            self._log("  [ERROR] config.plist missing!")
            errors += 1

        for kext in self.config.get("Kernel", {}).get("Add", []):
            kp = kexts_path / kext["BundlePath"]
            if not kp.exists():
                self._log(f"  [WARN] Missing kext: {kext['BundlePath']}")
                errors += 1

        for drv in self.config.get("UEFI", {}).get("Drivers", []):
            dp = drivers_path / drv["Path"]
            if not dp.exists():
                self._log(f"  [WARN] Missing driver: {drv['Path']}")
                errors += 1

        if errors == 0:
            self._log("  Validation passed")
        else:
            self._log(f"  Validation completed with {errors} warning(s)")
