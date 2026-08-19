"""
start.py: Start automatic patching of host
"""

import logging
import plistlib
import subprocess

from packaging import version
from PySide2.QtWidgets import QApplication, QMessageBox

from ... import constants
from ...support import (
    utilities,
    global_settings,
    network_handler,
)
from ...support.update import check_update
from ..patchsets import (
    HardwarePatchsetDetection,
    HardwarePatchsetValidation,
)


class StartAutomaticPatching:
    """
    Start automatic patching of host
    """

    def __init__(self, global_constants: constants.Constants):
        self.constants: constants.Constants = global_constants

    def start_auto_patch(self):
        """
        Initiates automatic patching

        Auto Patching's main purpose is to try and tell the user they're missing root patches
        New users may not realize OS updates remove our patches, so we try and run when nessasary

        Conditions for running:
            - Verify running GUI (TUI users can write their own scripts)
            - Verify the Snapshot Seal is intact (if not, assume user is running patches)
            - Verify this model needs patching (if not, assume user upgraded hardware and MacBoxTool was not removed)
            - Verify there are no updates for MacBoxTool (ensure we have the latest patch sets)

        If all these tests pass, start Root Patcher
        """

        logging.info("- Starting Automatic Patching")
        if self.constants.qt_variant is False:
            logging.info("- Auto Patch option is not supported on TUI, please use GUI")
            return

        update_result = self._check_for_updates()
        if update_result.get("if_update"):
            update_version = update_result.get("update_version", "")
            logging.info("- Found new version: {version}".format(version=update_version))
            self._prompt_update(update_version)
            return

        if utilities.check_seal() is True:
            logging.info("- Detected Snapshot seal intact, detecting patches")
            patches = HardwarePatchsetDetection(self.constants).device_properties
            if not any(not patch.startswith("Settings") and not patch.startswith("Validation") and patches[patch] is True for patch in patches):
                patches = {}
            if patches:
                logging.info("- Detected applicable patches, determining whether possible to patch")
                if patches[HardwarePatchsetValidation.PATCHING_NOT_POSSIBLE] is True:
                    logging.info("- Cannot run patching")
                    return

                logging.info("- Determined patching is possible, checking for MacBoxTool updates")
                patch_string = ""
                for patch in patches:
                    if patches[patch] is True and not patch.startswith("Settings") and not patch.startswith("Validation"):
                        patch_string += f"- {patch}\n"

                logging.info("- No new binaries found on Github, proceeding with patching")

                warning_str = ""
                if network_handler.NetworkUtilities(self.constants).verify_network_connection("https://api.github.com/repos/pyquick/MacBoxTool/releases/latest", 5) is False:
                    warning_str = "\n\nWARNING: We're unable to verify whether there are any new releases of MacBoxTool on Github. Be aware that you may be using an outdated version for this OS. If you're unsure, verify on Github that MacBoxTool {version} is the latest official release".format(version=self.constants.macboxtool_version)

                dialog_text = (
                    "MacBoxTool has detected you're running without Root Patches, and would like to install them.\n\n"
                    "macOS wipes all root patches during OS installs and updates, so they need to be reinstalled.\n\n"
                    "Following Patches have been detected for your system:\n"
                    f"{patch_string}\n"
                    f"Would you like to apply these patches?{warning_str}"
                )
                if self._ask_yes_no("Root Patches Required", dialog_text):
                    self._open_sys_patch(start_patching=True)
                return

            logging.info("- No patches detected")
        else:
            logging.info("- Detected Snapshot seal not intact, skipping")

        if self._determine_if_versions_match():
            self._determine_if_boot_matches()

    def _check_for_updates(self) -> dict:
        try:
            return check_update.CheckUpdate(self.constants).check_update()
        except Exception as e:
            logging.error("- Failed to check for MacBoxTool updates: {error}".format(error=e))
            return check_update.UPDATE_RESULT_TEMPLATE.copy()

    def _prompt_update(self, update_version: str):
        current_version = self.constants.macboxtool_version
        message = (
            "A new version of MacBoxTool is available.\n\n"
            "MacBoxTool {version} is now available. You have {current_version}.\n\n"
            "Would you like to open the Updater page?"
        ).format(version=update_version or "latest", current_version=current_version)
        if self._ask_yes_no("Update Available", message):
            self._open_updater()

    def _escape_applescript_text(self, text: str) -> str:
        return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")

    def _ask_yes_no(self, title: str, message: str) -> bool:
        app = QApplication.instance()
        if app:
            result = QMessageBox.question(
                self._main_window(),
                title,
                message,
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            return result == QMessageBox.Yes

        escaped_title = self._escape_applescript_text(title)
        escaped_message = self._escape_applescript_text(message)
        args = [
            "/usr/bin/osascript",
            "-e",
            f'display dialog "{escaped_message}" with title "{escaped_title}" buttons {{"No", "Yes"}} default button "Yes" with icon POSIX file "{self.constants.app_icon_path}"',
        ]
        output = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        return output.returncode == 0

    def _main_window(self):
        try:
            from ... import app_entry
            return getattr(app_entry, "_qt_window", None)
        except Exception:
            return None

    def _open_window_page(self, page_name: str):
        window = self._main_window()
        if window and hasattr(window, page_name):
            window.show()
            window.raise_()
            window.activateWindow()
            window.stackedWidget.setCurrentWidget(getattr(window, page_name))
            return True
        return False

    def _open_updater(self):
        if self._open_window_page("updater"):
            return
        self.constants.start_updater = True
        self._open_gui_if_needed()
        logging.info("- Unable to locate GUI Updater page")

    def _open_sys_patch(self, start_patching: bool = False):
        if self._open_window_page("sys_patch_page"):
            page = self._main_window().sys_patch_page
            if start_patching:
                if getattr(page, "available_patches", False) and getattr(page, "patches", None):
                    page.pending_auto_patch = False
                    page.start_root_patching()
                else:
                    page.pending_auto_patch = True
                    self.constants.start_sys_patch_now = True
            return
        self.constants.start_sys_patch = True
        self.constants.start_sys_patch_now = start_patching
        self._open_gui_if_needed()
        logging.info("- Unable to locate GUI Root Patching page")

    def _open_build(self):
        if self._open_window_page("build"):
            return
        self.constants.start_build_install = True
        self._open_gui_if_needed()
        logging.info("- Unable to locate GUI Build page")

    def _open_gui_if_needed(self):
        if QApplication.instance() is not None:
            return
        from ...qt_gui.gui_entry import OpenGUI
        settings = global_settings.GlobalSettings(self.constants)
        OpenGUI(self.constants, settings).gui_main_menu()

    def _version_is_newer_than_local(self, other_version: str) -> bool:
        try:
            return version.parse(str(other_version)) > version.parse(str(self.constants.macboxtool_version))
        except version.InvalidVersion:
            return False

    def _determine_if_versions_match(self):
        """
        Determine if the booted version of MacBoxTool matches the installed version

        ie. Installed app is 0.2.0, but EFI version is 0.1.0

        Returns:
            bool: True if versions match, False if not
        """

        logging.info("- Checking booted vs installed MacBoxTool build")
        if self.constants.computer.mbt_version is None:
            logging.info("- Booted version not found")
            return True

        if self.constants.computer.mbt_version == self.constants.macboxtool_version:
            logging.info("- Versions match")
            return True

        if self.constants.special_build is True:
            logging.info("- Special build detected, assuming installed is older")
            return False

        if self._version_is_newer_than_local(self.constants.computer.mbt_version):
            logging.info("- Installed version is newer than booted version")
            return True

        build_type = "a different" if self.constants.special_build else "an outdated"
        dialog_text = "MacBoxTool has detected that you are booting {build_type} OpenCore build\n- Booted: {booted_version}\n- Installed: {installed_version}\n\nWould you like to update the OpenCore bootloader?".format(
            build_type=build_type,
            booted_version=self.constants.computer.mbt_version,
            installed_version=self.constants.macboxtool_version,
        )
        if self._ask_yes_no("Update OpenCore Bootloader?", dialog_text):
            logging.info("- Launching GUI's Build/Install menu")
            self._open_build()

        return False

    def _determine_if_boot_matches(self):
        """
        Determine if the boot drive matches the macOS drive
        ie. Booted from USB, but macOS is on internal disk

        Goal of this function is to determine whether the user
        is using a USB drive to Boot OpenCore but macOS does not
        reside on the same drive as the USB.

        If we determine them to be mismatched, notify the user
        and ask if they want to install to install to disk.
        """

        logging.info("- Determining if macOS drive matches boot drive")

        should_notify = global_settings.GlobalSettings(self.constants).find_key("AutoPatch_Notify_Mismatched_Disks")
        if should_notify is False:
            logging.info("- Skipping due to user preference")
            return
        if self.constants.host_is_hackintosh is True:
            logging.info("- Skipping due to hackintosh")
            return
        if not self.constants.booted_oc_disk:
            logging.info("- Failed to find disk OpenCore launched from")
            return

        root_disk = self.constants.booted_oc_disk.strip("disk")
        root_disk = "disk" + root_disk.split("s")[0]

        logging.info("  - Boot Drive: {boot_disk} ({root_disk})".format(
            boot_disk=self.constants.booted_oc_disk, root_disk=root_disk,
        ))
        macOS_disk = utilities.get_disk_path()
        logging.info("  - macOS Drive: {macos_disk}".format(macos_disk=macOS_disk))
        physical_stores = utilities.find_apfs_physical_volume(macOS_disk)
        logging.info("  - APFS Physical Stores: {physical_stores}".format(physical_stores=physical_stores))

        disk_match = False
        for disk in physical_stores:
            if root_disk in disk:
                logging.info("- Boot drive matches macOS drive ({disk})".format(disk=disk))
                disk_match = True
                break

        if disk_match is True:
            return

        logging.info("- Boot Drive does not match macOS drive, checking if OpenCore is on a USB drive")

        disk_info = plistlib.loads(subprocess.run(["/usr/sbin/diskutil", "info", "-plist", root_disk], stdout=subprocess.PIPE).stdout)
        try:
            if disk_info["Ejectable"] is False:
                logging.info("- Boot Disk is not removable, skipping prompt")
                return

            logging.info("- Boot Disk is ejectable, prompting user to install to internal")

            dialog_text = "MacBoxTool has detected that you are booting OpenCore from an USB or External drive.\n\nIf you would like to boot your Mac normally without a USB drive plugged in, you can install OpenCore to the internal hard drive.\n\nWould you like to launch MacBoxTool and install to disk?"
            if self._ask_yes_no("Install OpenCore to Internal Disk?", dialog_text):
                logging.info("- Launching GUI's Build/Install menu")
                self._open_build()

        except KeyError:
            logging.info("- Unable to determine if boot disk is removable, skipping prompt")
