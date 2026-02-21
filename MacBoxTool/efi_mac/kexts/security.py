"""
security.py: Security-related kext management

Logic from MacBoxTool: security.py, firmware.py, misc.py
"""

import logging
from .base import KextManager
from ...datasets import smbios_data, cpu_data, os_data, model_array

logger = logging.getLogger(__name__)


class SecurityKextManager(KextManager):
    """Manages Security-related kexts."""

    def apply(self) -> list[str]:
        model_info = smbios_data.smbios_dictionary.get(self.model, {})
        cpu_gen = model_info.get("CPU Generation", 999)
        max_os = model_info.get("Max OS Supported", 0)

        # AMFIPass: only for pre-Sonoma models (legacy security.py:95-97)
        # AMFIPass patches AMFI to allow unsigned kexts without disabling AMFI entirely
        # Do NOT combine with amfi=0x80 boot-arg (which breaks TCC: Camera, Mic prompts)
        if max_os < os_data.os_data.sonoma:
            self.enable_kext("AMFIPass.kext", self.constants.amfipass_version)
            self._log("  AMFIPass (pre-Sonoma AMFI patching)")

        # RSRHelper: KC UUID mismatch after RSR (legacy security.py:74)
        self.enable_kext("RSRHelper.kext", self.constants.rsrhelper_version)
        self._log("  RSRHelper (RSR KC UUID mismatch)")

        # CSLVFixup: Library Validation bypass (legacy security.py:89)
        if getattr(self.constants, 'disable_cs_lv', False):
            self.enable_kext("CSLVFixup.kext", self.constants.cslvfixup_version)
            self._log("  CSLVFixup (Library Validation bypass)")
            # Enable Library Validation kernel patches
            for patch in self.config.get("Kernel", {}).get("Patch", []):
                if patch.get("Comment") in (
                    "Disable Library Validation Enforcement",
                    "Disable _csr_check() in _vnode_check_signature",
                ):
                    patch["Enabled"] = True
            self._log("  Kernel patches: Library Validation disabled")

        # MacBoxTool firmware.py: CryptexFixup only for Ivy Bridge and older (no AVX2.0)
        if cpu_gen <= cpu_data.CPUGen.ivy_bridge.value:
            self.enable_kext("CryptexFixup.kext", self.constants.cryptexfixup_version)
            self._log("  CryptexFixup (pre-AVX2.0, Ivy Bridge or older)")

        # MacBoxTool firmware.py: SSE4.1 kexts for Penryn and older
        if cpu_gen <= cpu_data.CPUGen.penryn.value:
            self.enable_kext("AAAMouSSE.kext", self.constants.mousse_version)
            self.enable_kext("telemetrap.kext", self.constants.telemetrap_version)
            self._log("  AAAMouSSE + telemetrap (Penryn SSE4.1)")

        # MacBoxTool firmware.py: Legacy power management for Ivy Bridge and older
        if cpu_gen <= cpu_data.CPUGen.ivy_bridge.value:
            self.enable_kext("AppleIntelCPUPowerManagement.kext", self.constants.aicpupm_version)
            self.enable_kext("AppleIntelCPUPowerManagementClient.kext", self.constants.aicpupm_version)
            self._log("  AICPUPM (legacy power management)")

        # MacBoxTool firmware.py: ASPP-Override for Sandy Bridge and older
        if cpu_gen <= cpu_data.CPUGen.sandy_bridge.value:
            self.enable_kext("ASPP-Override.kext", self.constants.aspp_override_version)
            self._log("  ASPP-Override (pre-Ivy Bridge power management)")

        # MacBoxTool firmware.py: NoAVXFSCompressionTypeZlib for pre-Sandy Bridge
        if cpu_gen < cpu_data.CPUGen.sandy_bridge.value:
            self.enable_kext("NoAVXFSCompressionTypeZlib.kext", self.constants.apfs_zlib_version)
            self.enable_kext("NoAVXFSCompressionTypeZlib-AVXpel.kext", self.constants.apfs_zlib_v2_version)
            self._log("  NoAVXFSCompressionTypeZlib (pre-Sandy Bridge)")

        # SimpleMSR: firmware throttling disable (legacy firmware.py:119)
        if self.constants.disable_fw_throttle:
            self.enable_kext("SimpleMSR.kext", self.constants.simplemsr_version)
            self._log("  SimpleMSR (firmware throttling disable)")

        # AutoPkgInstaller: automatic OCLP installation (legacy security.py:54)
        if max_os < os_data.os_data.sonoma:
            self.enable_kext("AutoPkgInstaller.kext", self.constants.autopkg_version)
            self._log("  AutoPkgInstaller (auto OCLP install)")

        # AppleMCEReporterDisabler: for multi-socket SMBIOS spoofing (legacy firmware.py:335)
        if self.constants.serial_settings in ("Moderate", "Advanced"):
            override_model = self.constants.override_smbios
            if override_model != "Default":
                ov_info = smbios_data.smbios_dictionary.get(override_model, {})
                if ov_info.get("CPU Count", 1) > 1:
                    self.enable_kext("AppleMCEReporterDisabler.kext", self.constants.mce_version)
                    self._log("  AppleMCEReporterDisabler (multi-socket SMBIOS)")

        # DebugEnhancer: kext debug mode (legacy misc.py:355)
        if self.constants.kext_debug:
            self.enable_kext("DebugEnhancer.kext", self.constants.debugenhancer_version)
            self._log("  DebugEnhancer (kext debug)")

        # FeatureUnlock: conditional on fu_status (legacy misc.py:78)
        if self.constants.fu_status and max_os < os_data.os_data.sonoma:
            self.enable_kext("FeatureUnlock.kext", self.constants.featureunlock_version)
            self._log("  FeatureUnlock (pre-Sonoma model)")

        # RestrictEvents with revblock/revpatch NVRAM args (legacy misc.py:82-160)
        self._restrict_events_handling(model_info, cpu_gen)

        return self.log_lines

    def _restrict_events_handling(self, model_info, cpu_gen):
        """RestrictEvents handler with NVRAM revblock/revpatch args."""
        oclp_guid = self.config.setdefault("NVRAM", {}).setdefault("Add", {}).setdefault(
            "4D1FDA02-38C7-4A6A-9CC6-4BCCA8B30102", {}
        )

        # Generate block arguments
        block_args = []
        if self.model in ("MacBookPro6,1", "MacBookPro6,2", "MacBookPro9,1", "MacBookPro10,1"):
            block_args.append("gmux")
        if self.model in model_array.MacPro:
            block_args.append("pcie")
        if self.constants.disable_mediaanalysisd:
            block_args.append("media")

        # Generate patch arguments
        patch_args = []
        if not self.constants.allow_oc_everywhere and (
            self.constants.serial_settings == "None" or not self.constants.secure_status
        ):
            patch_args.append("sbvmm")
        if cpu_gen == cpu_data.CPUGen.ivy_bridge.value:
            patch_args.append("f16c")

        # If block_args set but no patch_args, disable expensive userspace patching
        if block_args and not patch_args:
            patch_args = ["none"]

        # Enable RestrictEvents if any args needed
        block_str = ",".join(block_args)
        patch_str = ",".join(patch_args)

        if block_str:
            self.enable_kext("RestrictEvents.kext", self.constants.restrictevents_version)
            oclp_guid["revblock"] = block_str
            self._log(f"  RestrictEvents revblock: {block_str}")

        if patch_str:
            self.enable_kext("RestrictEvents.kext", self.constants.restrictevents_version)
            oclp_guid["revpatch"] = patch_str
            self._log(f"  RestrictEvents revpatch: {patch_str}")

        # EFICheckDisabler only if RestrictEvents is NOT enabled (they conflict)
        if not self._is_kext_enabled("RestrictEvents.kext"):
            self.enable_kext("EFICheckDisabler.kext", self.constants.eficheckdisabler_version)
            self._log("  EFICheckDisabler (RestrictEvents not enabled)")

    def _is_kext_enabled(self, bundle_path: str) -> bool:
        """Check if a kext is already enabled in config."""
        for entry in self.config.get("Kernel", {}).get("Add", []):
            if entry.get("BundlePath") == bundle_path and entry.get("Enabled"):
                return True
        return False
