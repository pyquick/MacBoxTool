"""
awac.py: AWAC (Always Wake Auto Clock) ACPI management
"""


import logging
from .base import ACPIManager

logger = logging.getLogger(__name__)


class AWACACPIManager(ACPIManager):
    """Manages AWAC-related ACPI tables."""

    def apply(self) -> list[str]:
        """
        Apply AWAC ACPI configuration.

        Returns:
            Log lines
        """
        # Disable AWAC for models that need legacy RTC
        self.add_acpi("SSDT-AWAC-DISABLE.aml")

        return self.log_lines
