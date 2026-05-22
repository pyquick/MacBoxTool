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
from ..support.integrity_verification import ChunklistStatus


class NetworkCheckWorker(QThread):
    """Worker thread for checking network connectivity."""
    finished_signal = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_cancelled = False

    def run(self):
        try:
            result = NetworkUtilities.check_network()
            if not self._is_cancelled:
                self.finished_signal.emit(result)
        except Exception as e:
            logging.warning(f"Network check error: {e}")
            if not self._is_cancelled:
                self.finished_signal.emit(False)

    def cancel(self):
        self._is_cancelled = True


class ValidateExtractWorker(QThread):
    """Worker thread for validating and extracting macOS installer."""

    # 新增阶段信号
    stage_changed_signal = Signal(str)  # "validate" 或 "extract"
    progress_signal = Signal(str)  # For progress updates
    finished_signal = Signal(bool, str)  # For completion (success, message)

    def __init__(self, chunklist_url: str, constants: Constants, filename: str, parent=None):
        super().__init__(parent)
        self.chunklist_url = chunklist_url
        self.constants = constants
        self.filename = filename

    def run(self):
        try:
            # ========== 阶段 1: 验证 ==========
            self.stage_changed_signal.emit("validate")
            self.progress_signal.emit("Validating macOS installer...")
            logging.info(f"Starting validation for: {self.filename}")

            # 下载 chunklist
            logging.info(f"Downloading chunklist from: {self.chunklist_url}")
            chunklist_stream = NetworkUtilities().get(self.chunklist_url).content

            if not chunklist_stream:
                error_msg = "Failed to download chunklist"
                logging.error(error_msg)
                self.finished_signal.emit(False, error_msg)
                return

            logging.info("Chunklist downloaded successfully")

            # 验证文件
            from ..support.integrity_verification import ChunklistVerification
            chunk_obj = ChunklistVerification(
                self.constants.payload_path / self.filename,
                chunklist_stream
            )

            if chunk_obj.chunks is None:
                error_msg = "Invalid chunklist format"
                logging.error(error_msg)
                self.finished_signal.emit(False, error_msg)
                return

            logging.info(f"Starting validation of {chunk_obj.total_chunks} chunks")
            chunk_obj.validate()

            # 等待验证完成
            while chunk_obj.status == ChunklistStatus.IN_PROGRESS:
                self.progress_signal.emit(
                    f"Validating... {chunk_obj.current_chunk}/{chunk_obj.total_chunks}"
                )
                QThread.msleep(100)

            if chunk_obj.status == ChunklistStatus.FAILURE:
                error_msg = f"Validation failed: {chunk_obj.error_msg}"
                logging.error(error_msg)
                self.finished_signal.emit(False, error_msg)
                return

            logging.info("Validation completed successfully")

            # ========== 阶段 2: 提取 ==========
            self.stage_changed_signal.emit("extract")
            self.progress_signal.emit("Extracting macOS installer...")
            logging.info("Starting installer extraction")

            from ..support import macos_installer_handler
            result = macos_installer_handler.InstallerCreation(
                global_constants=self.constants
            ).install_macOS_installer(str(self.constants.payload_path))

            if result:
                logging.info("Installer extraction completed successfully")
                self.progress_signal.emit("Installation completed successfully")
                self.finished_signal.emit(True, "macOS installer validated and extracted successfully")
            else:
                error_msg = "Failed to extract macOS installer"
                logging.error(error_msg)
                self.finished_signal.emit(False, error_msg)

        except Exception as e:
            error_msg = f"Error during validation/extraction: {str(e)}"
            logging.error(error_msg, exc_info=True)
            self.finished_signal.emit(False, error_msg)


