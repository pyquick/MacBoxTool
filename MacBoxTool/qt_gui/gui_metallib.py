"""
gui_metallib.py: Metallib Support Package download interface
"""

from ..include import *
from .gui_support import DefGUI
from ..UIkit.components.widgets.label import BodyLabel, CaptionLabel
from ..UIkit.components.widgets.button import PrimaryPushButton, TransparentToolButton
from ..UIkit.components.widgets.label import ImageLabel
from ..UIkit.components.widgets.progress_ring import IndeterminateProgressRing
from ..UIkit.components.widgets.switch_button import SwitchButton
from ..UIkit.common.style_sheet import isDarkTheme
from ..support.network_handler import DownloadObject
from .gui_task import TaskManager
from PySide6.QtWidgets import QFrame
from PySide6.QtGui import QPainter, QColor, QPainterPath
import requests
import threading


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


class MetallibCard(NoAnimCardWidget):
    """Metallib card widget"""

    download_clicked = Signal(dict)

    def __init__(self, metallib_data: dict, constants: Constants, parent=None):
        super().__init__(parent)
        self.metallib_data = metallib_data
        self.constants = constants
        self.setFixedHeight(80)
        self.setBorderRadius(8)

        icon_path = str(constants.payload_path / "Icon/AppIcons/Package.png")
        self.icon_widget = ImageLabel(icon_path, self)
        self.icon_widget.setFixedSize(48, 48)

        self.title_label = BodyLabel("Metallib Support Package")
        self.title_label.setStyleSheet("font-weight: 600;")

        date_str = metallib_data.get("date", "Unknown")
        self.date_label = CaptionLabel(f"Release: {date_str}")

        version = metallib_data.get("version", "Unknown")
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
            InfoBar.success("Link Copied", "Download link copied to clipboard", duration=2000, position=InfoBarPosition.TOP_RIGHT, parent=self.window())


class MetallibList(ScrollArea):
    """Metallib list interface"""

    def __init__(self, global_constants: Constants, ui_support: DefGUI = None, global_settings: GlobalSettings = None, parent=None):
        super().__init__(parent)
        self.setObjectName("Metallib")
        self.constants = global_constants
        self.settings = global_settings
        self.available_metallibs = []
        self.available_metallibs_latest = []
        self.show_latest_only = False

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

        logging.info("MetallibList initialized")
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
        self.loading_label = BodyLabel("Fetching packages...")
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading_layout.addWidget(self.progress_ring, 0, Qt.AlignmentFlag.AlignCenter)
        loading_layout.addWidget(self.loading_label, 0, Qt.AlignmentFlag.AlignCenter)
        self.expandLayout.addWidget(self.loading_container)
        self.loading_container.setVisible(False)

    def load_metallibs(self):
        self._show_loading(True)

        def _fetch():
            try:
                response = requests.get(self.constants.metallib_api_link, timeout=10)
                if response.status_code == 200:
                    self.available_metallibs = response.json()
                    self.available_metallibs.sort(key=lambda x: (x.get("build", ""), x.get("version", "")), reverse=True)
                    # Extract latest (top 4)
                    self.available_metallibs_latest = self.available_metallibs[:4]
            except Exception as e:
                logging.error(f"Failed to fetch Metallib data: {e}")

        thread = threading.Thread(target=_fetch)
        thread.start()

        def _check():
            if thread.is_alive():
                QTimer.singleShot(100, _check)
                return
            self._show_loading(False)
            self._display_metallibs()

        QTimer.singleShot(100, _check)

    def _on_latest_toggle(self, checked: bool):
        """Handle latest-only toggle"""
        self.show_latest_only = checked
        if self.available_metallibs:
            self._display_metallibs()

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
        while self.expandLayout.count():
            item = self.expandLayout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

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

        self._render_batch(0, metallibs)

    def _render_batch(self, start_index: int, metallibs: list, batch_size: int = 20):
        """Batch render cards to avoid UI freeze"""
        end_index = min(start_index + batch_size, len(metallibs))

        for i in range(start_index, end_index):
            metallib = metallibs[i]
            card = MetallibCard(metallib, self.constants, self)
            card.download_clicked.connect(self._on_download)
            self.expandLayout.addWidget(card)

        if end_index < len(metallibs):
            QTimer.singleShot(10, lambda: self._render_batch(end_index, metallibs, batch_size))
        else:
            self.expandLayout.addStretch()

    def _on_download(self, metallib_data: dict):
        url = metallib_data.get("url")
        version = metallib_data.get("version")
        build = metallib_data.get("build")

        save_path = self.settings.find_key("download_path") or str(self.constants.payload_path)
        filename = f"MetallibSupportPkg-{version}-{build}.pkg"
        download_obj = DownloadObject(url, save_path, filename)

        icon_path = str(self.constants.payload_path / "Icon/AppIcons/Package.png")
        TaskManager.start_download(download_obj, icon=icon_path)

        InfoBar.success("Download Started", f"{filename} is downloading. Check Tasks for progress.", duration=3000, position=InfoBarPosition.TOP_RIGHT, parent=self)

