"""
security.py: Security-related kext management

Logic from OCLP-R: security.py, firmware.py, misc.py
"""

import logging
from .base import KextManager
from ...datasets import smbios_data, cpu_data, os_data

logger = logging.getLogger(__name__)


class SecurityKextManager(KextManager):
    """Manages Security-related kexts."""

    def apply(self) -> list[str]:
        model_info = smbios_data.smbios_dictionary.get(self.model, {})
        cpu_gen = model_info.get("CPU Generation", 999)
        max_os = model_info.get("Max OS Supported", 0)

        # OCLP-R misc.py: FeatureUnlock only for models older than Sonoma
        if max_os < os_data.os_data.sonoma:
            self.enable_kext("FeatureUnlock.kext", self.constants.featureunlock_version)
            self._log("  FeatureUnlock (pre-Sonoma model)")

        # OCLP-R firmware.py: CryptexFixup only for Ivy Bridge and older (no AVX2.0)
        if cpu_gen <= cpu_data.CPUGen.ivy_bridge.value:
            self.enable_kext("CryptexFixup.kext", self.constants.cryptexfixup_version)
            self._log("  CryptexFixup (pre-AVX2.0, Ivy Bridge or older)")

        # OCLP-R firmware.py: SSE4.1 kexts for Penryn and older
        if cpu_gen <= cpu_data.CPUGen.penryn.value:
            self.enable_kext("AAAMouSSE.kext", self.constants.mousse_version)
            self.enable_kext("telemetrap.kext", self.constants.telemetrap_version)
            self._log("  AAAMouSSE + telemetrap (Penryn SSE4.1)")

        # OCLP-R firmware.py: Legacy power management for Ivy Bridge and older
        if cpu_gen <= cpu_data.CPUGen.ivy_bridge.value:
            self.enable_kext("AppleIntelCPUPowerManagement.kext", self.constants.aicpupm_version)
            self.enable_kext("AppleIntelCPUPowerManagementClient.kext", self.constants.aicpupm_version)
            self._log("  AICPUPM (legacy power management)")

        # OCLP-R firmware.py: ASPP-Override for Sandy Bridge and older
        if cpu_gen <= cpu_data.CPUGen.sandy_bridge.value:
            self.enable_kext("ASPP-Override.kext", self.constants.aspp_override_version)
            self._log("  ASPP-Override (pre-Ivy Bridge power management)")

        # OCLP-R firmware.py: NoAVXFSCompressionTypeZlib for pre-Sandy Bridge
        if cpu_gen < cpu_data.CPUGen.sandy_bridge.value:
            self.enable_kext("NoAVXFSCompressionTypeZlib.kext", self.constants.apfs_zlib_version)
            self.enable_kext("NoAVXFSCompressionTypeZlib-AVXpel.kext", self.constants.apfs_zlib_v2_version)
            self._log("  NoAVXFSCompressionTypeZlib (pre-Sandy Bridge)")

        # OCLP-R misc.py: RestrictEvents for pre-Sonoma (verbose mode, process blocking)
        # This must be loaded BEFORE EFICheckDisabler as they conflict
        # https://github.com/dortania/OpenCore-Legacy-Patcher/issues/940
        if max_os < os_data.os_data.sonoma:
            self.enable_kext("RestrictEvents.kext", self.constants.restrictevents_version)
            self._log("  RestrictEvents (pre-Sonoma)")

        # OCLP-R misc.py: EFICheckDisabler - conflict with RestrictEvents
        # Only enable if RestrictEvents is NOT enabled
        restrictevents_enabled = self._is_kext_enabled("RestrictEvents.kext")
        if not restrictevents_enabled:
            self.enable_kext("EFICheckDisabler.kext", self.constants.eficheckdisabler_version)
            self._log("  EFICheckDisabler (RestrictEvents not enabled)")

        return self.log_lines

    def _is_kext_enabled(self, bundle_path: str) -> bool:
        """Check if a kext is already enabled in config."""
        for entry in self.config.get("Kernel", {}).get("Add", []):
            if entry.get("BundlePath") == bundle_path and entry.get("Enabled"):
                return True
        return False
