"""
acpi.py: SSDT/ACPI selection for Hackintosh EFI

Selects appropriate SSDTs based on CPU generation and form factor.
References: https://dortania.github.io/Getting-Started-With-ACPI/
"""

import logging
from ..efi_mac.acpi.base import ACPIManager

logger = logging.getLogger(__name__)


# --- SSDT requirement maps ---

# CPU power management (requires Haswell+ for XCPM)
_PLUG_GENS = {
    "haswell", "broadwell", "skylake", "kaby_lake",
    "coffee_lake", "comet_lake", "rocket_lake", "alder_lake", "raptor_lake",
}

# EC + USBX desktop (Skylake+)
_EC_USBX_DESKTOP_GENS = {
    "skylake", "kaby_lake", "coffee_lake", "comet_lake",
    "rocket_lake", "alder_lake", "raptor_lake",
}

# EC + USBX laptop (Skylake - Comet Lake)
_EC_USBX_LAPTOP_GENS = {
    "skylake", "kaby_lake", "coffee_lake", "comet_lake",
}

# Legacy EC only (pre-Skylake Intel desktop/laptop)
_EC_LEGACY_GENS = {"ivy_bridge", "haswell", "broadwell"}

# AWAC disable (Kaby Lake+ — H310/B360/H370/Z390/Z490+ has AWAC)
_AWAC_GENS = {
    "kaby_lake", "coffee_lake", "comet_lake",
    "rocket_lake", "alder_lake", "raptor_lake",
}

# PMC native NVRAM (300-series chipset: Z370/Z390/B360/H370/H310)
_PMC_GENS = {"kaby_lake", "coffee_lake"}

# RHUB USB root-hub reset (400-series+: Z490, B460, etc.)
_RHUB_GENS = {"comet_lake", "rocket_lake", "alder_lake", "raptor_lake"}

# SSDT-IMEI: Ivy Bridge CPU on 6-series chipset (H61/B65/Z68/P67/H67)
# or Sandy Bridge CPU on 7-series chipset
_IMEI_GENS = {"sandy_bridge", "ivy_bridge"}

# HEDT platforms needing SSDT-UNC (unused/phantom ACPI device disable)
_HEDT_UNC_GENS = {"ivy_bridge_e", "haswell_e"}

# HEDT platforms needing SSDT-RTC0-RANGE (X99/X299 RTC fix)
_HEDT_RTC_GENS = {"haswell_e", "broadwell_e", "skylake_x"}

# AMD Zen platforms
_AMD_ZEN_GENS = {"zen", "zen2", "zen3", "zen4"}
# AMD B550/A520 need SSDT-CPUR (CPU definition fix)
_AMD_CPUR_GENS = {"zen2", "zen3"}  # Ryzen 3000+ on B550/A520


