"""
gui_hardware_compat.py: Hardware compatibility dialog with simple/detailed modes
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QFrame, QVBoxLayout, QHBoxLayout, QScrollArea,
                               QLabel, QWidget, QPushButton)

from ..UIkit.common.style_sheet import FluentStyleSheet, isDarkTheme
from ..UIkit.common.icon import FluentIcon
from ..UIkit.components.widgets.button import PrimaryPushButton, PushButton
from ..UIkit.components.widgets.switch_button import SwitchButton
from ..UIkit.components.widgets.card_widget import CardWidget
from ..UIkit.components.widgets.label import SubtitleLabel, BodyLabel, CaptionLabel
from ..UIkit.components.dialog_box.mask_dialog_base import MaskDialogBase
from ..detections.hardware_info import HardwareInfo
from ..datasets.compatibility_data import CompatibilityChecker, CompatStatus


# Status colors
STATUS_COLORS = {
    CompatStatus.SUPPORTED: QColor(72, 199, 142),    # Green
    CompatStatus.PARTIAL: QColor(255, 198, 54),      # Yellow
    CompatStatus.UNSUPPORTED: QColor(239, 83, 80),   # Red
    CompatStatus.UNKNOWN: QColor(142, 142, 147),     # Gray
}

# Status icons
STATUS_ICONS = {
    CompatStatus.SUPPORTED: FluentIcon.ACCEPT,
    CompatStatus.PARTIAL: FluentIcon.CANCEL,
    CompatStatus.UNSUPPORTED: FluentIcon.CANCEL,
    CompatStatus.UNKNOWN: FluentIcon.QUESTION,
}

# Status text
STATUS_TEXT = {
    CompatStatus.SUPPORTED: "Supported",
    CompatStatus.PARTIAL: "Partial",
    CompatStatus.UNSUPPORTED: "Unsupported",
    CompatStatus.UNKNOWN: "Unknown",
}


class CompatCardWidget(CardWidget):
    """Single hardware compatibility card widget.

    Displays icon, title, status badge, message, and optional details.
    """

    def __init__(self, title: str, status: CompatStatus, message: str,
                 details: list[str] = None, icon: FluentIcon = None, parent=None):
        super().__init__(parent=parent)
        self.title = title
        self.status = status
        self.message = message
        self.details = details or []
        self.icon = icon or FluentIcon.INFO

        self._isDetailedMode = False
        self._setupUi()

    def _setupUi(self):
        """Initialize the card UI layout."""
        self.setFixedHeight(80)
        self.setMinimumWidth(400)

        # Main horizontal layout
        self.mainLayout = QHBoxLayout(self)
        self.mainLayout.setContentsMargins(16, 12, 16, 12)
        self.mainLayout.setSpacing(12)

        # Icon on the left
        self.iconLabel = QLabel(self)
        self.iconLabel.setPixmap(self.icon.value().pixmap(24, 24))
        self.mainLayout.addWidget(self.iconLabel)

        # Content area (title + message + details)
        self.contentLayout = QVBoxLayout()
        self.contentLayout.setSpacing(4)
        self.contentLayout.setContentsMargins(0, 0, 0, 0)

        # Title row with status badge
        self.titleLayout = QHBoxLayout()
        self.titleLayout.setSpacing(8)

        self.titleLabel = BodyLabel(self.title)
        self.titleLabel.setFont(self.titleLabel.font())
        self.titleLayout.addWidget(self.titleLabel)

        # Status badge
        self.statusBadge = CaptionLabel(STATUS_TEXT.get(self.status, "Unknown"))
        self.statusColor = STATUS_COLORS.get(self.status, STATUS_COLORS[CompatStatus.UNKNOWN])
        self._styleStatusBadge()
        self.titleLayout.addWidget(self.statusBadge)
        self.titleLayout.addStretch(1)

        self.contentLayout.addLayout(self.titleLayout)

        # Message
        self.messageLabel = CaptionLabel(self.message)
        self.messageLabel.setTextColor(QColor(128, 128, 128))
        self.contentLayout.addWidget(self.messageLabel)

        # Details (hidden in simple mode)
        self.detailsLabel = CaptionLabel()
        self.detailsLabel.setTextColor(QColor(100, 100, 100))
        self.detailsLabel.setWordWrap(True)
        self.detailsLabel.setVisible(False)
        self.contentLayout.addWidget(self.detailsLabel)

        self.mainLayout.addLayout(self.contentLayout, 1)

        self._updateDetails()

    def _styleStatusBadge(self):
        """Apply styling to status badge based on status color."""
        color = self.statusColor
        self.statusBadge.setStyleSheet(f"""
            background-color: rgba({color.red()}, {color.green()}, {color.blue()}, 80);
            color: white;
            border-radius: 4px;
            padding: 2px 8px;
        """)

    def _updateDetails(self):
        """Update details display based on mode."""
        if self._isDetailedMode and self.details:
            details_str = " | ".join(self.details)
            self.detailsLabel.setText(details_str)
            self.detailsLabel.setVisible(True)
            self.setFixedHeight(100)
        else:
            self.detailsLabel.setVisible(False)
            self.setFixedHeight(80)

    def setDetailedMode(self, isDetailed: bool):
        """Toggle detailed mode showing additional details."""
        self._isDetailedMode = isDetailed
        self._updateDetails()

    def updateContent(self, title: str, status: CompatStatus, message: str,
                      details: list[str] = None):
        """Update card content dynamically."""
        self.title = title
        self.status = status
        self.message = message
        self.details = details or []

        self.titleLabel.setText(title)
        self.messageLabel.setText(message)
        self.statusBadge.setText(STATUS_TEXT.get(status, "Unknown"))
        self.statusColor = STATUS_COLORS.get(status, STATUS_COLORS[CompatStatus.UNKNOWN])
        self._styleStatusBadge()

        self._updateDetails()


class HardwareCompatDialog(MaskDialogBase):
    """Hardware compatibility check dialog with simple/detailed modes.

    Shows compatibility cards for CPU, GPU, Network, Storage, etc.
    Simple mode shows only CPU + GPU. Detailed mode shows all cards.

    Signals:
        importClicked: Emitted when Import button is clicked
        copyClicked: Emitted when Copy button is clicked
        continueClicked: Emitted when Continue button is clicked
    """

    importClicked = Signal()
    copyClicked = Signal()
    continueClicked = Signal()

    def __init__(self, hw_info: HardwareInfo, parent=None):
        super().__init__(parent=parent)
        self.hw_info = hw_info
        self._isDetailedMode = False

        # Run compatibility checks
        self.compat_results = self._runCompatibilityChecks()

        self._setupUi()
        self._populateCards()

    def _setupUi(self):
        """Initialize the dialog UI."""
        self.setShadowEffect(60, (0, 10), QColor(0, 0, 0, 50))
        self.setMaskColor(QColor(0, 0, 0, 76))

        # Main container
        self.widget.setMinimumWidth(550)
        self.widget.setMinimumHeight(500)

        # Main layout
        self.mainLayout = QVBoxLayout(self.widget)
        self.mainLayout.setContentsMargins(0, 0, 0, 0)
        self.mainLayout.setSpacing(0)

        # Header area
        self.headerFrame = QFrame(self.widget)
        self.headerFrame.setObjectName("headerFrame")
        self.headerLayout = QHBoxLayout(self.headerFrame)
        self.headerLayout.setContentsMargins(24, 16, 24, 16)
        self.headerLayout.setSpacing(12)

        # Title
        self.titleLabel = SubtitleLabel("Hardware Compatibility")
        self.headerLayout.addWidget(self.titleLabel, 1)

        # Simple/Detailed toggle
        self.modeSwitchLayout = QHBoxLayout()
        self.modeSwitchLayout.setSpacing(8)

        self.simpleLabel = BodyLabel("Simple")
        self.simpleLabel.setTextColor(QColor(128, 128, 128))
        self.modeSwitchLayout.addWidget(self.simpleLabel)

        self.detailSwitch = SwitchButton()
        self.detailSwitch.setChecked(False)
        self.detailSwitch.checkedChanged.connect(self._onModeToggled)
        self.modeSwitchLayout.addWidget(self.detailSwitch)

        self.detailedLabel = BodyLabel("Detailed")
        self.detailedLabel.setTextColor(QColor(128, 128, 128))
        self.modeSwitchLayout.addWidget(self.detailedLabel)

        self.headerLayout.addLayout(self.modeSwitchLayout)

        self.mainLayout.addWidget(self.headerFrame)

        # Scroll area for cards
        self.scrollArea = QScrollArea(self.widget)
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.cardsContainer = QFrame(self.scrollArea)
        self.cardsLayout = QVBoxLayout(self.cardsContainer)
        self.cardsLayout.setContentsMargins(24, 12, 24, 12)
        self.cardsLayout.setSpacing(12)
        self.cardsLayout.addStretch(1)

        self.scrollArea.setWidget(self.cardsContainer)
        self.mainLayout.addWidget(self.scrollArea, 1)

        # Button group
        self.buttonGroup = QFrame(self.widget)
        self.buttonGroup.setFixedHeight(81)
        self.buttonGroup.setObjectName("buttonGroup")
        self.buttonLayout = QHBoxLayout(self.buttonGroup)
        self.buttonLayout.setContentsMargins(24, 16, 24, 16)
        self.buttonLayout.setSpacing(12)

        # Import button
        self.importButton = PushButton("Import", self.buttonGroup)
        self.importButton.setIcon(FluentIcon.DOWNLOAD)
        self.importButton.clicked.connect(self._onImportClicked)
        self.buttonLayout.addWidget(self.importButton)

        # Copy button
        self.copyButton = PushButton("Copy", self.buttonGroup)
        self.copyButton.setIcon(FluentIcon.COPY)
        self.copyButton.clicked.connect(self._onCopyClicked)
        self.buttonLayout.addWidget(self.copyButton)

        # Spacer
        self.buttonLayout.addStretch(1)

        # Continue button
        self.continueButton = PrimaryPushButton("Continue", self.buttonGroup)
        self.continueButton.setIcon(FluentIcon.RIGHT_ARROW)
        self.continueButton.clicked.connect(self._onContinueClicked)
        self.buttonLayout.addWidget(self.continueButton)

        self.mainLayout.addWidget(self.buttonGroup)

        # Apply stylesheet
        self._applyStylesheet()

    def _applyStylesheet(self):
        """Apply Fluent stylesheet to dialog."""
        FluentStyleSheet.DIALOG.apply(self)

        # Header style
        self.headerFrame.setStyleSheet("""
            #headerFrame {
                background-color: transparent;
                border-bottom: 1px solid rgba(128, 128, 128, 30);
            }
        """)

        # Button group style
        self.buttonGroup.setStyleSheet("""
            #buttonGroup {
                background-color: transparent;
                border-top: 1px solid rgba(128, 128, 128, 30);
            }
        """)

    def _runCompatibilityChecks(self) -> dict:
        """Run all compatibility checks and return results."""
        results = {}

        # CPU compatibility
        if hasattr(self.hw_info, 'cpu') and self.hw_info.cpu:
            cpu = self.hw_info.cpu
            if cpu.name:
                results['cpu'] = CompatibilityChecker.check_cpu(cpu)

        # GPU compatibility (list)
        if hasattr(self.hw_info, 'gpu') and self.hw_info.gpu:
            gpu_results = []
            for gpu in self.hw_info.gpu:
                if gpu.name:
                    gpu_results.append(CompatibilityChecker.check_gpu(gpu))
            if gpu_results:
                results['gpu'] = gpu_results

        # Network compatibility (placeholder for now)
        if hasattr(self.hw_info, 'network') and self.hw_info.network:
            results['network'] = self._checkNetworkCompatibility()

        # Storage compatibility (placeholder for now)
        if hasattr(self.hw_info, 'storage') and self.hw_info.storage:
            results['storage'] = self._checkStorageCompatibility()

        return results

    def _checkNetworkCompatibility(self) -> list:
        """Check network hardware compatibility."""
        results = []
        for net in self.hw_info.network:
            if net.name:
                # Basic check - mark as unknown for now
                results.append(CompatResult(
                    status=CompatStatus.UNKNOWN,
                    message=f"Network: {net.name}",
                    notes=["Network compatibility check not implemented"]
                ))
        return results

    def _checkStorageCompatibility(self) -> list:
        """Check storage hardware compatibility."""
        results = []
        for stor in self.hw_info.storage:
            if stor.name:
                # Basic check - mark as unknown for now
                results.append(CompatResult(
                    status=CompatStatus.UNKNOWN,
                    message=f"Storage: {stor.name}",
                    notes=["Storage compatibility check not implemented"]
                ))
        return results

    def _populateCards(self):
        """Populate the card list with compatibility results."""
        # Clear existing cards
        while self.cardsLayout.count() > 0:
            item = self.cardsLayout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Get card categories based on mode
        categories = self._getCardCategories()

        # Create cards for each category
        for category in categories:
            cards = self._createCardsForCategory(category)
            for card in cards:
                self.cardsLayout.insertWidget(self.cardsLayout.count() - 1, card)

        # Add stretch at the end
        self.cardsLayout.addStretch(1)

    def _getCardCategories(self) -> list:
        """Get list of categories to display based on current mode."""
        if self._isDetailedMode:
            return ['cpu', 'gpu', 'network', 'storage']
        else:
            # Simple mode: only CPU and GPU
            return ['cpu', 'gpu']

    def _createCardsForCategory(self, category: str) -> list:
        """Create cards for a specific category."""
        cards = []

        if category == 'cpu':
            result = self.compat_results.get('cpu')
            if result:
                icon = FluentIcon.CPU
                details = []
                if result.notes:
                    details.extend(result.notes)
                if result.kexts_needed:
                    details.append(f"Kexts: {', '.join(result.kexts_needed)}")

                card = CompatCardWidget(
                    title=f"CPU: {self.hw_info.cpu.name if self.hw_info.cpu else 'Unknown'}",
                    status=result.status,
                    message=result.message,
                    details=details,
                    icon=icon
                )
                cards.append(card)

        elif category == 'gpu':
            gpu_results = self.compat_results.get('gpu', [])
            icon = FluentIcon.MEDIA
            for i, result in enumerate(gpu_results):
                gpu_name = self.hw_info.gpu[i].name if i < len(self.hw_info.gpu) else "Unknown"
                details = []
                if result.notes:
                    details.extend(result.notes)
                if result.kexts_needed:
                    details.append(f"Kexts: {', '.join(result.kexts_needed)}")

                card = CompatCardWidget(
                    title=f"GPU: {gpu_name}",
                    status=result.status,
                    message=result.message,
                    details=details,
                    icon=icon
                )
                cards.append(card)

        elif category == 'network':
            net_results = self.compat_results.get('network', [])
            icon = FluentIcon.WIFI
            for i, result in enumerate(net_results):
                net_name = self.hw_info.network[i].name if i < len(self.hw_info.network) else "Unknown"
                card = CompatCardWidget(
                    title=f"Network: {net_name}",
                    status=result.status,
                    message=result.message,
                    details=result.notes,
                    icon=icon
                )
                cards.append(card)

        elif category == 'storage':
            stor_results = self.compat_results.get('storage', [])
            icon = FluentIcon.FOLDER
            for i, result in enumerate(stor_results):
                stor_name = self.hw_info.storage[i].name if i < len(self.hw_info.storage) else "Unknown"
                card = CompatCardWidget(
                    title=f"Storage: {stor_name}",
                    status=result.status,
                    message=result.message,
                    details=result.notes,
                    icon=icon
                )
                cards.append(card)

        return cards

    def _onModeToggled(self, isChecked: bool):
        """Handle simple/detailed mode toggle."""
        self._isDetailedMode = isChecked
        self._populateCards()

    def _onImportClicked(self):
        """Handle Import button click."""
        self.importClicked.emit()

    def _onCopyClicked(self):
        """Handle Copy button click."""
        self.copyClicked.emit()

    def _onContinueClicked(self):
        """Handle Continue button click."""
        self.continueClicked.emit()
        self.accept()

    def getCompatSummary(self) -> dict:
        """Get a summary of compatibility results for external use."""
        summary = {
            'cpu': None,
            'gpu': [],
            'network': [],
            'storage': [],
        }

        if 'cpu' in self.compat_results:
            result = self.compat_results['cpu']
            summary['cpu'] = {
                'status': result.status.value,
                'message': result.message,
            }

        if 'gpu' in self.compat_results:
            for result in self.compat_results['gpu']:
                summary['gpu'].append({
                    'status': result.status.value,
                    'message': result.message,
                })

        return summary