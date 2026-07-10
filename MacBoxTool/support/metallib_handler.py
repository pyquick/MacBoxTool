"""
metallib_handler.py: Module for resolving MetallibSupportPkg for root patching
"""

import logging
import subprocess

from pathlib import Path

from .. import constants
from . import network_handler, subprocess_wrapper


METALLIB_ASSET_LIST: list = None


class MetalLibraryObject:
    """
    Resolve and install MetallibSupportPkg for the current macOS build.
    """

    def __init__(self, global_constants: constants.Constants, host_build: str, host_version: str) -> None:
        self.constants = global_constants
        self.host_build = host_build
        self.host_version = host_version

        self.metallib_url = ""
        self.metallib_url_build = ""
        self.metallib_url_version = ""
        self.metallib_installed_path = ""
        self.metallib_already_installed = False
        self.metallib_pkg_path = str(self.constants.metallib_download_path)

        self.success = False
        self.error_msg = ""

        self._get_latest_metallib()

    def _get_remote_metallibs(self) -> list:
        global METALLIB_ASSET_LIST

        logging.info("Pulling MetallibSupportPkg list from API")
        if METALLIB_ASSET_LIST:
            return METALLIB_ASSET_LIST

        response = network_handler.NetworkUtilities(self.constants).get(
            self.constants.metallib_api_link,
            timeout=5,
        )
        if response.status_code != 200:
            logging.info("Could not fetch MetallibSupportPkg list")
            return None

        METALLIB_ASSET_LIST = response.json()
        return METALLIB_ASSET_LIST

    def _find_metallib_source(self) -> str:
        candidates = [
            Path("/Library/Application Support/Dortania/MetallibSupportPkg"),
            Path("/Library/Application Support/MetallibSupportPkg"),
            Path("/Library/Application Support/OpenCore-Patcher/MetallibSupportPkg"),
            Path("/Library/Application Support/MacBoxTool/MetallibSupportPkg"),
        ]
        markers = [
            Path("System/iOSSupport/System/Library/PrivateFrameworks/VFX.framework/Versions/A/Resources/default.metallib"),
            Path("System/Library/Video/Plug-Ins/AV1DecoderSW.bundle/Contents/Resources/default.metallib"),
        ]

        for candidate in candidates:
            if any((candidate / marker).exists() for marker in markers):
                return str(candidate)
            if not candidate.exists():
                continue
            for system_dir in candidate.rglob("System"):
                if any((system_dir.parent / marker).exists() for marker in markers):
                    return str(system_dir.parent)
        return ""

    def _get_latest_metallib(self) -> None:
        source_path = self._find_metallib_source()
        if source_path:
            logging.info("MetallibSupportPkg already installed, skipping download")
            self.metallib_installed_path = source_path
            self.metallib_already_installed = True
            self.success = True
            return

        if Path(self.metallib_pkg_path).exists():
            logging.info("MetallibSupportPkg package already downloaded")
            self.success = True
            return

        remote_metallibs = self._get_remote_metallibs()
        if not remote_metallibs:
            self.error_msg = "Could not retrieve MetallibSupportPkg catalog"
            logging.warning(self.error_msg)
            return

        selected = None
        for metallib in remote_metallibs:
            if metallib.get("build") == self.host_build:
                selected = metallib
                break

        if selected is None:
            host_prefix = self.host_build[:3]
            compatible = [item for item in remote_metallibs if str(item.get("build", "")).startswith(host_prefix)]
            if compatible:
                selected = compatible[0]

        if selected is None:
            selected = remote_metallibs[0]
            logging.info("No exact MetallibSupportPkg match found, using latest available")

        self.metallib_url = selected.get("url", "")
        self.metallib_url_build = selected.get("build", "")
        self.metallib_url_version = selected.get("version", "")

        if not self.metallib_url:
            self.error_msg = "MetallibSupportPkg catalog entry does not include a URL"
            logging.error(self.error_msg)
            return

        logging.info("Following MetallibSupportPkg is recommended:")
        logging.info("- Build: {0}".format(self.metallib_url_build))
        logging.info("- Version: {0}".format(self.metallib_url_version))
        logging.info("- URL: {0}".format(self.metallib_url))
        self.success = True

    def retrieve_download(self) -> network_handler.DownloadObject:
        self.success = False
        self.error_msg = ""

        if self.metallib_already_installed:
            logging.info("No download required, MetallibSupportPkg already installed")
            self.success = True
            return None

        download_path = Path(self.metallib_pkg_path)
        if download_path.exists():
            logging.info("No download required, MetallibSupportPkg package already downloaded")
            self.success = True
            return None

        if not self.metallib_url:
            self.error_msg = "Could not retrieve MetallibSupportPkg catalog, no package to download"
            logging.error(self.error_msg)
            return None

        download_path = Path(self.metallib_pkg_path)
        self.success = True
        return network_handler.DownloadObject(self.metallib_url, str(download_path.parent), download_path.name)

    def install_metallib(self) -> bool:
        source_path = self._find_metallib_source()
        if source_path:
            self.metallib_already_installed = True
            self.metallib_installed_path = source_path
            self.success = True
            return True

        pkg_path = Path(self.metallib_pkg_path)
        if not pkg_path.exists():
            self.error_msg = "MetallibSupportPkg does not exist: {0}".format(pkg_path)
            logging.error(self.error_msg)
            return False

        logging.info("Installing MetallibSupportPkg: {0}".format(pkg_path.name))
        result = subprocess_wrapper.run_as_root(
            ["/usr/sbin/installer", "-pkg", str(pkg_path), "-target", "/"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        if result.returncode != 0:
            logging.info("Failed to install MetallibSupportPkg:")
            subprocess_wrapper.log(result)
            self.error_msg = "Failed to install MetallibSupportPkg"
            return False

        source_path = self._find_metallib_source()
        if not source_path:
            self.error_msg = "MetallibSupportPkg installed but source files were not found"
            logging.error(self.error_msg)
            return False

        self.metallib_already_installed = True
        self.metallib_installed_path = source_path
        self.success = True
        return True
