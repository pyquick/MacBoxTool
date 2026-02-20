"""
build.py: EFI builder for unsupported Macs (Windows)

This file now serves as a compatibility layer that imports from the new
modular architecture. The actual implementation is in builder.py and
related modules.

References OCLP-R efi_builder pattern.
Output: ~/.macboxtool/efi_builder/
"""

import logging
from pathlib import Path

from .. import constants
from ..datasets import model_array

logger = logging.getLogger(__name__)


# Import from new modular architecture
from .builder import BuildOpenCore as _BuildOpenCoreNew


class BuildOpenCore(_BuildOpenCoreNew):
    """
    Build OpenCore EFI for a given Mac model.

    This class maintains backward compatibility with the old API
    while using the new modular architecture internally.
    """

    def __init__(self, model: str, global_constants: constants.Constants):
        """
        Initialize the EFI builder.

        Args:
            model: Target Mac model (e.g., "MacPro7,1")
            global_constants: Constants instance
        """
        super().__init__(model, global_constants)

        # Maintain backward compatibility properties
        self.oc_build = self.paths["oc_build"]
        self.oc_folder = self.paths["oc_folder"]
        self.kexts_path = self.paths["kexts_path"]
        self.acpi_path = self.paths["acpi_path"]
        self.drivers_path = self.paths["drivers_path"]
        self.plist_path = self.paths["plist_path"]


# Re-export for compatibility
__all__ = ["BuildOpenCore"]
