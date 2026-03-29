"""
base.py: Base OpenCore extraction and directory structure generation
"""


import logging
import shutil
import zipfile
from pathlib import Path

from .. import constants
from .utils import rmtree_handler

logger = logging.getLogger(__name__)


class BaseGenerator:
    """Generates the base OpenCore directory structure."""

    def __init__(self, model: str, global_constants: constants.Constants):
        self.model = model
        self.constants = global_constants
        self.log_lines: list[str] = []

        # Build paths
        self.build_path = self.constants.build_path
        self.oc_build = self.build_path / "OpenCore-Build"
        self.oc_folder = self.oc_build / "EFI" / "OC"
        self.kexts_path = self.oc_folder / "Kexts"
        self.acpi_path = self.oc_folder / "ACPI"
        self.drivers_path = self.oc_folder / "Drivers"
        self.plist_path = self.oc_folder / "config.plist"

        # Payload paths
        self.payload_base = Path(__file__).parent.parent.parent / "payloads"
        self.oc_zip = self.payload_base / "OpenCore" / "OpenCore-RELEASE.zip"
        self.config_template = self.constants.config_template_path
        self.payload_kexts = self.payload_base / "Kexts"
        self.payload_acpi = self.payload_base / "ACPI"

    def _log(self, msg: str):
        logger.info(msg)
        self.log_lines.append(msg)

    def generate(self) -> tuple[dict, list[str]]:
        """
        Generate base folder structure and extract OpenCore.

        Returns:
            Tuple of (config dict, log lines)
        """
        self._log("[STEP] Generating base folder structure")

        # Clean previous build
        if self.oc_build.exists():
            self._log(f"  Removing old build: {self.oc_build}")
            shutil.rmtree(self.oc_build, onerror=rmtree_handler)

        self.build_path.mkdir(parents=True, exist_ok=True)
        self._log(f"  Build path: {self.build_path}")

        # Extract OpenCore
        if not self.oc_zip.exists():
            self._log(f"  [ERROR] OpenCore zip not found: {self.oc_zip}")
            raise FileNotFoundError(f"OpenCore zip not found: {self.oc_zip}")

        self._log(f"  Extracting: {self.oc_zip.name}")
        try:
            from .security import SecurityValidator
            with zipfile.ZipFile(self.oc_zip) as z:
                SecurityValidator.safe_extract(z, self.build_path)
        except (zipfile.BadZipFile, ValueError) as e:
            self._log(f"  [ERROR] Extraction failed: {e}")
            raise
        self._log(f"  Extracted to: {self.oc_build}")

        # Copy config.plist template
        if not self.config_template.exists():
            self._log(f"  [ERROR] Config template not found: {self.config_template}")
            raise FileNotFoundError(f"Config template not found: {self.config_template}")

        shutil.copy(self.config_template, self.plist_path)
        self._log(f"  Copied config.plist template -> {self.plist_path}")

        # Load and return config
        import plistlib
        config = plistlib.load(self.plist_path.open("rb"))
        self._log(f"  Loaded config.plist ({len(config)} sections)")

        return config, self.log_lines

    def get_paths(self) -> dict:
        """Return dictionary of build paths."""
        return {
            "build_path": self.build_path,
            "oc_build": self.oc_build,
            "oc_folder": self.oc_folder,
            "kexts_path": self.kexts_path,
            "acpi_path": self.acpi_path,
            "drivers_path": self.drivers_path,
            "plist_path": self.plist_path,
            "payload_kexts": self.payload_kexts,
            "payload_acpi": self.payload_acpi,
        }
