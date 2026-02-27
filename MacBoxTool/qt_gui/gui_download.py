"""
gui_download.py: Download card widget
"""

from ..include import *
from ..support.network_handler import DownloadObject, DownloadStatus
from ..UIkit.components.widgets.card_widget import CardWidget
from ..UIkit.components.widgets.label import BodyLabel, CaptionLabel
from ..UIkit.components.widgets.button import TransparentToolButton
from ..UIkit.common.icon import FluentIcon


class DownloadCard(CardWidget):
    """Download card with progress bar and file operations"""

    open_file_signal = Signal(object)  # DownloadObject
    open_folder_signal = Signal(object)  # DownloadObject
    remove_signal = Signal(object)  # DownloadObject

    def __init__(self, download_object: DownloadObject, parent=None):
        super().__init__(parent)
        self.download = download_object

        # Icon widget
        self.icon_widget = IconWidget(FluentIcon.ZIP_FOLDER)
        self.icon_widget.setFixedSize(48, 48)

        # Title and status labels
        self.title_label = BodyLabel(self.download.filename)
        self.status_label = CaptionLabel(self._get_status_text())
        self.status_label.setTextColor("#606060", "#d2d2d2")

        # Progress bar
        self.progress_bar = ProgressBar()
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(self.download.get_progress_percentage())

        # Size label and percentage
        self.size_label = CaptionLabel(self.download.get_size_display())
        self.size_label.setTextColor("#606060", "#d2d2d2")

        self.percent_label = CaptionLabel(f"{self.download.get_progress_percentage()}%")
        self.percent_label.setTextColor("#0078D4", "#0078D4")

        # More button with menu
        self.more_button = TransparentToolButton(FluentIcon.MORE)
        self.more_button.setFixedSize(32, 32)
        self._create_context_menu()

        # Layouts
        self.h_box_layout = QHBoxLayout(self)
        self.v_box_layout = QVBoxLayout()
        self.text_layout = QVBoxLayout()
        self.progress_layout = QHBoxLayout()

        self._init_ui()

    def _init_ui(self):
        self.setFixedHeight(88)
        self.setBorderRadius(8)

        # Main horizontal layout
        self.h_box_layout.setContentsMargins(20, 11, 11, 11)
        self.h_box_layout.setSpacing(15)
        self.h_box_layout.addWidget(self.icon_widget)

        # Text vertical layout (title + status)
        self.text_layout.setContentsMargins(0, 0, 0, 0)
        self.text_layout.setSpacing(4)
        self.text_layout.addWidget(self.title_label, 0, Qt.AlignmentFlag.AlignVCenter)
        self.text_layout.addWidget(self.status_label, 0, Qt.AlignmentFlag.AlignVCenter)

        # Progress layout
        self.progress_layout.setContentsMargins(0, 4, 0, 0)
        self.progress_layout.setSpacing(8)
        self.progress_layout.addWidget(self.progress_bar, 1)

        # Combine text + progress layout
        self.v_box_layout.setContentsMargins(0, 0, 0, 0)
        self.v_box_layout.setSpacing(2)
        self.v_box_layout.addLayout(self.text_layout)
        self.v_box_layout.addLayout(self.progress_layout)
        self.v_box_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.h_box_layout.addLayout(self.v_box_layout)

        # Size and percentage labels
        self.h_box_layout.addWidget(self.size_label, 0, Qt.AlignmentFlag.AlignRight)
        self.h_box_layout.addWidget(self.percent_label, 0, Qt.AlignmentFlag.AlignRight)

        # Spacer
        self.h_box_layout.addStretch(1)

        # More button
        self.h_box_layout.addWidget(self.more_button, 0, Qt.AlignmentFlag.AlignRight)

        self._update_button_state()

    def _create_context_menu(self):
        """Create context menu for more button"""
        self.menu = QMenu(self)

        self.open_file_action = QAction("Open File", self)
        self.open_folder_action = QAction("Open Folder", self)
        self.remove_action = QAction("Remove from List", self)

        self.open_file_action.triggered.connect(lambda: self.open_file_signal.emit(self.download))
        self.open_folder_action.triggered.connect(lambda: self.open_folder_signal.emit(self.download))
        self.remove_action.triggered.connect(lambda: self.remove_signal.emit(self.download))

        self.menu.addAction(self.open_file_action)
        self.menu.addAction(self.open_folder_action)
        self.menu.addSeparator()
        self.menu.addAction(self.remove_action)

        self.more_button.setMenu(self.menu)

    def _update_button_state(self):
        """Update button state based on download status"""
        is_completed = self.download.is_completed()

        # Open File: disabled during download
        self.open_file_action.setEnabled(is_completed)

        # Open Folder: always enabled if completed
        self.open_folder_action.setEnabled(is_completed)

    def _get_status_text(self) -> str:
        """Get status text based on download status"""
        status_map = {
            DownloadStatus.PENDING: "Waiting...",
            DownloadStatus.DOWNLOADING: "Downloading...",
            DownloadStatus.COMPLETED: "Completed",
            DownloadStatus.FAILED: f"Failed: {self.download.error_message}",
            DownloadStatus.CANCELLED: "Cancelled"
        }
        return status_map.get(self.download.status, "Unknown")

    def update_progress(self):
        """Update progress bar and labels"""
        self.progress_bar.setValue(self.download.get_progress_percentage())
        self.size_label.setText(self.download.get_size_display())
        self.percent_label.setText(f"{self.download.get_progress_percentage()}%")
        self.status_label.setText(self._get_status_text())
        self._update_button_state()

    def set_status(self, status: DownloadStatus):
        """Update download status"""
        self.download.status = status
        self.status_label.setText(self._get_status_text())
        self._update_button_state()


class IconWidget(QWidget):
    """Icon widget wrapper"""

    def __init__(self, icon, parent=None):
        super().__init__(parent)
        self.icon = icon
        self._icon_size = QSize(24, 24)
        self.setFixedSize(48, 48)

    def setIcon(self, icon):
        self.icon = icon
        self.update()

    def setFixedSize(self, w, h):
        super().setFixedSize(w, h)
        self._icon_size = QSize(w - 24, h - 24)

    def paintEvent(self, _event=None):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing)

        if hasattr(self.icon, 'icon'):
            pixmap = self.icon.icon.pixmap(self._icon_size)
        else:
            pixmap = QPixmap(self._icon)

        if not pixmap.isNull():
            x = (self.width() - pixmap.width()) // 2
            y = (self.height() - pixmap.height()) // 2
            painter.drawPixmap(x, y, pixmap)