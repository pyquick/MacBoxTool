"""
gui_metallib.py: Metallib Support Package download interface
"""

from ..include import *
from ..support.ui.qt_helpers import WorkerShutdownMixin, clear_layout
from .gui_support import DefGUI
from ..support.net.network_handler import DownloadObject
from ..support.artifacts.kdk_sort import build_letter_to_minor, sort_packages
from ..support.artifacts.build_version import (
    build_to_kernel,
    build_to_marketing_name,
    version_major_minor,
)
from ..support.ui.cards import NoAnimCardWidget
from ..support.ui.package_icon import package_icon_path
from .gui_task import TaskManager
import re


def build_to_display_version(item):
    build = item.get("build", "")
    kernel_major = build_to_kernel(build)
    match = re.match(r'^\d+([A-Za-z])', str(build or ""))
    if kernel_major is None or not match:
        return item.get("version", "Unknown")

    major_version = os_data.os_conversion.kernel_to_os(kernel_major)
    minor_version = build_letter_to_minor(match.group(1))
    expected_version = f"{major_version}.{minor_version}"
    upstream_version = item.get("version", "Unknown")
    upstream_major_minor = version_major_minor(upstream_version)

    if kernel_major == 24 and match.group(1).upper() == "G" and upstream_major_minor:
        upstream_major, upstream_minor = upstream_major_minor
        if upstream_major == 15 and 6 <= upstream_minor <= 99:
            return upstream_version

    if upstream_major_minor == (int(major_version), minor_version):
        return upstream_version
    return expected_version


def display_version_major(item):
    try:
        return int(str(build_to_display_version(item)).split('.')[0])
    except (ValueError, IndexError):
        return 0


def sort_by_build(items):
    return sort_packages(items)



class MetallibCard(NoAnimCardWidget):
    """Metallib card widget"""

    download_clicked = Signal(dict)

    def __init__(self, metallib_data: dict, constants: Constants, parent=None):
        super().__init__(parent)
        self.metallib_data = metallib_data
        self.constants = constants
        self.setFixedHeight(80)
        self.setBorderRadius(12)

        # 使用 build 推断显示版本，避免上游 beta version 错误。
        major_version = display_version_major(metallib_data)
        icon_path = package_icon_path(constants, major_version, require_exists=False)

        self.icon_widget = ImageLabel(icon_path, self)
        self.icon_widget.setFixedSize(48, 48)

        name = build_to_marketing_name(metallib_data)
        self.title_label = BodyLabel(f"macOS {name}" if name else "macOS")
        self.title_label.setStyleSheet("font-weight: 600;")

        date_str = metallib_data.get("date", "Unknown")
        self.date_label = CaptionLabel(f"Release: {date_str}")

        version = build_to_display_version(metallib_data)
        build = metallib_data.get("build", "Unknown")
        self.version_label = CaptionLabel(f"Version: {version} | Build: {build}")

        self.download_button = PrimaryPushButton("Download")
        self.download_button.setFixedWidth(100)
        self.download_button.clicked.connect(lambda: self.download_clicked.emit(self.metallib_data))

        self.copy_link_button = TransparentToolButton(FluentIcon.COPY)
        self.copy_link_button.setFixedSize(32, 32)
        self.copy_link_button.setToolTip("Copy Download Link")
        self.copy_link_button.clicked.connect(self._on_copy_link)

        self._init_layout()

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
        url = self.metallib_data.get("url")
        if url:
            QApplication.clipboard().setText(url)
            InfoBar.success(
                "Link Copied",
                "Download link copied to clipboard",
                duration=2000,
                position=InfoBarPosition.BOTTOM_RIGHT,
                parent=self.window(),
            )