class HackACPI:
    """Select and enable SSDTs for Hackintosh hardware."""

    def __init__(self, config: dict, constants, paths: dict,
                 cpu_gen: str, is_laptop: bool,
                 chipset: str = "", vendor: str = ""):
        self.config = config
        self.constants = constants
        self.paths = paths
        self.cpu_gen = cpu_gen
        self.is_laptop = is_laptop
        # Chipset string used for chipset-specific decisions (e.g., B550)
        self.chipset = chipset.upper() if chipset else ""
        self.vendor = vendor.upper() if vendor else ""
        self.log_lines: list[str] = []

        # Reuse efi_mac ACPIManager for file copy + enable
        self.acpi_mgr = ACPIManager(config, constants, "", paths)

    def _log(self, msg: str):
        logger.info(msg)
        self.log_lines.append(msg)

    def apply(self) -> list[str]:
        """Select and enable SSDTs based on CPU generation and platform."""
        self._log("[STEP] Selecting ACPI/SSDTs (Hackintosh)")
        self._log(f"  CPU: {self.cpu_gen}, Laptop: {self.is_laptop}, "
                  f"Chipset: {self.chipset}")

        if self.cpu_gen in _AMD_ZEN_GENS:
            self._apply_amd_zen()
        elif self.cpu_gen in ("ivy_bridge_e", "haswell_e", "broadwell_e", "skylake_x"):
            self._apply_hedt()
        else:
            self._apply_intel()

        self.log_lines.extend(self.acpi_mgr.log_lines)
        return self.log_lines

    # ------------------------------------------------------------------
    # Intel desktop / laptop
    # ------------------------------------------------------------------

    def _apply_intel(self):
        """Apply Intel platform SSDTs."""
        # SSDT-PLUG: CPU power management (Haswell+)
        if self.cpu_gen in _PLUG_GENS:
            self.acpi_mgr.add_acpi("SSDT-PLUG.aml")
            self._log("  + SSDT-PLUG (CPU power management)")

        # EC / EC-USBX
        if self.is_laptop and self.cpu_gen in _EC_USBX_LAPTOP_GENS:
            self.acpi_mgr.add_acpi("SSDT-EC-USBX-Laptop.aml")
            self._log("  + SSDT-EC-USBX-Laptop (EC + USB power, laptop)")
        elif not self.is_laptop and self.cpu_gen in _EC_USBX_DESKTOP_GENS:
            self.acpi_mgr.add_acpi("SSDT-EC-USBX.aml")
            self._log("  + SSDT-EC-USBX (EC + USB power, desktop)")
        elif self.cpu_gen in _EC_LEGACY_GENS:
            self.acpi_mgr.add_acpi("SSDT-EC.aml")
            self._log("  + SSDT-EC (embedded controller, legacy)")

        # SSDT-AWAC: disable AWAC, enable legacy RTC (Kaby Lake 300-series+)
        if self.cpu_gen in _AWAC_GENS:
            self.acpi_mgr.add_acpi("SSDT-AWAC-DISABLE.aml")
            self._log("  + SSDT-AWAC-DISABLE (AWAC clock fix)")

        # SSDT-PMC: native NVRAM on 300-series chipsets
        if self.cpu_gen in _PMC_GENS:
            self.acpi_mgr.add_acpi("SSDT-PMC.aml")
            self._log("  + SSDT-PMC (native NVRAM, 300-series)")

        # SSDT-RHUB: USB root-hub reset (400-series+)
        if self.cpu_gen in _RHUB_GENS and not self.is_laptop:
            self.acpi_mgr.add_acpi("SSDT-RHUB.aml")
            self._log("  + SSDT-RHUB (USB root-hub reset, 400-series+)")

        # SSDT-IMEI: IMEI device fix (Ivy Bridge on 6-series, Sandy on 7-series)
        if self.cpu_gen in _IMEI_GENS:
            self.acpi_mgr.add_acpi("SSDT-IMEI.aml")
            self._log("  + SSDT-IMEI (IMEI device, mixed-gen chipset)")

        # Laptop-specific
        if self.is_laptop:
            self._apply_laptop_extras()

    # ------------------------------------------------------------------
    # Laptop extras
    # ------------------------------------------------------------------

    def _apply_laptop_extras(self):
        """Apply laptop-specific SSDTs."""
        # Backlight control (all Intel laptops Ivy Bridge+)
        self.acpi_mgr.add_acpi("SSDT-PNLF.aml")
        self._log("  + SSDT-PNLF (backlight control)")

        # GPIO trackpad interrupt (Haswell+ I2C trackpads)
        if self.cpu_gen not in ("sandy_bridge", "ivy_bridge"):
            self.acpi_mgr.add_acpi("SSDT-GPI0.aml")
            self._log("  + SSDT-GPI0 (I2C trackpad GPIO interrupt)")

    # ------------------------------------------------------------------
    # AMD Zen
    # ------------------------------------------------------------------

    def _apply_amd_zen(self):
        """Apply AMD Zen platform SSDTs."""
        # EC-USBX for AMD (fake EC + USB power)
        self.acpi_mgr.add_acpi("SSDT-EC-USBX-AMD.aml")
        self._log("  + SSDT-EC-USBX-AMD (fake EC + USB power, AMD)")

        # SSDT-CPUR: CPU definition fix for B550/A520 (Zen2/Zen3)
        if self.cpu_gen in _AMD_CPUR_GENS and self._is_b550_a520():
            self.acpi_mgr.add_acpi("SSDT-CPUR.aml")
            self._log("  + SSDT-CPUR (CPU definition fix, B550/A520)")

    def _is_b550_a520(self) -> bool:
        """Check if chipset is B550 or A520."""
        return any(x in self.chipset for x in ("B550", "A520"))

    # ------------------------------------------------------------------
    # Intel HEDT (X79/X99/X299)
    # ------------------------------------------------------------------

    def _apply_hedt(self):
        """Apply Intel HEDT platform SSDTs."""
        # SSDT-PLUG (Haswell-E+)
        if self.cpu_gen in ("haswell_e", "broadwell_e", "skylake_x"):
            self.acpi_mgr.add_acpi("SSDT-PLUG.aml")
            self._log("  + SSDT-PLUG (CPU power, HEDT)")

        # EC-USBX (all HEDT)
        self.acpi_mgr.add_acpi("SSDT-EC-USBX.aml")
        self._log("  + SSDT-EC-USBX (EC + USB power, HEDT)")

        # SSDT-UNC: disable unused ACPI devices (Ivy Bridge-E / Haswell-E)
        if self.cpu_gen in _HEDT_UNC_GENS:
            self.acpi_mgr.add_acpi("SSDT-UNC.aml")
            self._log("  + SSDT-UNC (unused ACPI device disable, X79/X99)")

        # SSDT-RTC0-RANGE: RTC memory range fix (Haswell-E / Broadwell-E / Skylake-X)
        if self.cpu_gen in _HEDT_RTC_GENS:
            self.acpi_mgr.add_acpi("SSDT-RTC0-RANGE.aml")
            self._log("  + SSDT-RTC0-RANGE (RTC memory range, X99/X299)")
