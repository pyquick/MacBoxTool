"""
quirks.py: Booter and Kernel quirks for Hackintosh EFI

Sets appropriate quirks based on CPU generation and platform.
References: https://dortania.github.io/OpenCore-Install-Guide/
"""

import logging
from ..efi_mac.config import ConfigManager

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Booter quirk sets per platform group
# --------------------------------------------------------------------------

# Pre-Skylake Intel (Ivy Bridge, Haswell, Broadwell)
_BOOTER_PRE_SKYLAKE = {
    "AvoidRuntimeDefrag": True,
    "EnableSafeModeSlide": True,
    "EnableWriteUnprotector": True,
    "ProvideCustomSlide": True,
    "SetupVirtualMap": True,
}

# Skylake / Kaby Lake
_BOOTER_SKYLAKE = {
    "AvoidRuntimeDefrag": True,
    "EnableSafeModeSlide": True,
    "EnableWriteUnprotector": True,
    "ProvideCustomSlide": True,
    "SetupVirtualMap": True,
}

# Coffee Lake+ (300-series and newer, modern memory map)
_BOOTER_COFFEE_LAKE_PLUS = {
    "AvoidRuntimeDefrag": True,
    "DevirtualiseMmio": True,
    "EnableSafeModeSlide": True,
    "EnableWriteUnprotector": False,
    "ProtectUefiServices": True,
    "ProvideCustomSlide": True,
    "RebuildAppleMemoryMap": True,
    "ResizeAppleGpuBars": -1,
    "SyncRuntimePermissions": True,
    "SetupVirtualMap": True,
}

# Comet Lake (SetupVirtualMap must be False on most Z490 boards)
_BOOTER_COMET_LAKE_OVERRIDE = {
    "SetupVirtualMap": False,
}

# HEDT (X79/X99/X299 — same modern base, no SetupVirtualMap issues)
_BOOTER_HEDT = {
    "AvoidRuntimeDefrag": True,
    "DevirtualiseMmio": True,
    "EnableSafeModeSlide": True,
    "EnableWriteUnprotector": False,
    "ProvideCustomSlide": True,
    "RebuildAppleMemoryMap": True,
    "ResizeAppleGpuBars": -1,
    "SetupVirtualMap": True,
    "SyncRuntimePermissions": True,
}

# AMD Zen
_BOOTER_AMD_ZEN = {
    "AvoidRuntimeDefrag": True,
    "EnableSafeModeSlide": True,
    "EnableWriteUnprotector": False,
    "RebuildAppleMemoryMap": True,
    "ResizeAppleGpuBars": -1,
    "SetupVirtualMap": True,
    "SyncRuntimePermissions": True,
}

# AMD B550/A520/TRx40 — SetupVirtualMap must be False
_BOOTER_AMD_B550_OVERRIDE = {
    "SetupVirtualMap": False,
}

# --------------------------------------------------------------------------
# Kernel quirk sets per platform group
# --------------------------------------------------------------------------

# Base quirks for all platforms
_KERNEL_BASE = {
    "DisableLinkeditJettison": True,
    "PanicNoKextDump": True,
    "PowerTimeoutKernelPanic": True,
}

# Intel: disable VT-d DMAR table (all Intel that may have VT-d)
_KERNEL_INTEL_IO_MAPPER = {
    "DisableIoMapper": True,
}

# Ivy Bridge: AppleCpuPmCfgLock (no XCPM, uses old PM)
_KERNEL_IVY_BRIDGE = {
    "AppleCpuPmCfgLock": True,
}

# Haswell through Comet Lake: AppleXcpmCfgLock (XCPM + CFG Lock)
_KERNEL_XCPM_CFG_LOCK = {
    "AppleXcpmCfgLock": True,
}

# HEDT (Ivy Bridge-E + Haswell-E): extra MSR emulation
_KERNEL_HEDT_EXTRA_MSRS = {
    "AppleXcpmExtraMsrs": True,
}

