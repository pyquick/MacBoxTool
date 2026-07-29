"""
commit_info.py: Parse commit metadata from Windows bundles or macOS Info.plist.
"""

import json
import plistlib
import sys

from pathlib import Path


class ParseCommitInfo:

    def __init__(self, binary_path: str) -> None:
        """
        Parameters:
            binary_path (str): Path to binary
        """

        self.binary_path = str(binary_path)
        self.metadata_path = self._convert_binary_path_to_metadata_path()
        self.plist_path = self._convert_binary_path_to_plist_path()


    def _convert_binary_path_to_metadata_path(self) -> Path | None:
        """Resolve commit metadata packaged with a frozen Windows executable."""
        if sys.platform != "win32" or not getattr(sys, "frozen", False):
            return None

        metadata_path = Path(getattr(sys, "_MEIPASS", Path(self.binary_path).parent)) / "commit_info.json"
        return metadata_path if metadata_path.is_file() else None

    def _convert_binary_path_to_plist_path(self) -> str:
        """
        Resolve Info.plist path from binary path
        """

        if Path(self.binary_path).exists():
            plist_path = self.binary_path.replace("MacOS/MacBoxTool", "Info.plist")
            if Path(plist_path).exists() and plist_path.endswith(".plist"):
                return plist_path
        return None


    def generate_commit_info(self) -> tuple:
        """
        Generate commit info from Info.plist

        Returns:
            tuple: (Branch, Commit Date, Commit URL)
        """

        if self.metadata_path:
            try:
                metadata = json.loads(self.metadata_path.read_text(encoding="utf-8"))
                return (
                    metadata["Branch"],
                    metadata["Commit Date"],
                    metadata["Commit URL"],
                )
            except (OSError, ValueError, KeyError, TypeError):
                pass

        if self.plist_path:
            plist_info = plistlib.load(Path(self.plist_path).open("rb"))
            if "Github" in plist_info:
                return (
                    plist_info["Github"]["Branch"],
                    plist_info["Github"]["Commit Date"],
                    plist_info["Github"]["Commit URL"],
                )
        return (
            "Running from source",
            "Not applicable",
            "N/A",
        )