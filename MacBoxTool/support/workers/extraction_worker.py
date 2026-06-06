"""
extraction_worker.py: QThread worker for macOS installer extraction
Handles pkg extraction in background thread
"""

import logging
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QThread, Signal

from ..macos_installer_handler import InstallerCreation


class ExtractionWorker(QThread):
    """
    Background worker for extracting macOS installers

    Extracts InstallAssistant.pkg directly into payloads directory
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
        """
        Extract InstallAssistant.pkg into payloads directory.
        Result stored in self.result.
        """
        self.result = InstallerCreation(
            global_constants=self.constants
        ).install_macOS_installer(self.constants.payload_path)

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