class MetallibList(WorkerShutdownMixin, ScrollArea):
    """Metallib list interface"""

    def __init__(self, global_constants: Constants, ui_support: DefGUI = None, global_settings: GlobalSettings = None, parent=None):
        super().__init__(parent)
        self.setObjectName("Metallib")
        self.constants = global_constants
        self.settings = global_settings
        self.available_metallibs = []
        self.available_metallibs_latest = []
        self.show_latest_only = True
        self.is_loading = False
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

        logging.info("[MetalLibList] Initialized")
        self.load_metallibs()

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
        self.loading_label = BodyLabel("Loading Metallibs...")
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading_layout.addWidget(self.progress_ring, 0, Qt.AlignmentFlag.AlignCenter)
        loading_layout.addWidget(self.loading_label, 0, Qt.AlignmentFlag.AlignCenter)
        self.expandLayout.addWidget(self.loading_container)
        self.loading_container.setVisible(False)

    def load_metallibs(self):
        """Load MetalLib data using multi-process worker."""
        self._show_loading(True)

        # Clean up old worker
        if self._data_worker is not None:
            self._data_worker.stop()
            self._data_worker = None

        # Create new data processing worker
        from ..support.artifacts.multiprocess_data_handler import DataProcessorWorker

        self._data_worker = DataProcessorWorker(
            self.constants.metallib_api_link,
            "metallib",
            self
        )
        self._data_worker.data_ready.connect(self._on_data_ready)
        self._data_worker.error_occurred.connect(self._on_data_error)
        self._data_worker.start_processing()

    def _on_data_ready(self, data: dict):
        """Callback when data processing completes."""
        metallibs = sort_by_build(data.get("all", []))
        if not metallibs:
            metallibs = sort_by_build(data.get("latest", []))

        self.available_metallibs = metallibs
        self.available_metallibs_latest = metallibs[:4]
        self._display_metallibs()

    def _on_data_error(self, error_msg: str):
        """Callback when data processing fails."""
        logging.error(f"[MetalLibList] Failed to process data: {error_msg}")
        self._show_loading(False)

        # Show error notification
        from ..UIkit import InfoBar, InfoBarPosition

        InfoBar.error(
            "Loading Failed",
            f"Failed to load MetalLib packages: {error_msg}",
            duration=5000,
            position=InfoBarPosition.BOTTOM_RIGHT,
            parent=self
        )

    def _on_latest_toggle(self, checked: bool):
        """Handle latest-only toggle"""
        self.show_latest_only = checked
        self.is_loading = False
        clear_layout(self.expandLayout)
        self._init_loading()
        self._show_loading(True)
        if self.available_metallibs:
            QTimer.singleShot(800,lambda:self._display_metallibs())

    def _show_loading(self, show: bool):
        if show:
            self.loading_container.setVisible(True)
            self.progress_ring.setVisible(True)
            self.progress_ring.start()
        else:
            self.progress_ring.stop()
            self.progress_ring.setVisible(False)
            self.loading_container.setVisible(False)

    def _display_metallibs(self):
        # Clear all widgets from layout
        self.is_loading = True
        clear_layout(self.expandLayout)

        # Re-add header and loading container
        self._init_header()
        self.header_container.setVisible(True)
        self._init_loading()

        metallibs = self.available_metallibs_latest if self.show_latest_only else self.available_metallibs

        if not metallibs:
            label = BodyLabel("No Metallib packages available")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.expandLayout.addWidget(label)
            return

        # Limit to 4 cards only when showing latest only
        if self.show_latest_only:
            metallibs = metallibs[:4]
            logging.info("[MetalLibList] Latest mode: limiting to 4 cards")

        self._render_batch(0, metallibs)

    def _render_batch(self, start_index: int, metallibs: list, batch_size: int = 10):
        """Batch render cards to avoid UI freeze"""
        
        end_index = min(start_index + batch_size, len(metallibs))
        if self.is_loading:
            # Show loading progress
            total = len(metallibs)
            if hasattr(self, 'loading_label'):
                self.loading_label.setText(f"Loading Metallibs... ({end_index}/{total})")

            for i in range(start_index, end_index):
                metallib = metallibs[i]
                card = MetallibCard(metallib, self.constants, self)
                card.download_clicked.connect(self._on_download)
                self.expandLayout.addWidget(card)

            if end_index < len(metallibs):
                QTimer.singleShot(50, lambda: self._render_batch(end_index, metallibs, batch_size))
            else:
                self.expandLayout.addStretch()
                self._show_loading(False)
        else:
            # Clear all widgets from layout
            clear_layout(self.expandLayout)
            self._init_loading()
            self._show_loading(True)
            if self.available_metallibs:
                QTimer.singleShot(800, lambda: self._display_metallibs())

    def _on_download(self, metallib_data: dict):
        url = metallib_data.get("url")
        version = build_to_display_version(metallib_data)
        build = metallib_data.get("build")

        # Unified logging style
        logging.info(f"[MetalLib] Starting download: MetalLib Support Package ({version} - {build})")
        logging.info(f"[MetalLib] URL: {url}")

        save_path = self.settings.find_key("download_path") or str(self.constants.payload_path)
        filename = f"MetallibSupportPkg-{version}-{build}.pkg"
        download_obj = DownloadObject(url, save_path, filename)

        # 使用 build 推断显示版本，避免上游 beta version 错误。
        major_version = display_version_major(metallib_data)
        icon_path = package_icon_path(self.constants, major_version, require_exists=False)

        TaskManager.start_download(download_obj, icon=icon_path)

        InfoBar.success("Download Started", f"{filename} is downloading.", duration=3000, position=InfoBarPosition.BOTTOM_RIGHT, parent=self)

    def cleanup_workers(self, deadline=None):
        """Stop the data-processing worker before this page is destroyed."""
        if self._data_worker is not None:
            self._data_worker.stop()
            self._data_worker = None

