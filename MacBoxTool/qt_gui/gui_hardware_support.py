"""Hardware support page."""

from ..include import *
from ..constants import Constants
from ..support.hack import CompatStatus, ComponentResult, evaluate
from .gui_support import DefGUI


class HardwareSupport(ScrollArea):
    """Display hardware compatibility using UIKit widgets."""

    def __init__(self, global_constants: Constants, ui_support: DefGUI = None, parent=None):
        super().__init__(parent=parent)
        logging.info("init gui_hardware_support")
        self.constants = global_constants
        self.ui_support = ui_support
        self.scrollWidget = QWidget()
        self.expandLayout = QVBoxLayout(self.scrollWidget)
        self.setObjectName("HardwareSupport")
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)
        self.enableTransparentBackground()
        self.refresh()

    def _status(self, status: CompatStatus) -> tuple[str, str, InfoLevel, FluentIcon]:
        """Return the custom-card type, sentence, UIKit level, and icon."""
        return {
            CompatStatus.PERFECT: (
                "success",
                "This device is fully compatible.",
                InfoLevel.SUCCESS,
                FluentIcon.COMPLETED,
            ),
            CompatStatus.CONDITIONAL: (
                "warning",
                "This device is mostly compatible.",
                InfoLevel.WARNING,
                FluentIcon.INFO,
            ),
            CompatStatus.INCOMPATIBLE: (
                "error",
                "This device has limited compatibility.",
                InfoLevel.ERROR,
                FluentIcon.CLOSE,
            ),
            CompatStatus.UNKNOWN: (
                "warning",
                "This device is compatible, but some details require confirmation.",
                InfoLevel.WARNING,
                FluentIcon.INFO,
            ),
        }.get(
            status,
            (
                "warning",
                "This device is compatible, but some details require confirmation.",
                InfoLevel.WARNING,
                FluentIcon.INFO,
            ),
        )

    def _score_panel(self, report) -> QWidget:
        """Build the score block with a prominent total score."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING["small"])

        score_label = StrongBodyLabel(f"Score: {report.score}")
        score_label.setStyleSheet("font-size: 40px; font-weight: 700;")
        layout.addWidget(score_label)

        metadata = BodyLabel(f"Grade: {report.grade}  |  OS: {report.os_name or 'Unknown'}")
        metadata.setWordWrap(True)
        layout.addWidget(metadata)
        return panel

    def _comment_card(self, report) -> CardWidget:
        """Render the single-sentence compatibility comment with custom_card."""
        card_type, sentence, _, icon = self._status(report.status)
        if self.ui_support:
            return self.ui_support.custom_card(
                card_type=card_type,
                icon=icon,
                title="Compatibility",
                body=sentence,
            )

        card = CardWidget()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(SPACING["large"], SPACING["large"], SPACING["large"], SPACING["large"])
        layout.addWidget(StrongBodyLabel("Compatibility"))
        layout.addWidget(BodyLabel(sentence))
        return card

    def _hardware_card(self, result: ComponentResult) -> CardWidget:
        """Render only detected hardware details, without compatibility remarks."""
        card = CardWidget()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(SPACING["large"], SPACING["large"], SPACING["large"], SPACING["large"])
        layout.setSpacing(SPACING["small"])

        title = StrongBodyLabel(result.category)
        title.setStyleSheet("font-size: 16px; font-weight: 600;")
        layout.addWidget(title)

        hardware = BodyLabel(result.name or "Unknown")
        hardware.setWordWrap(True)
        layout.addWidget(hardware)
        return card

    def _clear_layout(self) -> None:
        """Remove previous widgets before refreshing."""
        while self.expandLayout.count():
            item = self.expandLayout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def refresh(self) -> None:
        """Recalculate and display the current hardware report."""
        self._clear_layout()
        self.expandLayout.setContentsMargins(
            SPACING["xxlarge"], SPACING["xlarge"], SPACING["xxlarge"], SPACING["xlarge"]
        )
        self.expandLayout.setSpacing(SPACING["large"])

        report = evaluate(self.constants.computer, self.constants)
        self.expandLayout.addWidget(SubtitleLabel("Hardware Support"))
        self.expandLayout.addWidget(self._score_panel(report))
        self.expandLayout.addWidget(self._comment_card(report))

        badge_row = QHBoxLayout()
        badge_row.setContentsMargins(0, 0, 0, 0)
        badge_row.addStretch()
        self.expandLayout.addLayout(badge_row)

        for result in report.components:
            self.expandLayout.addWidget(self._hardware_card(result))
        self.expandLayout.addStretch()
