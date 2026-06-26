"""
install_update.py: Install MacBoxTool update package.
"""

import logging
import subprocess
from pathlib import Path

from .. import subprocess_wrapper


class InstallUpdate:
    """Install downloaded PKG update."""

    def __init__(self, pkg_download_path: Path):
        self.pkg_download_path = Path(pkg_download_path)

    def install_update(self) -> bool:
        logging.info(f"[Update] Installing update: {self.pkg_download_path}")
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
