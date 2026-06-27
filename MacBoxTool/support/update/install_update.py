"""
install_update.py: Install MacBoxTool update package.
"""

import logging
import subprocess
from pathlib import Path
import os
from ... import constants
from .. import subprocess_wrapper
import zipfile

class InstallUpdate:
    """Install downloaded PKG update."""

    def __init__(self, pkg_download_path: Path, constants:constants.Constants):
        self.pkg_download_path = Path(pkg_download_path)
        self.constants=constants

    def extract_zip_files(self):
        if self.constants.allow_nightly_check and not self.constants.stable_available:
            with zipfile.ZipFile(self.pkg_download_path,"r") as ext:
                ext.extractall(self.constants.payload_path)
        return

    def install_update(self) -> bool:
        logging.info(f"[Update] Installing update: {self.pkg_download_path}")
        self.extract_zip_files()
        result = subprocess_wrapper.run_as_root(
            ["/usr/sbin/installer", "-pkg", str(self.pkg_download_path), "-target", "/"],
            capture_output=True,
        )
        if result.returncode == 0:
            logging.info("[Update] Update installed successfully")
            return True

        stderr = result.stderr.decode("utf-8", errors="ignore") if result.stderr else ""
        if "User cancelled" in stderr:
            logging.info("[Update] User cancelled update")
        else:
            logging.critical("[Update] Failed to install update")
            subprocess_wrapper.log(result)
            logging.error("[Update] Failed to install update, opening PKG manually")
            subprocess.run(["/usr/bin/open", str(self.pkg_download_path)])
        return False
