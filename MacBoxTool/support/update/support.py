"""
support.py: GitHub release and nightly manifest helpers for updates.
"""
import logging
import platform

import requests
from packaging import version

from ... import constants as constants


class VisitGithubAPI:
    """Read update metadata from GitHub releases and the nightly manifest."""

    def __init__(
        self,
        constants: constants.Constants,
        repo_name: str = "MacBoxTool",
        token: str = "",
        user: str = "pyquick",
        fetch_latest: bool = True,
    ):
        """Store API options and optionally fetch the latest release."""
        self.constants: constants.Constants = constants
        self.token: str = token or getattr(self.constants, "github_token", "") or ""
        self.url = f"https://api.github.com/repos/{user}/{repo_name}/releases/latest"

        if fetch_latest:
            self.find_latest_release_stable()

    def _github_headers(self) -> dict:
        """Build authenticated GitHub API headers when a token is configured."""
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def find_latest_release_stable(self) -> None:
        """Fetch and validate the latest stable GitHub release payload."""
        logging.info(f"[Update] Requesting latest release: {self.url}")
        response = requests.get(self.url, headers=self._github_headers(), verify=False, timeout=20)
        response.raise_for_status()

        self.information: dict = response.json()
        for key in ("tag_name", "assets", "target_commitish", "name", "published_at", "body"):
            if key not in self.information:
                raise KeyError(f"GitHub latest release response missing '{key}'")

        self.latest_tag_name: str = self.information["tag_name"]
        self.tag_name_list: list = self.latest_tag_name.split(".")
        self.assets: list = self.information["assets"]
        self.target_branch: str = self.information["target_commitish"]
        self.release_name: str = self.information["name"]
        self.publish_time: str = self.information["published_at"]
        self.changelog: str = self.information["body"]

    def arch_check(self) -> list:
        """Return the workflow and artifact names for the current architecture."""
        if platform.machine() == "x86_64":
            return ["build-app-qt-intel", "MacBoxTool-x86_64.pkg"]
        if platform.machine() == "arm64":
            return ["build-app-qt-arm", "MacBoxTool-arm64.pkg"]
        raise RuntimeError(f"Unsupported architecture: {platform.machine()}")

    def find_and_compare_latest_release_nightly(self) -> list[bool, str, str]:
        """Check the nightly manifest and return the nightly download URL."""
        workflow, artifact = self.arch_check()
        self.nightly_url = f"https://nightly.link/pyquick/MacBoxTool/workflows/{workflow}/main/{artifact}.zip"
        self.check_url = "https://pyquick.github.io/MacBoxTool/manifest.json"

        response = requests.get(self.check_url, verify=False, timeout=20)
        response.raise_for_status()
        manifest: dict = response.json()
        if "build" not in manifest:
            raise KeyError("nightly manifest missing 'build'")

        local_build = version.parse(str(self.constants.nightly_build))
        remote_build = version.parse(str(manifest["build"]))
        if remote_build > local_build:
            return True, self.nightly_url, artifact
        return False, "", ""

    def compare_tags(self) -> bool:
        """Return True when the remote stable release is newer than local."""
        local_version = version.parse(str(self.constants.macboxtool_version))
        remote_version = version.parse(str(self.latest_tag_name))
        return remote_version > local_version

    def update_log(self) -> str:
        """Return the latest release changelog."""
        return self.changelog

    def update_version(self) -> str:
        """Return the latest release version tag."""
        return self.latest_tag_name

    def assets_decode(self) -> dict:
        """Select the installer asset that matches the current architecture."""
        datas: list = []
        for asset in self.assets:
            name = asset["name"]
            if "Uninstaller" in name or "uninstaller" in name:
                continue

            if "x86_64" in name and "x86_64" in platform.machine():
                arch = "x86_64"
            elif "arm64" in name and "arm64" in platform.machine():
                arch = "arm64"
            else:
                continue

            datas.append({
                "name": name,
                "arch": arch,
                "download_url": asset["browser_download_url"],
            })

        logging.info(f"[Update] Matched release assets: {datas}")
        if not datas:
            raise RuntimeError("No matching installer asset found for current architecture")
        return datas[0]
