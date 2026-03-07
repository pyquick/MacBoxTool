"""
gui_download.py: Download card widget
"""

from ..include import *
from ..support.network_handler import DownloadObject, DownloadStatus
from ..UIkit.components.widgets.card_widget import CardWidget
from ..UIkit.components.widgets.label import BodyLabel, CaptionLabel, ImageLabel
from ..UIkit.components.widgets.button import TransparentToolButton
from ..UIkit.components.widgets.menu import RoundMenu
from ..UIkit.common.icon import FluentIcon, Action


class DownloadCard(CardWidget):
    """Download card following UIkit AppCard pattern, with progress bar"""

    open_file_signal = Signal(object)
    open_folder_signal = Signal(object)
    cancel_signal = Signal(object)
    pause_signal = Signal(object)
    resume_signal = Signal(object)

    def __init__(self, download_object: DownloadObject, icon=None, parent=None):
        super().__init__(parent)
        self.download = download_object

        self.setFixedHeight(73)
        self._init_widgets(icon)
        self._init_layout()
        self._create_context_menu()
        self._update_button_state()

    # ── Widget Initialization ──

    def _init_widgets(self, icon):
        """Initialize all widgets"""
        # Use provided icon or default to Package.png
        if icon is None:
            from pathlib import Path
            icon = str(Path(__file__).parent.parent / "payloads/Icon/AppIcons/Package.png")

        # Always use ImageLabel for better performance
        self.iconWidget = ImageLabel(icon, self)
        self.iconWidget.setFixedSize(48, 48)

        self.titleLabel = BodyLabel(self.download.filename, self)
        self.titleLabel.setWordWrap(False)
        self.contentLabel = CaptionLabel(self._get_status_text(), self)
        self.contentLabel.setTextColor("#606060", "#d2d2d2")
        self.contentLabel.setWordWrap(False)

        self.progressBar = ProgressBar(self)
        self.progressBar.setFixedWidth(200)
        self.progressBar.setFixedHeight(4)
        self.progressBar.setRange(0, 100)
        self.progressBar.setValue(self.download.get_progress_percentage())

        self.speedLabel = CaptionLabel(self.download.get_speed_display(), self)
        self.speedLabel.setTextColor("#606060", "#d2d2d2")
        self.speedLabel.setFixedWidth(80)
        self.speedLabel.setAlignment(Qt.AlignmentFlag.AlignRight)

        self.sizeLabel = CaptionLabel(self.download.get_size_display(), self)
        self.sizeLabel.setTextColor("#606060", "#d2d2d2")
        self.sizeLabel.setFixedWidth(150)
        self.sizeLabel.setAlignment(Qt.AlignmentFlag.AlignRight)

        self.percentLabel = CaptionLabel(f"{self.download.get_progress_percentage()}%", self)
        self.percentLabel.setTextColor("#0078D4", "#0078D4")
        self.percentLabel.setFixedWidth(50)
        self.percentLabel.setAlignment(Qt.AlignmentFlag.AlignRight)

        self.moreButton = TransparentToolButton(FluentIcon.MORE, self)
        self.moreButton.setFixedSize(32, 32)

    def _init_layout(self):
        """Setup layout structure"""
        self.hBoxLayout = QHBoxLayout(self)
        self.vBoxLayout = QVBoxLayout()

        self.hBoxLayout.setContentsMargins(20, 11, 11, 11)
        self.hBoxLayout.setSpacing(15)
        self.hBoxLayout.addWidget(self.iconWidget)

        self.vBoxLayout.setContentsMargins(0, 0, 0, 0)
        self.vBoxLayout.setSpacing(4)
        self.vBoxLayout.addWidget(self.titleLabel)
        self.vBoxLayout.addWidget(self.contentLabel)
        self.hBoxLayout.addLayout(self.vBoxLayout, 1)

        self.hBoxLayout.addWidget(self.progressBar, 0, Qt.AlignmentFlag.AlignVCenter)
        self.hBoxLayout.addWidget(self.speedLabel, 0, Qt.AlignmentFlag.AlignVCenter)
        self.hBoxLayout.addWidget(self.sizeLabel, 0, Qt.AlignmentFlag.AlignVCenter)
        self.hBoxLayout.addWidget(self.percentLabel, 0, Qt.AlignmentFlag.AlignVCenter)
        self.hBoxLayout.addWidget(self.moreButton, 0, Qt.AlignmentFlag.AlignVCenter)

    # ── Context Menu ──

    def _create_context_menu(self):
        """Create RoundMenu with actions"""
        self.menu = RoundMenu(parent=self)

        self.cancel_action = Action(FluentIcon.CLOSE, "Cancel Download", self)
        self.pause_action = Action(FluentIcon.PAUSE, "Pause Download", self)
        self.resume_action = Action(FluentIcon.PLAY, "Resume Download", self)
        self.open_file_action = Action(FluentIcon.DOCUMENT, "Open File", self)
        self.open_folder_action = Action(FluentIcon.FOLDER, "Open Folder", self)

        self.cancel_action.triggered.connect(lambda: self.cancel_signal.emit(self.download))
        self.pause_action.triggered.connect(lambda: self.pause_signal.emit(self.download))
        self.resume_action.triggered.connect(lambda: self.resume_signal.emit(self.download))
        self.open_file_action.triggered.connect(lambda: self.open_file_signal.emit(self.download))
        self.open_folder_action.triggered.connect(lambda: self.open_folder_signal.emit(self.download))

        self.menu.addAction(self.cancel_action)
        self.menu.addAction(self.pause_action)
        self.menu.addAction(self.resume_action)
        self.menu.addSeparator()
        self.menu.addAction(self.open_file_action)
        self.menu.addAction(self.open_folder_action)

        self.moreButton.clicked.connect(self._show_menu)

    def _show_menu(self):
        pos = self.moreButton.mapToGlobal(QPoint(self.moreButton.width(), self.moreButton.height()))
        self.menu.exec(pos)

    # ── Helpers ──

    def _get_status_text(self) -> str:
        return {
            DownloadStatus.PENDING: "Waiting...",
            DownloadStatus.DOWNLOADING: "Downloading...",
            DownloadStatus.PAUSED: "Paused",
            DownloadStatus.COMPLETED: "Completed",
            DownloadStatus.FAILED: f"Failed: {self.download.error_message}",
            DownloadStatus.CANCELLED: "Cancelled",
        }.get(self.download.status, "Unknown")

    def _update_button_state(self):
        is_downloading = self.download.status == DownloadStatus.DOWNLOADING
        is_paused = self.download.status == DownloadStatus.PAUSED
        is_active = is_downloading or is_paused or self.download.status == DownloadStatus.PENDING
        is_completed = self.download.is_completed()

        self.cancel_action.setEnabled(is_active)
        self.pause_action.setEnabled(is_downloading)
        self.resume_action.setEnabled(is_paused)
        self.open_file_action.setEnabled(is_completed)
        self.open_folder_action.setEnabled(is_completed)

    # ── Public Methods ──

    def update_progress(self):
        self.progressBar.setValue(self.download.get_progress_percentage())
        self.speedLabel.setText(self.download.get_speed_display())
        self.sizeLabel.setText(self.download.get_size_display())
        self.percentLabel.setText(f"{self.download.get_progress_percentage()}%")
        self.contentLabel.setText(self._get_status_text())
        self._update_button_state()

    def set_status(self, status: DownloadStatus):
        self.download.status = status
        self.contentLabel.setText(self._get_status_text())
        self._update_button_state()
