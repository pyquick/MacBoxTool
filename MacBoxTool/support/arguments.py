"""
arguments.py: CLI argument handling
"""

import sys
import time
import logging
import plistlib
import threading
import subprocess

from pathlib import Path

from . import subprocess_wrapper

from .. import constants


from ..efi_builder import build
from ..sys_patch import sys_patch
from ..sys_patch.auto_patcher import StartAutomaticPatching

from ..datasets import (
    model_array,
    os_data
)

from ..support import kdk_handler, metallib_handler
from ..support.network_handler import NetworkUtilities
from ..sys_patch.patchsets import HardwarePatchsetDetection, HardwarePatchsetSettings

from . import (
    utilities,
    defaults,
    validation,
)



# Generic building args
class arguments:

    def __init__(self, global_constants: constants.Constants) -> None:
        self.constants: constants.Constants = global_constants

        self.args = utilities.check_cli_args()

        self._parse_arguments()


    def _parse_arguments(self) -> None:
        """
        Parses arguments passed to the patcher
        """
        
            
        if self.args.validate:
            self._validation_handler()
            return

        if self.args.build:
            self._build_handler()
            return

        if self.args.patch_sys_vol:
            self._sys_patch_handler()
            return

        if self.args.unpatch_sys_vol:
            self._sys_unpatch_handler()
            return

        if self.args.prepare_for_update:
            self._prepare_for_update_handler()
            return

        if self.args.cache_os:
            self._cache_os_handler()
            return

        if self.args.auto_patch:
            self._sys_patch_auto_handler()
            return
        
        


    def _validation_handler(self) -> None:
        """
        Enter validation mode
        """
        logging.info("Set Validation Mode")
        validation.PatcherValidation(self.constants)

    
        

    def _sys_patch_handler(self) -> None:
        """
        Start root volume patching
        """

        logging.info("Set System Volume patching")
        if "Library/InstallerSandboxes/" in str(self.constants.payload_path):
            logging.info("- Running from Installer Sandbox, blocking OS updaters")
            thread = threading.Thread(target=sys_patch.PatchSysVolume(self.constants.custom_model or self.constants.computer.real_model, self.constants, None).start_patch)
            thread.start()
            while thread.is_alive():
                utilities.block_os_updaters()
                time.sleep(1)
        else:
            sys_patch.PatchSysVolume(self.constants.custom_model or self.constants.computer.real_model, self.constants, None).start_patch()


    def _sys_unpatch_handler(self) -> None:
        """
        Start root volume unpatching
        """
        logging.info("Set System Volume unpatching")
        sys_patch.PatchSysVolume(self.constants.custom_model or self.constants.computer.real_model, self.constants, None).start_unpatch()


    def _sys_patch_auto_handler(self) -> None:
        """
        Start root volume auto patching
        """

        logging.info("Set Auto patching")
        StartAutomaticPatching(self.constants).start_auto_patch()


    def _prepare_for_update_handler(self) -> None:
        """
        Prepare host for macOS update
        """
        logging.info("Preparing host for macOS update")

        os_data = utilities.fetch_staged_update(variant="Update")
        if os_data[0] is None:
            logging.info("No update staged, skipping")
            return

        os_version = os_data[0]
        os_build   = os_data[1]

        logging.info(f"{'Preparing for update to'} {os_version} ({os_build})")

        self._clean_le_handler()


    def _cache_os_handler(self) -> None:
        """
        Fetch KDK/Metallib for incoming OS, notifying the user via CLI and GUI popup
        """
        results = subprocess.run(["/bin/ps", "-ax"], stdout=subprocess.PIPE)
        if results.stdout.decode("utf-8").count("MacBoxTool --cache_os") > 1:
            logging.info("Another instance of OS caching is running, exiting")
            return

        # Read staged update from Preflight.plist
        os_data = utilities.fetch_staged_update(variant="Preflight")
        if os_data[0] is None:
            logging.info("No staged update found, exiting")
            return

        os_version, os_build = os_data
        logging.info(f"macOS Update detected: {os_version} ({os_build})")

        # Detect hardware requirements for incoming OS
        results = HardwarePatchsetDetection(
            constants=self.constants,
            xnu_major=int(os_build[:2]),
            xnu_minor=0,
            os_build=os_build,
            os_version=os_version,
        ).device_properties

        needs_kdk = bool(results.get(HardwarePatchsetSettings.KERNEL_DEBUG_KIT_REQUIRED, False))
        needs_metallib = bool(results.get(HardwarePatchsetSettings.METALLIB_SUPPORT_PKG_REQUIRED, False))

        if not needs_kdk and not needs_metallib:
            logging.info("No additional resources required for incoming OS, exiting")
            return

        # Create KDK/Metallib objects and retrieve download objects
        download_tasks: list[tuple[str, object, object]] = []

        kdk_obj = None
        metallib_obj = None

        if needs_kdk:
            logging.info("KDK required, resolving...")
            kdk_obj = kdk_handler.KernelDebugKitObject(
                self.constants, os_build, os_version,
                passive=True, check_backups_only=True,
            )
            if kdk_obj.success:
                dl = kdk_obj.retrieve_download()
                if dl is not None:
                    download_tasks.append(("KDK", dl, kdk_obj))
                else:
                    logging.info("KDK already cached, skipping")
            else:
                logging.warning(f"KDK resolution failed: {kdk_obj.error_msg}")

        if needs_metallib:
            logging.info("MetallibSupportPkg required, resolving...")
            metallib_obj = metallib_handler.MetalLibraryObject(
                self.constants, os_build, os_version,
            )
            if metallib_obj.success:
                dl = metallib_obj.retrieve_download()
                if dl is not None:
                    download_tasks.append(("Metallib", dl, metallib_obj))
                else:
                    logging.info("Metallib already cached, skipping")
            else:
                logging.warning(f"Metallib resolution failed: {metallib_obj.error_msg}")

        if not download_tasks:
            logging.info("All resources already cached, exiting")
            return

        # Notify user via CLI and GUI popup
        resource_names = ", ".join(name for name, _, _ in download_tasks)
        logging.info(f"macOS Update detected, downloading {resource_names} for macOS {os_version} ({os_build})")
        if self.constants.launcher_script is None:
            try:
                subprocess.Popen(
                    [self.constants.launcher_binary, "--gui_os_update", os_version, os_build],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
            except Exception as e:
                logging.warning(f"Failed to show GUI popup: {e}")

        # Download files
        net_util = NetworkUtilities(self.constants)

        for name, dl_obj, _ in download_tasks:
            file_path = Path(dl_obj.save_path) / dl_obj.filename
            logging.info(f"Downloading {name} ({dl_obj.filename})...")
            if not self._download_file(net_util, dl_obj.url, file_path):
                logging.error(f"Failed to download {name}")
                return
            logging.info(f"{name} download complete")

        # Validate and install
        if kdk_obj and needs_kdk:
            logging.info("Validating KDK checksum...")
            if not kdk_obj.validate_kdk_checksum():
                logging.error(f"KDK checksum validation failed: {kdk_obj.error_msg}")
                return
            logging.info("KDK checksum validated")

            kdk_path = self.constants.kdk_download_path
            if kdk_path.exists():
                logging.info("Installing KDK backup (only_install_backup=True)...")
                if not kdk_handler.KernelDebugKitUtilities().install_kdk_dmg(
                    kdk_path, only_install_backup=True,
                ):
                    logging.error("Failed to install KDK backup")
                    return
                logging.info("KDK backup installed successfully")

        if metallib_obj and needs_metallib:
            logging.info("Installing MetallibSupportPkg...")
            if not metallib_obj.install_metallib():
                logging.error("Failed to install MetallibSupportPkg")
                return
            logging.info("MetallibSupportPkg installed successfully")

        logging.info("OS caching completed successfully")

    def _download_file(self, net_util: NetworkUtilities, url: str, file_path: Path) -> bool:
        """
        Download a file synchronously without progress output.
        """
        try:
            response = net_util.get(url, stream=True, timeout=60)
        except Exception as e:
            logging.error(f"Download request failed: {e}")
            return False

        if response.status_code != 200:
            logging.error(f"Download failed: HTTP {response.status_code}")
            return False

        try:
            with open(file_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
        except Exception as e:
            logging.error(f"Download write error: {e}")
            if file_path.exists():
                file_path.unlink()
            return False

        return True


    def _clean_le_handler(self) -> None:
        """
        Clean /Library/Extensions of problematic kexts
        Note macOS Ventura and older do this automatically
        """

        if self.constants.detected_os < os_data.os_data.sonoma:
            return

        logging.info("Cleaning /Library/Extensions")

        for kext in Path("/Library/Extensions").glob("*.kext"):
            if not Path(f"{kext}/Contents/Info.plist").exists():
                continue
            try:
                kext_plist = plistlib.load(open(f"{kext}/Contents/Info.plist", "rb"))
            except Exception as e:
                logging.info(f"  {'- Failed to load plist for'} {kext.name}: {e}")
                continue
            if "GPUCompanionBundles" not in kext_plist:
                continue
            logging.info(f"  {'- Removing'} {kext.name}")
            subprocess_wrapper.run_as_root(["/bin/rm", "-rf", kext])


    def _build_handler(self) -> None:
        """
        Start config building process
        """
        logging.info("Set OpenCore Build")

        if self.args.model:
            if self.args.model:
                logging.info(f"{'- Using custom model:'} {self.args.model}")
                self.constants.custom_model = self.args.model
                defaults.GenerateDefaults(self.constants.custom_model, False, self.constants)
            elif self.constants.computer.real_model not in model_array.SupportedSMBIOS and self.constants.allow_oc_everywhere is False:
                logging.info(
                    """Your model is not supported by this patcher for running unsupported OSes!

If you plan to create the USB for another machine, please select the "Change Model" option in the menu."""
                )
                sys.exit(1)
            else:
                logging.info(f"{'- Using detected model:'} {self.constants.computer.real_model}")
                defaults.GenerateDefaults(self.constants.custom_model, True, self.constants)

        if self.args.verbose:
            logging.info("- Set verbose configuration")
            self.constants.verbose_debug = True
        else:
            self.constants.verbose_debug = False  # Override Defaults detected

        
        if self.args.debug_oc:
            logging.info("- Set OpenCore DEBUG configuration")
            self.constants.opencore_debug = True

        if self.args.debug_kext:
            logging.info("- Set kext DEBUG configuration")
            self.constants.kext_debug = True

        if self.args.hide_picker:
            logging.info("- Set HidePicker configuration")
            self.constants.showpicker = False

        if self.args.disable_sip:
            logging.info("- Set Disable SIP configuration")
            self.constants.sip_status = False
        else:
            self.constants.sip_status = True  # Override Defaults detected

        if self.args.disable_smb:
            logging.info("- Set Disable SecureBootModel configuration")
            self.constants.secure_status = False
        else:
            self.constants.secure_status = True  # Override Defaults detected

        if self.args.vault:
            logging.info("- Set Vault configuration")
            self.constants.vault = True

        if self.args.firewire:
            logging.info("- Set FireWire Boot configuration")
            self.constants.firewire_boot = True

        if self.args.nvme:
            logging.info("- Set NVMe Boot configuration")
            self.constants.nvme_boot = True

        if self.args.wlan:
            logging.info("- Set Wake on WLAN configuration")
            self.constants.enable_wake_on_wlan = True

        if self.args.disable_tb:
            logging.info("- Set Disable Thunderbolt configuration")
            self.constants.disable_tb = True

        if self.args.force_surplus:
            logging.info("- Forcing SurPlus override configuration")
            self.constants.force_surplus = True

        if self.args.moderate_smbios:
            logging.info("- Set Moderate SMBIOS Patching configuration")
            self.constants.serial_settings = "Moderate"

        if self.args.smbios_spoof:
            if self.args.smbios_spoof == "Minimal":
                self.constants.serial_settings = "Minimal"
            elif self.args.smbios_spoof == "Moderate":
                self.constants.serial_settings = "Moderate"
            elif self.args.smbios_spoof == "Advanced":
                self.constants.serial_settings = "Advanced"
            else:
                logging.info(f"{'- Unknown SMBIOS arg passed:'} {self.args.smbios_spoof}")

        if self.args.support_all:
            logging.info("- Building for natively supported model")
            self.constants.allow_oc_everywhere = True
            self.constants.serial_settings = "None"
        


        build.BuildOpenCore(self.constants.custom_model or self.constants.computer.real_model, self.constants)
