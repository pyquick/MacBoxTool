"""
misc.py: Miscellaneous kext management

Logic from MacBoxTool: misc.py (FireWire, TopCase, Thunderbolt, Webcam, USB, T1)
"""

import binascii
import logging
import shutil
from pathlib import Path
from .base import KextManager
from ...datasets import smbios_data, cpu_data, model_array

logger = logging.getLogger(__name__)


class MiscKextManager(KextManager):
    """Manages miscellaneous kexts (FireWire, TopCase, TB, Webcam, USB, T1)."""

    def apply(self) -> list[str]:
        model_info = smbios_data.smbios_dictionary.get(self.model, {})
        cpu_gen = model_info.get("CPU Generation", 999)
        computer = self.constants.computer

        self._topcase_handling(model_info, cpu_gen, computer)
        self._webcam_handling(model_info, cpu_gen, computer)
        self._firewire_handling()
        self._thunderbolt_handling()
        self._usb_handling(model_info, cpu_gen, computer)
        self._t1_handling()
        self._cpufriend_handling(model_info, cpu_gen)
        self._noavxfs_handling(model_info, cpu_gen)

        return self.log_lines

    def _topcase_handling(self, model_info, cpu_gen, computer):
        """SPI/USB Top Case handler (legacy misc.py:200-245)."""
        if not self.model.startswith("MacBook"):
            return
        if self.model not in smbios_data.smbios_dictionary:
            return

        # SPI-based top case for MacBookAir6,x and Broadwell-Kaby Lake MacBooks
        if self.model.startswith("MacBookAir6") or (
            cpu_data.CPUGen.broadwell <= cpu_gen <= cpu_data.CPUGen.kaby_lake
        ):
            self.enable_kext("AppleHSSPISupport.kext", self.constants.apple_spi_version)
            self.enable_kext("AppleHSSPIHIDDriver.kext", self.constants.apple_spi_hid_version)
            self.enable_kext("AppleTopCaseInjector.kext", self.constants.topcase_inj_version)
            self._log("  TopCase: SPI support (Broadwell-KabyLake)")

        # USB TopCase for pre-Skylake MacBooks
        if computer and computer.internal_keyboard_type and computer.trackpad_type:
            self._enable_usb_topcase(computer)
        elif cpu_gen < cpu_data.CPUGen.skylake.value:
            if self.model not in ("MacBookPro11,4", "MacBookPro11,5", "MacBookPro12,1", "MacBook8,1"):
                self._enable_usb_topcase_prebuilt(computer)

    def _enable_usb_topcase(self, computer):
        """Enable USB TopCase from on-device probing."""
        self.enable_kext("AppleUSBTopCase.kext", self.constants.topcase_version)
        for plugin in ("AppleUSBTCButtons.kext", "AppleUSBTCKeyboard.kext", "AppleUSBTCKeyEventDriver.kext"):
            bp = f"AppleUSBTopCase.kext/Contents/PlugIns/{plugin}"
            for entry in self.config.get("Kernel", {}).get("Add", []):
                if entry.get("BundlePath") == bp:
                    entry["Enabled"] = True
        if computer.internal_keyboard_type == "Legacy":
            self.enable_kext("LegacyKeyboardInjector.kext", self.constants.legacy_keyboard)
        if computer.trackpad_type == "Legacy":
            self.enable_kext("AppleUSBTrackpad.kext", self.constants.apple_trackpad)
        elif computer.trackpad_type == "Modern":
            self.enable_kext("AppleUSBMultitouch.kext", self.constants.multitouch_version)
        self._log("  TopCase: USB (on-device probe)")

    def _enable_usb_topcase_prebuilt(self, computer):
        """Enable USB TopCase for prebuilt (fallback)."""
        self.enable_kext("AppleUSBTopCase.kext", self.constants.topcase_version)
        for plugin in ("AppleUSBTCButtons.kext", "AppleUSBTCKeyboard.kext", "AppleUSBTCKeyEventDriver.kext"):
            bp = f"AppleUSBTopCase.kext/Contents/PlugIns/{plugin}"
            for entry in self.config.get("Kernel", {}).get("Add", []):
                if entry.get("BundlePath") == bp:
                    entry["Enabled"] = True
        self.enable_kext("AppleUSBMultitouch.kext", self.constants.multitouch_version)
        if self.model == "MacBook5,2":
            self.enable_kext("AppleUSBTrackpad.kext", self.constants.apple_trackpad)
            self.enable_kext("LegacyKeyboardInjector.kext", self.constants.legacy_keyboard)
        self._log("  TopCase: USB (prebuilt fallback)")

    def _webcam_handling(self, model_info, cpu_gen, computer):
        """iSight/Camera handler (legacy misc.py:265-280)."""
        if model_info.get("Legacy iSight"):
            self.enable_kext("LegacyUSBVideoSupport.kext", self.constants.apple_isight_version)
            self._log("  Webcam: Legacy iSight")

        if computer and computer.pcie_webcam:
            self.enable_kext("AppleCameraInterface.kext", self.constants.apple_camera_version)
            self._log("  Webcam: PCIe camera interface")
        elif self.model.startswith("MacBook") and (
            cpu_data.CPUGen.haswell <= cpu_gen <= cpu_data.CPUGen.kaby_lake
        ):
            self.enable_kext("AppleCameraInterface.kext", self.constants.apple_camera_version)
            self._log("  Webcam: PCIe camera (prebuilt Haswell-KabyLake)")

    def _firewire_handling(self):
        """FireWire boot handler (legacy misc.py:181-197)."""
        if not self.constants.firewire_boot:
            return
        self.enable_kext("IOFireWireFamily.kext", self.constants.fw_kext)
        self.enable_kext("IOFireWireSBP2.kext", self.constants.fw_kext)
        self.enable_kext("IOFireWireSerialBusProtocolTransport.kext", self.constants.fw_kext)
        bp = "IOFireWireFamily.kext/Contents/PlugIns/AppleFWOHCI.kext"
        for entry in self.config.get("Kernel", {}).get("Add", []):
            if entry.get("BundlePath") == bp:
                entry["Enabled"] = True
        self._log("  FireWire boot support")

    def _thunderbolt_handling(self):
        """Thunderbolt disable for 2013-2014 MacBook Pro (legacy misc.py:248-262)."""
        if not self.constants.disable_tb:
            return
        if self.model not in ("MacBookPro11,1", "MacBookPro11,2", "MacBookPro11,3", "MacBookPro11,4", "MacBookPro11,5"):
            return
        if self.model in ("MacBookPro11,3", "MacBookPro11,5"):
            tb_path = "PciRoot(0x0)/Pci(0x1,0x1)/Pci(0x0,0x0)/Pci(0x0,0x0)/Pci(0x0,0x0)"
        else:
            tb_path = "PciRoot(0x0)/Pci(0x1,0x0)/Pci(0x0,0x0)/Pci(0x0,0x0)/Pci(0x0,0x0)"
        self.config["DeviceProperties"]["Add"][tb_path] = {
            "class-code": binascii.unhexlify("FFFFFFFF"),
            "device-id": binascii.unhexlify("FFFF0000"),
        }
        self._log("  Thunderbolt: disabled (MacBookPro11,x)")

    def _usb_handling(self, model_info, cpu_gen, computer):
        """USB Map + UHCI/OHCI handler (legacy misc.py:283-337)."""
        # UHCI/OHCI for Penryn and specific Mac Pro/Xserve models
        if cpu_gen <= cpu_data.CPUGen.penryn.value or self.model in ("MacPro4,1", "MacPro5,1", "Xserve3,1"):
            self.enable_kext("USB1.1-Injector.kext", self.constants.apple_usb_11_injector)
            for plugin in ("AppleUSBOHCI.kext", "AppleUSBOHCIPCI.kext", "AppleUSBUHCI.kext", "AppleUSBUHCIPCI.kext"):
                bp = f"USB1.1-Injector.kext/Contents/PlugIns/{plugin}"
                for entry in self.config.get("Kernel", {}).get("Add", []):
                    if entry.get("BundlePath") == bp:
                        entry["Enabled"] = True
            self._log("  USB: UHCI/OHCI legacy support")

    def _t1_handling(self):
        """T1 Security Chip handler (legacy misc.py:387-404)."""
        if self.model not in ("MacBookPro13,2", "MacBookPro13,3", "MacBookPro14,2", "MacBookPro14,3"):
            return
        # Block existing kexts
        for identifier in ("com.apple.driver.AppleSSE", "com.apple.driver.AppleKeyStore", "com.apple.driver.AppleCredentialManager"):
            for entry in self.config.get("Kernel", {}).get("Block", []):
                if entry.get("Identifier") == identifier:
                    entry["Enabled"] = True
        # Inject patched kexts
        self.enable_kext("corecrypto_T1.kext", self.constants.t1_corecrypto_version)
        self.enable_kext("AppleSSE.kext", self.constants.t1_sse_version)
        self.enable_kext("AppleKeyStore.kext", self.constants.t1_key_store_version)
        self.enable_kext("AppleCredentialManager.kext", self.constants.t1_credential_version)
        self.enable_kext("KernelRelayHost.kext", self.constants.kernel_relay_version)
        self._log("  T1 Security Chip support")

    def _cpufriend_handling(self, model_info, cpu_gen):
        """CPUFriend power management with DataProvider (legacy misc.py:168-178)."""
        if self.constants.disallow_cpufriend:
            return
        if self.constants.serial_settings == "None":
            return

        # Allow CPUFriend for most models, except special cases
        if self.model in ("iMac7,1", "Xserve2,1", "Hackdoc1,1"):
            return
        if self.constants.allow_oc_everywhere:
            return

        # Enable CPUFriend.kext from payload
        self.enable_kext("CPUFriend.kext", self.constants.cpufriend_version)

        # Copy and enable CPUFriendDataProvider.kext for the target model
        pp_map_path = self.constants.platform_plugin_plist_path / f"{self.model}/Info.plist"

        # Use kexts_path from KextManager (not constants which might be different)
        pp_kext_folder = self.kexts_path / "CPUFriendDataProvider.kext"

        if pp_map_path.exists():
            # Create kext folder structure
            pp_contents = pp_kext_folder / "Contents"
            pp_contents.mkdir(parents=True, exist_ok=True)

            # Copy Info.plist
            shutil.copy(pp_map_path, pp_contents / "Info.plist")

            # Add/ensure entry in config.plist if not already present
            kernel_add = self.config.get("Kernel", {}).get("Add", [])
            found = False
            for entry in kernel_add:
                if entry.get("BundlePath") == "CPUFriendDataProvider.kext":
                    entry["Enabled"] = True
                    found = True
                    break

            # If not found in config, add it
            if not found:
                self.config.setdefault("Kernel", {}).setdefault("Add", []).append({
                    "BundlePath": "CPUFriendDataProvider.kext",
                    "Enabled": True,
                    "MaxKernel": ""
                })

            self._log(f"  CPUFriend + DataProvider ({self.model})")
        else:
            self._log(f"  CPUFriend (no DataProvider for {self.model})")

    def _noavxfs_handling(self, model_info, cpu_gen):
        """NoAVXFSCompressionTypeZlib for pre-Sandy Bridge CPUs."""
        # In macOS 12.4+, Apple added AVX1.0 usage in AppleFSCompressionTypeZlib
        # Pre-Sandy Bridge CPUs don't support AVX1.0
        if cpu_gen >= cpu_data.CPUGen.sandy_bridge.value:
            return

        self.enable_kext("NoAVXFSCompressionTypeZlib.kext", self.constants.apfs_zlib_version)
        self.enable_kext("NoAVXFSCompressionTypeZlib-AVXpel.kext", self.constants.apfs_zlib_v2_version)
        self._log("  NoAVXFS: AVX1.0 compression workaround (pre-Sandy Bridge)")
