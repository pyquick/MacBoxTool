"""
base.py: Base UEFI Driver management

Logic from MacBoxTool: firmware.py (_firmware_driver_handling), misc.py (_general_oc_handling)
"""


import shutil
import logging
from pathlib import Path
from ... import constants
from ...datasets import smbios_data, cpu_data
from ..config import ConfigManager

logger = logging.getLogger(__name__)


class DriverManager:
    """Manages UEFI Driver operations for EFI building."""

    def __init__(self, config: dict, constants: constants.Constants, model: str, paths: dict):
        self.config = config
        self.constants = constants
        self.model = model
        self.paths = paths
        self.log_lines: list[str] = []

        self.config_mgr = ConfigManager(config, paths["plist_path"])

    def _log(self, msg: str):
        logger.info(msg)
        self.log_lines.append(msg)

    def enable_driver(self, driver_path: str) -> bool:
        """
        Enable a driver in config by Path.

        Args:
            driver_path: Path of the driver (e.g., "OpenRuntime.efi")

        Returns:
            True if found and enabled, False otherwise
        """
        return self.config_mgr.enable_driver(driver_path)

    def _copy_and_enable(self, src_path: Path, filename: str) -> bool:
        """Copy driver to Drivers/ and enable in config."""
        drivers_path = self.paths["drivers_path"]
        if src_path.exists():
            shutil.copy(src_path, drivers_path)
            self.enable_driver(filename)
            self._log(f"  + {filename}")
            return True
        self._log(f"  [WARN] Driver not found: {src_path}")
        return False

    def enable_base_drivers(self) -> list[str]:
        """Enable base UEFI drivers needed for all models."""
        self._log("[STEP] Enabling UEFI Drivers")

        model_info = smbios_data.smbios_dictionary.get(self.model, {})
        cpu_gen = model_info.get("CPU Generation", 999)

        # Base drivers (always required)
        for drv in ("OpenRuntime.efi", "OpenCanopy.efi", "ResetNvramEntry.efi"):
            self.enable_driver(drv)
            self._log(f"  + {drv}")

        # macOS 26 APFS FileVault 2 fix (legacy firmware.py:224-227)
        # The macOS 26 APFS EFI driver's FV2 is broken, use macOS 15's instead
        if self.constants.allow_apfs_aligned_patch:
            self._copy_and_enable(self.constants.sequoia_apfs_driver_path, "apfs_aligned.efi")
            self.config_mgr.set_uefi_apfs("EnableJumpstart", False)
        else:
            self.config_mgr.set_uefi_apfs("EnableJumpstart", True)
        self.config_mgr.set_uefi_apfs("MinDate", -1)
        self.config_mgr.set_uefi_apfs("MinVersion", -1)

        # ExFat for pre-Sandy Bridge (legacy firmware.py:230-234)
        if cpu_gen < cpu_data.CPUGen.sandy_bridge.value:
            self._copy_and_enable(self.constants.exfat_legacy_driver_path, "ExFatDxeLegacy.efi")

        # NVMe boot support (legacy firmware.py:237-240)
        if self.constants.nvme_boot:
            self._copy_and_enable(self.constants.nvme_driver_path, "NvmExpressDxe.efi")

        # USB 3.0 boot support (legacy firmware.py:243-249)
        if self.constants.xhci_boot:
            self._copy_and_enable(self.constants.xhci_driver_path, "XhciDxe.efi")
            self._copy_and_enable(self.constants.usb_bus_driver_path, "UsbBusDxe.efi")

        # PCIe Link Rate fix for MacPro3,1 (legacy firmware.py:252-255)
        if self.model == "MacPro3,1":
            self._copy_and_enable(self.constants.link_rate_driver_path, "FixPCIeLinkRate.efi")

        # AMD GOP injection (legacy graphics_audio.py:405)
        if self.constants.amd_gop_injection:
            self._copy_and_enable(self.constants.amd_gop_driver_path, "AMDGOP.efi")

        # Nvidia Kepler GOP injection (legacy graphics_audio.py:410)
        if self.constants.nvidia_kepler_gop_injection:
            self._copy_and_enable(self.constants.nvidia_kepler_gop_driver_path, "NVGOP_GK.efi")

        return self.log_lines
