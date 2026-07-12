"""
gui_task.py: Download Task page - displays download tasks from other services
"""

from ..include import *
from .gui_support import DefGUI
from .. import constants
from .gui_download import DownloadCard
from ..support.network_handler import (
    DownloadObject, DownloadWorker, DownloadStatus,
    NetworkUtilities, DownloadHistory
)
from ..support.workers.validation_worker import ValidationWorker
from ..support.workers.extraction_worker import ExtractionWorker


class NetworkCheckWorker(QThread):
    """Worker thread for checking network connectivity."""
    finished_signal = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_cancelled = False

    def run(self):
        try:
            result = NetworkUtilities().check_network()
            if not self._is_cancelled:
                self.finished_signal.emit(result)
        except Exception as e:
            logging.warning(f"Network check error: {e}")
            if not self._is_cancelled:
                self.finished_signal.emit(False)

    def cancel(self):
        self._is_cancelled = True


# Global task manager for registering downloads from other services
class TaskManager:
    """Global task manager for download tasks"""
    _instance = None
    _downloads: list[DownloadObject] = []
    _workers: dict[int, DownloadWorker] = {}
    _validation_workers: dict[int, ValidationWorker] = {}
    _extraction_workers: dict[int, ExtractionWorker] = {}
    _icons: dict[int, object] = {}  # download id -> icon for DownloadCard
    _shutting_down = False
    aconstants: Constants = None



    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def set_constants(cls, global_constants: Constants):
        """Set the shared constants object used by download follow-up workers."""
        cls.aconstants = global_constants

    @classmethod
    def start_download(cls, download: DownloadObject, icon=None) -> DownloadWorker:
        """Start a download and register it for display in TaskInterface.

        Usage:
            download = DownloadObject(url, save_path, filename)
            TaskManager.start_download(download, icon="/path/to/icon.png")
        """
        cls._shutting_down = False
        cls.register_download(download)
        if icon is not None:
            cls._icons[id(download)] = icon
            download.icon_path = icon

        worker = DownloadWorker(download, cls.aconstants)
        cls._workers[id(download)] = worker

        worker.finished_signal.connect(
            lambda success, msg: cls._on_download_finished(download, success, msg)
        )
        worker.start()
        return worker


    @classmethod
    def _stop_worker(cls, worker, timeout: int = 5000) -> bool:
        """Cancel and wait for a QThread worker before it can be destroyed."""
        if not worker:
            return True

        try:
            if hasattr(worker, "cancel"):
                worker.cancel()
            if hasattr(worker, "requestInterruption"):
                worker.requestInterruption()
            if worker.isRunning() and not worker.wait(timeout):
                logging.warning(f"Worker {worker.__class__.__name__} did not stop in {timeout}ms; terminating")
                worker.terminate()
                worker.wait(1000)
            if not worker.isRunning():
                worker.deleteLater()
                return True
        except RuntimeError:
            return True
        except Exception as e:
            logging.warning(f"Failed to stop worker {worker}: {e}")

        return False

    @classmethod
    def cancel_download(cls, download: DownloadObject):
        """Cancel active download, validation, and extraction workers for a download."""
        worker = cls._workers.pop(id(download), None)
        cls._stop_worker(worker, 5000)

        validation_worker = cls._validation_workers.pop(id(download), None)
        cls._stop_worker(validation_worker, 5000)

        extraction_worker = cls._extraction_workers.pop(id(download), None)
        cls._stop_worker(extraction_worker, 5000)

    @classmethod
    def shutdown_all(cls):
        """Stop all task workers before application shutdown."""
        cls._shutting_down = True
        for download in cls.get_downloads():
            cls.cancel_download(download)

        for worker in list(cls._workers.values()):
            cls._stop_worker(worker, 5000)
        for worker in list(cls._validation_workers.values()):
            cls._stop_worker(worker, 5000)
        for worker in list(cls._extraction_workers.values()):
            cls._stop_worker(worker, 5000)

        cls._workers.clear()
        cls._validation_workers.clear()
        cls._extraction_workers.clear()
        cls._icons.clear()

    @classmethod
    def pause_download(cls, download: DownloadObject):
        """Pause an active download"""
        worker = cls._workers.get(id(download))
        if worker and worker.isRunning():
            worker.pause()

    @classmethod
    def resume_download(cls, download: DownloadObject):
        """Resume a paused download"""
        worker = cls._workers.get(id(download))
        if worker:
            worker.resume()

    @classmethod
    def _on_download_finished(cls, download: DownloadObject, success: bool, message: str):
        """Handle download completion — auto-start validation if successful"""
        worker = cls._workers.pop(id(download), None)

        # 清理 worker
        if worker:
            worker.deleteLater()
        cls._icons.pop(id(download), None)

        if success and not cls._shutting_down:
            logging.info(f"Download completed: {download.filename}")
            # Automatically start validation for modern macOS installers
            if download.filename == "InstallAssistant.pkg":
                # Use the stored chunklist URL from download object
                chunklist_url = download.chunklist_url
                if not chunklist_url:
                    logging.error(f"No chunklist URL available for {download.filename}")
                    download.status = DownloadStatus.FAILED
                    download.error_message = "No chunklist URL available"
                else:
                    # Switch to VALIDATING so DownloadCard shows indeterminate progress bar
                    download.status = DownloadStatus.VALIDATING
                    cls.start_validation(download, chunklist_url)
            else:
                download.status = DownloadStatus.COMPLETED
        else:
            logging.warning(f"Download failed: {download.filename} - {message}")

    @classmethod
    def start_validation(cls, download: DownloadObject, chunklist_url: str) -> ValidationWorker:
        """Start validation worker for downloaded installer

        Args:
            download: DownloadObject with completed installer
            chunklist_url: URL to download chunklist from

        Returns:
            ValidationWorker instance
        """
        from pathlib import Path

        pkg_path = Path(download.save_path) / download.filename
        worker = ValidationWorker(pkg_path, chunklist_url)
        cls._validation_workers[id(download)] = worker

        worker.finished_signal.connect(
            lambda success, msg: cls._on_validation_finished(download, success, msg)
        )
        worker.progress_signal.connect(
            lambda current, total: cls._on_validation_progress(download, current, total)
        )
        worker.status_changed_signal.connect(
            lambda status: cls._on_status_changed(download, status)
        )
        worker.start()
        return worker

    @classmethod
    def _on_validation_progress(cls, download: DownloadObject, current_chunk: int, total_chunks: int):
        """Handle validation progress updates"""
        # Update download object with chunk progress
        download.current_validation_chunk = current_chunk
        download.total_validation_chunks = total_chunks

    @classmethod
    def _on_status_changed(cls, download: DownloadObject, status: str):
        """Handle status changes during validation/extraction"""
        # Map string status to DownloadStatus enum
        status_map = {
            "validating": DownloadStatus.VALIDATING,
            "extracting": DownloadStatus.EXTRACTING,
            "validation_complete": DownloadStatus.COMPLETED,
        }
        new_status = status_map.get(status)
        if new_status and download.status != new_status:
            download.status = new_status

    @classmethod
    def _on_validation_finished(cls, download: DownloadObject, success: bool, message: str):
        """Handle validation completion - auto-start extraction on success"""
        worker = cls._validation_workers.pop(id(download), None)

        if worker:
            worker.deleteLater()

        if success and not cls._shutting_down:
            logging.info(f"Validation completed: {download.filename}")
            # Automatically start extraction
            download.status = DownloadStatus.EXTRACTING
            from pathlib import Path
            pkg_path = Path(download.save_path) / download.filename
            cls.start_extraction(download, pkg_path)
        else:
            logging.error(f"Validation failed: {download.filename} - {message}")
            download.status = DownloadStatus.FAILED
            # Show error dialog in GUI (handled by DownloadCard)

    @classmethod
    def start_extraction(cls, download: DownloadObject, pkg_path: Path) -> ExtractionWorker:
        """Start extraction worker for validated installer

        Args:
            download: DownloadObject with validated installer
            pkg_path: Path to InstallAssistant.pkg

        Returns:
            ExtractionWorker instance
        """
        from pathlib import Path

        worker = ExtractionWorker(pkg_path, cls.aconstants or Constants())
        cls._extraction_workers[id(download)] = worker

        worker.finished_signal.connect(
            lambda success, msg: cls._on_extraction_finished(download, success, msg)
        )
        worker.status_changed_signal.connect(
            lambda status: cls._on_status_changed(download, status)
        )
        worker.start()
        return worker

    @classmethod
    def _on_extraction_finished(cls, download: DownloadObject, success: bool, message: str):
        """Handle extraction completion"""
        worker = cls._extraction_workers.pop(id(download), None)

        if worker:
            worker.deleteLater()

        if success:
            logging.info(f"Extraction completed: {download.filename}")
            download.status = DownloadStatus.COMPLETED
        else:
            logging.error(f"Extraction failed: {download.filename} - {message}")
            download.status = DownloadStatus.FAILED


    @classmethod
    def register_download(cls, download: DownloadObject):
        """Register a download task to be displayed"""
        if download not in cls._downloads:
            cls._downloads.append(download)

    @classmethod
    def unregister_download(cls, download: DownloadObject):
        """Unregister a download task"""
        if download in cls._downloads:
            cls._downloads.remove(download)
        cls._workers.pop(id(download), None)
        # Also cleanup validation and extraction workers
        cls._validation_workers.pop(id(download), None)
        cls._extraction_workers.pop(id(download), None)

    @classmethod
    def get_downloads(cls) -> list[DownloadObject]:
        """Get all registered downloads"""
        return cls._downloads.copy()

    @classmethod
    def clear(cls):
        """Clear all registered downloads"""
        cls._downloads.clear()
        cls._workers.clear()
        cls._validation_workers.clear()
        cls._extraction_workers.clear()


