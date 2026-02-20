"""
storage.py: Storage-related kext management

Logic from OCLP-R: storage.py
"""

import logging
from .base import KextManager
from ...datasets import smbios_data, cpu_data
from ...detections import device_probe
from ...support import utilities

logger = logging.getLogger(__name__)


class StorageKextManager(KextManager):
    """Manages Storage-related kexts."""

    def apply(self) -> list[str]:
        model_info = smbios_data.smbios_dictionary.get(self.model, {})
        cpu_gen = model_info.get("CPU Generation", 999)
        stock_storage = model_info.get("Stock Storage", [])

        computer = self.constants.computer
        nvme_devices = [i for i in computer.storage if isinstance(i, device_probe.NVMeController)] if computer else []

        # NVMeFix with ASPM handling for 3rd party NVMe
        if self.constants.allow_nvme_fixing is True:
            for i, controller in enumerate(nvme_devices):
                if controller.vendor_id == 0x106b:
                    continue
                self._log(f"  Found 3rd Party NVMe SSD ({i+1}): {utilities.friendly_hex(controller.vendor_id)}:{utilities.friendly_hex(controller.device_id)}")
                self.config["#Revision"][f"Hardware-NVMe-{i}"] = f"{utilities.friendly_hex(controller.vendor_id)}:{utilities.friendly_hex(controller.device_id)}"

                # Disable Bit 0 (L0s), enable Bit 1 (L1)
                nvme_aspm = (controller.aspm & (~0b11)) | 0b10

                if controller.pci_path:
                    self._log(f"  Found NVMe ({i}) at {controller.pci_path}")
                    self.config["DeviceProperties"]["Add"].setdefault(controller.pci_path, {})["pci-aspm-default"] = nvme_aspm
                    self.config["DeviceProperties"]["Add"][controller.pci_path.rpartition("/")[0]] = {"pci-aspm-default": nvme_aspm}
                else:
                    if "-nvmefaspm" not in self.config["NVRAM"]["Add"]["7C436110-AB2A-4BBB-A880-FE41995C9F82"]["boot-args"]:
                        self._log("  Falling back to -nvmefaspm")
                        self.config["NVRAM"]["Add"]["7C436110-AB2A-4BBB-A880-FE41995C9F82"]["boot-args"] += " -nvmefaspm"

                if controller.vendor_id != 0x144D and controller.device_id != 0xA804:
                    self.enable_kext("NVMeFix.kext", self.constants.nvmefix_version)

                # S1X/S3X NVMe: Apple SSD AP0128H/0256H/0128J/0256J (vendor 0x106b, device 0x2001/0x2003)
                if any((controller.vendor_id == 0x106b and controller.device_id in [0x2001, 0x2003]) for controller in nvme_devices):
                    self.enable_kext("IOS3XeFamily.kext", self.constants.s3x_nvme_version)
                    self._log("  IOS3XeFamily (S1X/S3X Apple NVMe)")

        # PATA support
        if "PATA" in stock_storage:
            self.enable_kext("AppleIntelPIIXATA.kext", self.constants.piixata_version)
            self._log("  AppleIntelPIIXATA (PATA)")

        # AHCI patch for MacBookAir6,x
        if self.model in ("MacBookAir6,1", "MacBookAir6,2"):
            self.enable_kext("MonteAHCIPort.kext", self.constants.monterey_ahci_version)
            self._log("  MonteAHCIPort (MacBookAir6 AHCI)")

        # SDXC for pre-Sandy Bridge models with SDXC
        if cpu_gen <= cpu_data.CPUGen.sandy_bridge.value:
            if self.model.startswith("MacBookPro8") or self.model.startswith("Macmini5"):
                self.enable_kext("BigSurSDXC.kext", self.constants.bigsursdxc_version)
                self._log("  BigSurSDXC (pre-VT-d SDXC)")

        return self.log_lines
