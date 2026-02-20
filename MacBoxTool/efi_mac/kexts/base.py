"""
base.py: Base Kext management - handles common kext operations
"""


import logging
import zipfile
from pathlib import Path

from ..config import ConfigManager
from ..utils import find_kext_zip
from ... import constants

logger = logging.getLogger(__name__)


class KextManager:
    """Manages kext operations for EFI building."""

    def __init__(self, config: dict, constants: constants.Constants, model: str, paths: dict):
        self.config = config
        self.constants = constants
        self.model = model
        self.paths = paths
        self.log_lines: list[str] = []

        self.kexts_path = paths["kexts_path"]
        self.payload_kexts = paths["payload_kexts"]

        self.config_mgr = ConfigManager(config, paths["plist_path"])

    def _log(self, msg: str):
        logger.info(msg)
        self.log_lines.append(msg)

    def enable_kext(self, kext_name: str, version: str) -> bool:
        """
        Copy a kext zip to Kexts/ and extract it, enable in config.

        Args:
            kext_name: Name of the kext (e.g., "Lilu.kext")
            version: Version string for logging

        Returns:
            True if successful, False otherwise
        """
        zip_path = find_kext_zip(self.payload_kexts, kext_name)
        if not zip_path:
            self._log(f"  [WARN] Kext not found: {kext_name}")
            return False

        self._log(f"  + {kext_name} v{version} ({zip_path.name})")
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(self.kexts_path)

        # Enable in config if entry exists
        if self.config_mgr.enable_kext(kext_name):
            return True
        return False

    def enable_base_kexts(self) -> list[str]:
        """
        Enable base kexts needed for all models.

        Returns:
            Log lines
        """
        self._log("[STEP] Enabling kexts")

        # Lilu is always required
        self.enable_kext("Lilu.kext", self.constants.lilu_version)
        self.config_mgr.set_quirk("DisableLinkeditJettison", True)

        # Import and enable feature-specific kexts
        from .gpu import GPUKextManager
        gpu_mgr = GPUKextManager(self.config, self.constants, self.model, self.paths)
        self.log_lines.extend(gpu_mgr.apply())

        from .audio import AudioKextManager
        audio_mgr = AudioKextManager(self.config, self.constants, self.model, self.paths)
        self.log_lines.extend(audio_mgr.apply())

        from .bluetooth import BluetoothKextManager
        bt_mgr = BluetoothKextManager(self.config, self.constants, self.model, self.paths)
        self.log_lines.extend(bt_mgr.apply())

        from .storage import StorageKextManager
        storage_mgr = StorageKextManager(self.config, self.constants, self.model, self.paths)
        self.log_lines.extend(storage_mgr.apply())

        from .network import NetworkKextManager
        net_mgr = NetworkKextManager(self.config, self.constants, self.model, self.paths)
        self.log_lines.extend(net_mgr.apply())

        from .usb import USBKextManager
        usb_mgr = USBKextManager(self.config, self.constants, self.model, self.paths)
        self.log_lines.extend(usb_mgr.apply())

        from .security import SecurityKextManager
        sec_mgr = SecurityKextManager(self.config, self.constants, self.model, self.paths)
        self.log_lines.extend(sec_mgr.apply())

        from .misc import MiscKextManager
        misc_mgr = MiscKextManager(self.config, self.constants, self.model, self.paths)
        self.log_lines.extend(misc_mgr.apply())

        return self.log_lines
