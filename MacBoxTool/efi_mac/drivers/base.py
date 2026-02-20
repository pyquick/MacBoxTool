"""
base.py: Base UEFI Driver management
"""


import logging
from ... import constants
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

    def enable_base_drivers(self) -> list[str]:
        """
        Enable base UEFI drivers needed for all models.

        Returns:
            Log lines
        """
        self._log("[STEP] Enabling UEFI Drivers")

        # OpenRuntime is always required
        self.enable_driver("OpenRuntime.efi")
        self._log("  + OpenRuntime.efi")

        # OpenCanopy for boot picker (PickerMode=External)
        self.enable_driver("OpenCanopy.efi")
        self._log("  + OpenCanopy.efi")

        # ResetNvramEntry for NVRAM reset option
        self.enable_driver("ResetNvramEntry.efi")
        self._log("  + ResetNvramEntry.efi")

        # UEFI APFS settings
        self.config_mgr.set_uefi_apfs("EnableJumpstart", True)
        self.config_mgr.set_uefi_apfs("MinDate", -1)
        self.config_mgr.set_uefi_apfs("MinVersion", -1)
        self._log("  APFS: EnableJumpstart=True, MinDate=-1, MinVersion=-1")

        return self.log_lines
