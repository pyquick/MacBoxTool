"""
base.py: Base Kext management - handles common kext operations
"""


import logging
import zipfile
from pathlib import Path
from typing import Any
from ..config import ConfigManager
import subprocess
from ..utils import find_kext_zip
from ... import constants
import plistlib
import shutil

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

    @staticmethod
    def get_item_by_kv(iterable: dict, key: str, value: Any) -> dict:
        """
        Gets an item from a list of dicts by key and value

        Parameters:
            iterable (list): List of dicts
            key       (str): Key to search for
            value     (any): Value to search for

        """

        item = None
        for i in iterable:
            if i[key] == value:
                item = i
                break
        return item

    def _log(self, msg: str):
        logger.info(msg)
        self.log_lines.append(msg)

    def get_kext_by_bundle_path(self, bundle_path: str) -> dict:
        """
        Gets a kext by bundle path

        Parameters:
            bundle_path (str): Relative bundle path of the kext in the EFI folder
        """

        kext: dict = self.get_item_by_kv(self.config["Kernel"]["Add"], "BundlePath", bundle_path)
        if not kext:
            logging.info("- Could not find kext {bundle_path}!".format(bundle_path=bundle_path))
            raise IndexError
        return kext
    
    def get_efi_binary_by_path(self, bundle_name: str, entry_type: str, efi_type: str) -> dict:
        """
        Gets an EFI binary by name

        Parameters:
            bundle_name (str): Name of the EFI binary
            entry_type  (str): Type of EFI binary (UEFI, Misc)
            efi_type    (str): Type of EFI binary (Drivers, Tools)
        """

        efi_binary: dict = self.get_item_by_kv(self.config[entry_type][efi_type], "Path", bundle_name)
        if not efi_binary:
            logging.info("- Could not find {efi_type}: {bundle_name}!".format(efi_type=efi_type, bundle_name=bundle_name))
            raise IndexError
        return efi_binary

    def sign_files(self) -> None:
        """
        Signs files for on OpenCorePkg's Vault system
        """

        if self.constants.vault is False:
            return

        logging.info("- Vaulting EFI\n=========================================")
        popen = subprocess.Popen([str(self.constants.vault_path), f"{self.constants.oc_folder}/"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
        for stdout_line in iter(popen.stdout.readline, ""):
            logging.info(stdout_line.strip())
        logging.info("=========================================")

    def validate_pathing(self) -> None:
        """
        Validate whether all files are accounted for on-disk

        This ensures that OpenCore won't hit a critical error and fail to boot
        """

        logging.info("- Validating generated config")
        if not Path(self.constants.opencore_release_folder / Path("EFI/OC/config.plist")).exists():
            logging.info("- OpenCore config file missing!!!")
            raise Exception("OpenCore config file missing")

        config_plist = plistlib.load(Path(self.constants.opencore_release_folder / Path("EFI/OC/config.plist")).open("rb"))

        for acpi in config_plist["ACPI"]["Add"]:
            if not Path(self.constants.opencore_release_folder / Path("EFI/OC/ACPI") / Path(acpi["Path"])).exists():
                logging.info("- Missing ACPI Table: {acpi['Path']}")
                raise Exception(f"Missing ACPI Table: {acpi['Path']}")

        for kext in config_plist["Kernel"]["Add"]:
            kext_path = Path(self.constants.opencore_release_folder / Path("EFI/OC/Kexts") / Path(kext["BundlePath"]))
            kext_binary_path = Path(kext_path / Path(kext["ExecutablePath"]))
            kext_plist_path = Path(kext_path / Path(kext["PlistPath"]))
            if not kext_path.exists():
                logging.info("- Missing kext: {kext_path}".format(kext_path=kext_path))
                raise Exception(f"{'Missing'} {kext_path}")
            if not kext_binary_path.exists():
                logging.info("- Missing {kext}'s binary: {kext_binary_path}".format(kext=kext['BundlePath'], kext_binary_path=kext_binary_path))
                raise Exception(f"{'Missing'} {kext_binary_path}")
            if not kext_plist_path.exists():
                logging.info("- Missing {kext}'s plist: {kext_plist_path}".format(kext=kext['BundlePath'], kext_plist_path=kext_plist_path))
                raise Exception(f"{'Missing'} {kext_plist_path}")

        for tool in config_plist["Misc"]["Tools"]:
            if not Path(self.constants.opencore_release_folder / Path("EFI/OC/Tools") / Path(tool["Path"])).exists():
                logging.info("- Missing tool: {tool}".format(tool=tool['Path']))
                raise Exception("- Missing tool: {tool}".format(tool=tool['Path']))

        for driver in config_plist["UEFI"]["Drivers"]:
            if not Path(self.constants.opencore_release_folder / Path("EFI/OC/Drivers") / Path(driver["Path"])).exists():
                logging.info("- Missing driver: {driver}".format(driver=driver['Path']))
                raise Exception("- Missing driver: {driver}".format(driver=driver['Path']))

        # Validating local files
        # Report if they have no associated config.plist entry (i.e. they're not being used)
        for tool_files in Path(self.constants.opencore_release_folder / Path("EFI/OC/Tools")).glob("*"):
            if tool_files.name not in [x["Path"] for x in config_plist["Misc"]["Tools"]]:
                logging.info("- Missing tool from config: {tool_files_name}".format(tool_files_name=tool_files.name))
                raise Exception("- Missing tool from config: {tool_files_name}".format(tool_files_name=tool_files.name))

        for driver_file in Path(self.constants.opencore_release_folder / Path("EFI/OC/Drivers")).glob("*"):
            if driver_file.name not in [x["Path"] for x in config_plist["UEFI"]["Drivers"]]:
                logging.info("- Found extra driver: {driver_file_name}".format(driver_file_name=driver_file.name))
                raise Exception("- Found extra driver: {driver_file_name}".format(driver_file_name=driver_file.name))

        self._validate_malformed_kexts(self.constants.opencore_release_folder / Path("EFI/OC/Kexts"))

    def _validate_malformed_kexts(self, directory: str | Path) -> None:
        """
        Validate Info.plist and executable pathing for kexts
        """
        for kext_folder in Path(directory).glob("*.kext"):
            if not Path(kext_folder / Path("Contents/Info.plist")).exists():
                continue

            kext_data = plistlib.load(Path(kext_folder / Path("Contents/Info.plist")).open("rb"))
            if "CFBundleExecutable" in kext_data:
                expected_executable = Path(kext_folder / Path("Contents/MacOS") / Path(kext_data["CFBundleExecutable"]))
                if not expected_executable.exists():
                    logging.info("- Missing executable for {kext_folder_name}: Contents/MacOS/{expected_executable_name}".format(kext_folder_name=kext_folder.name, expected_executable_name=expected_executable.name))
                    raise Exception("- Missing executable for {kext_folder_name}: Contents/MacOS/{expected_executable_name}".format(kext_folder_name=kext_folder.name, expected_executable_name=expected_executable.name))

            if Path(kext_folder / Path("Contents/PlugIns")).exists():
                self._validate_malformed_kexts(kext_folder / Path("Contents/PlugIns"))

    
    
    def enable_kext(self, kext_name: str, kext_version: str, kext_path: Path, check: bool = False) -> None:
        """
        Enables a kext in the config.plist

        Parameters:
            kext_name     (str): Name of the kext
            kext_version  (str): Version of the kext
            kext_path    (Path): Path to the kext
        """

        kext: dict = self.get_kext_by_bundle_path(kext_name)

        if callable(check) and not check():
            # Check failed
            return

        if kext["Enabled"] is True:
            return

        logging.info("- Adding {kext_name} {kext_version}".format(kext_name=kext_name, kext_version=kext_version))
        shutil.copy(kext_path, self.constants.kexts_path)
        kext["Enabled"] = True
    
    

    def enable_base_kexts(self) -> list[str]:
        """
        Enable base kexts needed for all models.

        Returns:
            Log lines
        """
        self._log("[STEP] Enabling kexts")

        # Lilu is always required
        self.enable_kext("Lilu.kext", self.constants.lilu_version, self.constants.lilu_path)
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
    
    def cleanup(self) -> None:
        """
        Clean up files and entries
        """

        logging.info("- Cleaning up files")
        # Remove unused entries
        entries_to_clean = {
            "ACPI":   ["Add", "Delete", "Patch"],
            "Booter": ["Patch"],
            "Kernel": ["Add", "Block", "Force", "Patch"],
            "Misc":   ["Tools"],
            "UEFI":   ["Drivers"],
        }

        for entry in entries_to_clean:
            for sub_entry in entries_to_clean[entry]:
                for item in list(self.config[entry][sub_entry]):
                    if item["Enabled"] is False:
                        self.config[entry][sub_entry].remove(item)

        for kext in self.constants.kexts_path.rglob("*.zip"):
            with zipfile.ZipFile(kext) as zip_file:
                zip_file.extractall(self.constants.kexts_path)
            kext.unlink()

        for item in self.constants.oc_folder.rglob("*.zip"):
            with zipfile.ZipFile(item) as zip_file:
                zip_file.extractall(self.constants.oc_folder)
            item.unlink()

        if not self.constants.recovery_status:
            # Crashes in RecoveryOS for unknown reason
            for i in self.constants.build_path.rglob("__MACOSX"):
                shutil.rmtree(i)

        # Remove unused plugins inside of kexts
        # Following plugins are sometimes unused as there's different variants machines need
        known_unused_plugins = [
            "AirPortBrcm4331.kext",
            "AirPortAtheros40.kext",
            "AppleAirPortBrcm43224.kext",
            "AirPortBrcm4360_Injector.kext",
            "AirPortBrcmNIC_Injector.kext"
        ]
        for kext in Path(self.constants.opencore_release_folder / Path("EFI/OC/Kexts")).glob("*.kext"):
            for plugin in Path(kext / "Contents/PlugIns/").glob("*.kext"):
                should_remove = True
                for enabled_kexts in self.config["Kernel"]["Add"]:
                    if enabled_kexts["BundlePath"].endswith(plugin.name):
                        should_remove = False
                        break
                if should_remove:
                    if plugin.name not in known_unused_plugins:
                        raise Exception(" - Unknown plugin found: {plugin_name}".format(plugin_name=plugin.name))
                    shutil.rmtree(plugin)

        #Path(self.constants.opencore_zip_copied).unlink()