# Global task manager for registering downloads from other services
class TaskManager:
    """Global task manager for download tasks"""
    _instance = None
    _downloads: list[DownloadObject] = []
    _workers: dict[int, DownloadWorker] = {}
    _validate_workers: dict[int, ValidateExtractWorker] = {}  # validate/extract workers
    _icons: dict[int, object] = {}  # download id -> icon for DownloadCard
    _installer_data: dict[int, dict] = {}  # download id -> installer_data
    _installer_list_instance = None  # Reference to MacOSInstallerList instance
    aconstants :Constants = Constants()
    is_validate:bool = False
        

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def start_download(cls, download: DownloadObject, icon=None, macos_install:bool=False, chunklist_url:str="", installer_data:dict=None) -> DownloadWorker:
        """Start a download and register it for display in TaskInterface.

        Usage:
            download = DownloadObject(url, save_path, filename)
            TaskManager.start_download(download, icon="/path/to/icon.png")
        """
        cls.register_download(download)
        cls.chunklist_url=chunklist_url
        cls.is_validate=macos_install
        if icon is not None:
            cls._icons[id(download)] = icon
            download.icon_path = icon

        # Register installer_data if provided
        if installer_data is not None:
            cls.register_installer_data(download, installer_data)

        worker = DownloadWorker(download)
        cls._workers[id(download)] = worker

        worker.finished_signal.connect(
            lambda success, msg: cls._on_download_finished(download, success, msg)
        )
        worker.start()
        return worker


    @classmethod
    def cancel_download(cls, download: DownloadObject):
        """Cancel an active download"""
        worker = cls._workers.get(id(download))
        if worker and worker.isRunning():
            worker.cancel()
            # Wait for thread to finish before cleanup
            worker.wait(3000)  # Wait up to 3 seconds

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
        """Handle download completion — cleanup worker and trigger validation/extract"""
        worker = cls._workers.pop(id(download), None)
        is_validate = cls.is_validate

        if is_validate and success:
            # 获取必要参数
            chunklist_url = cls.chunklist_url
            installer_data = cls._installer_data.pop(id(download), None)

            # 创建并启动 ValidateExtractWorker
            validate_worker = ValidateExtractWorker(
                chunklist_url=chunklist_url,
                constants=cls.aconstants,
                filename=download.filename,
                parent=None
            )

            # 注册 worker
            cls._validate_workers[id(download)] = validate_worker

            # 连接信号
            validate_worker.stage_changed_signal.connect(
                lambda stage: cls._on_stage_changed(download, stage)
            )
            validate_worker.progress_signal.connect(
                lambda msg: cls._on_validate_progress(download, msg)
            )
            validate_worker.finished_signal.connect(
                lambda success, msg: cls._on_validate_finished(download, success, msg)
            )

            # 启动验证/提取
            validate_worker.start()
            logging.info(f"Started validation/extraction for: {download.filename}")

        # 清理 worker
        if worker:
            worker.deleteLater()
        cls._icons.pop(id(download), None)
        if success:
            logging.info(f"Download completed: {download.filename}")
        else:
            logging.warning(f"Download failed: {download.filename} - {message}")

    @classmethod
    def _on_stage_changed(cls, download: DownloadObject, stage: str):
        """Handle validation/extraction stage change"""
        if hasattr(cls, '_stage_changed_callback') and cls._stage_changed_callback:
            cls._stage_changed_callback(download, stage)

    @classmethod
    def _on_validate_progress(cls, download: DownloadObject, message: str):
        """Handle validation/extraction progress update"""
        if hasattr(cls, '_progress_callback') and cls._progress_callback:
            cls._progress_callback(download, message)

    @classmethod
    def _on_validate_finished(cls, download: DownloadObject, success: bool, message: str):
        """Handle validation/extraction completion"""
        worker = cls._validate_workers.pop(id(download), None)
        if worker:
            worker.deleteLater()
        if success:
            logging.info(f"Validation/Extraction completed: {download.filename}")
        else:
            logging.warning(f"Validation/Extraction failed: {download.filename} - {message}")

    
    @classmethod
    def register_download(cls, download: DownloadObject):
        """Register a download task to be displayed"""
        if download not in cls._downloads:
            cls._downloads.append(download)

    @classmethod
    def register_installer_list(cls, installer_list_instance):
        """Register MacOSInstallerList instance for validation/extraction callbacks"""
        cls._installer_list_instance = installer_list_instance

    @classmethod
    def register_installer_data(cls, download: DownloadObject, installer_data: dict):
        """Register installer_data for a download task"""
        cls._installer_data[id(download)] = installer_data

    @classmethod
    def unregister_download(cls, download: DownloadObject):
        """Unregister a download task"""
        if download in cls._downloads:
            cls._downloads.remove(download)
        cls._workers.pop(id(download), None)

    @classmethod
    def get_downloads(cls) -> list[DownloadObject]:
        """Get all registered downloads"""
        return cls._downloads.copy()

    @classmethod
    def clear(cls):
        """Clear all registered downloads"""
        cls._downloads.clear()
        cls._workers.clear()


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

        # Download cards (key: download object id)
        self.download_cards: dict[int, DownloadCard] = {}

        # Validate/Extract progress cards (key: download object id)
        self.validate_cards: dict[int, QWidget] = {}

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

        # Set up callbacks for validation/extraction
        TaskManager._validate_started_callback = self._show_validate_progress
        TaskManager._stage_changed_callback = self._on_validate_stage_changed
        TaskManager._progress_callback = self._on_validate_progress_update

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
        self.network_worker = NetworkCheckWorker(self)
        self.network_worker.finished_signal.connect(self._on_network_check_finished)
        self.network_worker.start()

        # Set timeout to show "Missing network connection" after 10s
        QTimer.singleShot(10000, self._on_network_check_timeout)

    def _on_network_check_finished(self, connected: bool):
        """Handle network check result"""
        self.network_connected = connected
        if connected:
            self.network_status_card.setContent("Connected")
        else:
            self.network_status_card.setContent("Disconnected - Cannot access network")

    def _on_network_check_timeout(self):
        """Handle network check timeout after 10s"""
        if hasattr(self, 'network_worker') and self.network_worker.isRunning():
            self.network_status_card.setContent("Missing network connection")
            self.network_worker.cancel()

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
                completed.append(card.download)

        for download in completed:
            self._move_to_history(download)

        # Show empty label if no downloads
        if not current_downloads and self.empty_label is None:
            self.empty_label = BodyLabel("No active downloads")
            self.empty_label.setTextColor("#808080", "#808080")
            self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.active_downloads_layout.addWidget(self.empty_label)

        # Check for new validation/extraction workers and show progress
        for worker_id, worker in list(TaskManager._validate_workers.items()):
            if worker_id not in self.validate_cards and worker.isRunning():
                # Find the corresponding download
                for download in current_downloads:
                    if id(download) == worker_id:
                        self._show_validate_progress(download)
                        break

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
                position=InfoBarPosition.TOP_RIGHT,
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
                position=InfoBarPosition.TOP_RIGHT,
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
            position=InfoBarPosition.TOP_RIGHT,
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

    def _show_validate_progress(self, download: DownloadObject):
        """Show validation/extraction progress for a download"""
        download_id = id(download)

        # Find the existing download card
        if download_id not in self.download_cards:
            return

        card = self.download_cards[download_id]

        # Switch card to validation mode
        card.show_validate_progress("Validating...")

        # Mark as validating to prevent duplicate cards
        self.validate_cards[download_id] = card

        # Connect to worker for progress updates
        worker = self.task_manager._validate_workers.get(download_id)
        if worker:
            worker.progress_signal.connect(card.update_validate_status)
            worker.finished_signal.connect(
                lambda success, msg: self._on_validate_complete(download, success, msg)
            )

    def _on_validate_stage_changed(self, download: DownloadObject, stage: str):
        """Handle validation/extraction stage change"""
        download_id = id(download)
        if download_id not in self.download_cards:
            return

        card = self.download_cards[download_id]

        if stage == "validate":
            card.show_validate_progress("Validating...")
            logging.info(f"Validation stage started for: {download.filename}")
        elif stage == "extract":
            card.update_validate_status("Extracting...")
            logging.info(f"Extraction stage started for: {download.filename}")

    def _on_validate_progress_update(self, download: DownloadObject, message: str):
        """Handle validation/extraction progress updates"""
        download_id = id(download)
        if download_id not in self.download_cards:
            return

        card = self.download_cards[download_id]
        card.update_validate_status(message)

    def _on_validate_complete(self, download: DownloadObject, success: bool, message: str):
        """Handle validation/extraction completion"""
        download_id = id(download)

        # Remove from validating cards
        if download_id in self.validate_cards:
            card = self.validate_cards.pop(download_id)

            # Return card to normal mode
            if card and download_id in self.download_cards:
                card.hide_validate_progress()

        # Show completion message based on success
        if success:
            InfoBar.success(
                "Installation Complete",
                "macOS installer has been validated and extracted successfully",
                duration=5000,
                position=InfoBarPosition.TOP_RIGHT,
                parent=self
            )
        else:
            InfoBar.error(
                "Installation Failed",
                f"Failed to validate or extract macOS installer: {message}",
                duration=5000,
                position=InfoBarPosition.TOP_RIGHT,
                parent=self
            )

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
            position=InfoBarPosition.TOP_RIGHT,
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

    def closeEvent(self, event):
        """Handle close event - cancel all active downloads and network check"""
        # Cancel network check worker
        if hasattr(self, 'network_worker') and self.network_worker.isRunning():
            self.network_worker.cancel()
            self.network_worker.wait(1000)

        # Cancel all active downloads
        for download in self.task_manager.get_downloads():
            if download.status in (DownloadStatus.DOWNLOADING, DownloadStatus.PAUSED):
                self.task_manager.cancel_download(download)
        event.accept()