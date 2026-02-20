"""
audio.py: Audio-related kext management

Logic from MacBoxTool: graphics_audio.py
"""

import logging
from .base import KextManager
from ...datasets import model_array, smbios_data, os_data

logger = logging.getLogger(__name__)


class AudioKextManager(KextManager):
    """Manages Audio-related kexts."""

    def apply(self) -> list[str]:
        model_info = smbios_data.smbios_dictionary.get(self.model, {})
        max_os = model_info.get("Max OS Supported", 0)
        nforce = model_info.get("nForce Chipset", False)

        if self.constants.set_alc_usage is not True:
            return self.log_lines

        # Audio DeviceProperties for models dropped before Mojave
        if max_os <= os_data.os_data.high_sierra:
            if not (self.model.startswith("Xserve") or self.model in ("MacPro4,1", "iMac7,1", "iMac8,1")):
                hdef_path = "PciRoot(0x0)/Pci(0x8,0x0)" if nforce else "PciRoot(0x0)/Pci(0x1b,0x0)"
                if self.model == "MacPro3,1":
                    self.config["DeviceProperties"]["Add"][hdef_path] = {
                        "apple-layout-id": 90, "use-apple-layout-id": 1, "alc-layout-id": 13,
                    }
                else:
                    self.config["DeviceProperties"]["Add"][hdef_path] = {
                        "apple-layout-id": 90, "use-apple-layout-id": 1, "use-layout-id": 1,
                    }
                self._log(f"  DeviceProperties: Audio layout at {hdef_path}")

        # AppleALC for legacy audio or Mac Pro models
        if (self.model in model_array.LegacyAudio or self.model in model_array.MacPro):
            self.enable_kext("AppleALC.kext", self.constants.applealc_version)
        elif max_os <= os_data.os_data.high_sierra:
            self.enable_kext("AppleALC.kext", self.constants.applealc_version)
        elif (self.model.startswith("MacPro") and self.model != "MacPro6,1") or self.model.startswith("Xserve"):
            self.enable_kext("AppleALC.kext", self.constants.applealc_version)

        return self.log_lines
