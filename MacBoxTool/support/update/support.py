"""
support.py: GitHub release and nightly manifest helpers for updates.
"""
import json
import logging
import platform

import requests
from packaging import version

from ... import constants as constants
from ..on_nightly import CheckNightly


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
        self.system_darwin_version = int(platform.release().split(".")[0])
        self.check_url = "https://pyquick.github.io/MacBoxTool/manifest.json"
        self.branch = "main" if self.system_darwin_version >= 20 else "PySide2"
        self.qt_flavor = "PySide6" if self.branch == "main" else "PySide2"
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

    @staticmethod
    def _decode_json_response(response: requests.Response) -> dict:
        """Decode API JSON, tolerating trailing commas added by network proxies."""
        payload = response.text
        try:
            return json.loads(payload)
        except json.JSONDecodeError as error:
            cleaned_payload = []
            in_string = False
            escaped = False

            for index, character in enumerate(payload):
                if in_string:
                    cleaned_payload.append(character)
                    if escaped:
                        escaped = False
                    elif character == "\\":
                        escaped = True
                    elif character == '"':
                        in_string = False
                    continue

                if character == '"':
                    in_string = True
                    cleaned_payload.append(character)
                    continue

                if character == ",":
                    next_index = index + 1
                    while next_index < len(payload) and payload[next_index].isspace():
                        next_index += 1
                    if next_index < len(payload) and payload[next_index] in "}]":
                        continue

                cleaned_payload.append(character)

            cleaned_payload = "".join(cleaned_payload)
            if cleaned_payload == payload:
                raise RuntimeError(f"Invalid JSON response: {error}") from error

            logging.warning("[Update] Retrying JSON parsing after removing trailing commas")
            try:
                return json.loads(cleaned_payload)
            except json.JSONDecodeError as cleaned_error:
                raise RuntimeError(f"Invalid JSON response: {cleaned_error}") from cleaned_error

    def find_latest_release_stable(self) -> None:
        """Fetch and validate the latest stable GitHub release payload."""
        
        logging.info(f"[Update] Requesting latest release: {self.url}")
        response = requests.get(self.url, headers=self._github_headers(), verify=False, timeout=20)
        response.raise_for_status()
        
        self.information: dict = self._decode_json_response(response)
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
            artifact = "MacBoxTool-PySide2-x86_64.pkg"
            if self.qt_flavor == "PySide6":
                artifact = "MacBoxTool-x86_64.pkg"
            return ["build-app-qt-intel", artifact]
        if platform.machine() == "arm64":
            artifact = "MacBoxTool-PySide2-arm64.pkg"
            if self.qt_flavor == "PySide6":
                artifact = "MacBoxTool-arm64.pkg"
            return ["build-app-qt-arm", artifact]
        raise RuntimeError(f"Unsupported architecture: {platform.machine()}")

    def find_and_compare_latest_release_nightly(self) -> list[bool, str, str, str]:
        """Check the nightly manifest and return the nightly download URL."""
        workflow, artifact = self.arch_check()
        self.nightly_url = f"https://nightly.link/pyquick/MacBoxTool/workflows/{workflow}/main/{artifact}.zip"

        response = requests.get(self.check_url, verify=False, timeout=20)
        response.raise_for_status()
        manifest: dict = self._decode_json_response(response)

        remote_build = str(manifest["nightly_latest"][self.branch]["build"])
        local_build = version.parse(str(self.constants.nightly_build))
        remote_build_version = version.parse(remote_build)
        
        if remote_build_version > local_build:
            return True, self.nightly_url, artifact, remote_build

        return False, "", "", ""
    
    def is_higher_stable_is_coming(self) -> bool:
        """
        Check stable is higher than nightly.
        Manifest.json is always higher than stable (or same as stable)
        """
        response = requests.get(self.check_url, verify=False, timeout=20)
        response.raise_for_status()
        manifest: dict = self._decode_json_response(response)

        local_version = version.parse(str(self.constants.macboxtool_version))
        local_build = version.parse(str(self.constants.nightly_build))

        manifest_version_stable = version.parse(str(manifest["stable_latest"][self.branch]["version"]))
        manifest_build_stable = version.parse(str(manifest["stable_latest"][self.branch]["build"]))

        return manifest_version_stable >= local_version or manifest_build_stable >= local_build


    def compare_tags(self) -> bool:
        """Return True when the remote stable release is newer than local."""
        response = requests.get(self.check_url, verify=False, timeout=20)
        # Only stable can use it, nightly us is_higher_stable_is_coming()
        if CheckNightly(self.constants).check(): return False
        response.raise_for_status()
        manifest: dict = self._decode_json_response(response)

        manifest_version_stable = version.parse(str(manifest["stable_latest"][self.branch]["version"]))
        manifest_build_stable = version.parse(str(manifest["stable_latest"][self.branch]["build"])) # manifest

        local_version = version.parse(str(self.constants.macboxtool_version))
        local_build = version.parse(str(self.constants.nightly_build))

        return manifest_version_stable > local_version or manifest_build_stable > local_build
        

    def update_log(self) -> str:
        """Return the latest release changelog."""
        return self.changelog

    def update_version(self) -> str:
        """Return the latest release version tag."""
        return self.latest_tag_name

    def assets_decode(self) -> dict:
        """Select the installer asset for the current architecture and Qt flavor."""
        architecture = platform.machine()
        candidates = []
        for asset in self.assets:
            name = asset["name"]
            lower_name = name.lower()
            if "uninstaller" in lower_name or "autopkg" in lower_name:
                continue
            if architecture not in name:
                continue

            candidates.append({
                "name": name,
                "arch": architecture,
                "download_url": asset["browser_download_url"],
            })

        flavor_candidates = [
            asset for asset in candidates
            if ("pyside2" in asset["name"].lower()) == (self.qt_flavor == "PySide2")
        ]
        if flavor_candidates:
            candidates = flavor_candidates
        elif candidates:
            logging.warning(
                "[Update] No %s asset found for %s; falling back to same-architecture asset",
                self.qt_flavor,
                architecture,
            )

        candidates.sort(key=lambda asset: asset["name"])
        logging.info(f"[Update] Matched release assets: {candidates}")
        if not candidates:
            raise RuntimeError(
                f"No {self.qt_flavor} installer asset found for {architecture}"
            )
        return candidates[0]
