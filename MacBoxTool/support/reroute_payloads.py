"""
reroute_payloads.py: Reroute binaries to tmp directory, and mount a disk image of the payloads
Implements a shadowfile to avoid direct writes to the dmg
"""

import atexit
import os
import plistlib
import tempfile
import subprocess
import sys
import time

import logging

from pathlib import Path

from . import subprocess_wrapper

from .. import constants


class RoutePayloadDiskImage:

    def __init__(self, global_constants: constants.Constants) -> None:
        self.constants: constants.Constants = global_constants

        # The Windows package ships payloads as a normal directory in
        # PyInstaller's internal data location. It must never attempt to mount
        # the macOS DMG assets.
        if sys.platform == "win32":
            logging.info("Windows: using local payloads directory")
            return

        self._setup_tmp_disk_image()


    def _setup_tmp_disk_image(self) -> None:
        """
        Initialize temp directory and mount payloads.dmg
        Create overlay for patcher to write to

        Currently only applicable for GUI variant and not running from source
        """

        if self.constants.qt_variant is True and not self.constants.launcher_script:
            logging.info("Running in compiled binary, switching to tmp directory")
            self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
            logging.info("New payloads location: {0}".format(self.temp_dir.name))
            logging.info("Creating payloads directory")
            Path(self.temp_dir.name / Path("payloads")).mkdir(parents=True, exist_ok=True)
            self._unmount_active_dmgs(unmount_all_active=False)
            output = subprocess_wrapper.run_as_root(
                [
                    "/usr/bin/hdiutil", "attach", "-noverify", f"{self.constants.payload_path_dmg}",
                    "-mountpoint", Path(self.temp_dir.name / Path("payloads")),
                    "-nobrowse",
                    "-shadow", Path(self.temp_dir.name / Path("payloads_overlay")),
                    "-passphrase", "password"
                ],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT
            )
            if output.returncode == 0:
                logging.info("Mounted payloads.dmg")
                self.constants.current_path = Path(self.temp_dir.name)
                self.constants.payload_path = Path(self.temp_dir.name) / Path("payloads")
                atexit.register(self._unmount_active_dmgs, unmount_all_active=False)
            else:
                logging.info("Failed to mount payloads.dmg")
                subprocess_wrapper.log(output)


    def _unmount_active_dmgs(self, unmount_all_active: bool = True) -> None:
        """
        Unmounts disk images associated with MBT

        Finds all DMGs that are mounted, and forcefully unmount them
        If our disk image was previously mounted, we need to unmount it to use again
        This can happen if we crash during a previous secession, however 'atexit' class should hopefully avoid this

        Parameters:
            unmount_all_active (bool): If True, unmount all active DMGs, otherwise only unmount our own DMG
        """

        try:
            dmg_info = subprocess.run(["/usr/bin/hdiutil", "info", "-plist"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            if dmg_info.returncode != 0:
                subprocess_wrapper.log(dmg_info)
                return
            dmg_info = plistlib.loads(dmg_info.stdout)
        except Exception:
            logging.exception("Failed to query mounted disk images")
            return

        temp_dir_name = self.temp_dir.name if hasattr(self, "temp_dir") else None

        did_detach = False
        for variant in ["PyquickInternalResources.dmg", "Universal-Binaries.dmg", "payloads.dmg"]:
            for image in dmg_info.get("images", []):
                try:
                    if not image["image-path"].endswith(variant):
                        continue

                    if unmount_all_active is False:
                        # Check that only our personal payloads.dmg is unmounted
                        if temp_dir_name is None or "shadow-path" not in image or temp_dir_name not in image["shadow-path"]:
                            continue
                        logging.info("Unmounting personal {0}".format(variant))
                    else:
                        logging.info(f"Unmounting {variant} at: {image['system-entities'][0]['dev-entry']}")

                    self._detach_disk_image(image)
                    did_detach = True
                except Exception:
                    logging.exception("Failed to unmount {0}".format(variant))

        if unmount_all_active is False and temp_dir_name is not None:
            personal_mountpoint = Path(temp_dir_name) / Path("payloads")
            if os.path.ismount(personal_mountpoint):
                logging.error("Failed to unmount payloads.dmg at: {0}".format(personal_mountpoint))
                return
            # Only clean up the temp dir after detaching our own image (atexit path).
            # During setup this is called before mounting, so the fresh temp dir
            # (and the mountpoint just created) must be kept alive.
            if did_detach:
                self._cleanup_temp_dir()


    def _detach_disk_image(self, image: dict) -> None:
        """
        Detach a mounted disk image, verifying the mount point is removed

        Parameters:
            image (dict): hdiutil info entry for the disk image
        """

        dev_entry = image["system-entities"][0]["dev-entry"]
        mountpoint = image["system-entities"][0].get("mount-point")

        for attempt in range(1, 4):
            try:
                output = subprocess_wrapper.run_as_root(
                    ["/usr/bin/hdiutil", "detach", dev_entry, "-force"],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT
                )
                if output.returncode != 0:
                    subprocess_wrapper.log(output)
                elif mountpoint is None or not os.path.ismount(mountpoint):
                    return
            except Exception:
                logging.exception("Failed to detach {0}".format(dev_entry))

            if mountpoint is not None:
                # Fallback: detach by mount point path
                try:
                    output = subprocess_wrapper.run_as_root(
                        ["/usr/bin/hdiutil", "detach", mountpoint, "-force"],
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT
                    )
                    if output.returncode != 0:
                        subprocess_wrapper.log(output)
                    elif not os.path.ismount(mountpoint):
                        return
                except Exception:
                    logging.exception("Failed to detach {0}".format(mountpoint))

            time.sleep(0.5)

        logging.error("Failed to detach disk image {0} after {1} attempts".format(dev_entry, attempt))


    def _cleanup_temp_dir(self) -> None:
        """
        Remove the temp directory now that our disk image has been detached
        """

        try:
            self.temp_dir.cleanup()
        except Exception:
            logging.exception("Failed to clean up temp directory: {0}".format(self.temp_dir.name))