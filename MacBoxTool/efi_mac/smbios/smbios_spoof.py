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
from ...datasets import smbios_data, model_array, cpu_data

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
            self._enable_smc_spoof()
            # UEFI 1.2 DataHub fix for Ivy Bridge and older (Lilu race condition)
            model_info = smbios_data.smbios_dictionary.get(self.model, {})
            cpu_gen = model_info.get("CPU Generation", 999)
            if cpu_gen <= cpu_data.CPUGen.ivy_bridge.value:
                pi = self.config.setdefault("PlatformInfo", {})
                pi.setdefault("DataHub", {})["BoardProduct"] = self._get_spoofed_board()
                pi["UpdateDataHub"] = True
                self._log("  DataHub BoardProduct set (UEFI 1.2 Lilu fix)")
            # Custom serial numbers in None mode
            if self.constants.custom_serial_number and self.constants.custom_board_serial_number:
                pi = self.config.setdefault("PlatformInfo", {})
                pi["UpdateSMBIOS"] = True
                pi["UpdateNVRAM"] = True
                smbios_sec = pi.setdefault("SMBIOS", {})
                smbios_sec["SystemSerialNumber"] = self.constants.custom_serial_number
                smbios_sec["BoardSerialNumber"] = self.constants.custom_board_serial_number
                pi.setdefault("PlatformNVRAM", {})["MLB"] = self.constants.custom_board_serial_number
                self._log("  Custom serial numbers applied (None mode)")
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

        # Post-processing: strip USB maps and patch CPUFriend for spoofed model
        self._strip_usb_map()
        self._patch_cpufriend_model()

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

        smbios_sec = pi.setdefault("SMBIOS", {})
        smbios_sec["BoardProduct"] = self.spoofed_board
        smbios_sec["SystemProductName"] = self.model
        smbios_sec["BoardVersion"] = self.model
        smbios_sec["BIOSVersion"] = "9999.999.999.999.999"

        pnvram = pi.setdefault("PlatformNVRAM", {})
        pnvram["BID"] = self.spoofed_board

        # FirmwareFeatures generation for Minimal mode
        fw_features = self._generate_fw_features()
        if fw_features is not None:
            pnvram["FirmwareFeatures"] = fw_features
            pnvram["FirmwareFeaturesMask"] = fw_features
            smbios_sec["FirmwareFeatures"] = fw_features
            smbios_sec["FirmwareFeaturesMask"] = fw_features
            self._log("  FirmwareFeatures generated for Minimal spoof")

        # Custom serial numbers in Minimal mode
        if self.constants.custom_serial_number and self.constants.custom_board_serial_number:
            smbios_sec["SystemSerialNumber"] = self.constants.custom_serial_number
            smbios_sec["BoardSerialNumber"] = self.constants.custom_board_serial_number
            pnvram["MLB"] = self.constants.custom_board_serial_number
            self._log("  Custom serial numbers applied (Minimal mode)")

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

        # Custom serial numbers in Moderate mode
        if self.constants.custom_serial_number and self.constants.custom_board_serial_number:
            generic = pi.setdefault("Generic", {})
            generic["SystemSerialNumber"] = self.constants.custom_serial_number
            generic["MLB"] = self.constants.custom_board_serial_number
            self._log("  Custom serial numbers applied (Moderate mode)")

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

    def _generate_fw_features(self):
        """Generate FirmwareFeatures value for the spoofed model."""
        spoofed_info = smbios_data.smbios_dictionary.get(self.spoofed_model, {})
        fw = spoofed_info.get("FirmwareFeatures")
        if fw is not None:
            if isinstance(fw, int):
                return fw.to_bytes(8, "little") if fw > 0xFFFFFFFF else fw.to_bytes(4, "little")
            return fw
        return None

    def _strip_usb_map(self):
        """Post-process USB-Map kexts to match spoofed model."""
        if self.spoofed_model == self.model:
            return
        level = self.constants.serial_settings

        for map_name in ("USB-Map.kext", "USB-Map-Tahoe.kext"):
            map_plist = self.paths.get("kexts_path", Path()) / map_name / "Contents" / "Info.plist"
            if not map_plist.exists():
                continue
            try:
                with open(map_plist, "rb") as f:
                    data = plistlib.load(f)
                iokit = data.get("IOKitPersonalities", {})
                # Strip entries not matching current model
                keys_to_remove = [k for k in iokit if k != self.model]
                for k in keys_to_remove:
                    del iokit[k]
                # Rename model entry to spoofed model
                if self.model in iokit:
                    iokit[self.spoofed_model] = iokit.pop(self.model)
                    entry = iokit[self.spoofed_model]
                    if "model" in entry:
                        entry["model"] = self.spoofed_model
                # Revert USB renames for Minimal/None serial settings
                if level in ("Minimal", "None"):
                    raw = plistlib.dumps(data).decode("utf-8", errors="replace")
                    raw = raw.replace("EH01", "EHC1").replace("EH02", "EHC2").replace("SHC1", "XHC1")
                    data = plistlib.loads(raw.encode("utf-8"))
                with open(map_plist, "wb") as f:
                    plistlib.dump(data, f)
                self._log(f"  USB-Map post-processed: {map_name}")
            except Exception as e:
                self._log(f"  [WARN] Failed to strip USB map {map_name}: {e}")

    def _patch_cpufriend_model(self):
        """Patch CPUFriendDataProvider to match spoofed model."""
        if self.spoofed_model == self.model:
            return
        pp_plist = self.paths.get("kexts_path", Path()) / "CPUFriendDataProvider.kext" / "Contents" / "Info.plist"
        if not pp_plist.exists():
            return
        try:
            with open(pp_plist, "rb") as f:
                data = plistlib.load(f)
            iokit = data.get("IOKitPersonalities", {})
            if self.model in iokit:
                iokit[self.spoofed_model] = iokit.pop(self.model)
                entry = iokit[self.spoofed_model]
                if "cf-frequency-data" in entry:
                    raw = str(entry["cf-frequency-data"])
                    if self.model in raw:
                        raw = raw.replace(self.model, self.spoofed_model)
                        entry["cf-frequency-data"] = ast.literal_eval(raw)
            with open(pp_plist, "wb") as f:
                plistlib.dump(data, f)
            self._log(f"  CPUFriendDataProvider patched: {self.model} → {self.spoofed_model}")
        except Exception as e:
            self._log(f"  [WARN] Failed to patch CPUFriendDataProvider: {e}")

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
