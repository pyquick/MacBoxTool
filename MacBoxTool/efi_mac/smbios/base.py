"""
base.py: SMBIOS information management
"""


import logging
from datetime import date
from ...datasets import smbios_data
from ... import constants

logger = logging.getLogger(__name__)


class SMBIOSManager:
    """Manages SMBIOS information for EFI building."""

    def __init__(self, config: dict, constants: constants.Constants, model: str, paths: dict):
        self.config = config
        self.constants = constants
        self.model = model
        self.paths = paths
        self.log_lines: list[str] = []

    def _log(self, msg: str):
        logger.info(msg)
        self.log_lines.append(msg)

    def set_revision(self) -> list[str]:
        """
        Set revision info in config.plist.

        Returns:
            Log lines
        """
        self._log("[STEP] Setting revision info")

        rev = self.config.setdefault("#Revision", {})
        rev["Build-Version"] = f"MacBoxTool {self.constants.mactoolbox_version} - {date.today()}"
        rev["Build-Type"] = "OpenCore Built for External Machine"
        rev["OpenCore-Version"] = f"{self.constants.opencore_version} - RELEASE"
        rev["Original-Model"] = self.model

        self._log(f"  Model: {self.model}")
        self._log(f"  Version: {self.constants.mactoolbox_version}")

        # Configure PlatformInfo with Board ID from smbios_data
        from ..config import ConfigManager
        config_mgr = ConfigManager(self.config, self.paths["plist_path"])
        model_info = smbios_data.smbios_dictionary.get(self.model, {})
        board_id = model_info.get("Board ID")
        config_mgr.set_platform_info(self.model, board_id)
        self._log(f"  PlatformInfo: SystemProductName={self.model}, BoardID={board_id}")

        # Import and apply NVRAM settings
        from .nvram import NVRAMManager
        nvram_mgr = NVRAMManager(self.config, self.constants, self.model, self.paths)
        self.log_lines.extend(nvram_mgr.apply())

        return self.log_lines
