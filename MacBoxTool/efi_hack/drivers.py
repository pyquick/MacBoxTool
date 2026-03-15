"""
drivers.py: UEFI driver selection for Hackintosh EFI

Required:
  HfsPlus.efi      — HFS+ volume support (macOS installer, Recovery)
  OpenRuntime.efi  — NVRAM fix, memory management (replaces AptioMemoryFix)

Optional:
  OpenCanopy.efi       — graphical boot picker
  ResetNvramEntry.efi  — NVRAM reset menu entry
  OpenLinuxBoot.efi    — Linux boot support (user opt-in only)

References: https://dortania.github.io/OpenCore-Install-Guide/
"""

import logging
import shutil
from pathlib import Path

from ..efi_mac.config import ConfigManager

logger = logging.getLogger(__name__)

# APFS version bounds for specific macOS targets
# Use -1 / -1 to allow any version (Big Sur+)
_APFS_ANY = (-1, -1)

_APFS_MIN_VERSION = {
    "high_sierra": (748077008000000, 20180621),
    "mojave":      (945275007000000, 20190820),
    "catalina":    (1412101001000000, 20200306),
}


class HackDrivers:
    """Select and enable UEFI drivers for Hackintosh."""

    def __init__(self, config: dict, constants, paths: dict,
                 target_macos: str = ""):
        self.config = config
        self.constants = constants
        self.paths = paths
        # target_macos: e.g. "high_sierra", "mojave", "catalina", "big_sur"
        self.target_macos = target_macos.lower().replace(" ", "_")
        self.log_lines: list[str] = []
        self.config_mgr = ConfigManager(config, paths["plist_path"])

    def _log(self, msg: str):
        logger.info(msg)
        self.log_lines.append(msg)

    def _copy_and_enable(self, src_path: Path, filename: str) -> bool:
        """Copy driver to Drivers/ dir and register it in config."""
        drivers_path = self.paths["drivers_path"]
        if src_path.exists():
            shutil.copy(src_path, drivers_path / filename)
            self.config_mgr.enable_driver(filename)
            self._log(f"  + {filename}")
            return True
        self._log(f"  [WARN] Driver not found: {src_path}")
        return False

    def _enable_only(self, filename: str):
        """Enable a driver that is already present in config template."""
        self.config_mgr.enable_driver(filename)
        self._log(f"  + {filename}")

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def apply(self) -> list[str]:
        """Select and enable UEFI drivers."""
        self._log("[STEP] Selecting UEFI Drivers (Hackintosh)")

        self._add_required_drivers()
        self._add_optional_drivers()
        self._configure_apfs()

        return self.log_lines

    # ------------------------------------------------------------------
    # Required
    # ------------------------------------------------------------------

    def _add_required_drivers(self):
        """Add drivers that are always required."""
        # HfsPlus: needed to read HFS+ volumes (macOS installer + Recovery)
        hfs_path = getattr(self.constants, "hfsplus_driver_path", None)
        if hfs_path and Path(hfs_path).exists():
            self._copy_and_enable(Path(hfs_path), "HfsPlus.efi")
        else:
            # Fall back to enabling from template (already bundled)
            self._enable_only("HfsPlus.efi")
            self._log("  [NOTE] HfsPlus.efi sourced from config template")

        # OpenRuntime: NVRAM fix + memory slide management
        self._enable_only("OpenRuntime.efi")

    # ------------------------------------------------------------------
    # Optional
    # ------------------------------------------------------------------

    def _add_optional_drivers(self):
        """Add optional drivers based on constants / user preferences."""
        # OpenCanopy: graphical boot picker (needs Resources/ folder)
        if getattr(self.constants, "showpicker", True):
            self._enable_only("OpenCanopy.efi")

        # ResetNvramEntry: adds "Reset NVRAM" to OpenCore picker
        if getattr(self.constants, "nvram_reset_entry", True):
            self._enable_only("ResetNvramEntry.efi")

        # OpenLinuxBoot: Linux boot support (explicit opt-in only)
        if getattr(self.constants, "linux_boot_support", False):
            self._enable_only("OpenLinuxBoot.efi")
            self._log("  + OpenLinuxBoot.efi (Linux boot support)")

        # APFS aligned patch driver (macOS 26+ FileVault 2 compatibility)
        if getattr(self.constants, "allow_apfs_aligned_patch", False):
            apfs_drv = getattr(self.constants, "sequoia_apfs_driver_path", None)
            if apfs_drv:
                self._copy_and_enable(Path(apfs_drv), "apfs_aligned.efi")
                self.config_mgr.set_uefi_apfs("EnableJumpstart", False)
            else:
                self.config_mgr.set_uefi_apfs("EnableJumpstart", True)
        else:
            self.config_mgr.set_uefi_apfs("EnableJumpstart", True)

    # ------------------------------------------------------------------
    # APFS version policy
    # ------------------------------------------------------------------

    def _configure_apfs(self):
        """Set APFS MinVersion/MinDate to allow the target macOS version."""
        if self.target_macos in _APFS_MIN_VERSION:
            min_ver, min_date = _APFS_MIN_VERSION[self.target_macos]
            self._log(f"  APFS: MinVersion={min_ver}, MinDate={min_date} "
                      f"(targeting {self.target_macos})")
        else:
            # Big Sur and later — allow any APFS version
            min_ver, min_date = _APFS_ANY
            self._log("  APFS: MinVersion=-1, MinDate=-1 (Big Sur+)")

        self.config_mgr.set_uefi_apfs("MinVersion", min_ver)
        self.config_mgr.set_uefi_apfs("MinDate", min_date)
