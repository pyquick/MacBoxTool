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
        self.pkg_download_path = self.constants.payload_path / self.asset["name"]
        download = DownloadObject(
            self.asset["download_url"],
            str(self.constants.payload_path),
            self.asset["name"],
        )
        super().__init__(download)

    def run(self):
        logging.info(f"[Update] Downloading update: {self.asset['name']}")
        self.constants.payload_path.mkdir(parents=True, exist_ok=True)
        super().run()

    def update_package_path(self) -> Path:
        return self.pkg_download_path
