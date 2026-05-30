"""
gui_kdk.py: Kernel Debug Kit download interface
"""

from ..include import *
from .gui_support import DefGUI
from .gui_task import TaskManager

class NoAnimCardWidget(QFrame):
    """Simple card widget without hover animation"""

    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._borderRadius = 5

    def mouseReleaseEvent(self, e):
        super().mouseReleaseEvent(e)
        self.clicked.emit()

    def getBorderRadius(self):
        return self._borderRadius

    def setBorderRadius(self, radius: int):
        self._borderRadius = radius
        self.update()

    def paintEvent(self, e):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        r = self.borderRadius
        d = 2 * r

        isDark = isDarkTheme()

        # draw top border
        path = QPainterPath()
        path.arcMoveTo(1, h - d - 1, d, d, 240)
        path.arcTo(1, h - d - 1, d, d, 225, -60)
        path.lineTo(1, r)
        path.arcTo(1, 1, d, d, -180, -90)
        path.lineTo(w - r, 1)
        path.arcTo(w - d - 1, 1, d, d, 90, -90)
        path.lineTo(w - 1, h - r)
        path.arcTo(w - d - 1, h - d - 1, d, d, 0, -60)

        topBorderColor = QColor(0, 0, 0, 20)
        if isDark:
            topBorderColor = QColor(255, 255, 255, 13)
        else:
            topBorderColor = QColor(0, 0, 0, 15)

        painter.strokePath(path, topBorderColor)

        # draw bottom border
        path = QPainterPath()
        path.arcMoveTo(1, h - d - 1, d, d, 240)
        path.arcTo(1, h - d - 1, d, d, 240, 30)
        path.lineTo(w - r - 1, h - 1)
        path.arcTo(w - d - 1, h - d - 1, d, d, 270, 30)

        painter.strokePath(path, topBorderColor)

        # draw background
        painter.setPen(Qt.NoPen)
        bgColor = QColor(255, 255, 255, 13 if isDark else 170)
        painter.setBrush(bgColor)
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), r, r)

    borderRadius = Property(int, getBorderRadius, setBorderRadius)



