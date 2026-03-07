"""
gui_kdk.py: Kernel Debug Kit download interface
"""

from ..include import *
from .gui_support import DefGUI
from ..UIkit.components.widgets.card_widget import CardWidget
from ..UIkit.components.widgets.label import BodyLabel, CaptionLabel
from ..UIkit.components.widgets.button import PrimaryPushButton, TransparentToolButton
from ..UIkit.components.widgets.label import ImageLabel
from ..UIkit.components.widgets.progress_ring import IndeterminateProgressRing
from ..support.network_handler import DownloadObject
from .gui_task import TaskManager
import requests
import threading


class KDKCard(CardWidget):
    """KDK card widget"""

    download_clicked = Signal(dict)

    def __init__(self, kdk_data: dict, constants: Constants, parent=None):
        super().__init__(parent)
        self.kdk_data = kdk_data
        self.constants = constants
        self.setFixedHeight(80)
        self.setBorderRadius(8)

        icon_path = str(constants.payload_path / "Icon/AppIcons/Package.png")
        self.icon_widget = ImageLabel(icon_path, self)
        self.icon_widget.setFixedSize(48, 48)

        self.title_label = BodyLabel("Kernel Debug Kit")
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
        self.constants = global_constants
        self.settings = global_settings
        self.available_kdks = []

        self.scrollWidget = QWidget()
        self.expandLayout = QVBoxLayout(self.scrollWidget)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)
        self.enableTransparentBackground()

        self.expandLayout.setContentsMargins(SPACING["xxlarge"], SPACING["xlarge"], SPACING["xxlarge"], SPACING["xlarge"])
        self.expandLayout.setSpacing(SPACING["large"])

        self.loading_container = QWidget()
        loading_layout = QVBoxLayout(self.loading_container)
        loading_layout.setContentsMargins(0, 0, 0, 0)
        loading_layout.setSpacing(SPACING["medium"])
        loading_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_ring = IndeterminateProgressRing(self)
        self.progress_ring.setFixedSize(48, 48)
        self.loading_label = BodyLabel("Fetching packages...")
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading_layout.addWidget(self.progress_ring, 0, Qt.AlignmentFlag.AlignCenter)
        loading_layout.addWidget(self.loading_label, 0, Qt.AlignmentFlag.AlignCenter)
        self.expandLayout.addWidget(self.loading_container)
        self.loading_container.setVisible(False)

        logging.info("KDKList initialized")
        self.load_kdks()

    def load_kdks(self):
        self._show_loading(True)

        def _fetch():
            try:
                response = requests.get(self.constants.kdk_api_link, timeout=10)
                if response.status_code == 200:
                    self.available_kdks = response.json()
                    self.available_kdks.sort(key=lambda x: (x.get("build", ""), x.get("version", "")), reverse=True)
            except Exception as e:
                logging.error(f"Failed to fetch KDK data: {e}")

        thread = threading.Thread(target=_fetch)
        thread.start()

        def _check():
            if thread.is_alive():
                QTimer.singleShot(100, _check)
                return
            self._show_loading(False)
            self._display_kdks()

        QTimer.singleShot(100, _check)

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
        while self.expandLayout.count() > 1:
            item = self.expandLayout.takeAt(1)
            if item.widget():
                item.widget().deleteLater()

        if not self.available_kdks:
            label = BodyLabel("No KDK packages available")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.expandLayout.addWidget(label)
            return

        self._render_batch(0)

    def _render_batch(self, start_index: int, batch_size: int = 20):
        """Batch render cards to avoid UI freeze"""
        end_index = min(start_index + batch_size, len(self.available_kdks))

        for i in range(start_index, end_index):
            kdk = self.available_kdks[i]
            card = KDKCard(kdk, self.constants, self)
            card.download_clicked.connect(self._on_download)
            self.expandLayout.addWidget(card)

        if end_index < len(self.available_kdks):
            QTimer.singleShot(10, lambda: self._render_batch(end_index, batch_size))
        else:
            self.expandLayout.addStretch()

    def _on_download(self, kdk_data: dict):
        url = kdk_data.get("url")
        version = kdk_data.get("version")
        build = kdk_data.get("build")

        save_path = self.settings.find_key("download_path") or str(self.constants.payload_path)
        filename = f"KDK_{version}_{build}.dmg"
        download_obj = DownloadObject(url, save_path, filename)

        icon_path = str(self.constants.payload_path / "Icon/AppIcons/Package.png")
        TaskManager.start_download(download_obj, icon=icon_path)

        InfoBar.success("Download Started", f"{filename} is downloading. Check Tasks for progress.", duration=3000, position=InfoBarPosition.TOP_RIGHT, parent=self)

