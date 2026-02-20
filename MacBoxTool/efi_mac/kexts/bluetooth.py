"""
bluetooth.py: Bluetooth-related kext management

Logic extracted from OCLP-R efi_builder/bluetooth.py (_prebuilt_assumption path).
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
        bt_model = model_info.get("Bluetooth Model")

        if bt_model is None:
            return self.log_lines

        self._log(f"  BT chipset: {bt_model.name}")

        # All legacy BT (<= BRCM20702_v1) need BlueToolFixup for Monterey+
        if bt_model <= BT.BRCM20702_v1:
            self.enable_kext("BlueToolFixup.kext", self.constants.bluetool_version)

            # BRCM2046/2070: additionally need Bluetooth-Spoof + -btlfxallowanyaddr
            if bt_model <= BT.BRCM2070:
                self.enable_kext("Bluetooth-Spoof.kext", self.constants.btspoof_version)
                self._log(f"  BT: legacy ({bt_model.name}) - BlueToolFixup + Bluetooth-Spoof")
            else:
                self._log(f"  BT: BRCM20702_v1 ({bt_model.name}) - BlueToolFixup")

            # Pre-Ivy Bridge firmware can't upload BT firmware properly
            cpu_gen = model_info.get("CPU Generation", 999)
            if cpu_gen < cpu_data.CPUGen.ivy_bridge.value:
                self._log(f"  BT: pre-Ivy Bridge firmware - needs firmware workaround")

        # BRCM20702_v2 / BRCM20703 / BRCM20703_UART: modern BT 4.0+
        elif bt_model in (BT.BRCM20702_v2, BT.BRCM20703, BT.BRCM20703_UART):
            self.enable_kext("BlueToolFixup.kext", self.constants.bluetool_version)
            self._log(f"  BT: modern ({bt_model.name}) - BlueToolFixup")

        return self.log_lines
