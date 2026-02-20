"""
usb.py: USB-related ACPI management
"""


import logging
from .base import ACPIManager

logger = logging.getLogger(__name__)


class USBACPIManager(ACPIManager):
    """Manages USB-related ACPI tables."""

    def apply(self) -> list[str]:
        """
        Apply USB ACPI configuration.

        Returns:
            Log lines
        """
        # Disable EHCx for modern USB ports
        self.add_acpi("SSDT-EHCx-DISABLE.aml")

        return self.log_lines