class KDKCard(NoAnimCardWidget):
    """KDK card widget"""

    download_clicked = Signal(dict)

    def __init__(self, kdk_data: dict, constants: Constants, parent=None):
        super().__init__(parent)
        self.kdk_data = kdk_data
        self.constants = constants
        self.setFixedHeight(80)
        self.setBorderRadius(8)

        # Use version-specific Package icon (Packagexx.png where 11<=xx<=26)
        version = kdk_data.get("version", "Unknown")
        try:
            major_version = int(str(version).split('.')[0])
            icon_path = self.get_package_icon_path(major_version)
        except (ValueError, IndexError):
            icon_path = str(constants.payload_path / "Icon/AppIcons/Package.png")

        self.icon_widget = ImageLabel(icon_path, self)
        self.icon_widget.setFixedSize(48, 48)
        self.name=""

        def check_macos_veersion():
            build = kdk_data.get("build", "Unknown")[:2]
            if build=="25": self.name="Tahoe"
            if build=="24": self.name="Sequoia"
            if build=="23": self.name="Sonoma"
            if build=="22": self.name= "Ventura"
            else: self.name==""

        check_macos_veersion()

        self.title_label = BodyLabel(f"macOS {self.name}")
        self.title_label.setStyleSheet("font-weight: 600;")

        date_str = kdk_data.get("date", "Unknown")
        self.date_label = CaptionLabel(f"Release: {date_str}")

        version = kdk_data.get("version", "Unknown")
        build = kdk_data.get("build", "Unknown")
        
        file_size = kdk_data.get("fileSize", 0)
        size_mb = file_size / (1024 * 1024) if file_size else 0
        self.version_label = CaptionLabel(f"Version: {version} | Build: {build} | Size: {size_mb:.0f} MB")

        self.download_button = PrimaryPushButton("Download")
        self.download_button.setFixedWidth(100)
        self.download_button.clicked.connect(lambda: self.download_clicked.emit(self.kdk_data))

        self.copy_link_button = TransparentToolButton(FluentIcon.COPY)
        self.copy_link_button.setFixedSize(32, 32)
        self.copy_link_button.setToolTip("Copy Download Link")
        self.copy_link_button.clicked.connect(self._on_copy_link)

        self._init_layout()

    def get_package_icon_path(self, major_version: int) -> str:
        """
        Get package icon path for a given macOS major version.
        Returns PNG path with version-specific icon (Packagexx.png where 11<=xx<=26).

        Args:
            major_version: macOS major version (e.g., 11 for Big Sur, 15 for Sequoia)

        Returns:
            str: Path to package icon PNG file
        """
        # Map version to package icon index (11-26)
        if 11 <= major_version <= 26:
            version_to_index = {
                11: 1,  # Big Sur -> Package11
                12: 2,  # Monterey -> Package12
                13: 3,  # Ventura -> Package13
                14: 4,  # Sonoma -> Package14
                15: 5,  # Sequoia -> Package15
                26: 6,  # Tahoe -> Package26
            }
            index = version_to_index.get(major_version)
            if index is not None and index < len(self.constants.package_icns_paths):
                icns_path = self.constants.package_icns_paths[index]
                # Convert .icns to .png
                return icns_path.rsplit('.', 1)[0] + '.png'

        # Fallback to generic Package.png
        return str(self.constants.package_icns_path_generic.rsplit('.', 1)[0] + '.png')

    def _init_layout(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(16)
        layout.addWidget(self.icon_widget, 0, Qt.AlignmentFlag.AlignVCenter)

        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(4)
        info_layout.addWidget(self.title_label)
        info_layout.addWidget(self.date_label)
        info_layout.addWidget(self.version_label)
        layout.addLayout(info_layout, 1)

        layout.addWidget(self.copy_link_button, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.download_button, 0, Qt.AlignmentFlag.AlignVCenter)

    def _on_copy_link(self):
        url = self.kdk_data.get("url")
        if url:
            QApplication.clipboard().setText(url)
            InfoBar.success("Link Copied", "Download link copied to clipboard", duration=2000, position=InfoBarPosition.TOP_RIGHT, parent=self.window())


class KDKList(ScrollArea):
    """KDK list interface"""

    def __init__(self, global_constants: Constants, ui_support: DefGUI = None, global_settings: GlobalSettings = None, parent=None):
        super().__init__(parent)
        self.setObjectName("KDK")
        self.is_already_list: bool = False
        self.constants = global_constants
        self.settings = global_settings
        self.is_loading = False
        self.available_kdks = []
        self.available_kdks_latest = []
        self.show_latest_only = True
        self._data_worker = None  # Multi-process data worker

        self.scrollWidget = QWidget()
        self.expandLayout = QVBoxLayout(self.scrollWidget)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)
        self.enableTransparentBackground()

        self.expandLayout.setContentsMargins(SPACING["xxlarge"], SPACING["xlarge"], SPACING["xxlarge"], SPACING["xlarge"])
        self.expandLayout.setSpacing(SPACING["large"])

        self._init_header()
        self._init_loading()

        logging.info("[KDKList] Initialized")
        self.load_kdks()

    def get_package_icon_path(self, major_version: int) -> str:
        """
        Get package icon path for a given macOS major version.
        Returns PNG path with version-specific icon (Packagexx.png where 11<=xx<=26).

        Args:
            major_version: macOS major version (e.g., 11 for Big Sur, 15 for Sequoia)

        Returns:
            str: Path to package icon PNG file
        """
        # Map version to package icon index (11-26)
        if 11 <= major_version <= 26:
            version_to_index = {
                11: 1,  # Big Sur -> Package11
                12: 2,  # Monterey -> Package12
                13: 3,  # Ventura -> Package13
                14: 4,  # Sonoma -> Package14
                15: 5,  # Sequoia -> Package15
                26: 6,  # Tahoe -> Package26
            }
            index = version_to_index.get(major_version)
            if index is not None and index < len(self.constants.package_icns_paths):
                icns_path = self.constants.package_icns_paths[index]
                # Convert .icns to .png
                return icns_path.rsplit('.', 1)[0] + '.png'

        # Fallback to generic Package.png
        return str(self.constants.package_icns_path_generic.rsplit('.', 1)[0] + '.png')

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

    def _init_loading(self):
        """Initialize loading indicator"""
        self.loading_container = QWidget()
        loading_layout = QVBoxLayout(self.loading_container)
        loading_layout.setContentsMargins(0, 0, 0, 0)
        loading_layout.setSpacing(SPACING["medium"])
        loading_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_ring = IndeterminateProgressRing(self)
        self.progress_ring.setFixedSize(48, 48)
        self.loading_label = BodyLabel("Loading KDKs...")
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading_layout.addWidget(self.progress_ring, 0, Qt.AlignmentFlag.AlignCenter)
        loading_layout.addWidget(self.loading_label, 0, Qt.AlignmentFlag.AlignCenter)
        self.expandLayout.addWidget(self.loading_container)
        self.loading_container.setVisible(False)

    def load_kdks(self):
        """Load KDK data using multi-process worker."""
        self._show_loading(True)

        # Clean up old worker
        if self._data_worker is not None:
            self._data_worker.stop()
            self._data_worker = None

        # Create new data processing worker
        from ..support.multiprocess_data_handler import DataProcessorWorker

        self._data_worker = DataProcessorWorker(
            self.constants.kdk_api_link,
            "kdk",
            self
        )
        self._data_worker.data_ready.connect(self._on_data_ready)
        self._data_worker.error_occurred.connect(self._on_data_error)
        self._data_worker.start_processing()

    def _on_data_ready(self, data: dict):
        """Callback when data processing completes."""
        self.available_kdks = data.get("all", [])
        self.available_kdks_latest = data.get("latest", [])
        self._display_kdks()

    def _on_data_error(self, error_msg: str):
        """Callback when data processing fails."""
        logging.error(f"[KDKList] Failed to process data: {error_msg}")
        self._show_loading(False)

        # Show error notification
        from qfluentwidgets import InfoBar, InfoBarPosition

        InfoBar.error(
            "Loading Failed",
            f"Failed to load KDK packages: {error_msg}",
            duration=5000,
            position=InfoBarPosition.TOP_RIGHT,
            parent=self
        )

    def _on_latest_toggle(self, checked: bool):
        """Handle latest-only toggle"""
        self.show_latest_only = checked
        self.is_loading = False
        # Clear all widgets from layout
        while self.expandLayout.count():
            item = self.expandLayout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._init_loading()
        self._show_loading(True)
        if self.available_kdks:
            QTimer.singleShot(800, lambda: self._display_kdks())
            

    def _show_loading(self, show: bool):
        if show:
            self.loading_container.setVisible(True)
            self.progress_ring.setVisible(True)
            self.progress_ring.start()
        else:
            self.progress_ring.stop()
            self.progress_ring.setVisible(False)
            self.loading_container.setVisible(False)

    def _display_kdks(self):
        # Clear all widgets from layout
        self.is_loading = True
        while self.expandLayout.count():
            item = self.expandLayout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Re-add header and loading container
        self._init_header()
        self.header_container.setVisible(True)
        self._init_loading()
        
        kdks = self.available_kdks_latest if self.show_latest_only else self.available_kdks

        if not kdks:
            label = BodyLabel("No KDK packages available")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.expandLayout.addWidget(label)
            return
        
        self.is_already_list = True

        # Limit to 4 cards only when showing latest only
        if self.show_latest_only:
            kdks = kdks[:4]

        self._render_batch(0, kdks)

    def _render_batch(self, start_index: int, kdks: list, batch_size: int = 10):
        if self.is_loading:
            """Batch render cards to avoid UI freeze"""
            end_index = min(start_index + batch_size, len(kdks))

            # Show loading progress
            total = len(kdks)
            if hasattr(self, 'loading_label'):
                self.loading_label.setText(f"Loading KDKs... ({end_index}/{total})")

            for i in range(start_index, end_index):
                kdk = kdks[i]
                card = KDKCard(kdk, self.constants, self)
                card.download_clicked.connect(self._on_download)
                self.expandLayout.addWidget(card)

            if end_index < len(kdks):
                QTimer.singleShot(50, lambda: self._render_batch(end_index, kdks, batch_size))
            else:
                self.expandLayout.addStretch()
                self._show_loading(False)
        else:
            # Clear all widgets from layout
            while self.expandLayout.count():
                item = self.expandLayout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            self._init_loading()
            self._show_loading(True)
            if self.available_kdks:
                QTimer.singleShot(800, lambda: self._display_kdks())
            
            

    def _on_download(self, kdk_data: dict):
        url = kdk_data.get("url")
        version = kdk_data.get("version")
        build = kdk_data.get("build")

        # Unified logging style
        logging.info(f"[KDK] Starting download: Kernel Debug Kit ({version} - {build})")
        logging.info(f"[KDK] URL: {url}")

        save_path = self.settings.find_key("download_path") or str(self.constants.payload_path)
        filename = f"KDK_{version}_{build}.dmg"
        download_obj = DownloadObject(url, save_path, filename)

        # Use version-specific Package icon (Packagexx.png where 11<=xx<=26)
        try:
            major_version = int(str(version).split('.')[0])
            icon_path = self.get_package_icon_path(major_version)
        except (ValueError, IndexError):
            icon_path = str(self.constants.payload_path / "Icon/AppIcons/Package.png")

        TaskManager.start_download(download_obj, icon=icon_path)

        InfoBar.success("Download Started", f"{filename} is downloading.", duration=3000, position=InfoBarPosition.TOP_RIGHT, parent=self)

    def closeEvent(self, event):
        """Clean up resources when window closes."""
        if self._data_worker is not None:
            self._data_worker.stop()
            self._data_worker = None
        super().closeEvent(event)

