"""
usb.py: USB-related kext management
"""


import logging
from .base import KextManager
from ...datasets import model_array
from ... import constants

logger = logging.getLogger(__name__)


class USBKextManager(KextManager):
    """Manages USB-related kexts."""

    def apply(self) -> list[str]:
        """
        Apply USB kext configuration.

        Returns:
            Log lines
        """
        # Models with USB map requirements
        if self.model in model_array.Missing_USB_Map:
            self._log("  Model uses legacy USB configuration")

        # Models missing USB map in Ventura+
        if self.model in model_array.Missing_USB_Map_Ventura:
            self._log("  Model requires updated USB map for Ventura+")

        return self.log_lines
