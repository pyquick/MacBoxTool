"""
install_update.py: Install downloaded MacBoxTool update packages.
"""
import logging
import subprocess
import zipfile
from pathlib import Path

from ... import constants
from .. import subprocess_wrapper


class InstallUpdate:
    """Install a downloaded stable package or nightly archive."""

    def __init__(self, pkg_download_path: Path, constants: constants.Constants):
        """Store the downloaded package path and constants."""
        self.pkg_download_path = Path(pkg_download_path)
        self.constants = constants

    def extract_zip_files(self):
        """Extract nightly archives before installation."""
        if self.constants.allow_nightly_check and not self.constants.stable_available:
            with zipfile.ZipFile(self.pkg_download_path, "r") as archive:
                archive.extractall(self.constants.payload_path)

    def install_update(self) -> bool:
        """Install the downloaded update with the privileged installer helper."""
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