# HP systems: LAPIC panic workaround
_KERNEL_LAPIC = {
    "LapicKernelPanic": True,
}

# AMD Zen: DummyPowerManagement replaces XCPM, ProvideCurrentCpuInfo
_KERNEL_AMD_ZEN = {
    "DummyPowerManagement": True,
    "ProvideCurrentCpuInfo": True,
    "PanicNoKextDump": True,
    "PowerTimeoutKernelPanic": True,
    "DisableLinkeditJettison": True,
}


class HackQuirks:
    """Apply Booter and Kernel quirks for Hackintosh."""

    def __init__(self, config: dict, constants, paths: dict,
                 cpu_gen: str, is_laptop: bool,
                 vendor: str = "", chipset: str = ""):
        self.config = config
        self.constants = constants
        self.paths = paths
        self.cpu_gen = cpu_gen
        self.is_laptop = is_laptop
        self.vendor = vendor.upper() if vendor else ""
        self.chipset = chipset.upper() if chipset else ""
        self.log_lines: list[str] = []
        self.config_mgr = ConfigManager(config, paths["plist_path"])

    def _log(self, msg: str):
        logger.info(msg)
        self.log_lines.append(msg)

    def apply(self) -> list[str]:
        """Apply appropriate quirks."""
        self._log("[STEP] Applying Quirks (Hackintosh)")
        self._apply_booter_quirks()
        self._apply_kernel_quirks()
        self._apply_misc_quirks()
        return self.log_lines

    # ------------------------------------------------------------------
    # Booter quirks
    # ------------------------------------------------------------------

    def _apply_booter_quirks(self):
        """Apply Booter quirks based on CPU generation."""
        amd_gens = {"zen", "zen2", "zen3", "zen4"}
        hedt_gens = {"ivy_bridge_e", "haswell_e", "broadwell_e", "skylake_x"}
        coffee_plus = {"coffee_lake", "comet_lake", "rocket_lake",
                       "alder_lake", "raptor_lake"}
        skylake_kaby = {"skylake", "kaby_lake"}
        pre_skylake = {"sandy_bridge", "ivy_bridge", "haswell", "broadwell"}

        if self.cpu_gen in amd_gens:
            quirks = dict(_BOOTER_AMD_ZEN)
            if self._is_b550_a520_trx40():
                quirks.update(_BOOTER_AMD_B550_OVERRIDE)
                self._log("  Booter: AMD B550/A520/TRx40 SetupVirtualMap=False")
            label = "AMD Zen"
        elif self.cpu_gen in hedt_gens:
            quirks = dict(_BOOTER_HEDT)
            label = "Intel HEDT"
        elif self.cpu_gen in coffee_plus:
            quirks = dict(_BOOTER_COFFEE_LAKE_PLUS)
            if self.cpu_gen == "comet_lake":
                quirks.update(_BOOTER_COMET_LAKE_OVERRIDE)
                self._log("  Booter: Comet Lake SetupVirtualMap=False")
            label = "Coffee Lake+"
        elif self.cpu_gen in skylake_kaby:
            quirks = dict(_BOOTER_SKYLAKE)
            label = "Skylake/Kaby Lake"
        else:
            quirks = dict(_BOOTER_PRE_SKYLAKE)
            label = "pre-Skylake"

        for quirk, value in quirks.items():
            self.config_mgr.set_booter_quirk(quirk, value)
        self._log(f"  Booter: {label} quirks applied")

    def _is_b550_a520_trx40(self) -> bool:
        return any(x in self.chipset for x in ("B550", "A520", "TRX40"))

    # ------------------------------------------------------------------
    # Kernel quirks
    # ------------------------------------------------------------------

    def _apply_kernel_quirks(self):
        """Apply Kernel quirks based on CPU generation."""
        amd_gens = {"zen", "zen2", "zen3", "zen4"}
        hedt_extra_msr = {"ivy_bridge_e", "haswell_e"}
        xcpm_gens = {"haswell", "broadwell", "skylake", "kaby_lake",
                     "coffee_lake", "comet_lake", "rocket_lake",
                     "alder_lake", "raptor_lake", "haswell_e",
                     "broadwell_e", "skylake_x"}

        if self.cpu_gen in amd_gens:
            for quirk, value in _KERNEL_AMD_ZEN.items():
                self.config_mgr.set_quirk(quirk, value)
            self._log("  Kernel: AMD Zen quirks (DummyPowerManagement, ProvideCurrentCpuInfo)")
            return

        # Intel base quirks
        for quirk, value in _KERNEL_BASE.items():
            self.config_mgr.set_quirk(quirk, value)
        self._log("  Kernel: base quirks (PanicNoKextDump, PowerTimeoutKernelPanic, "
                  "DisableLinkeditJettison)")

        # DisableIoMapper for all Intel (VT-d bypass)
        for quirk, value in _KERNEL_INTEL_IO_MAPPER.items():
            self.config_mgr.set_quirk(quirk, value)
        self._log("  Kernel: DisableIoMapper (VT-d bypass)")

        # Ivy Bridge: old PM (no XCPM)
        if self.cpu_gen == "ivy_bridge":
            for quirk, value in _KERNEL_IVY_BRIDGE.items():
                self.config_mgr.set_quirk(quirk, value)
            self._log("  Kernel: AppleCpuPmCfgLock (Ivy Bridge legacy PM)")

        # XCPM + CFG Lock workaround (Haswell+)
        if self.cpu_gen in xcpm_gens:
            for quirk, value in _KERNEL_XCPM_CFG_LOCK.items():
                self.config_mgr.set_quirk(quirk, value)
            self._log("  Kernel: AppleXcpmCfgLock (CFG Lock workaround)")

        # HEDT extra MSR emulation (Ivy Bridge-E + Haswell-E)
        if self.cpu_gen in hedt_extra_msr:
            for quirk, value in _KERNEL_HEDT_EXTRA_MSRS.items():
                self.config_mgr.set_quirk(quirk, value)
            self._log("  Kernel: AppleXcpmExtraMsrs (HEDT MSR emulation)")

        # HP LAPIC panic
        if "HP" in self.vendor:
            for quirk, value in _KERNEL_LAPIC.items():
                self.config_mgr.set_quirk(quirk, value)
            self._log("  Kernel: LapicKernelPanic (HP system)")

        # APFS trim (if constant is set)
        if getattr(self.constants, "apfs_trim_timeout", False):
            self.config_mgr.set_quirk("SetApfsTrimTimeout", 0)
            self._log("  Kernel: SetApfsTrimTimeout=0")

    # ------------------------------------------------------------------
    # Misc quirks
    # ------------------------------------------------------------------

    def _apply_misc_quirks(self):
        """Apply Misc section settings."""
        misc = self.config.setdefault("Misc", {})

        # Boot
        boot = misc.setdefault("Boot", {})
        boot["Timeout"] = getattr(self.constants, "oc_timeout", 5)
        if self.constants.showpicker:
            boot["ShowPicker"] = True
            self._log("  Misc: ShowPicker=True")

        # Security
        security = misc.setdefault("Security", {})
        security["AllowSetDefault"] = True
        security["ScanPolicy"] = 0
        security["SecureBootModel"] = "Disabled"  # Hackintosh cannot match Apple hardware
        if self.constants.vault:
            security["Vault"] = "Secure"
        else:
            security["Vault"] = "Optional"
        self._log("  Misc: SecureBootModel=Disabled, ScanPolicy=0")

        # Debug
        if self.constants.opencore_debug:
            debug = misc.setdefault("Debug", {})
            debug["AppleDebug"] = True
            debug["ApplePanic"] = True
            debug["Target"] = 0x43
            self._log("  Misc: OpenCore debug enabled (Target=0x43)")
