"""
usb.py: USB-related kext management

Logic from MacBoxTool: misc.py (_usb_handling)
"""

import shutil
import logging
from pathlib import Path
from .base import KextManager
from ...datasets import model_array, smbios_data, cpu_data

logger = logging.getLogger(__name__)


class USBKextManager(KextManager):
    """Manages USB-related kexts."""

    def apply(self) -> list[str]:
        self._usb_map_handling()
        return self.log_lines

    def _usb_map_handling(self):
        """USB Map kext handler (legacy misc.py:288-311)."""
        usb_map_path = self.constants.plist_folder_path / "AppleUSBMaps/Info.plist"
        usb_map_tahoe_path = self.constants.plist_folder_path / "AppleUSBMaps/Info-Tahoe.plist"

        needs_map = (
            self.model in model_array.Missing_USB_Map
            or self.model in model_array.Missing_USB_Map_Ventura
            or self.constants.serial_settings in ("Moderate", "Advanced")
        )
        if not (
            usb_map_path.exists()
            and usb_map_tahoe_path.exists()
            and (not self.constants.allow_oc_everywhere or self.constants.allow_native_spoofs)
            and self.model not in ("Xserve2,1", "Pyquick1,1")
            and needs_map
        ):
            return

        # Create USB-Map.kext under the build kexts_path (not constants path)
        map_contents = self.kexts_path / "USB-Map.kext" / "Contents"
        map_contents.mkdir(parents=True, exist_ok=True)
        shutil.copy(usb_map_path, map_contents)

        # Create USB-Map-Tahoe.kext (rename Info-Tahoe.plist -> Info.plist)
        map_contents_tahoe = self.kexts_path / "USB-Map-Tahoe.kext" / "Contents"
        map_contents_tahoe.mkdir(parents=True, exist_ok=True)
        shutil.copy(usb_map_tahoe_path, map_contents_tahoe / "Info.plist")

        # Enable both in config
        for bp in ("USB-Map.kext", "USB-Map-Tahoe.kext"):
            for entry in self.config.get("Kernel", {}).get("Add", []):
                if entry.get("BundlePath") == bp:
                    entry["Enabled"] = True
        self._log("  USB-Map.kext + USB-Map-Tahoe.kext")

        # Ventura-only models: set MinKernel unless serial spoofing
        if (
            self.model in model_array.Missing_USB_Map_Ventura
            and self.constants.serial_settings not in ("Moderate", "Advanced")
        ):
            for entry in self.config.get("Kernel", {}).get("Add", []):
                if entry.get("BundlePath") == "USB-Map.kext":
                    entry["MinKernel"] = "22.0.0"
            self._log("  USB-Map.kext MinKernel=22.0.0 (Ventura+)")
