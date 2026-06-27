"""
fetch_update.py: Download MacBoxTool update packages.
"""
import logging
from pathlib import Path

from ...constants import Constants
from ..network_handler import DownloadObject, DownloadWorker
from .support import VisitGithubAPI


class FetchUpdate(DownloadWorker):
    """Prepare and download the update asset selected by the checker."""

    def __init__(self, constants: Constants, update_result: dict = None):
        """Create a download worker for the selected update asset."""
        self.constants = constants
        update_result = update_result or {}

        # Prefer the asset selected during check_for_update to avoid duplicate
        # network requests when the user clicks Download.
        if update_result.get("download_url") and update_result.get("download_name"):
            download = self._download_from_result(update_result)
        elif self.constants.allow_nightly_check and not self.constants.stable_available:
            download = self._download_from_nightly_manifest()
        else:
            download = self._download_from_latest_release()

        super().__init__(download, self.constants)

    def _download_from_result(self, update_result: dict) -> DownloadObject:
        """Build a download object from check_update metadata."""
        self.pkg_download_path = self.constants.payload_path / update_result["download_name"]
        return DownloadObject(
            update_result["download_url"],
            str(self.constants.payload_path),
            update_result["download_name"],
        )

    def _download_from_nightly_manifest(self) -> DownloadObject:
        """Build a download object from the nightly manifest."""
        github_api = VisitGithubAPI(constants=self.constants, fetch_latest=False)
        nightly = github_api.find_and_compare_latest_release_nightly()
        if not nightly[0]:
            raise RuntimeError("No newer nightly build is available")

        self.pkg_download_path = self.constants.payload_path / f"{nightly[2]}.zip"
        return DownloadObject(
            nightly[1],
            str(self.constants.payload_path),
            f"{nightly[2]}.zip",
        )

    def _download_from_latest_release(self) -> DownloadObject:
        """Build a download object from the latest stable release."""
        github_api = VisitGithubAPI(constants=self.constants)
        asset = github_api.assets_decode()
        self.pkg_download_path = self.constants.payload_path / asset["name"]
        return DownloadObject(
            asset["download_url"],
            str(self.constants.payload_path),
            asset["name"],
        )

    def run(self):
        """Create the payload folder and start the download."""
        logging.info(f"[Update] Downloading update: {self.pkg_download_path.name}")
        self.constants.payload_path.mkdir(parents=True, exist_ok=True)
        super().run()

    def update_package_path(self) -> Path:
        """Return the target path for the downloaded update."""
        return self.pkg_download_path
