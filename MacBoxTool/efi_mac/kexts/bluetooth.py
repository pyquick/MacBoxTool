"""
bluetooth.py: Bluetooth-related kext management

Logic extracted from MacBoxTool efi_builder/bluetooth.py (_prebuilt_assumption path).
Since MacBoxTool runs on Windows, we use smbios_data lookup instead of live hardware detection.
"""

import logging
from .base import KextManager
from ...datasets import smbios_data, bluetooth_data, cpu_data

logger = logging.getLogger(__name__)

BT = bluetooth_data.bluetooth_data


class BluetoothKextManager(KextManager):
    """Manages Bluetooth-related kexts."""

    def apply(self) -> list[str]:
        model_info = smbios_data.smbios_dictionary.get(self.model, {})

        # On-model detection first
        if not self.constants.custom_model and self.constants.computer and hasattr(self.constants.computer, 'bluetooth') and self.constants.computer.bluetooth:
            self._on_model(model_info)
            return self.log_lines

        # Prebuilt fallback
        bt_model = model_info.get("Bluetooth Model")
        if bt_model is None:
            return self.log_lines

        self._log(f"  BT chipset: {bt_model.name}")
        self._prebuilt(bt_model, model_info)
        return self.log_lines

    def _on_model(self, model_info):
        """On-model Bluetooth detection using live hardware."""
        bt = self.constants.computer.bluetooth
        bt_type = bt.chipset if hasattr(bt, 'chipset') else str(type(bt).__name__)
        cpu_gen = model_info.get("CPU Generation", 999)
        self._log(f"  BT chipset (on-model): {bt_type}")

        if hasattr(bt, 'is_3rd_party') and bt.is_3rd_party:
            # 3rd party Bluetooth 4.0
            self.enable_kext("BlueToolFixup.kext", self.constants.bluetool_version,self.constants.bluetool_path)
            self.config.setdefault("Kernel", {}).setdefault("Quirks", {})["ExtendBTFeatureFlags"] = True
            self._log("  BT: 3rd Party BT 4.0 - BlueToolFixup + ExtendBTFeatureFlags")
            return

        bt_name = str(bt_type)
        if "BRCM2070" in bt_name or "BRCM2046" in bt_name:
            self.enable_kext("BlueToolFixup.kext", self.constants.bluetool_version,self.constants.bluetool_path)
            self.enable_kext("Bluetooth-Spoof.kext", self.constants.btspoof_version,self.constants.bluetool_path)
            self._log(f"  BT: legacy ({bt_name}) - BlueToolFixup + Bluetooth-Spoof")
        elif "BRCM20702" in bt_name:
            self.enable_kext("BlueToolFixup.kext", self.constants.bluetool_version,self.constants.bluetool_path)
            # Cross-reference WiFi chipset
            wifi = self.constants.computer.wifi if hasattr(self.constants.computer, 'wifi') else None
            if wifi and hasattr(wifi, 'chipset'):
                from ...detections import device_probe
                if wifi.chipset == device_probe.Broadcom.Chipsets.AirPortBrcm4360:
                    self._log(f"  BT: BRCM20702 + AirPortBrcm4360 WiFi - BlueToolFixup")
                    return
            if cpu_gen < cpu_data.CPUGen.ivy_bridge.value:
                self._log(f"  BT: BRCM20702 pre-Ivy Bridge - BlueToolFixup + firmware workaround")
            else:
                self._log(f"  BT: BRCM20702 - BlueToolFixup")
        else:
            # Modern BT (BRCM20703, etc.)
            self.enable_kext("BlueToolFixup.kext", self.constants.bluetool_version,self.constants.bluetool_path)
            self._log(f"  BT: modern ({bt_name}) - BlueToolFixup")

    def _prebuilt(self, bt_model, model_info):
        """Prebuilt Bluetooth kext handling from smbios_data."""
        # All legacy BT (<= BRCM20702_v1) need BlueToolFixup for Monterey+
        if bt_model <= BT.BRCM20702_v1:
            self.enable_kext("BlueToolFixup.kext", self.constants.bluetool_version,self.constants.bluetool_path)

            # BRCM2046/2070: additionally need Bluetooth-Spoof + -btlfxallowanyaddr
            if bt_model <= BT.BRCM2070:
                self.enable_kext("Bluetooth-Spoof.kext", self.constants.btspoof_version,self.constants.btspoof_path)
                self._log(f"  BT: legacy ({bt_model.name}) - BlueToolFixup + Bluetooth-Spoof")
            else:
                self._log(f"  BT: BRCM20702_v1 ({bt_model.name}) - BlueToolFixup")

            # Pre-Ivy Bridge firmware can't upload BT firmware properly
            cpu_gen = model_info.get("CPU Generation", 999)
            if cpu_gen < cpu_data.CPUGen.ivy_bridge.value:
                self._log(f"  BT: pre-Ivy Bridge firmware - needs firmware workaround")

        # BRCM20702_v2 / BRCM20703 / BRCM20703_UART: modern BT 4.0+
        elif bt_model in (BT.BRCM20702_v2, BT.BRCM20703, BT.BRCM20703_UART):
            self.enable_kext("BlueToolFixup.kext", self.constants.bluetool_version,self.constants.bluetool_path)
            self._log(f"  BT: modern ({bt_model.name}) - BlueToolFixup")
