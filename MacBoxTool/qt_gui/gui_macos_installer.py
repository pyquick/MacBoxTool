"""
gui_macos_installer.py: macOS Installer list with InstallerCard
"""

from ..include import *
from .. import sucatalog
from .gui_support import DefGUI
from .gui_task import TaskManager
from concurrent.futures import ThreadPoolExecutor, as_completed
import sys


def _installer_download_size(installer_data: dict) -> int:
    install_assistant = installer_data.get("InstallAssistant") or {}
    components = install_assistant.get("LegacyComponents") or []

    if components:
        total_size = 0
        for component in components:
            try:
                total_size += int(component.get("Size", 0) or 0)
            except (AttributeError, TypeError, ValueError):
                continue
        if total_size:
            return total_size

    try:
        return max(0, int(install_assistant.get("Size", 0) or 0))
    except (TypeError, ValueError):
        return 0


def _format_file_size(size: int) -> str:
    if size <= 0:
        return "Unknown"

    units = ("B", "KB", "MB", "GB", "TB")
    value = float(size)
    unit_index = 0
    while value >= 1024 and unit_index < len(units) - 1:
        value /= 1024
        unit_index += 1

    if unit_index == 0:
        return f"{int(value)} {units[unit_index]}"
    return f"{value:.2f} {units[unit_index]}"


def _installer_icon_path(installer_data: dict, constants: Constants) -> str:
    install_assistant = installer_data.get("InstallAssistant") or {}
    xnu_major = install_assistant.get("XNUMajor", 0)

    if not xnu_major:
        from ..datasets.os_data import os_conversion
        version = installer_data.get("Version", "0.0.0")
        try:
            if version.startswith("10."):
                xnu_major = os_conversion.os_to_kernel(version)
            else:
                xnu_major = int(version.split(".")[0]) + 9
        except (TypeError, ValueError, IndexError):
            xnu_major = 0

    if 11 <= xnu_major < 20:
        icon_paths = constants.icon_path_legacy
        icon_index = 20 - xnu_major
    elif xnu_major >= 20:
        icon_paths = constants.icons_path
        icon_index = xnu_major - 19
    else:
        icon_paths = constants.icons_path
        icon_index = 0

    try:
        icon_path = icon_paths[icon_index]
    except (IndexError, TypeError):
        icon_path = constants.icon_path_macos_generic

    png_path = str(Path(icon_path).with_suffix(".png"))
    if not Path(png_path).exists():
        logging.warning(f"Icon not found: {png_path}, falling back to Generic")
        png_path = str(Path(constants.icon_path_macos_generic).with_suffix(".png"))

    return png_path


class InstallerCard(CardWidget):
    """Installer card widget for displaying macOS installer info"""

    download_clicked = Signal(dict)

    def __init__(self, installer_data: dict, constants: Constants, parent=None):
        super().__init__(parent)
        self.installer_data = installer_data
        self.constants = constants

        logging.info(f"[InstallerCard] Initializing: {installer_data.get('Title', 'Unknown')}")
        self._init_card()
        self._init_icon()
        self._init_info_labels()
        self._init_download_button()
        self._init_layout()

    # ── Sub-init Methods ──

    def _init_card(self):
        """Initialize card size and border"""
        self.setFixedHeight(96)

    def _init_icon(self):
        """Initialize macOS icon widget using XNUMajor"""
        self.icon_widget = ImageLabel(
            _installer_icon_path(self.installer_data, self.constants), self
        )
        self.icon_widget.setFixedSize(48, 48)

    def _init_info_labels(self):
        """Initialize title, date, version, and size labels"""
        title = self.installer_data.get("Title", "Unknown")
        build = self.installer_data.get("Build", "Unknown")
        self.title_label = BodyLabel(f"{title} {build}")
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

        size = _installer_download_size(self.installer_data)
        self.size_label = CaptionLabel(f"Size: {_format_file_size(size)}")

    def _init_download_button(self):
        """Initialize download button"""
        self.download_button = PrimaryPushButton("Download")
        self.download_button.setFixedWidth(100)
        self.download_button.clicked.connect(self._on_download_clicked)

        

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
        self.info_layout.addWidget(self.size_label, 0, Qt.AlignmentFlag.AlignVCenter)
        self.info_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.main_layout.addLayout(self.info_layout, 1)

        # Right: Download button
        self.main_layout.addWidget(self.copy_link_button, 0, Qt.AlignmentFlag.AlignVCenter)
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
                position=InfoBarPosition.BOTTOM_RIGHT,
                parent=self
            )

    


