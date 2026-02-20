"""
config.py: config.plist management
"""


import logging
import plistlib
from pathlib import Path

logger = logging.getLogger(__name__)


class ConfigManager:
    """Manages config.plist loading, modification, and saving."""

    def __init__(self, config: dict, plist_path: Path):
        self.config = config
        self.plist_path = plist_path
        self.log_lines: list[str] = []

    def _log(self, msg: str):
        logger.info(msg)
        self.log_lines.append(msg)

    def cleanup(self) -> list[str]:
        """
        Remove disabled entries from config.

        Returns:
            Log lines
        """
        start = len(self.log_lines)
        self._log("[STEP] Cleanup")

        # Remove disabled kernel entries
        kernel_add = self.config.get("Kernel", {}).get("Add", [])
        enabled = [k for k in kernel_add if k.get("Enabled", False)]
        removed = len(kernel_add) - len(enabled)
        self.config["Kernel"]["Add"] = enabled
        self._log(f"  Removed {removed} disabled kext entries")

        # Remove disabled ACPI entries
        acpi_add = self.config.get("ACPI", {}).get("Add", [])
        enabled_acpi = [a for a in acpi_add if a.get("Enabled", False)]
        removed_acpi = len(acpi_add) - len(enabled_acpi)
        self.config["ACPI"]["Add"] = enabled_acpi
        self._log(f"  Removed {removed_acpi} disabled ACPI entries")

        # Remove disabled driver entries
        drivers = self.config.get("UEFI", {}).get("Drivers", [])
        enabled_drv = [d for d in drivers if d.get("Enabled", True)]
        self.config["UEFI"]["Drivers"] = enabled_drv

        # Remove disabled tool entries
        tools = self.config.get("Misc", {}).get("Tools", [])
        enabled_tools = [t for t in tools if t.get("Enabled", True)]
        self.config["Misc"]["Tools"] = enabled_tools

        return self.log_lines[start:]

    def save(self) -> list[str]:
        """
        Save config.plist to disk.

        Returns:
            Log lines
        """
        start = len(self.log_lines)
        self._log("[STEP] Saving config.plist")
        plistlib.dump(self.config, self.plist_path.open("wb"), sort_keys=True)
        self._log(f"  Saved: {self.plist_path}")
        return self.log_lines[start:]

    def get_kernel_add(self) -> list:
        """Get Kernel/Add section."""
        return self.config.get("Kernel", {}).get("Add", [])

    def get_acpi_add(self) -> list:
        """Get ACPI/Add section."""
        return self.config.get("ACPI", {}).get("Add", [])

    def get_drivers(self) -> list:
        """Get UEFI/Drivers section."""
        return self.config.get("UEFI", {}).get("Drivers", [])

    def get_nvram_add(self) -> dict:
        """Get NVRAM/Add section."""
        return self.config.get("NVRAM", {}).get("Add", {})

    def enable_kext(self, kext_name: str) -> bool:
        """
        Enable a kext in config by BundlePath.

        Args:
            kext_name: BundlePath of the kext (e.g., "Lilu.kext")

        Returns:
            True if found and enabled, False otherwise
        """
        for entry in self.config.get("Kernel", {}).get("Add", []):
            if entry.get("BundlePath") == kext_name:
                entry["Enabled"] = True
                return True
        return False

    def enable_acpi(self, acpi_name: str) -> bool:
        """
        Enable an ACPI entry in config by Path.

        Args:
            acpi_name: Path of the ACPI file (e.g., "SSDT-EC.aml")

        Returns:
            True if found and enabled, False otherwise
        """
        for entry in self.config.get("ACPI", {}).get("Add", []):
            if entry.get("Path") == acpi_name:
                entry["Enabled"] = True
                return True
        return False

    def enable_driver(self, driver_path: str) -> bool:
        """
        Enable a driver in config by Path.

        Args:
            driver_path: Path of the driver (e.g., "OpenRuntime.efi")

        Returns:
            True if found and enabled, False otherwise
        """
        for entry in self.config.get("UEFI", {}).get("Drivers", []):
            if entry.get("Path") == driver_path:
                entry["Enabled"] = True
                return True
        return False

    def set_quirk(self, quirk_name: str, value: bool) -> bool:
        """
        Set a kernel quirk value.

        Args:
            quirk_name: Name of the quirk (e.g., "DisableLinkeditJettison")
            value: Boolean value to set

        Returns:
            True if found and set, False otherwise
        """
        quirks = self.config.get("Kernel", {}).get("Quirks", {})
        if quirk_name in quirks:
            quirks[quirk_name] = value
            return True
        return False

    def set_booter_quirk(self, quirk_name: str, value) -> bool:
        """Set a Booter quirk value."""
        quirks = self.config.get("Booter", {}).get("Quirks", {})
        if quirk_name in quirks:
            quirks[quirk_name] = value
            return True
        return False

    def set_uefi_apfs(self, key: str, value) -> bool:
        """Set a UEFI/APFS value."""
        apfs = self.config.get("UEFI", {}).get("APFS", {})
        if key in apfs:
            apfs[key] = value
            return True
        return False

    def set_misc_security(self, key: str, value) -> bool:
        """Set a Misc/Security value."""
        security = self.config.get("Misc", {}).get("Security", {})
        if key in security:
            security[key] = value
            return True
        return False

    def set_platform_info(self, model: str, board_id: str = None):
        """Configure PlatformInfo for the target model."""
        pi = self.config.setdefault("PlatformInfo", {})
        pi["Automatic"] = True
        pi["UpdateDataHub"] = True
        pi["UpdateNVRAM"] = True
        pi["UpdateSMBIOS"] = True
        generic = pi.setdefault("Generic", {})
        generic["SystemProductName"] = model
        if board_id:
            generic["SystemProductName"] = model
            # Write board-id into NVRAM for DataHub injection
            nvram_add = self.config.setdefault("NVRAM", {}).setdefault("Add", {})
            dh_guid = nvram_add.setdefault("4D1EDE05-38C7-4A6A-9CC6-4BCCA8B38C14", {})
            dh_guid["board-id"] = board_id
