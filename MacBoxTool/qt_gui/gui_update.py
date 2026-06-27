"""
gui_update.py: MacBoxTool update interface.
"""
from ..include import *
from .gui_support import DefGUI
from ..support.update import check_update, fetch_update, install_update, launch


class InstallUpdateWorker(QThread):
    """Run package installation outside the GUI thread."""

    finished_signal = Signal(bool, str)

    def __init__(self, pkg_path: Path, constants: Constants, parent=None):
        """Store installation inputs for the worker thread."""
        super().__init__(parent)
        self.pkg_path = pkg_path
        self.constants = constants

    def run(self):
        """Execute the installer and emit the result."""
        try:
            success = install_update.InstallUpdate(self.pkg_path, self.constants).install_update()
            if success:
                self.finished_signal.emit(True, "Update installed successfully")
            else:
                self.finished_signal.emit(False, "Failed to install update")
        except Exception as e:
            logging.error(f"[Update] Install failed: {e}")
            self.finished_signal.emit(False, str(e))


class Updater(ScrollArea):
    """GUI page for checking, downloading, and installing updates."""

    def __init__(
        self,
        global_constants: Constants,
        ui_support: DefGUI = None,
        global_settings: GlobalSettings = None,
        parent=None,
    ):
        """Initialize update page state and widgets."""
        super().__init__(parent)

        logging.info("init gui_update")
        self.setObjectName("Update")

        # Shared application state.
        self.constants = global_constants
        self.gui_support = ui_support
        self.settings = global_settings

        # Runtime update state.
        self.update_result = None
        self.update_worker = None
        self.install_worker = None
        self.pkg_download_path = None
        self.auto_download_install = False
        self.is_downloading_update = False

        self.scrollWidget = QWidget()
        self.expandLayout = QVBoxLayout(self.scrollWidget)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)
        self.enableTransparentBackground()

        self.init_ui()

    # ------------------------------------------------------------------
    # GUI construction
    # ------------------------------------------------------------------

    def init_ui(self):
        """Create the update page layout."""
        self.expandLayout.setContentsMargins(
            SPACING["xxlarge"],
            SPACING["xlarge"],
            SPACING["xxlarge"],
            SPACING["xlarge"],
        )
        self.expandLayout.setSpacing(SPACING["large"])

        title_label = SubtitleLabel("Update MacBoxTool")
        title_label.setStyleSheet("font-size: 24px; font-weight: bold;")
        self.expandLayout.addWidget(title_label)

        self._build_update_cards()
        self.expandLayout.addWidget(self.update_group)
        self.expandLayout.addWidget(self.progress_widgets(), 1)
        self.expandLayout.addWidget(self.changelog(), 1)
        self.expandLayout.addStretch()

        self._connect_signals()

    def _build_update_cards(self):
        """Build the settings cards used by the update page."""
        self.update_group = SettingCardGroup("Updater", self.scrollWidget)

        self.status_card = PushSettingCard(
            text="Check for update",
            icon=FluentIcon.INFO,
            title="Update Status",
            content=f"Current version: {self.constants.macboxtool_version}",
            parent=self.update_group,
        )

        self.download_card = PushSettingCard(
            text="Download",
            icon=FluentIcon.DOWNLOAD,
            title="Download Update",
            content="Download the latest installer package",
            parent=self.update_group,
        )
        self.download_card.setEnabled(False)

        self.install_card = PushSettingCard(
            text="Install",
            icon=FluentIcon.SAVE,
            title="Install Update",
            content="Install the downloaded package and relaunch MacBoxTool",
            parent=self.update_group,
        )
        self.install_card.setEnabled(False)
        self.install_card.setVisible(False)

        self.auto_card = SwitchSettingCard(
            icon=FluentIcon.SYNC,
            title="Automatically Download & Install",
            content="After an update is found, download and install it automatically",
            parent=self.update_group,
        )

        self.nightly_card = SwitchSettingCard(
            icon=FluentIcon.CODE,
            title="Allow Install Nightly Build",
            content="Explore the latest build and give feedback.",
            parent=self.update_group,
        )

        self.update_group.addSettingCard(self.status_card)
        self.update_group.addSettingCard(self.download_card)
        self.update_group.addSettingCard(self.auto_card)
        self.update_group.addSettingCard(self.nightly_card)
        self.update_group.addSettingCard(self.install_card)

        if self.constants.allow_nightly_check:
            self.nightly_card.setVisible(False)

    def progress_widgets(self):
        """Build the shared progress panel for check/download/install actions."""
        self.progress_container = CardWidget()
        self.progress_layout = QHBoxLayout(self.progress_container)
        self.progress_layout.setContentsMargins(
            SPACING["xxlarge"],
            SPACING["xxlarge"],
            SPACING["xxlarge"],
            SPACING["xxlarge"],
        )

        # Check and install use an indeterminate ring.
        self.check_ring = IndeterminateProgressRing(self)
        self.check_ring.setFixedSize(80, 80)
        self.check_ring.setVisible(False)

        # Download uses a determinate ring with live percentage updates.
        self.progress_ring = ProgressRing(self)
        self.progress_ring.setRange(0, 100)
        self.progress_ring.setValue(0)
        self.progress_ring.setTextVisible(True)
        self.progress_ring.setFixedSize(80, 80)
        self.progress_ring.setStrokeWidth(4)
        self.progress_ring.setVisible(False)

        self.progress_label = SubtitleLabel("")
        self.progress_layout.addWidget(self.check_ring, 0, Qt.AlignmentFlag.AlignVCenter)
        self.progress_layout.addWidget(self.progress_ring, 0, Qt.AlignmentFlag.AlignVCenter)
        self.progress_layout.addWidget(self.progress_label, 1, Qt.AlignmentFlag.AlignVCenter)
        self.progress_container.setVisible(False)

        return self.progress_container

    def changelog(self):
        """Build the changelog panel. CLI logs must not be written here."""
        card = CardWidget()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(
            SPACING["large"],
            SPACING["large"],
            SPACING["large"],
            SPACING["large"],
        )

        label = StrongBodyLabel("Update Changelog")
        layout.addWidget(label)

        self.log_box = TextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setFixedHeight(360)
        self.log_box.setPlaceholderText("")
        layout.addWidget(self.log_box)

        return card

    def _connect_signals(self):
        """Wire GUI actions to update handlers."""
        self.status_card.clicked.connect(self.check_for_update)
        self.download_card.clicked.connect(self.download_update)
        self.install_card.clicked.connect(self.install_update)
        self.nightly_card.checkedChanged.connect(self._on_check_nightly_changed)
        self.auto_card.checkedChanged.connect(self._on_auto_download_install_changed)

    # ------------------------------------------------------------------
    # GUI state helpers
    # ------------------------------------------------------------------

    def _set_busy(self, busy: bool, message: str, mode: str = "idle"):
        """Update controls and progress indicators for a running action."""
        self.progress_label.setText(message)
        self.progress_container.setVisible(busy)
        self.check_ring.setVisible(mode in ("checking", "installing"))
        self.progress_ring.setVisible(mode == "downloading")

        if mode in ("checking", "installing"):
            self.check_ring.start()
        else:
            self.check_ring.stop()

        if not busy and mode != "downloading":
            self.progress_ring.setValue(0)

        self.status_card.setEnabled(not busy)
        self.auto_card.setEnabled(not busy)

        has_update = bool(self.update_result and self.update_result.get("if_update", False))
        self.download_card.setEnabled((not busy and has_update) or self.is_downloading_update)
        self.download_card.button.setText("Cancel" if self.is_downloading_update else "Download")

        has_installer = self.pkg_download_path is not None
        self.install_card.setVisible(has_installer)
        self.install_card.setEnabled(not busy and has_installer)

    def _log_update(self, message: str, level: int = logging.INFO):
        """Write update diagnostics to CLI/logging only."""
        logging.log(level, f"[Update] {message}")

    def _format_size(self, size: int) -> str:
        """Format byte counts for the download progress label."""
        if size == 0:
            return "0 B"

        units = ["B", "KB", "MB", "GB", "TB"]
        size_float = float(size)
        unit_index = 0
        while size_float >= 1024 and unit_index < len(units) - 1:
            size_float /= 1024
            unit_index += 1

        if unit_index == 0:
            return f"{int(size_float)} {units[unit_index]}"
        return f"{size_float:.2f} {units[unit_index]}"

    # ------------------------------------------------------------------
    # User action handlers
    # ------------------------------------------------------------------

    def _on_auto_download_install_changed(self, checked: bool):
        """Store the automatic update preference."""
        self.auto_download_install = checked

    def _on_check_nightly_changed(self, checked: bool):
        """Store whether nightly builds can be installed."""
        self.constants.allow_nightly_check = checked

    def check_for_update(self):
        """Check for stable or nightly updates without blocking the GUI."""
        self._set_busy(True, "Checking for updates...", "checking")
        self.log_box.clear()

        def _check():
            """Run update metadata checks in a background thread."""
            try:
                checker = check_update.CheckUpdate(self.constants)
                self.update_result = checker.check_update()
            except Exception as e:
                logging.error(f"[Update] Check failed: {e}")
                self.update_result = {"if_update": False, "update_log": str(e), "error": True}

        self._log_update("Checking for updates...")
        thread = threading.Thread(target=_check, daemon=True)
        thread.start()

        def _finish_check():
            """Poll the check thread and update the GUI when done."""
            if thread.is_alive():
                QTimer.singleShot(100, _finish_check)
                return

            self._set_busy(False, "Check complete")
            self.status_card.setEnabled(True)
            self.auto_card.setEnabled(True)

            if self.update_result.get("error"):
                self._log_update(self.update_result.get("update_log", "Failed to check update"), logging.ERROR)
                InfoBar.error(
                    "Update",
                    "Failed to check update",
                    duration=3000,
                    position=InfoBarPosition.TOP_RIGHT,
                    parent=self.scrollWidget,
                )
                return

            if self.update_result.get("if_update"):
                self.status_card.setContent("Update available")
                self.download_card.setEnabled(True)
                self.download_card.button.setText("Download")
                self.log_box.setMarkdown(self.update_result.get("update_log", ""))
                InfoBar.info(
                    "Update",
                    "Update available",
                    duration=3000,
                    position=InfoBarPosition.TOP_RIGHT,
                    parent=self.scrollWidget,
                )
                if self.auto_download_install:
                    QTimer.singleShot(0, self.download_update)
            else:
                self.status_card.setContent(f"You're on the latest version: {self.constants.macboxtool_version}")
                self._log_update("You're up to date")
                InfoBar.success(
                    "Update",
                    "You're up to date",
                    duration=3000,
                    position=InfoBarPosition.TOP_RIGHT,
                    parent=self.scrollWidget,
                )

        QTimer.singleShot(100, _finish_check)

    def download_update(self):
        """Start or cancel the update download."""
        if self.is_downloading_update and self.update_worker:
            self.update_worker.cancel()
            self.progress_label.setText("Cancelling download...")
            self.download_card.setEnabled(False)
            self._log_update("Cancelling download...")
            return

        try:
            self.update_worker = fetch_update.FetchUpdate(self.constants, self.update_result)
            self.pkg_download_path = self.update_worker.update_package_path()
        except Exception as e:
            self.is_downloading_update = False
            self.pkg_download_path = None
            self._set_busy(False, "Download preparation failed")
            self._log_update(f"Download preparation failed: {e}", logging.ERROR)
            InfoBar.error(
                "Update",
                "Failed to prepare update download",
                duration=5000,
                position=InfoBarPosition.TOP_RIGHT,
                parent=self.scrollWidget,
            )
            return

        self.is_downloading_update = True
        self.progress_ring.setValue(0)
        self.download_card.button.setText("Cancel")
        self._set_busy(True, "Preparing downloading update...", "downloading")
        self._log_update(f"Downloading: {self.pkg_download_path.name}")

        self.update_worker.progress_signal.connect(self._on_download_progress)
        self.update_worker.finished_signal.connect(self._on_download_finished)
        self.update_worker.start()

    def install_update(self):
        """Install the downloaded package."""
        if not self.pkg_download_path:
            return

        self._set_busy(True, "Installing update...", "installing")
        self._log_update(f"Installing: {self.pkg_download_path}")
        self.install_worker = InstallUpdateWorker(self.pkg_download_path, self.constants, self)
        self.install_worker.finished_signal.connect(self._on_install_finished)
        self.install_worker.start()

    # ------------------------------------------------------------------
    # Worker callbacks
    # ------------------------------------------------------------------

    def _on_download_progress(self, downloaded, total):
        """Refresh the determinate progress ring during downloads."""
        if total:
            percent = int((downloaded / total) * 100)
            self.progress_ring.setValue(percent)
            self.progress_label.setText(
                f"Downloading update... {percent}% ({self._format_size(downloaded)} / {self._format_size(total)})"
            )
        else:
            self.progress_label.setText(f"Downloading update... {self._format_size(downloaded)}")

    def _on_download_finished(self, success: bool, message: str):
        """Restore GUI state after the download worker exits."""
        self.is_downloading_update = False
        self.download_card.button.setText("Download")
        self.pkg_download_path = None
        self._set_busy(False, "Download complete" if success else "Download failed")

        if success:
            self.progress_ring.setValue(100)
            self._log_update(f"Downloaded: {message}")
            self.pkg_download_path = Path(message)
            self._set_busy(False, "Download complete")
            InfoBar.success(
                "Update",
                "Update downloaded",
                duration=3000,
                position=InfoBarPosition.TOP_RIGHT,
                parent=self.window(),
            )
            if self.auto_download_install:
                QTimer.singleShot(0, self.install_update)
        else:
            self._log_update(f"Download failed: {message}")
            if "cancelled" in str(message).lower():
                InfoBar.info(
                    "Update",
                    "Download cancelled",
                    duration=3000,
                    position=InfoBarPosition.TOP_RIGHT,
                    parent=self.window(),
                )
            else:
                InfoBar.error(
                    "Update",
                    "Download failed",
                    duration=3000,
                    position=InfoBarPosition.TOP_RIGHT,
                    parent=self.window(),
                )

    def _on_install_finished(self, success: bool, message: str):
        """Restore GUI state after installation finishes."""
        self._set_busy(False, message)
        self._log_update(message)

        if success:
            InfoBar.success(
                "Update",
                "Update installed, relaunching...",
                duration=3000,
                position=InfoBarPosition.TOP_RIGHT,
                parent=self.window(),
            )
            launch.LaunchUpdate().launch_update()
        else:
            InfoBar.error(
                "Update",
                message,
                duration=5000,
                position=InfoBarPosition.TOP_RIGHT,
                parent=self.window(),
            )

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def _cancel_update_download(self):
        """Cancel an active download before the page/window is destroyed."""
        if self.is_downloading_update and self.update_worker:
            logging.info("[Update] Cancelling update download during shutdown")
            self.update_worker.cancel()
            self.is_downloading_update = False

    def cleanup_workers(self):
        """Clean up active update workers."""
        self._cancel_update_download()

    def closeEvent(self, event):
        """Cancel update work before the widget closes."""
        self.cleanup_workers()
        super().closeEvent(event)
