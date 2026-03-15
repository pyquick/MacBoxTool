"""
platform_info.py: SMBIOS / PlatformInfo configuration for Hackintosh EFI

Applies the chosen SMBIOS model and sets all Generic PlatformInfo fields.
Handles vendor-specific overrides (Dell UpdateSMBIOSMode=Custom).

References: https://dortania.github.io/OpenCore-Install-Guide/
"""

import logging
from ..datasets.smbios_data import smbios_dictionary
from ..efi_mac.config import ConfigManager

logger = logging.getLogger(__name__)

# Vendors that need UpdateSMBIOSMode=Custom + CustomSMBIOSGuid=True
# (prevents SMBIOS data from leaking to non-Apple OS)
_VENDOR_CUSTOM_SMBIOS = {"DELL"}


class HackPlatformInfo:
    """Configure PlatformInfo / SMBIOS for Hackintosh."""

    def __init__(self, config: dict, constants, paths: dict,
                 smbios_model: str, vendor: str = ""):
        self.config = config
        self.constants = constants
        self.paths = paths
        self.smbios_model = smbios_model
        self.vendor = vendor.upper() if vendor else ""
        self.log_lines: list[str] = []
        self.config_mgr = ConfigManager(config, paths["plist_path"])

    def _log(self, msg: str):
        logger.info(msg)
        self.log_lines.append(msg)

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def apply(self) -> list[str]:
        """Apply PlatformInfo settings."""
        self._log("[STEP] Setting PlatformInfo (Hackintosh)")

        model_info = smbios_dictionary.get(self.smbios_model, {})
        board_id = model_info.get("Board ID", "")

        self._log(f"  SMBIOS model : {self.smbios_model}")
        if model_info.get("Marketing Name"):
            self._log(f"  Marketing    : {model_info['Marketing Name']}")
        self._log(f"  Board ID     : {board_id}")

        # Write base PlatformInfo keys
        self.config_mgr.set_platform_info(self.smbios_model, board_id)

        # Populate PlatformInfo dict
        pi = self.config.setdefault("PlatformInfo", {})
        pi["Automatic"] = True
        pi["UpdateDataHub"] = True
        pi["UpdateNVRAM"] = True
        pi["UpdateSMBIOS"] = True

        # Default: Create — overwrites SMBIOS tables in memory
        # Custom: only patches specific fields — needed for Dell to avoid
        # breaking their BIOS self-test (CustomSMBIOSGuid must also be True)
        if self.vendor in _VENDOR_CUSTOM_SMBIOS:
            pi["UpdateSMBIOSMode"] = "Custom"
            pi["CustomSMBIOSGuid"] = True
            self._log(f"  UpdateSMBIOSMode=Custom, CustomSMBIOSGuid=True "
                      f"(vendor: {self.vendor})")
        else:
            pi["UpdateSMBIOSMode"] = "Create"

        # Generic section
        generic = pi.setdefault("Generic", {})
        generic["SystemProductName"] = self.smbios_model
        generic["AdviseFeatures"] = True

        # ROM: 6-byte network MAC (used for Apple ID / iServices)
        # Left empty — user must fill in their actual NIC MAC address
        if not generic.get("ROM"):
            generic["ROM"] = b"\x00\x00\x00\x00\x00\x00"
            self._log("  [NOTE] ROM: replace with your NIC MAC address "
                      "(required for iMessage / FaceTime)")

        # Serial / MLB / UUID must be generated with GenSMBIOS
        # We write empty strings as explicit placeholders
        for field in ("SystemSerialNumber", "MLB", "SystemUUID"):
            if not generic.get(field):
                generic[field] = ""

        self._log("  [NOTE] Generate SystemSerialNumber / MLB / SystemUUID "
                  "with GenSMBIOS before booting")

        return self.log_lines