class TaskInterface(ScrollArea):
    """Download Task page - displays downloads from other services"""

    def __init__(self, global_constants: Constants, ui_support: DefGUI = None,
                 global_settings: GlobalSettings = None, parent=None):
        super().__init__(parent)


        logging.info("init gui_task")


        self.setObjectName("Task")

        self.constants = global_constants
        self.gui_support = ui_support
        self.settings = global_settings

        # Task manager instance
        self.task_manager = TaskManager
        self.task_manager.set_constants(self.constants)
        self.network_worker = None
        self.network_timeout_timer = QTimer(self)
        self.network_timeout_timer.setSingleShot(True)
        self.network_timeout_timer.timeout.connect(self._on_network_check_timeout)

        # Download cards (key: download object id)
        self.download_cards: dict[int, DownloadCard] = {}

        # History
        self.download_history = DownloadHistory()

        # Scroll widget setup
        self.scrollWidget = QWidget()
        self.expandLayout = QVBoxLayout(self.scrollWidget)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)
        self.enableTransparentBackground()

        # Timer for refreshing download list
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._refresh_downloads)
        self.refresh_timer.start(10)  # Update every 10ms (0.01s) for smooth speed display

        self.init_ui()

    def init_ui(self):
        self.expandLayout.setContentsMargins(
            SPACING["xxlarge"], SPACING["xlarge"],
            SPACING["xxlarge"], SPACING["xlarge"]
        )
        self.expandLayout.setSpacing(SPACING["large"])

        # Title
        self.expandLayout.addWidget(self._create_title())

        # Network status card
        self.expandLayout.addWidget(self._create_network_status_card())

        # Active downloads section
        self.expandLayout.addWidget(self._create_active_downloads_header())
        self.active_downloads_container = QWidget()
        self.active_downloads_layout = QVBoxLayout(self.active_downloads_container)
        self.active_downloads_layout.setContentsMargins(0, 0, 0, 0)
        self.active_downloads_layout.setSpacing(SPACING["medium"])
        self.expandLayout.addWidget(self.active_downloads_container)

        # Placeholder for empty state
        self.empty_label = BodyLabel("No active downloads")
        self.empty_label.setTextColor("#808080", "#808080")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.active_downloads_layout.addWidget(self.empty_label)

        # Download history section
        self.expandLayout.addWidget(self._create_history_header())
        self.history_container = QWidget()
        self.history_layout = QVBoxLayout(self.history_container)
        self.history_layout.setContentsMargins(0, 0, 0, 0)
        self.history_layout.setSpacing(SPACING["medium"])
        self.expandLayout.addWidget(self.history_container)

        # History empty label
        self.history_empty_label = BodyLabel("No download history")
        self.history_empty_label.setTextColor("#808080", "#808080")
        self.history_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.history_layout.addWidget(self.history_empty_label)

        # Add stretch
        self.expandLayout.addStretch()

        # Check network status
        self._check_network_status()

        # Load history
        self._load_history()

    def _create_title(self) -> QWidget:
        title_label = SubtitleLabel("Download Tasks")
        title_label.setStyleSheet("font-size: 24px; font-weight: bold;")
        return title_label

    def _create_network_status_card(self) -> SettingCard:
        self.network_status_card = SettingCard(
            FluentIcon.INFO,
            "Network Status",
            "Checking...",
            self
        )
        self.network_status_card.setMinimumWidth(1000)
        return self.network_status_card

    def _create_active_downloads_header(self) -> QWidget:
        header = BodyLabel("Active Downloads")
        header.setStyleSheet("font-size: 16px; font-weight: bold;")
        return header

    def _create_history_header(self) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING["medium"])

        header = BodyLabel("Download History")
        header.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(header)

        self.clear_all_button = TransparentToolButton(FluentIcon.DELETE, container)
        self.clear_all_button.setFixedSize(32, 32)
        self.clear_all_button.setToolTip("Clear All History")
        self.clear_all_button.clicked.connect(self._on_clear_all_history)
        layout.addWidget(self.clear_all_button)

        layout.addStretch()
        return container

    def _check_network_status(self):
        """Check network connectivity using a worker thread"""
        worker = self.network_worker
        try:
            if worker is not None and worker.isRunning():
                return
        except RuntimeError:
            self.network_worker = None

        self.network_worker = NetworkCheckWorker(self)
        self.network_worker.finished_signal.connect(self._on_network_check_finished)
        self.network_worker.finished.connect(self._on_network_worker_finished)
        self.network_worker.start()

        # Set timeout to show "Missing network connection" after 10s
        self.network_timeout_timer.start(10000)

    def _on_network_worker_finished(self):
        """Clear the worker reference before Qt deletes the C++ object."""
        worker = self.sender()
        if worker is self.network_worker:
            self.network_worker = None
        if self.network_timeout_timer.isActive():
            self.network_timeout_timer.stop()
        worker.deleteLater()

    def _on_network_check_finished(self, connected: bool):
        """Handle network check result"""
        self.network_connected = connected
        if connected:
            self.network_status_card.setContent("Connected")
        else:
            self.network_status_card.setContent("Disconnected - Cannot access network")
        self.network_worker = None

    def _on_network_check_timeout(self):
        """Handle network check timeout after 10s"""
        worker = self.network_worker
        if worker is None:
            return

        try:
            if worker.isRunning():
                self.network_status_card.setContent("Missing network connection")
                worker.cancel()
        except RuntimeError:
            self.network_worker = None

    def _refresh_downloads(self):
        """Refresh the download list from task manager"""
        current_downloads = self.task_manager.get_downloads()

        # Get current card download objects
        current_card_ids = set(self.download_cards.keys())
        current_download_ids = set(id(d) for d in current_downloads)

        # Remove cards for downloads that are no longer registered
        for download_id in current_card_ids - current_download_ids:
            card = self.download_cards.pop(download_id)
            self.active_downloads_layout.removeWidget(card)
            card.deleteLater()

        # Add new cards for new downloads
        for download in current_downloads:
            download_id = id(download)
            if download_id not in self.download_cards:
                # Create new card with optional icon
                icon = self.task_manager._icons.get(download_id)
                card = DownloadCard(download, icon=icon, parent=self)
                card.cancel_signal.connect(self._on_cancel_download)
                card.pause_signal.connect(self._on_pause_download)
                card.resume_signal.connect(self._on_resume_download)
                card.open_file_signal.connect(self._on_open_file)
                card.open_folder_signal.connect(self._on_open_folder)
                card.retry_download_signal.connect(self._on_retry_download)

                self.download_cards[download_id] = card

                # Remove empty label if exists
                if self.empty_label:
                    self.empty_label.hide()
                    self.empty_label = None

                self.active_downloads_layout.addWidget(card)

        # Update progress for all cards and auto-move completed to history
        completed = []
        for download_id, card in list(self.download_cards.items()):
            card.update_progress()
            if card.download.status in (DownloadStatus.COMPLETED, DownloadStatus.FAILED):
                # Don't move to history if validation or extraction workers are still active
                if download_id in self.task_manager._validation_workers or download_id in self.task_manager._extraction_workers:
                    continue
                completed.append(card.download)

        for download in completed:
            self._move_to_history(download)

        # Show empty label if no downloads
        if not current_downloads and self.empty_label is None:
            self.empty_label = BodyLabel("No active downloads")
            self.empty_label.setTextColor("#808080", "#808080")
            self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.active_downloads_layout.addWidget(self.empty_label)

    def _on_open_file(self, download: DownloadObject):
        """Handle open file action"""
        file_path = os.path.join(download.save_path, download.filename)
        if os.path.exists(file_path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(file_path))
        else:
            InfoBar.warning(
                title="File Not Found",
                content=f"File not found: {file_path}",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM_RIGHT,
                duration=3000,
                parent=self
            )

    def _on_open_folder(self, download: DownloadObject):
        """Handle open folder action"""
        folder_path = download.save_path
        if os.path.exists(folder_path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder_path))
        else:
            InfoBar.warning(
                title="Folder Not Found",
                content=f"Folder not found: {folder_path}",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM_RIGHT,
                duration=3000,
                parent=self
            )

    def _on_cancel_download(self, download: DownloadObject):
        """Handle cancel download action"""
        self.task_manager.cancel_download(download)

        InfoBar.warning(
            "Download Cancelled",
            f"{download.filename} has been cancelled.",
            duration=3000,
            position=InfoBarPosition.BOTTOM_RIGHT,
            parent=self,
        )

        # Auto-delete card after cancel
        QTimer.singleShot(500, lambda: self._on_remove_download(download))

    def _on_pause_download(self, download: DownloadObject):
        """Handle pause download action"""
        self.task_manager.pause_download(download)

    def _on_resume_download(self, download: DownloadObject):
        """Handle resume download action"""
        self.task_manager.resume_download(download)

    def _on_retry_download(self, download: DownloadObject):
        """Handle retry download after validation failure"""
        from pathlib import Path

        logging.info(f"Retrying download: {download.filename}")

        # Delete corrupted file
        file_path = Path(download.save_path) / download.filename
        if file_path.exists():
            try:
                file_path.unlink()
                logging.info(f"Deleted corrupted file: {file_path}")
            except Exception as e:
                logging.error(f"Failed to delete corrupted file: {e}")

        # Reset download status
        download.status = DownloadStatus.PENDING
        download.downloaded_size = 0
        download.error_message = ""

        # Restart download
        icon = self.task_manager._icons.get(id(download))
        self.task_manager.start_download(download, icon=icon)

        InfoBar.info(
            "Download Restarted",
            f"Restarting download for {download.filename}",
            duration=3000,
            position=InfoBarPosition.BOTTOM_RIGHT,
            parent=self,
        )

    def _on_remove_download(self, download: DownloadObject):
        """Handle remove download action"""
        # Cancel if still running
        self.task_manager.cancel_download(download)
        # Unregister from task manager
        self.task_manager.unregister_download(download)

        # Remove card
        download_id = id(download)
        if download_id in self.download_cards:
            card = self.download_cards.pop(download_id)
            self.active_downloads_layout.removeWidget(card)
            card.deleteLater()

    def _move_to_history(self, download: DownloadObject):
        """Move a completed/failed download from active to history"""
        download_id = id(download)

        # Save icon before unregistering
        icon = self.task_manager._icons.get(download_id)

        # Remove from active
        self.task_manager.unregister_download(download)
        if download_id in self.download_cards:
            card = self.download_cards.pop(download_id)
            self.active_downloads_layout.removeWidget(card)
            card.deleteLater()

        # Add to history
        self.download_history.add(download)
        self._add_history_card(download, icon)
        self.history_empty_label.hide()

    def _load_history(self):
        """Load download history"""
        history = self.download_history.history
        if history:
            # Hide empty label
            self.history_empty_label.hide()
            self.clear_all_button.show()
            for download in history:
                self._add_history_card(download)
        else:
            self.history_empty_label.show()
            self.clear_all_button.hide()

    def _add_history_card(self, download: DownloadObject, icon=None):
        """Add a history card"""
        # Use provided icon, or download's saved icon_path, or None (will use default)
        icon = icon or download.icon_path
        card = DownloadCard(download, icon=icon, parent=self)

        # Clear default menu and add history menu with Open File/Folder
        card.menu.clear()

        # Open File action
        open_file_action = Action(FluentIcon.DOCUMENT, "Open File", card)
        open_file_action.triggered.connect(lambda: self._on_open_file(download))
        card.menu.addAction(open_file_action)

        # Open Folder action
        open_folder_action = Action(FluentIcon.FOLDER, "Open Folder", card)
        open_folder_action.triggered.connect(lambda: self._on_open_folder(download))
        card.menu.addAction(open_folder_action)

        # Separator
        card.menu.addSeparator()

        # Re-download action
        redownload_action = Action(FluentIcon.DOWNLOAD, "Re-download", card)
        redownload_action.triggered.connect(lambda: self._on_redownload(download, icon))
        card.menu.addAction(redownload_action)

        # Remove from list action
        remove_action = Action(FluentIcon.DELETE, "Remove from list", card)
        remove_action.triggered.connect(lambda: self._on_remove_history(download))
        card.menu.addAction(remove_action)

        # Hide unnecessary elements for history
        card.progressBar.hide()
        card.speedLabel.hide()
        card.sizeLabel.hide()
        card.percentLabel.hide()

        self.history_layout.addWidget(card)
        self.clear_all_button.show()

    def _on_remove_history(self, download: DownloadObject):
        """Remove download from history"""
        self.download_history.remove(download)

        # Find and remove the card
        for i in range(self.history_layout.count()):
            widget = self.history_layout.itemAt(i).widget()
            if isinstance(widget, DownloadCard) and widget.download == download:
                self.history_layout.removeWidget(widget)
                widget.deleteLater()
                break

        # Show empty label if no history
        if self.download_history.history:
            self.history_empty_label.hide()
            self.clear_all_button.show()
        else:
            self.history_empty_label.show()
            self.clear_all_button.hide()

    def _on_redownload(self, download: DownloadObject, icon=None):
        """Re-download a file from history"""
        new_download = DownloadObject(download.url, download.save_path, download.filename)
        TaskManager.start_download(new_download, icon=icon)

        InfoBar.success(
            "Download Started",
            f"{download.filename} is downloading again.",
            duration=3000,
            position=InfoBarPosition.BOTTOM_RIGHT,
            parent=self,
        )

    def _on_clear_all_history(self):
        """Clear all download history"""
        self.download_history.clear()

        # Remove all cards from layout
        while self.history_layout.count():
            item = self.history_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Show empty label and hide clear button
        self.history_empty_label.show()
        self.history_layout.addWidget(self.history_empty_label)
        self.clear_all_button.hide()

    def refresh(self):
        """Refresh the page"""
        self._check_network_status()
        self._refresh_downloads()

    def cleanup_workers(self):
        """Stop timers and workers owned by this task page."""
        if hasattr(self, 'refresh_timer'):
            self.refresh_timer.stop()
        if hasattr(self, 'network_timeout_timer'):
            self.network_timeout_timer.stop()
        worker = getattr(self, 'network_worker', None)
        if worker is not None:
            try:
                worker.cancel()
                if worker.isRunning() and not worker.wait(2000):
                    logging.warning("NetworkCheckWorker did not stop in 2000ms; terminating")
                    worker.terminate()
                    worker.wait(1000)
                worker.deleteLater()
            except RuntimeError:
                pass
            self.network_worker = None
        self.task_manager.shutdown_all()

    def closeEvent(self, event):
        """Handle close event - cancel all active downloads and network check"""
        self.cleanup_workers()
        super().closeEvent(event)