class MacOSInstallerList(ScrollArea):
    """Scrollable list of macOS installers"""

    def __init__(self, global_constants: Constants, ui_support: DefGUI = None, global_settings: GlobalSettings = None, parent=None):
        super().__init__(parent)

        self.setObjectName("MacOSInstaller")
        self.constants = global_constants
        self.ui_support = ui_support
        self.settings = global_settings

        logging.info("[MacOSInstallerList] Initialized")

        # Data
        self.available_installers = []
        self.available_installers_latest = []
        self.show_latest_only = True

        # Worker threads (keep references to prevent premature garbage collection)
        self._validation_worker = None
        self._extraction_worker = None

        # Loading state control
        self._loading_thread = None
        self._stop_loading = False

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
        # Interrupt previous loading if any
        if self._loading_thread and self._loading_thread.is_alive():
            logging.info("[MacOSInstallerList] Interrupting previous loading...")
            self._stop_loading = True
            # Wait for previous thread to finish (max 1 second)
            self._loading_thread.join(timeout=1.0)

        # Reset stop flag
        self._stop_loading = False

        logging.info("[MacOSInstallerList] Loading installers...")
        logging.info(f"[MacOSInstallerList] Catalog seed: {sucatalog.SeedType.DeveloperSeed.name}")

        self._show_loading(True)

        def _fetch_installers():
            if self._stop_loading:
                logging.info("[MacOSInstallerList] Loading was interrupted")
                return

            logging.info(f"[MacOSInstallerList] Loading catalog from: {sucatalog.SeedType.DeveloperSeed.name}")

            sucatalog_contents = sucatalog.CatalogURL(seed=sucatalog.SeedType.DeveloperSeed).url_contents

            if self._stop_loading:
                logging.info("[MacOSInstallerList] Loading was interrupted during fetch")
                return

            if sucatalog_contents is None:
                logging.error("Failed to download Installer Catalog from Apple")
                return

            catalog_versions = []
            did_find_latest = False
            for catalog_version in sucatalog.CatalogVersion:
                if not did_find_latest:
                    if catalog_version != sucatalog.CatalogVersion.GOLDEN_GATE:
                        continue
                    did_find_latest = True

                if catalog_version == sucatalog.CatalogVersion.BIG_SUR:
                    continue
                if catalog_version != sucatalog.CatalogVersion.GOLDEN_GATE:
                    catalog_versions.append(catalog_version)
                if catalog_version == sucatalog.CatalogVersion.SONOMA:
                    break

            def _fetch_catalog(version):
                logging.info(
                    f"[MacOSInstallerList] Loading catalog from: {version.name} "
                    f"{sucatalog.SeedType.DeveloperSeed.name}"
                )
                return version, sucatalog.CatalogURL(
                    version=version,
                    seed=sucatalog.SeedType.DeveloperSeed,
                ).url_contents

            with ThreadPoolExecutor(max_workers=min(4, len(catalog_versions))) as executor:
                futures = [executor.submit(_fetch_catalog, version) for version in catalog_versions]
                for future in as_completed(futures):
                    if self._stop_loading:
                        logging.info("[MacOSInstallerList] Loading was interrupted during catalog fetch")
                        executor.shutdown(wait=False, cancel_futures=True)
                        return
                    catalog_version, seed_contents = future.result()
                    if seed_contents is not None:
                        sucatalog_contents["Products"].update(seed_contents.get("Products", {}))

            catalog_products = sucatalog.CatalogProducts(sucatalog_contents)
            self.available_installers = catalog_products.products
            self.available_installers.sort(key=lambda x: x.get("Build", ""), reverse=True)
            self.available_installers_latest = catalog_products.latest_products

        thread = threading.Thread(target=_fetch_installers)
        self._loading_thread = thread
        thread.start()

        # Poll thread completion without blocking UI
        def _check_thread():
            if thread.is_alive():
                if not self._stop_loading:
                    QTimer.singleShot(100, _check_thread)
                return

            # Thread finished or was interrupted
            if self._stop_loading:
                logging.info("[MacOSInstallerList] Previous loading was interrupted, starting new load...")
                return

            if not self.available_installers and not self.available_installers_latest:
                self._show_error("Failed to download catalog")
                logging.error("[MacOSInstallerList] Failed to load installers")
                return

            logging.info(f"[MacOSInstallerList] Loaded {len(self.available_installers)} installers ({len(self.available_installers_latest)} latest)")

            for i, installer in enumerate(self.available_installers):
                title = installer.get("Title", "Unknown")
                version = installer.get("Version", "Unknown")
                build = installer.get("Build", "Unknown")
                post_date = installer.get("PostDate", "Unknown")
                install_assistant = installer.get("InstallAssistant") or {}
                size = install_assistant.get("Size", 0)
                size_mb = size / (1024 * 1024) if size else 0
                logging.info(f"[MacOSInstallerList] [{i+1}] {title} ({version} - {build}) | {size_mb:.2f} MB | {post_date}")

            logging.info("[MacOSInstallerList] Load completed successfully")

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
        self._clear_layout()
        self.init_ui()
        self._show_loading(True)
        
        if self.available_installers:
            QTimer.singleShot(800, lambda: self._display_installers())
            

    def _display_installers(self):
        """Display installer cards"""
        logging.info("[MacOSInstallerList] Displaying installers...")

        self._clear_layout()
        self._init_header()
        self.header_container.setVisible(True)

        installers = self.available_installers_latest if self.show_latest_only else self.available_installers

        # On Windows, filter out macOS 10.15 (Catalina) and earlier —
        # only macOS 11 (Big Sur) and above are supported
        if sys.platform == "win32":
            installers = [
                i for i in installers
                if self._installer_is_supported_on_windows(i)
            ]

        if not installers:
            logging.warning("[MacOSInstallerList] No installers available to display")
            no_data_label = BodyLabel("No installers available")
            no_data_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.expandLayout.addWidget(no_data_label)
            return

        # Limit to 4 cards only when showing latest only
        if self.show_latest_only:
            installers = installers[:4]
            logging.info("[MacOSInstallerList] Latest mode: limiting to 4 cards")

        logging.info(f"[MacOSInstallerList] Creating {len(installers)} cards...")

        for installer in installers:
            card = InstallerCard(installer, self.constants, self)
            card.download_clicked.connect(self._on_download_clicked)
            self.expandLayout.addWidget(card)

        self.expandLayout.addStretch(1)

        logging.info(f"[MacOSInstallerList] Displayed {len(installers)} cards")

    @staticmethod
    def _installer_is_supported_on_windows(installer: dict) -> bool:
        """
        Return False for macOS 10.15 (Catalina) and earlier on Windows.
        Only macOS 11 (Big Sur) and above are supported.
        """
        version = installer.get("Version", "0.0.0")
        try:
            parts = version.split(".")
            major = int(parts[0])
            # 10.x → only 10.16+ (i.e. 11+; 10.15 is Catalina, unsupported)
            if major == 10:
                if len(parts) >= 2:
                    return int(parts[1]) >= 16
                return False
            return major >= 11
        except (ValueError, IndexError):
            return True  # let unfamiliar versions through

    # ── Actions ──

    def _on_download_clicked(self, installer_data: dict):
        """Handle download button click - start actual download"""
        title = installer_data.get("Title", "Unknown")
        version = installer_data.get("Version", "Unknown")
        build = installer_data.get("Build", "Unknown")

        install_assistant = installer_data.get("InstallAssistant") or {}
        url = install_assistant.get("URL")
        integrity_data_url = install_assistant.get("IntegrityDataURL")  # Get chunklist URL
        legacy_installer = install_assistant.get("LegacyInstaller", False)
        requires_validation = install_assistant.get("RequiresValidation", False)
        requires_extraction = install_assistant.get("RequiresExtraction", False)
        legacy_components = install_assistant.get("LegacyComponents", [])

        if not url:
            logging.warning(f"[MacOSInstallerList] No download URL for {title}")
            InfoBar.error(
                "Download Failed",
                "No download URL available for this installer.",
                duration=3000,
                position=InfoBarPosition.BOTTOM_RIGHT,
                parent=self,
            )
            return

        if not integrity_data_url and not legacy_installer:
            logging.warning(f"[MacOSInstallerList] No IntegrityDataURL for {title}")

        logging.info(f"[MacOSInstaller] Starting download: {title} ({version} - {build})")
        logging.info(f"[MacOSInstaller] URL: {url}")

        png_path = _installer_icon_path(installer_data, self.constants)

        save_path = str(self.constants.payload_path)
        direct_download = install_assistant.get("DirectDownload", False)
        filename = Path(url).name if direct_download else "InstallAssistant.pkg"
        download_obj = DownloadObject(url, save_path, filename)
        download_obj.display_name = f"{title} {build}"
        download_obj.total_size = _installer_download_size(installer_data)

        if legacy_components:
            app_names = {
                "10.13": "Install macOS High Sierra.app",
                "10.14": "Install macOS Mojave.app",
                "10.15": "Install macOS Catalina.app",
            }
            download_obj.components = legacy_components
            download_obj.installer_app_name = next(
                (
                    app_name for version_prefix, app_name in app_names.items()
                    if version.startswith(version_prefix)
                ),
                None,
            )
            destination = (
                Path("/Applications") / download_obj.installer_app_name
                if download_obj.installer_app_name else None
            )
            if destination and destination.exists():
                answer = QMessageBox.question(
                    self.window(),
                    "Replace Existing Installer",
                    f"{destination} already exists. Replace it after downloading?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if answer != QMessageBox.StandardButton.Yes:
                    return
                download_obj.replace_existing_app = True

        # Store chunklist URL for validation
        download_obj.chunklist_url = integrity_data_url
        download_obj.legacy_installer = legacy_installer
        download_obj.requires_validation = requires_validation
        download_obj.requires_extraction = requires_extraction

        TaskManager.start_download(download_obj, icon=png_path)

        InfoBar.success(
            "Download Started",
            f"{title} ({version} - {build}) is downloading.",
            duration=2000,
            position=InfoBarPosition.BOTTOM_RIGHT,
            parent=self,
        )

    def cleanup_workers(self):
        """Clean up any running worker threads"""
        # Stop loading thread
        if self._loading_thread is not None and self._loading_thread.is_alive():
            self._stop_loading = True
            self._loading_thread.join(timeout=1.0)
            self._loading_thread = None

        if self._validation_worker is not None:
            if self._validation_worker.isRunning():
                self._validation_worker.cancel()
                self._validation_worker.requestInterruption()
                if not self._validation_worker.wait(5000):
                    logging.warning("ValidationWorker did not stop in 5000ms; terminating")
                    self._validation_worker.terminate()
                    self._validation_worker.wait(1000)
            self._validation_worker.deleteLater()
            self._validation_worker = None

        if self._extraction_worker is not None:
            if self._extraction_worker.isRunning():
                self._extraction_worker.cancel()
                self._extraction_worker.requestInterruption()
                if not self._extraction_worker.wait(5000):
                    logging.warning("ExtractionWorker did not stop in 5000ms; terminating")
                    self._extraction_worker.terminate()
                    self._extraction_worker.wait(1000)
            self._extraction_worker.deleteLater()
            self._extraction_worker = None

    def closeEvent(self, event):
        """Handle window close event"""
        self.cleanup_workers()
        super().closeEvent(event)
