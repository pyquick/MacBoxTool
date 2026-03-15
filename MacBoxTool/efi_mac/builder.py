"""
builder.py: Main EFI builder that coordinates all modules
"""


import logging
import plistlib
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

from .base import BaseGenerator
from .config import ConfigManager

if TYPE_CHECKING:
    from .. import constants

logger = logging.getLogger(__name__)


class BuildOpenCore:
    """Build OpenCore EFI for a given Mac model using modular architecture."""

    def __init__(self, model: str, global_constants):  # Constants instance passed at runtime
        from .security import SecurityValidator
        if not SecurityValidator.validate_model(model):
            raise ValueError(f"Invalid model format: {model}")
        self.model = model
        self.constants = global_constants
        self.config: dict = None
        self.log_lines: list[str] = []

        # Initialize base generator
        self.base_gen = BaseGenerator(model, global_constants)
        self.paths = self.base_gen.get_paths()

    def _log(self, msg: str):
        logger.info(msg)
        self.log_lines.append(msg)

    def build(self) -> list[str]:
        """
        Run the full build process.

        Returns:
            Log lines from the build process
        """
        self._log(f"=== Building OpenCore EFI for {self.model} ===")
        self._log(f"Date: {date.today()}")
        self._log(f"OpenCore version: {self.constants.opencore_version}")
        self._log("")

        # Validate model exists in smbios_dictionary
        from ..datasets.smbios_data import smbios_dictionary
        if self.model not in smbios_dictionary:
            self._log(f"[ERROR] Model {self.model} is not a known SMBIOS model!")
            return self.log_lines

        # Step 1: Generate base structure
        self.config, logs = self.base_gen.generate()
        self.log_lines.extend(logs)

        # Step 2: Set revision info
        from .smbios.base import SMBIOSManager
        smbios_mgr = SMBIOSManager(self.config, self.constants, self.model, self.paths)
        logs = smbios_mgr.set_revision()
        self.log_lines.extend(logs)

        # Step 3: Apply quirks (Booter, Kernel, Misc Security)
        from .smbios.quirks import QuirksManager
        quirks_mgr = QuirksManager(self.config, self.constants, self.model, self.paths)
        logs = quirks_mgr.apply()
        self.log_lines.extend(logs)

        # Step 4: Enable base kexts
        from .kexts.base import KextManager
        kext_mgr = KextManager(self.config, self.constants, self.model, self.paths)
        logs = kext_mgr.enable_base_kexts()
        self.log_lines.extend(logs)
        enabled_kexts = sum(1 for k in self.config.get("Kernel", {}).get("Add", []) if k.get("Enabled"))
        self._log(f"  Total enabled kexts: {enabled_kexts}")

        # Step 5: Enable base ACPI
        from .acpi.base import ACPIManager
        acpi_mgr = ACPIManager(self.config, self.constants, self.model, self.paths)
        logs = acpi_mgr.enable_base_acpi()
        self.log_lines.extend(logs)

        # Step 6: Enable drivers
        from .drivers.base import DriverManager
        driver_mgr = DriverManager(self.config, self.constants, self.model, self.paths)
        logs = driver_mgr.enable_base_drivers()
        self.log_lines.extend(logs)

        # Step 7: Apply NVRAM settings (boot-args, SIP, BT, MBT flags)
        from .smbios.nvram import NVRAMManager
        nvram_mgr = NVRAMManager(self.config, self.constants, self.model, self.paths)
        logs = nvram_mgr.apply()
        self.log_lines.extend(logs)

        # Step 7.5: 5K iMac / iMac Pro dual DisplayPort handling
        self._dual_dp_handling()

        # Step 7.6: Apply SMBIOS spoofing
        from .smbios.smbios_spoof import SMBIOSSpoofManager
        spoof_mgr = SMBIOSSpoofManager(self.config, self.constants, self.model, self.paths)
        logs = spoof_mgr.apply()
        self.log_lines.extend(logs)

        # Step 8: Cleanup disabled entries
        config_mgr = ConfigManager(self.config, self.paths["plist_path"])
        logs = config_mgr.cleanup()
        self.log_lines.extend(logs)

        # Step 9: Save config
        logs = config_mgr.save()
        self.log_lines.extend(logs)

        # Step 10: Validate
        self._validate()

        self._log("")
        self._log(f"[DONE] EFI built at: {self.paths['oc_build']}")

        return self.log_lines

    def _dual_dp_handling(self):
        """5K iMac / iMac Pro dual DisplayPort boot chain handling."""
        from ..datasets import smbios_data
        model_info = smbios_data.smbios_dictionary.get(self.model, {})
        if not model_info.get("Dual DisplayPort"):
            return

        self._log("[STEP] Dual DisplayPort handling (5K iMac)")
        import shutil

        oc_folder = self.paths["oc_folder"]
        oc_build = self.paths["oc_build"]

        # Set LauncherPath
        self.config.setdefault("Misc", {}).setdefault("Boot", {})["LauncherPath"] = "\\boot.efi"

        # Create diagnostics directory structure
        diags_dir = oc_build / ".diagnostics" / "Drivers" / "HardwareDrivers"
        diags_dir.mkdir(parents=True, exist_ok=True)

        # Move OpenCore to Product.efi under diagnostics
        boot_efi = oc_build / "EFI" / "BOOT" / "BOOTx64.efi"
        if boot_efi.exists():
            shutil.move(str(boot_efi), str(diags_dir / "Product.efi"))

        # Copy diags launcher to boot.efi
        if self.constants.diags_launcher_path.exists():
            shutil.copy(str(self.constants.diags_launcher_path), str(oc_build / "boot.efi"))
            self._log("  Dual DP: boot chain configured")
        else:
            self._log("  [WARN] diags launcher not found")

    def _validate(self):
        """
        Validate that referenced files exist on disk.

        Returns:
            Log lines from validation
        """
        self._log("[STEP] Validating EFI")
        errors = 0
        plist_path = self.paths["plist_path"]
        kexts_path = self.paths["kexts_path"]
        drivers_path = self.paths["drivers_path"]
        oc_folder = self.paths["oc_folder"]

        if not plist_path.exists():
            self._log("  [ERROR] config.plist missing!")
            errors += 1

        for kext in self.config.get("Kernel", {}).get("Add", []):
            kp = kexts_path / kext["BundlePath"]
            if not kp.exists():
                self._log(f"  [WARN] Missing kext: {kext['BundlePath']}")
                errors += 1

        for drv in self.config.get("UEFI", {}).get("Drivers", []):
            dp = drivers_path / drv["Path"]
            if not dp.exists():
                self._log(f"  [WARN] Missing driver: {drv['Path']}")
                errors += 1

        for tool in self.config.get("Misc", {}).get("Tools", []):
            tp = oc_folder / "Tools" / tool["Path"]
            if not tp.exists():
                self._log(f"  [WARN] Missing tool: {tool['Path']}")
                errors += 1

        if errors == 0:
            self._log("  Validation passed")
        else:
            self._log(f"  Validation completed with {errors} warning(s)")
