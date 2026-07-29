"""
extraction_worker.py: QThread worker for macOS installer extraction
Handles pkg extraction in background thread
"""

import logging
import subprocess
import tempfile
import sys
from pathlib import Path
from typing import Optional

from PySide2.QtCore import QThread, Signal

from ..macos_installer_handler import InstallerCreation

if sys.platform == "win32":
    from .. import utilities_win as utilities


class ExtractionWorker(QThread):
    """
    Background worker for extracting macOS installers

    Extracts a validated macOS installer package
    Emits completion status when done
    """

    # Signals
    finished_signal = Signal(bool, str)  # success, message
    status_changed_signal = Signal(str)  # status string

    def __init__(self, pkg_path: Path, constants):
        super().__init__()
        self.pkg_path = pkg_path
        self.constants = constants
        self._is_cancelled = False
        self.installer_creator: Optional[InstallerCreation] = None
        self.result = False

    def cancel(self) -> None:
        """Cancel extraction operation"""
        self._is_cancelled = True

    def extract_installer(self) -> None:
        """Extract or install the validated package and store the result."""
        if sys.platform == "win32":
            output_dir = Path(utilities.get_downloads_dir()) / self.pkg_path.stem
            logging.info(f"Extracting pkg to: {output_dir}")
            self.result = utilities.extract_pkg(str(self.pkg_path), str(output_dir))
            return

        if self.pkg_path.name == "InstallESDDmg.pkg":
            output_path = self.pkg_path.with_name("InstallESD.dmg")
            with tempfile.TemporaryDirectory(dir=self.pkg_path.parent) as temp_dir:
                result = subprocess.run(
                    ["/usr/bin/xar", "-xf", str(self.pkg_path), "InstallESD.dmg"],
                    cwd=temp_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                if result.returncode != 0:
                    logging.error(
                        f"Failed to extract InstallESD.dmg: "
                        f"{result.stderr.decode(errors='replace')}"
                    )
                    self.result = False
                    return

                extracted_path = Path(temp_dir) / "InstallESD.dmg"
                if not extracted_path.exists():
                    self.result = False
                    return
                extracted_path.replace(output_path)

            self.result = output_path.exists()
            return

        self.result = InstallerCreation(
            global_constants=self.constants
        ).install_macOS_installer(self.pkg_path)

    def run(self) -> None:
        """Main extraction workflow"""
        try:
            logging.info("Starting installer extraction")
            self.status_changed_signal.emit("extracting")

            if self._is_cancelled:
                self.finished_signal.emit(False, "Extraction cancelled")
                return

            self.extract_installer()

            if self._is_cancelled:
                self.finished_signal.emit(False, "Extraction cancelled")
                return

            if self.result:
                logging.info("Extraction completed successfully")
                self.finished_signal.emit(True, "Extraction successful")
            else:
                logging.error("Extraction failed")
                self.finished_signal.emit(False, "Extraction failed")

        except Exception as e:
            logging.error(f"Extraction worker error: {e}")
            self.finished_signal.emit(False, f"Extraction error: {str(e)}")