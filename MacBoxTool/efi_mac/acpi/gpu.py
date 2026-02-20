"""
gpu.py: GPU-related ACPI management
"""


import logging
from .base import ACPIManager
from ...datasets import model_array

logger = logging.getLogger(__name__)


class GPUACPIManager(ACPIManager):
    """Manages GPU-related ACPI tables."""

    def apply(self) -> list[str]:
        """
        Apply GPU ACPI configuration based on model.

        Returns:
            Log lines
        """
        # Disable dGPU for dual GPU models
        if self.model in model_array.DualGPUPatch:
            self.add_acpi("SSDT-DDGPU.aml")

        return self.log_lines
