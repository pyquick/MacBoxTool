"""
quirks.py: Model-specific quirks and settings

Logic extracted from MacBoxTool: firmware.py, smbios.py, security.py, misc.py
"""


import logging
from ...datasets import model_array, smbios_data, cpu_data, os_data
from ... import constants

logger = logging.getLogger(__name__)


class QuirksManager:
    """Manages model-specific quirks for EFI building."""

    def __init__(self, config: dict, constants: constants.Constants, model: str, paths: dict):
        self.config = config
        self.constants = constants
        self.model = model
        self.paths = paths
        self.log_lines: list[str] = []

    def _log(self, msg: str):
        logger.info(msg)
        self.log_lines.append(msg)

    def apply(self) -> list[str]:
        self._log("[STEP] Applying model-specific quirks")

        from ..config import ConfigManager
        config_mgr = ConfigManager(self.config, self.paths["plist_path"])

        model_info = smbios_data.smbios_dictionary.get(self.model, {})
        cpu_gen = model_info.get("CPU Generation", 999)
        max_os = model_info.get("Max OS Supported", 0)

        # --- Booter Quirks ---
        base_booter = [
            "AvoidRuntimeDefrag",
            "EnableSafeModeSlide",
            "ProvideCustomSlide",
            "RebuildAppleMemoryMap",
            "SyncRuntimePermissions",
            "SetupVirtualMap",
        ]
        for quirk in base_booter:
            config_mgr.set_booter_quirk(quirk, True)
        self._log(f"  Booter quirks: {', '.join(base_booter)}")

        # MacBoxTool smbios.py: Skip Board ID check (conditional on serial_settings)
        if self.constants.serial_settings == "None" and not self.constants.allow_oc_everywhere:
            self._enable_booter_patch("Skip Board ID check")
            self._log("  Booter patch: Skip Board ID check")

        # MacBoxTool firmware.py: Patch SkipLogo for models that natively support Monterey+
        if max_os >= os_data.os_data.monterey and self.model not in ["MacPro6,1", "Macmini7,1"]:
            self._enable_booter_patch("Patch SkipLogo")
            self._log("  Booter patch: Patch SkipLogo (Monterey+ native)")

        # MacBoxTool firmware.py: Haswell/Broadwell MacBooks - enable VMX for non-macOS
        if self.model.startswith("MacBook") and cpu_gen in (
            cpu_data.CPUGen.haswell.value, cpu_data.CPUGen.broadwell.value
        ):
            self.config.setdefault("UEFI", {}).setdefault("Quirks", {})["EnableVmx"] = True
            self._log("  UEFI quirk: EnableVmx (Haswell/Broadwell MacBook)")

        # MacBoxTool firmware.py: SignalAppleOS for switchable GPU models
        if "Switchable GPUs" in model_info:
            config_mgr.set_booter_quirk("SignalAppleOS", True)
            self._log("  Booter quirk: SignalAppleOS (switchable GPU)")

        # --- Kernel Quirks ---
        # MacBoxTool: ThirdPartyDrives - only for models with 3rd party SATA support
        stock_storage = model_info.get("Stock Storage", [])
        if any(drive in stock_storage for drive in ["SATA 2.5", "SATA 3.5", "mSATA"]):
            config_mgr.set_quirk("ThirdPartyDrives", True)
            self._log("  Kernel quirk: ThirdPartyDrives (3rd party SATA)")

        # MacBoxTool: DisableIoMapper - only for specific pre-2008 models without IOMMU
        # MacBookPro1,1 (2006), MacBookPro2,1 (2006-2007), MacBookPro3,1 (2007-2008)
        if self.model in ["MacBookPro1,1", "MacBookPro2,1", "MacBookPro3,1"]:
            config_mgr.set_quirk("DisableIoMapper", True)
            self._log("  Kernel quirk: DisableIoMapper (pre-2008 MacBook Pro)")

        # MacBoxTool firmware.py: PCI bus enumeration fix
        # Pre-Sandy Bridge (non-MacBook) or MacPro6,1 or MacBookPro4,1
        if (
            self.model in ["MacPro6,1", "MacBookPro4,1"] or
            (cpu_gen < cpu_data.CPUGen.sandy_bridge.value and not self.model.startswith("MacBook"))
        ):
            self._enable_kernel_patch("CaseySJ - Fix PCI bus enumeration (Ventura)")
            self._enable_kernel_patch("Fix PCI bus enumeration (Sonoma)")
            self._log("  Kernel patch: PCI bus enumeration fix")

        # MacBoxTool firmware.py: SurPlus patches for pre-Sandy Bridge (no RDRAND)
        if cpu_gen <= cpu_data.CPUGen.sandy_bridge.value:
            self._enable_kernel_patch("SurPlus v1 - PART 1 of 2 - Patch read_erandom (inlined in _early_random)")
            self._enable_kernel_patch("SurPlus v1 - PART 2 of 2 - Patch register_and_init_prng")
            self._log("  Kernel patch: SurPlus (no RDRAND)")

        # MacBoxTool firmware.py: IOHIDFamily patch for Penryn and older
        if cpu_gen <= cpu_data.CPUGen.penryn.value:
            self._enable_kernel_patch_by_id("com.apple.iokit.IOHIDFamily")
            self._log("  Kernel patch: IOHIDFamily (Penryn)")

        # MacBoxTool security.py: Force FileVault on broken seal + KC UUID mismatch
        self._enable_kernel_patch_by_comment("Force FileVault on Broken Seal")
        self._log("  Kernel patch: Force FileVault on Broken Seal")

        # MacBoxTool misc.py: CoreGraphics fix for Ivy Bridge (f16c)
        if cpu_gen == cpu_data.CPUGen.ivy_bridge.value:
            self._log("  RestrictEvents: f16c patch (Ivy Bridge CoreGraphics)")

        # --- Misc/Firmware Quirks ---

        # VMM CPUID patch (legacy firmware.py:301)
        if self.constants.set_vmm_cpuid:
            self._enable_kernel_patch("VMM CPUID")
            self._log("  Kernel patch: VMM CPUID")

        # APFS Trim timeout (legacy storage.py:198)
        if self.constants.apfs_trim_timeout:
            config_mgr.set_quirk("SetApfsTrimTimeout", 0)
            self._log("  Kernel quirk: SetApfsTrimTimeout=0")

        # ConnectDrivers disable for hibernation (legacy firmware.py:321)
        if self.constants.disable_connectdrivers:
            self.config.setdefault("UEFI", {})["ConnectDrivers"] = False
            self._log("  UEFI: ConnectDrivers disabled (hibernation)")

        # WriteFlash NVRAM toggle (legacy firmware.py:325)
        if not self.constants.nvram_write:
            self.config.setdefault("NVRAM", {})["WriteFlash"] = False
            self._log("  NVRAM: WriteFlash disabled")

        # ShowPicker toggle (legacy misc.py:377)
        if not self.constants.showpicker:
            self.config.setdefault("Misc", {}).setdefault("Boot", {})["ShowPicker"] = False
            self._log("  Misc: ShowPicker disabled")

        # Timeout (legacy misc.py:380)
        if self.constants.oc_timeout != 5:
            self.config.setdefault("Misc", {}).setdefault("Boot", {})["Timeout"] = self.constants.oc_timeout
            self._log(f"  Misc: Timeout={self.constants.oc_timeout}")

        # Vault (legacy misc.py:385)
        if self.constants.vault:
            config_mgr.set_misc_security("Vault", "Secure")
            self._log("  Misc: Vault=Secure")

        # GopPassThrough for UGA→GOP (legacy graphics_audio.py:371)
        if model_info.get("UGA Graphics"):
            self.config.setdefault("UEFI", {}).setdefault("Output", {})["GopPassThrough"] = "Apple"
            self._log("  UEFI: GopPassThrough=Apple (UGA→GOP)")

        # OpenCore Debug mode (legacy misc.py:357-360)
        if self.constants.opencore_debug:
            self.config.setdefault("Misc", {}).setdefault("Debug", {})["Target"] = 0x43
            self.config.setdefault("Misc", {}).setdefault("Debug", {})["DisplayLevel"] = 0x80000042
            self._log("  Debug: OpenCore debug mode (Target=0x43)")

        # SecureBootModel (conditional on secure_status)
        if not self.constants.secure_status:
            config_mgr.set_misc_security("SecureBootModel", "Disabled")
            self._log("  SecureBootModel: Disabled")

        return self.log_lines

    def _enable_booter_patch(self, comment: str):
        for patch in self.config.get("Booter", {}).get("Patch", []):
            if patch.get("Comment") == comment:
                patch["Enabled"] = True
                return

    def _enable_kernel_patch(self, comment: str):
        for patch in self.config.get("Kernel", {}).get("Patch", []):
            if patch.get("Comment") == comment:
                patch["Enabled"] = True
                return

    def _enable_kernel_patch_by_id(self, identifier: str):
        for patch in self.config.get("Kernel", {}).get("Patch", []):
            if patch.get("Identifier") == identifier:
                patch["Enabled"] = True
                return

    def _enable_kernel_patch_by_comment(self, comment: str):
        self._enable_kernel_patch(comment)
