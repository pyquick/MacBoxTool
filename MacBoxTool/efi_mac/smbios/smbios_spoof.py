"""
smbios_spoof.py: SMBIOS spoofing logic (Minimal/Moderate/Advanced)

Logic from efi_builder: smbios.py
"""

import ast
import binascii
import logging
import plistlib
import subprocess
import uuid
from pathlib import Path

from ... import constants
from ...datasets import smbios_data, model_array

logger = logging.getLogger(__name__)


class SMBIOSSpoofManager:
    """Manages SMBIOS spoofing for EFI building."""

    def __init__(self, config: dict, constants: constants.Constants, model: str, paths: dict):
        self.config = config
        self.constants = constants
        self.model = model
        self.paths = paths
        self.log_lines: list[str] = []

        self.spoofed_model = self._get_spoofed_model()
        self.spoofed_board = self._get_spoofed_board()

    def _log(self, msg: str):
        logger.info(msg)
        self.log_lines.append(msg)

    def _get_spoofed_model(self) -> str:
        if self.constants.override_smbios != "Default":
            return self.constants.override_smbios
        model_info = smbios_data.smbios_dictionary.get(self.model, {})
        return model_info.get("Spoofed Model", self.model)

    def _get_spoofed_board(self) -> str:
        info = smbios_data.smbios_dictionary.get(self.spoofed_model, {})
        return info.get("Board ID", "")

    def apply(self) -> list[str]:
        """Apply SMBIOS spoofing based on serial_settings level."""
        level = self.constants.serial_settings
        if level == "None":
            self._log("  SMBIOS: No spoofing (Board ID exemption only)")
            # SMC-Spoof + Board ID exemption handled in quirks
            self._enable_smc_spoof()
            return self.log_lines

        self._log(f"  SMBIOS: Spoofing level={level}, target={self.spoofed_model}")

        # USB rename patches for Moderate/Advanced
        if level in ("Moderate", "Advanced"):
            self._enable_usb_renames()

        # SMC-Spoof for all levels
        self._enable_smc_spoof()

        # Apply level-specific patches
        if level == "Minimal":
            self._minimal_patch()
        elif level == "Moderate":
            self._moderate_patch()
        elif level == "Advanced":
            self._advanced_patch()

        return self.log_lines

    def _enable_smc_spoof(self):
        """Enable SMC exemption patch and kext."""
        for patch in self.config.get("Kernel", {}).get("Patch", []):
            if patch.get("Identifier") == "com.apple.driver.AppleSMC":
                patch["Enabled"] = True

    def _enable_usb_renames(self):
        """Enable USB rename ACPI patches (XHC1→SHC1, EHC1→EH01, EHC2→EH02)."""
        for comment in ("XHC1 to SHC1", "EHC1 to EH01", "EHC2 to EH02"):
            for patch in self.config.get("ACPI", {}).get("Patch", []):
                if patch.get("Comment") == comment:
                    patch["Enabled"] = True
        self._log("  USB rename patches enabled")

    def _minimal_patch(self):
        """Minimal: Board ID + Firmware Features + BIOS version."""
        pi = self.config.setdefault("PlatformInfo", {})
        pi["UpdateNVRAM"] = True
        pi["UpdateSMBIOS"] = True
        pi["UpdateDataHub"] = True

        dh = pi.setdefault("DataHub", {})
        dh["BoardProduct"] = self.spoofed_board
        dh["SystemProductName"] = self.model

        smbios = pi.setdefault("SMBIOS", {})
        smbios["BoardProduct"] = self.spoofed_board
        smbios["SystemProductName"] = self.model
        smbios["BoardVersion"] = self.model
        smbios["BIOSVersion"] = "9999.999.999.999.999"

        pnvram = pi.setdefault("PlatformNVRAM", {})
        pnvram["BID"] = self.spoofed_board

        self._log("  Minimal spoof applied")

    def _moderate_patch(self):
        """Moderate: Full SMBIOS replacement (retains original serials)."""
        pi = self.config.setdefault("PlatformInfo", {})
        pi["Automatic"] = True
        pi["UpdateDataHub"] = True
        pi["UpdateNVRAM"] = True
        pi["UpdateSMBIOS"] = True
        self.config.setdefault("UEFI", {}).setdefault("ProtocolOverrides", {})["DataHub"] = True
        pi.setdefault("Generic", {})["SystemProductName"] = self.spoofed_model
        self._log("  Moderate spoof applied")

    def _advanced_patch(self):
        """Advanced: Full SMBIOS + generated/custom serials."""
        sn, mlb = self._get_serials()

        pi = self.config.setdefault("PlatformInfo", {})
        pi["Automatic"] = True
        pi["UpdateDataHub"] = True
        pi["UpdateNVRAM"] = True
        pi["UpdateSMBIOS"] = True
        self.config.setdefault("UEFI", {}).setdefault("ProtocolOverrides", {})["DataHub"] = True

        generic = pi.setdefault("Generic", {})
        generic["ROM"] = binascii.unhexlify("0016CB445566")
        generic["SystemProductName"] = self.spoofed_model
        generic["SystemSerialNumber"] = sn
        generic["MLB"] = mlb
        generic["SystemUUID"] = str(uuid.uuid4()).upper()

        mbt = self.config.setdefault("NVRAM", {}).setdefault("Add", {}).setdefault(
            "4D1FDA02-38C7-4A6A-9CC6-4BCCA8B30102", {}
        )
        mbt["OCLP-Spoofed-SN"] = sn
        mbt["OCLP-Spoofed-MLB"] = mlb
        self._log("  Advanced spoof applied")

    def _get_serials(self) -> tuple:
        """Get serial numbers from custom override or macserial."""
        if self.constants.custom_serial_number and self.constants.custom_board_serial_number:
            return self.constants.custom_serial_number, self.constants.custom_board_serial_number
        try:
            result = subprocess.run(
                [str(self.constants.macserial_path), "--generate", "--model", self.spoofed_model, "--num", "1"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=10
            )
            parts = result.stdout.decode().strip().split(" | ")
            if len(parts) == 2:
                return parts[0], parts[1]
        except Exception as e:
            self._log(f"  [WARN] macserial failed: {e}")
        return "XXXXXXXXXXXX", "XXXXXXXXXXXXXXXXX"
