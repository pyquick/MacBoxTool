"""
gui_macos_installer.py: macOS Installer list with InstallerCard
"""

from ..include import *
from .. import sucatalog
from .gui_support import DefGUI
from ..UIkit.components.widgets.card_widget import CardWidget
from ..UIkit.components.widgets.label import BodyLabel, CaptionLabel
from ..UIkit.components.widgets.button import PrimaryPushButton, TransparentToolButton
from ..UIkit.components.widgets.label import ImageLabel
from ..UIkit.components.widgets.progress_ring import IndeterminateProgressRing
from ..UIkit.components.widgets.switch_button import SwitchButton
from ..support.network_handler import DownloadObject
from .gui_task import TaskManager


class InstallerCard(CardWidget):
    """Installer card widget for displaying macOS installer info"""

    download_clicked = Signal(dict)

    def __init__(self, installer_data: dict, constants: Constants, parent=None):
        super().__init__(parent)
        self.installer_data = installer_data
        self.constants = constants

        logging.info(f"#####InstallerCard: {installer_data.get('Title', 'Unknown')}#####")
        self._init_card()
        self._init_icon()
        self._init_info_labels()
        self._init_download_button()
        self._init_layout()

    # ── Icon Helper ──

    def _macos_version_to_icon(self, version: int) -> int:
        """Convert macOS XNUMajor version to icon index"""
        try:
            self.constants.icons_path[version - 19]
            return version - 19
        except IndexError:
            return 0

    # ── Sub-init Methods ──

    def _init_card(self):
        """Initialize card size and border"""
        self.setFixedHeight(80)
        self.setBorderRadius(8)

    def _init_icon(self):
        """Initialize macOS icon widget using XNUMajor"""
        install_assistant = self.installer_data.get("InstallAssistant") or {}
        xnu_major = install_assistant.get("XNUMajor", 0)
        icon_index = self._macos_version_to_icon(xnu_major)
        icon_path = self.constants.icons_path[icon_index]
        png_path = icon_path.rsplit('.', 1)[0] + '.png'

        self.icon_widget = ImageLabel(png_path, self)
        self.icon_widget.setFixedSize(48, 48)

    def _init_info_labels(self):
        """Initialize title, date, and version labels"""
        title = self.installer_data.get("Title", "Unknown")
        self.title_label = BodyLabel(title)
        self.title_label.setStyleSheet("font-weight: 600;")

        post_date = self.installer_data.get("PostDate")
        if post_date:
            date_str = post_date.strftime("%Y-%m-%d") if hasattr(post_date, 'strftime') else str(post_date)
            self.date_label = CaptionLabel(f"Release: {date_str}")
        else:
            self.date_label = CaptionLabel("Release: Unknown")

        version_str = self.installer_data.get("Version", "0.0.0")
        build = self.installer_data.get("Build", "N/A")
        self.version_label = CaptionLabel(f"Version: {version_str} | Build: {build}")

    def _init_download_button(self):
        """Initialize download button"""
        self.download_button = PrimaryPushButton("Download")
        self.download_button.setFixedWidth(100)
        self.download_button.clicked.connect(self._on_download_clicked)

        self.validate_button = PrimaryPushButton("Validate")
        self.validate_button.setFixedWidth(100)
        self.validate_button.clicked.connect(self._on_validate_clicked)
        self.validate_button.hide()

        self.extract_button = PrimaryPushButton("Extract")
        self.extract_button.setFixedWidth(100)
        self.extract_button.clicked.connect(self._on_extract_clicked)
        self.extract_button.hide()

        self.copy_link_button = TransparentToolButton(FluentIcon.COPY)
        self.copy_link_button.setFixedSize(32, 32)
        self.copy_link_button.setToolTip("Copy Download Link")
        self.copy_link_button.clicked.connect(self._on_copy_link_clicked)

    def _init_layout(self):
        """Assemble card layout: icon | info | button"""
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(16, 12, 16, 12)
        self.main_layout.setSpacing(16)

        # Left: Icon
        self.main_layout.addWidget(self.icon_widget, 0, Qt.AlignmentFlag.AlignVCenter)

        # Middle: Info
        self.info_layout = QVBoxLayout()
        self.info_layout.setContentsMargins(0, 0, 0, 0)
        self.info_layout.setSpacing(4)
        self.info_layout.addWidget(self.title_label, 0, Qt.AlignmentFlag.AlignVCenter)
        self.info_layout.addWidget(self.date_label, 0, Qt.AlignmentFlag.AlignVCenter)
        self.info_layout.addWidget(self.version_label, 0, Qt.AlignmentFlag.AlignVCenter)
        self.info_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.main_layout.addLayout(self.info_layout, 1)

        # Right: Download button
        self.main_layout.addWidget(self.copy_link_button, 0, Qt.AlignmentFlag.AlignVCenter)
        self.main_layout.addWidget(self.validate_button, 0, Qt.AlignmentFlag.AlignVCenter)
        self.main_layout.addWidget(self.extract_button, 0, Qt.AlignmentFlag.AlignVCenter)
        self.main_layout.addWidget(self.download_button, 0, Qt.AlignmentFlag.AlignVCenter)

    # ── Actions ──

    def _on_download_clicked(self):
        """Handle download button click"""
        self.download_clicked.emit(self.installer_data)

    def _on_copy_link_clicked(self):
        """Handle copy link button click"""
        install_assistant = self.installer_data.get("InstallAssistant") or {}
        url = install_assistant.get("URL")
        if url:
            QApplication.clipboard().setText(url)
            InfoBar.success(
                "Link Copied",
                "Download link copied to clipboard",
                duration=2000,
                position=InfoBarPosition.TOP_RIGHT,
                parent=self.window()
            )

    def _on_validate_clicked(self):
        """Handle validate button click"""
        self.parent().validate_installer(self.installer_data)

    def _on_extract_clicked(self):
        """Handle extract button click"""
        self.parent().extract_installer(self.installer_data)


