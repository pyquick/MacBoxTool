"""
fetch_update.py: Download MacBoxTool update package.
"""

import logging
from pathlib import Path

from ...constants import Constants
from ..network_handler import DownloadObject, DownloadWorker
from .support import VisitGithubAPI


class FetchUpdate(DownloadWorker):
    """Download update package to payload path."""

    def __init__(self, constants: Constants):
        self.constants = constants
        self.asset = VisitGithubAPI(constants=self.constants).assets_decode()
        self.assets_nightly = VisitGithubAPI(self.constants).find_and_compare_latest_release_nightly()
        
        if self.constants.allow_nightly_check and not self.constants.stable_available:
            self.pkg_download_path = self.constants.payload_path / f"{self.assets_nightly[2]}.zip"
            download = DownloadObject(
                self.assets_nightly[1],
                str(self.constants.payload_path),
                f"{self.assets_nightly[2]}.zip",
            )
        else:
            self.pkg_download_path = self.constants.payload_path / self.asset["name"]
            download = DownloadObject(
                self.asset["download_url"],
                str(self.constants.payload_path),
                self.asset["name"],
            )
        super().__init__(download, self.constants)

    def run(self):
        if not self.constants.allow_nightly_check:
            logging.info(f"[Update] Downloading update: {self.asset['name']}")
        else:
            logging.info(f"[Update] Downloading update: {self.assets_nightly[2]}.zip")
        self.constants.payload_path.mkdir(parents=True, exist_ok=True)
        super().run()

    def update_package_path(self) -> Path:
        return self.pkg_download_path
