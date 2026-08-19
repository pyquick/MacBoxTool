"""
validation_worker.py: QThread worker for macOS installer validation
Handles chunklist verification in background thread
"""

import logging
import subprocess
import requests
from pathlib import Path
from io import BytesIO
from typing import Optional

from PySide2.QtCore import QThread, Signal

from ..integrity_verification import ChunklistVerification, ChunklistStatus
from ..network_handler import TLS_CERTIFICATE_BUNDLE


class ValidationWorker(QThread):
    """
    Background worker for validating macOS installers

    Validates downloaded InstallAssistant.pkg against Apple's chunklist
    Emits progress updates and completion status
    """

    # Signals
    progress_signal = Signal(int, int)  # current_chunk, total_chunks
    finished_signal = Signal(bool, str)  # success, message
    status_changed_signal = Signal(str)  # status string

    def __init__(self, pkg_path: Path, chunklist_url: str = None):
        """
        Initialize validation worker

        Args:
            pkg_path: Path to installer package to validate
            chunklist_url: URL to download CNKL integrity data from
        """
        super().__init__()
        self.pkg_path = pkg_path
        self.chunklist_url = chunklist_url
        self._is_cancelled = False
        self.chunk_obj: Optional[ChunklistVerification] = None

    def cancel(self) -> None:
        """Cancel validation operation"""
        self._is_cancelled = True
        if self.chunk_obj:
            self.chunk_obj.status = ChunklistStatus.FAILURE

    def run(self) -> None:
        """Main validation workflow"""
        try:
            logging.info("Starting installer validation")
            self.status_changed_signal.emit("validating")

            if self._is_cancelled:
                self.finished_signal.emit(False, "Validation cancelled")
                return

            if not self.chunklist_url:
                if self._verify_package_signature():
                    logging.info("Apple package signature validation completed successfully")
                    self.finished_signal.emit(True, "Validation successful")
                elif self._is_cancelled:
                    self.finished_signal.emit(False, "Validation cancelled")
                else:
                    self.finished_signal.emit(False, "Apple package signature validation failed")
                return

            # Download chunklist
            chunklist_stream = self._download_chunklist()
            if not chunklist_stream:
                error_msg = f"Failed to download chunklist from {self.chunklist_url}"
                logging.error(error_msg)
                self.finished_signal.emit(False, error_msg)
                return

            if self._is_cancelled:
                self.finished_signal.emit(False, "Validation cancelled")
                return

            # Create chunklist verification object and parse first to get total_chunks
            self.chunk_obj = ChunklistVerification(self.pkg_path, chunklist_stream)

            if not self.chunk_obj.parse():
                self.finished_signal.emit(False, "Failed to parse chunklist")
                return

            # Emit total chunks for progress bar (available after parsing)
            self.progress_signal.emit(0, self.chunk_obj.total_chunks)

            # Set progress callback for real-time updates during validation
            def _on_verify_progress(current: int, total: int):
                if self._is_cancelled:
                    self.chunk_obj.status = ChunklistStatus.FAILURE
                self.progress_signal.emit(current, total)

            self.chunk_obj.set_progress_callback(_on_verify_progress)

            # Start verification (synchronous, progress emitted via callback)
            self.chunk_obj.verify()

            # Check final status
            if self.chunk_obj.status == ChunklistStatus.FAILURE:
                error_msg = f"Hash mismatch on chunk {self.chunk_obj.current_chunk}"
                logging.error(error_msg)
                self.finished_signal.emit(False, error_msg)
            elif self.chunk_obj.status == ChunklistStatus.SUCCESS:
                logging.info("Validation completed successfully")
                self.finished_signal.emit(True, "Validation successful")
            else:
                self.finished_signal.emit(False, "Unknown validation status")

        except Exception as e:
            logging.error(f"Validation worker error: {e}")
            self.finished_signal.emit(False, f"Validation error: {str(e)}")

    def _verify_package_signature(self) -> bool:
        """Validate the XAR contents and Apple signing chain for a package."""
        if self._is_cancelled:
            return False

        result = subprocess.run(
            ["/usr/sbin/pkgutil", "--check-signature", str(self.pkg_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        if result.returncode != 0:
            logging.error(
                "Package signature validation failed: "
                f"{result.stdout.decode(errors='replace').strip()}"
            )
            return False
        return True

    def _download_chunklist(self) -> Optional[BytesIO]:
        """
        Download chunklist from Apple

        Returns:
            BytesIO with chunklist content if successful, None otherwise
        """
        try:
            logging.info(f"Downloading chunklist from: {self.chunklist_url}")

            response = requests.get(
                self.chunklist_url,
                timeout=30,
                stream=True,
                verify=TLS_CERTIFICATE_BUNDLE,
            )

            if response.status_code != 200:
                logging.error(f"Failed to download chunklist: HTTP {response.status_code}")
                logging.error(f"Response headers: {dict(response.headers)}")
                return None

            # Read content into BytesIO
            chunklist_content = BytesIO()
            chunklist_content.write(response.content)
            chunklist_content.seek(0)

            content_size = len(response.content)
            logging.info(f"Chunklist downloaded successfully: {content_size} bytes")

            # Validate chunklist content
            if content_size == 0:
                logging.error("Downloaded chunklist is empty")
                return None

            if content_size > 10 * 1024 * 1024:  # 10MB limit
                logging.warning(f"Chunklist size unusually large: {content_size} bytes")

            return chunklist_content

        except requests.exceptions.Timeout:
            logging.error("Chunklist download timed out")
            return None
        except requests.exceptions.ConnectionError as e:
            logging.error(f"Chunklist connection error: {e}")
            return None
        except Exception as e:
            logging.error(f"Error downloading chunklist: {e}")
            return None