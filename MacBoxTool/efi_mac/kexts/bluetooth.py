"""
bluetooth.py: Bluetooth-related kext management

Logic extracted from MacBoxTool efi_builder/bluetooth.py (_prebuilt_assumption path).
Since MacBoxTool runs on Windows, we use smbios_data lookup instead of live hardware detection.
"""

import logging
import binascii
from .base import KextManager
from ...detections import device_probe 
from ...datasets import smbios_data, bluetooth_data, cpu_data

logger = logging.getLogger(__name__)

BT = bluetooth_data.bluetooth_data


class BluetoothKextManager(KextManager):
    """Manages Bluetooth-related kexts."""

    def apply(self) -> list[str]:
        self.computer=self.constants.computer
        if not self.constants.custom_model and self.computer.bluetooth_chipset:
            self._on_model()
        else:
            self._prebuilt_assumption()

        self._log(f"  BT chipset: {self.computer.bluetooth_chipset}")
        return self.log_lines
    def _bluetooth_firmware_incompatibility_workaround(self) -> None:
        """
        For Mac firmwares that are unable to perform firmware uploads.
        Namely Macs with BCM2070 and BCM2046 chipsets, as well as pre-2012 Macs with upgraded chipsets.
        """
        self.config["NVRAM"]["Add"]["7C436110-AB2A-4BBB-A880-FE41995C9F82"]["bluetoothInternalControllerInfo"] = binascii.unhexlify("0000000000000000000000000000")
        self._log("- Adding NVRAM bluetoothInternalControllerInfo")
        self.config["NVRAM"]["Add"]["7C436110-AB2A-4BBB-A880-FE41995C9F82"]["bluetoothExternalDongleFailed"] = binascii.unhexlify("00")
        self._log("- Adding NVRAM bluetoothExternalDongleFailed")
        self.config["NVRAM"]["Delete"]["7C436110-AB2A-4BBB-A880-FE41995C9F82"] += ["bluetoothInternalControllerInfo", "bluetoothExternalDongleFailed"]
        self._log("- Adding NVRAM bluetoothExternalDongleFailed and bluetoothInternalControllerInfo to config")

    def _on_model(self) -> None:
        """
        On-Model Hardware Detection Handling
        """
        if self.computer.bluetooth_chipset in ["BRCM2070 Hub", "BRCM2046 Hub"]:
            self._log("- Fixing Legacy Bluetooth for macOS Monterey")
            self.enable_kext("BlueToolFixup.kext", self.constants.bluetool_version, self.constants.bluetool_path)
            self._log("- Adding BlueToolFixup.kext")
            self.enable_kext("Bluetooth-Spoof.kext", self.constants.btspoof_version, self.constants.btspoof_path)
            self._log("- Adding Bluetooth-Spoof.kext")
            self.config["NVRAM"]["Add"]["7C436110-AB2A-4BBB-A880-FE41995C9F82"]["boot-args"] += " -btlfxallowanyaddr"
            self._log("-Set NVRAM -btlfxallowanyaddr")
            self._bluetooth_firmware_incompatibility_workaround()
        elif self.computer.bluetooth_chipset == "BRCM20702 Hub":
            # BCM94331 can include either BCM2070 or BRCM20702 v1 Bluetooth chipsets
            # Note Monterey only natively supports BRCM20702 v2 (found with BCM94360)
            # Due to this, BlueToolFixup is required to resolve Firmware Uploading on legacy chipsets
            if self.computer.wifi:
                if self.computer.wifi.chipset == device_probe.Broadcom.Chipsets.AirPortBrcm4360:
                    self._log("- Fixing Legacy Bluetooth for macOS Monterey")
                    self.enable_kext("BlueToolFixup.kext", self.constants.bluetool_version, self.constants.bluetool_path)
                    self._log("- Adding BlueToolFixup.kext")

            # Older Mac firmwares (pre-2012) don't support the new chipsets correctly (regardless of WiFi card)
            if self.model in smbios_data.smbios_dictionary:
                if smbios_data.smbios_dictionary[self.model]["CPU Generation"] < cpu_data.CPUGen.ivy_bridge.value:
                    self._log("- Fixing Legacy Bluetooth for macOS Monterey")
                    self.enable_kext("BlueToolFixup.kext", self.constants.bluetool_version, self.constants.bluetool_path)
                    self._log("- Adding BlueToolFixup.kext")
                    self._bluetooth_firmware_incompatibility_workaround()
        elif self.computer.bluetooth_chipset == "3rd Party Bluetooth 4.0 Hub":
            self._log("- Detected 3rd Party Bluetooth Chipset")
            self.enable_kext("BlueToolFixup.kext", self.constants.bluetool_version, self.constants.bluetool_path)
            self._log("- Adding BlueToolFixup.kext")
            self._log("- Enabling Bluetooth FeatureFlags")
            self.config["Kernel"]["Quirks"]["ExtendBTFeatureFlags"] = True


    def _prebuilt_assumption(self) -> None:
        """
        Fall back to pre-built assumptions
        """

        if not self.model in smbios_data.smbios_dictionary:
            return
        if not "Bluetooth Model" in smbios_data.smbios_dictionary[self.model]:
            return

        if smbios_data.smbios_dictionary[self.model]["Bluetooth Model"] <= bluetooth_data.bluetooth_data.BRCM20702_v1.value:
            self._log("- Fixing Legacy Bluetooth for macOS Monterey")
            self.enable_kext("BlueToolFixup.kext", self.constants.bluetool_version, self.constants.bluetool_path)
            if smbios_data.smbios_dictionary[self.model]["Bluetooth Model"] <= bluetooth_data.bluetooth_data.BRCM2070.value:
                self.config["NVRAM"]["Add"]["7C436110-AB2A-4BBB-A880-FE41995C9F82"]["boot-args"] += " -btlfxallowanyaddr"
                self._bluetooth_firmware_incompatibility_workaround()
                self.enable_kext("Bluetooth-Spoof.kext", self.constants.btspoof_version, self.constants.btspoof_path)