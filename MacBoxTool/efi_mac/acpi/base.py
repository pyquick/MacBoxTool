"""
base.py: Base ACPI management
"""


import logging
import shutil
from pathlib import Path

from ..config import ConfigManager
from ..utils import find_acpi_file

logger = logging.getLogger(__name__)


class ACPIManager:
    """Manages ACPI operations for EFI building."""

    def __init__(self, config: dict, constants, model: str, paths: dict):
        self.config = config
        self.constants = constants
        self.model = model
        self.paths = paths
        self.log_lines: list[str] = []

        self.acpi_path = paths["acpi_path"]
        self.payload_acpi = paths["payload_acpi"]

        self.config_mgr = ConfigManager(config, paths["plist_path"])

    def _log(self, msg: str):
        logger.info(msg)
        self.log_lines.append(msg)

    def add_acpi(self, acpi_name: str) -> bool:
        """
        Copy an ACPI file to ACPI/ and enable in config.

        Args:
            acpi_name: Name of the ACPI file (e.g., "SSDT-EC.aml")

        Returns:
            True if successful, False otherwise
        """
        source = find_acpi_file(self.payload_acpi, acpi_name)
        if not source:
            self._log(f"  [WARN] ACPI file not found: {acpi_name}")
            return False

        try:
            from ..security import SecurityValidator
            dest = SecurityValidator.safe_path(self.acpi_path, source.name)
            if source.is_symlink():
                raise ValueError(f"Symlink not allowed: {source}")
            shutil.copy(source, dest, follow_symlinks=False)
        except (ValueError, OSError) as e:
            self._log(f"  [ERROR] Failed to copy {acpi_name}: {e}")
            return False
        self._log(f"  + {source.name}")

        # Enable in config if entry exists, otherwise add new entry
        if not self.config_mgr.enable_acpi(source.name):
            acpi_add = self.config.setdefault("ACPI", {}).setdefault("Add", [])
            acpi_add.append({"Comment": source.name, "Enabled": True, "Path": source.name})
        return True

    def enable_base_acpi(self) -> list[str]:
        """
        Enable base ACPI tables for all models.

        Returns:
            Log lines
        """
        self._log("[STEP] Enabling ACPI tables")


        

        from .gpu import GPUACPIManager
        gpu_mgr = GPUACPIManager(self.config, self.constants, self.model, self.paths)
        self.log_lines.extend(gpu_mgr.apply())

        

        from .firmware import FirmwareACPIManager
        fw_mgr = FirmwareACPIManager(self.config, self.constants, self.model, self.paths)
        self.log_lines.extend(fw_mgr.apply())

        return self.log_lines
