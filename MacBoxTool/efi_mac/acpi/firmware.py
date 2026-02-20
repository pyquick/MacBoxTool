"""
firmware.py: Firmware-related ACPI management

Logic from efi_builder: firmware.py (SSDT-CPBG, SSDT-PCI)
"""

import logging
from .base import ACPIManager
from ...datasets import smbios_data, cpu_data

logger = logging.getLogger(__name__)


class FirmwareACPIManager(ACPIManager):
    """Manages firmware-related ACPI tables."""

    def apply(self) -> list[str]:
        model_info = smbios_data.smbios_dictionary.get(self.model, {})
        cpu_gen = model_info.get("CPU Generation", 999)

        # SSDT-CPBG for Nehalem consumer models (legacy firmware.py:136)
        if cpu_gen == cpu_data.CPUGen.nehalem.value and self.model not in (
            "MacPro4,1", "MacPro5,1", "Xserve3,1"
        ):
            self.add_acpi("SSDT-CPBG.aml")

        # SSDT-PCI for Sandy/Ivy Bridge Windows 10 UEFI audio (legacy firmware.py:143)
        if cpu_gen in (cpu_data.CPUGen.sandy_bridge.value, cpu_data.CPUGen.ivy_bridge.value):
            self.add_acpi("SSDT-PCI.aml")
            # Enable BUF0→BUF1 ACPI patch
            for patch in self.config.get("ACPI", {}).get("Patch", []):
                if patch.get("Comment") == "BUF0 to BUF1":
                    patch["Enabled"] = True

        return self.log_lines
