"""
gpu.py: GPU-related kext management

Logic from OCLP-R: graphics_audio.py (_prebuilt_assumption path)
"""

import logging
from .base import KextManager
from ...datasets import model_array, smbios_data, os_data

logger = logging.getLogger(__name__)


class GPUKextManager(KextManager):
    """Manages GPU-related kexts."""

    def apply(self) -> list[str]:
        model_info = smbios_data.smbios_dictionary.get(self.model, {})
        max_os = model_info.get("Max OS Supported", 0)

        # WhateverGreen only for models that need GPU patching
        # OCLP-R: enabled for legacy GPU models, MacPro, DualGPU, MXM iMac
        needs_weg = (
            self.model in model_array.LegacyGPU or
            self.model in model_array.ModernGPU or
            self.model in model_array.MacPro or
            self.model in model_array.MXMiMac or
            self.model in model_array.DualGPUPatch
        )
        if needs_weg:
            self.enable_kext("WhateverGreen.kext", self.constants.whatevergreen_version)
            self._log("  WhateverGreen (GPU patching)")

        # OCLP-R graphics_audio.py: BacklightInjector for MXM iMacs
        if self.model in model_array.MXMiMac:
            self._log("  MXM iMac - may need BacklightInjector")

        # OCLP-R graphics_audio.py: AMDGPUWakeHandler for demuxed MacBookPro8,2/8,3
        if self.model in ("MacBookPro8,2", "MacBookPro8,3"):
            self._log("  MacBookPro8,x - dual GPU (software demux candidate)")

        # OCLP-R misc.py: KDKlessWorkaround for KDKless GPUs (Ivy-Skylake iGPU, Kepler)
        if self.model in model_array.ModernGPU and max_os < os_data.os_data.sonoma:
            self.enable_kext("KDKlessWorkaround.kext", self.constants.kdkless_version)
            self._log("  KDKlessWorkaround (KDKless GPU)")

        return self.log_lines
