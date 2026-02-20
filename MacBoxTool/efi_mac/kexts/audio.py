"""
audio.py: Audio-related kext management
"""


import logging
from .base import KextManager
from ...datasets import model_array
from ... import constants

logger = logging.getLogger(__name__)


class AudioKextManager(KextManager):
    """Manages Audio-related kexts."""

    def apply(self) -> list[str]:
        """
        Apply Audio kext configuration.

        Returns:
            Log lines
        """
        # AppleALC for audio support
        self.enable_kext("AppleALC.kext", self.constants.applealc_version)

        # Legacy audio models may need additional support
        if self.model in model_array.LegacyAudio:
            self._log("  Model uses legacy audio configuration")

        return self.log_lines
