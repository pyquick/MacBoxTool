"""
ec.py: EC (Embedded Controller) ACPI management
"""


import logging
from .base import ACPIManager

logger = logging.getLogger(__name__)


class ECACPIManager(ACPIManager):
    """Manages EC-related ACPI tables."""

    def apply(self) -> list[str]:
        """
        Apply EC ACPI configuration.

        Returns:
            Log lines
        """
        # Enable EC-USBX for proper power management
        self.add_acpi("SSDT-EC-USBX.aml")

        return self.log_lines