class MacOSInstallerList(ScrollArea):
    """Scrollable list of macOS installers"""

    def __init__(self, global_constants: Constants, ui_support: DefGUI = None, global_settings: GlobalSettings = None, parent=None):
        super().__init__(parent)

        self.setObjectName("MacOSInstaller")
        self.constants = global_constants
        self.ui_support = ui_support
        self.settings = global_settings

        logging.info("######################")
        logging.info("#####MacOSInstallerList:OK#####")
        logging.info("######################")

        # Data
        self.available_installers = []
        self.available_installers_latest = []
        self.show_latest_only = False

        self._init_scroll_area()
        self.init_ui()

    # ── Initialization ──

    def _init_scroll_area(self):
        """Initialize scroll area components"""
        self.scrollWidget = QWidget()
        self.expandLayout = QVBoxLayout(self.scrollWidget)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)
        self.enableTransparentBackground()

    def init_ui(self):
        """Initialize UI layout by assembling sub-components"""
        self.expandLayout.setContentsMargins(
            SPACING["xxlarge"], SPACING["xlarge"],
            SPACING["xxlarge"], SPACING["xlarge"]
        )
        self.expandLayout.setSpacing(SPACING["large"])
        self._init_layout()
        self._init_header()
        self._init_progress_ring()
        self._init_loading_label()
        self._init_loading_container()

    def _init_layout(self):
        """Initialize main layout margins and spacing"""
        self.expandLayout.setContentsMargins(
            SPACING["xxlarge"], SPACING["xlarge"],
            SPACING["xxlarge"], SPACING["xlarge"]
        )
        self.expandLayout.setSpacing(SPACING["medium"])

    def _init_header(self):
        """Initialize header with latest-only toggle"""
        self.header_container = QWidget()
        header_layout = QHBoxLayout(self.header_container)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(SPACING["medium"])

        header_layout.addStretch()

        latest_label = BodyLabel("Show Latest Only")
        header_layout.addWidget(latest_label)

        self.latest_switch = SwitchButton()
        self.latest_switch.setChecked(self.show_latest_only)
        self.latest_switch.checkedChanged.connect(self._on_latest_toggle)
        header_layout.addWidget(self.latest_switch)

        self.expandLayout.addWidget(self.header_container)
        self.header_container.setVisible(False)

    def _init_progress_ring(self):
        """Initialize indeterminate progress ring"""
        self.progress_ring = IndeterminateProgressRing()
        self.progress_ring.setFixedSize(48, 48)
        self.progress_ring.setVisible(False)

    def _init_loading_label(self):
        """Initialize loading text label"""
        self.loading_label = BodyLabel("Loading installers...")
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def _init_loading_container(self):
        """Assemble loading container with progress ring and label"""
        self.loading_container = QWidget()
        self.loading_layout = QVBoxLayout(self.loading_container)
        self.loading_layout.setContentsMargins(0, 0, 0, 0)
        self.loading_layout.setSpacing(SPACING["medium"])
        self.loading_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.loading_layout.addWidget(self.progress_ring, 0, Qt.AlignmentFlag.AlignCenter)
        self.loading_layout.addWidget(self.loading_label, 0, Qt.AlignmentFlag.AlignCenter)

        self.expandLayout.addWidget(self.loading_container)

    # ── Loading ──

    def load_installers(self):
        """Load installers from Apple catalog using background thread"""
        logging.info("######################")
        logging.info("#####load_installers:Start#####")
        logging.info(f"Fetching installer catalog: {sucatalog.SeedType.DeveloperSeed.name}")

        self._show_loading(True)

        def _fetch_installers():
            logging.info(f"Fetching installer catalog: {sucatalog.SeedType.DeveloperSeed.name}")

            sucatalog_contents = sucatalog.CatalogURL(seed=sucatalog.SeedType.DeveloperSeed).url_contents
            if sucatalog_contents is None:
                logging.error("Failed to download Installer Catalog from Apple")
                return

            self.available_installers = sucatalog.CatalogProducts(sucatalog_contents).products
            self.available_installers.sort(key=lambda x: x.get("Build", ""), reverse=True)
            self.available_installers_latest = sucatalog.CatalogProducts(sucatalog_contents).latest_products

        thread = threading.Thread(target=_fetch_installers)
        thread.start()

        # Poll thread completion without blocking UI
        def _check_thread():
            if thread.is_alive():
                QTimer.singleShot(100, _check_thread)
                return

            # Thread finished
            if not self.available_installers and not self.available_installers_latest:
                self._show_error("Failed to download catalog")
                logging.info("#####load_installers:Failed#####")
                logging.info("######################")
                return

            logging.info("Catalog downloaded successfully")
            logging.info(f"Found {len(self.available_installers)} installers")
            logging.info(f"Found {len(self.available_installers_latest)} latest installers")

            for i, installer in enumerate(self.available_installers):
                title = installer.get("Title", "Unknown")
                version = installer.get("Version", "Unknown")
                build = installer.get("Build", "Unknown")
                post_date = installer.get("PostDate", "Unknown")
                install_assistant = installer.get("InstallAssistant") or {}
                size = install_assistant.get("Size", 0)
                size_mb = size / (1024 * 1024) if size else 0
                logging.info(f"  [{i+1}] {title} ({version} - {build}) | Size: {size_mb:.2f} MB | Date: {post_date}")

            logging.info("#####load_installers:Success#####")
            logging.info("######################")

            self._show_loading(False)
            self._display_installers()

        QTimer.singleShot(100, _check_thread)

    # ── UI State ──

    def _show_loading(self, show: bool):
        """Show or hide loading indicator"""
        if show:
            self.loading_container.setVisible(True)
            self.progress_ring.setVisible(True)
            self.progress_ring.start()
        else:
            self.progress_ring.stop()
            self.progress_ring.setVisible(False)
            self.loading_container.setVisible(False)

    def _show_error(self, message: str):
        """Show error message"""
        self._show_loading(False)
        self._clear_layout()

        error_label = BodyLabel(message)
        error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.expandLayout.addWidget(error_label)

    def _clear_layout(self):
        """Clear all widgets from the layout"""
        while self.expandLayout.count():
            item = self.expandLayout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    # ── Display ──

    def _on_latest_toggle(self, checked: bool):
        """Handle latest-only toggle"""
        self.show_latest_only = checked
        if self.available_installers:
            self._display_installers()

    def _display_installers(self):
        """Display installer cards"""
        logging.info("#####_display_installers:Start#####")

        self._clear_layout()
        self._init_header()
        self.header_container.setVisible(True)

        installers = self.available_installers_latest if self.show_latest_only else self.available_installers

        if not installers:
            logging.warning("No installers available to display")
            no_data_label = BodyLabel("No installers available")
            no_data_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.expandLayout.addWidget(no_data_label)
            logging.info("#####_display_installers:NoData#####")
            return

        logging.info(f"Creating {len(installers)} installer cards...")

        for installer in installers:
            card = InstallerCard(installer, self.constants, self)
            card.download_clicked.connect(self._on_download_clicked)
            self.expandLayout.addWidget(card)

        self.expandLayout.addStretch(1)

        logging.info(f"#####_display_installers:Success ({len(installers)} cards)#####")

    # ── Actions ──

    def _on_download_clicked(self, installer_data: dict):
        """Handle download button click - start actual download"""
        title = installer_data.get("Title", "Unknown")
        version = installer_data.get("Version", "Unknown")
        build = installer_data.get("Build", "Unknown")

        install_assistant = installer_data.get("InstallAssistant") or {}
        url = install_assistant.get("URL")
        if not url:
            logging.warning("No download URL available")
            InfoBar.error(
                "Download Failed",
                "No download URL available for this installer.",
                duration=3000,
                position=InfoBarPosition.TOP_RIGHT,
                parent=self,
            )
            return

        logging.info(f"Starting download: {title} ({version} - {build})")
        logging.info(f"Download URL: {url}")

        # Resolve macOS version icon for DownloadCard
        xnu_major = install_assistant.get("XNUMajor", 0)
        try:
            icon_index = xnu_major - 19
            self.constants.icons_path[icon_index]
        except (IndexError, TypeError):
            icon_index = 0
        icon_path = self.constants.icons_path[icon_index]
        png_path = icon_path.rsplit('.', 1)[0] + '.png'

        # Use configured download path or fallback to payload_path
        save_path = self.settings.find_key("download_path") or str(self.constants.payload_path)
        filename = f"InstallAssistant-macOS_{version}-{build}.pkg"
        download_obj = DownloadObject(url, save_path, filename)

        TaskManager.start_download(download_obj, icon=png_path)

        InfoBar.success(
            "Download Started",
            f"{title} ({version} - {build}) is downloading. Check Tasks for progress.",
            duration=5000,
            position=InfoBarPosition.TOP_RIGHT,
            parent=self,
        )

    def validate_installer(self, installer_data: dict):
        """Validate downloaded installer"""
        from ..support import integrity_verification, network_handler

        version = installer_data.get("Version", "Unknown")
        build = installer_data.get("Build", "Unknown")
        install_assistant = installer_data.get("InstallAssistant") or {}

        save_path = self.settings.find_key("download_path") or str(self.constants.payload_path)
        filename = f"InstallAssistant-macOS_{version}-{build}.pkg"
        file_path = Path(save_path) / filename

        if not file_path.exists():
            InfoBar.error("File Not Found", f"Installer not found: {filename}", duration=3000, position=InfoBarPosition.TOP_RIGHT, parent=self)
            return

        chunklist_url = install_assistant.get("IntegrityDataURL")
        if not chunklist_url:
            InfoBar.error("No Chunklist", "No integrity data URL available", duration=3000, position=InfoBarPosition.TOP_RIGHT, parent=self)
            return

        # Download chunklist
        try:
            chunklist_data = network_handler.NetworkUtilities.custom_get(chunklist_url).content
        except Exception as e:
            InfoBar.error("Download Failed", f"Failed to download chunklist: {e}", duration=3000, position=InfoBarPosition.TOP_RIGHT, parent=self)
            return

        # Validate in thread
        self._validate_in_thread(file_path, chunklist_data, installer_data)

    def extract_installer(self, installer_data: dict):
        """Extract installer package"""
        from ..support import macos_installer_handler

        version = installer_data.get("Version", "Unknown")
        build = installer_data.get("Build", "Unknown")

        save_path = self.settings.find_key("download_path") or str(self.constants.payload_path)
        filename = f"InstallAssistant-macOS_{version}-{build}.pkg"
        file_path = Path(save_path) / filename

        if not file_path.exists():
            InfoBar.error("File Not Found", f"Installer not found: {filename}", duration=3000, position=InfoBarPosition.TOP_RIGHT, parent=self)
            return

        # Extract in thread
        self._extract_in_thread(file_path, installer_data)

    def _validate_in_thread(self, file_path: Path, chunklist_data: bytes, installer_data: dict):
        """Validate installer in background thread"""
        from ..support import integrity_verification

        class ValidationWorker(QThread):
            finished = Signal(bool, str)
            progress = Signal(int, int)

            def __init__(self, file_path, chunklist_data):
                super().__init__()
                self.file_path = file_path
                self.chunklist_data = chunklist_data

            def run(self):
                try:
                    chunk_obj = integrity_verification.ChunklistVerification(self.file_path, self.chunklist_data)
                    chunk_obj.validate()

                    while chunk_obj.status == integrity_verification.ChunklistStatus.IN_PROGRESS:
                        self.progress.emit(chunk_obj.current_chunk, chunk_obj.total_chunks)
                        QThread.msleep(100)

                    if chunk_obj.status == integrity_verification.ChunklistStatus.FAILURE:
                        self.finished.emit(False, f"Hash mismatch on chunk {chunk_obj.current_chunk}")
                    else:
                        self.finished.emit(True, "Validation successful")
                except Exception as e:
                    self.finished.emit(False, str(e))

        worker = ValidationWorker(file_path, chunklist_data)
        worker.finished.connect(lambda success, msg: self._on_validation_finished(success, msg, installer_data))
        worker.start()

        InfoBar.info("Validating", "Validating installer integrity...", duration=2000, position=InfoBarPosition.TOP_RIGHT, parent=self)

    def _extract_in_thread(self, file_path: Path, installer_data: dict):
        """Extract installer in background thread"""
        from ..support import macos_installer_handler

        class ExtractionWorker(QThread):
            finished = Signal(bool, str)

            def __init__(self, file_path, constants):
                super().__init__()
                self.file_path = file_path
                self.constants = constants

            def run(self):
                try:
                    handler = macos_installer_handler.InstallerCreation(self.constants)
                    result = handler.install_macOS_installer(str(self.file_path.parent))
                    if result:
                        self.finished.emit(True, "Extraction successful")
                    else:
                        self.finished.emit(False, "Extraction failed")
                except Exception as e:
                    self.finished.emit(False, str(e))

        worker = ExtractionWorker(file_path, self.constants)
        worker.finished.connect(lambda success, msg: self._on_extraction_finished(success, msg, installer_data))
        worker.start()

        InfoBar.info("Extracting", "Extracting installer...", duration=2000, position=InfoBarPosition.TOP_RIGHT, parent=self)

    def _on_validation_finished(self, success: bool, message: str, installer_data: dict):
        """Handle validation completion"""
        if success:
            InfoBar.success("Validation Complete", message, duration=3000, position=InfoBarPosition.TOP_RIGHT, parent=self)
        else:
            InfoBar.error("Validation Failed", message, duration=5000, position=InfoBarPosition.TOP_RIGHT, parent=self)

    def _on_extraction_finished(self, success: bool, message: str, installer_data: dict):
        """Handle extraction completion"""
        if success:
            InfoBar.success("Extraction Complete", message, duration=3000, position=InfoBarPosition.TOP_RIGHT, parent=self)
        else:
            InfoBar.error("Extraction Failed", message, duration=5000, position=InfoBarPosition.TOP_RIGHT, parent=self)
