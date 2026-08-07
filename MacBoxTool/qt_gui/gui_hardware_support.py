"""Hardware support page."""

from ..include import *
from ..constants import Constants
from ..support.hack import (
    CompatStatus,
    evaluate,
    native_cpu_macos_range,
    native_gpu_macos_range,
    native_wifi_macos_range,
)
from .gui_support import DefGUI


_VENDOR_NAMES = {
    0x1002: "AMD",
    0x1022: "AMD",
    0x106B: "Apple",
    0x10DE: "NVIDIA",
    0x10EC: "Realtek",
    0x144D: "Samsung",
    0x14E4: "Broadcom",
    0x15B7: "Western Digital",
    0x168C: "Qualcomm Atheros",
    0x1B4B: "Marvell",
    0x8086: "Intel",
}


class HardwareSupport(ScrollArea):
    """Display hardware compatibility and detected device data."""

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

    @staticmethod
    def _text(value) -> str:
        """Format optional probe values for display."""
        if value is None or value == "":
            return "Not available"
        return str(getattr(value, "value", value))

    @staticmethod
    def _hex(value) -> str:
        """Format numeric and string IDs as hexadecimal values."""
        if value is None or value == "":
            return "Not available"
        try:
            return f"0x{int(str(value), 0):04X}"
        except (TypeError, ValueError):
            return str(value)

    def _status(self, status: CompatStatus) -> tuple[str, str, FluentIcon, str]:
        """Return the card type, sentence, icon, and status color."""
        return {
            CompatStatus.PERFECT: (
                "success",
                "This device is fully compatible.",
                FluentIcon.COMPLETED,
                COLORS["success"],
            ),
            CompatStatus.CONDITIONAL: (
                "warning",
                "This device is mostly compatible.",
                FluentIcon.INFO,
                COLORS["warning"],
            ),
            CompatStatus.INCOMPATIBLE: (
                "error",
                "This device has limited compatibility.",
                FluentIcon.CLOSE,
                COLORS["error"],
            ),
            CompatStatus.UNKNOWN: (
                "warning",
                "Compatibility requires confirmation.",
                FluentIcon.INFO,
                COLORS["warning"],
            ),
        }.get(
            status,
            ("warning", "Compatibility requires confirmation.", FluentIcon.INFO, COLORS["warning"]),
        )

    def _score_panel(self, report) -> QWidget:
        """Build the score block with a prominent total score."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING["small"])

        score_label = StrongBodyLabel(f"Score: {report.score}")
        score_font = score_label.font()
        score_font.setPixelSize(40)
        score_font.setWeight(QFont.Weight.Bold)
        score_label.setFont(score_font)
        layout.addWidget(score_label)

        metadata = BodyLabel(f"Grade: {report.grade}  |  OS: {report.os_name or 'Unknown'}")
        metadata.setWordWrap(True)
        layout.addWidget(metadata)
        return panel

    def _comment_card(self, report) -> CardWidget:
        """Render the overall compatibility summary."""
        card_type, sentence, icon, _ = self._status(report.status)
        if self.ui_support:
            return self.ui_support.custom_card(
                card_type=card_type,
                icon=icon,
                title="Hardware Compatibility",
                body=sentence,
            )

        card = CardWidget()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(SPACING["large"], SPACING["large"], SPACING["large"], SPACING["large"])
        layout.addWidget(StrongBodyLabel("Hardware Compatibility"))
        layout.addWidget(BodyLabel(sentence))
        return card

    def _vendor_name(self, device) -> str:
        """Resolve a known vendor name and preserve its hexadecimal ID."""
        raw_id = getattr(device, "vendor_id", None)
        if raw_id is None or raw_id == "":
            vendor = getattr(device, "vendor", None)
            return self._text(vendor) if vendor else "Not available"
        try:
            vendor_id = int(str(raw_id), 0)
        except (TypeError, ValueError):
            return self._text(raw_id)
        return f"{_VENDOR_NAMES.get(vendor_id, 'Unknown vendor')} ({self._hex(vendor_id)})"

    @staticmethod
    def _processor_name(cpu) -> str:
        """Convert the detected CPU architecture to a readable processor name."""
        architecture = getattr(cpu, "architecture", None)
        value = str(getattr(architecture, "value", architecture) or "Unknown")
        return value.replace("_", " ").title()

    def _device_details(self, device, device_type: str) -> list[tuple[str, str]]:
        """Build separate PCI and I/O Registry detail rows for one device."""
        values = [
            ("Device Name", getattr(device, "name", None)),
            ("Model", None if device_type == "Processor" else getattr(device, "model", None)),
            ("Vendor", self._vendor_name(device)),
            ("Device ID", self._hex(getattr(device, "device_id", None))),
            ("Architecture", None if device_type == "Processor" else getattr(device, "arch", None) or getattr(device, "architecture", None)),
            ("Chipset", getattr(device, "chipset", None)),
            ("Class Code", self._hex(getattr(device, "class_code", None))),
            ("IORegistry Path", getattr(device, "acpi_path", None)),
            ("PCI Device Path", getattr(device, "pci_path", None)),
        ]
        values.extend(getattr(device, "extra_details", []) or [])
        return [(label, self._text(value)) for label, value in values if value not in (None, "", "Not available")]

    @staticmethod
    def _device_title(device, fallback: str) -> str:
        """Return the best detected model name for a device row."""
        if fallback == "Processor":
            return str(getattr(device, "name", None) or fallback)
        return str(
            getattr(device, "model", None)
            or getattr(device, "name", None)
            or fallback
        )

    def _detail_rows(self, device, device_type: str) -> list[tuple[str, str]]:
        """Return one display row for every detected hardware property."""
        details = self._device_details(device, device_type)
        if device_type == "Processor":
            details.insert(0, ("Processor", self._processor_name(device)))
        return details or [("Details", "No additional details detected")]

    @staticmethod
    def _detail_icon(label: str) -> FluentIcon:
        """Choose a semantic icon for each hardware detail."""
        if label == "Processor":
            return FluentIcon.SPEED_HIGH
        if "Security Chip" in label or label.startswith(("Apple T1", "Apple T2")):
            return FluentIcon.FINGERPRINT
        if label in ("Device Name", "Model") or label.endswith(" Name"):
            return FluentIcon.TAG
        if label == "Vendor" or label.endswith(" Vendor"):
            return FluentIcon.CERTIFICATE
        if label in ("Device ID", "Class Code") or label.endswith(" Device"):
            return FluentIcon.CODE
        if label == "Architecture":
            return FluentIcon.LAYOUT
        if label == "Chipset":
            return FluentIcon.DEVELOPER_TOOLS
        if label.endswith(" Path"):
            return FluentIcon.LINK
        if label.endswith(" Source"):
            return FluentIcon.CONNECT
        return FluentIcon.INFO

    def _row(self, icon: FluentIcon, title: str, subtitle: str = "", color: str | None = None) -> QWidget:
        """Create an icon, title, and subtitle row using UIKit labels."""
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(SPACING["large"], SPACING["medium"], SPACING["large"], SPACING["medium"])
        layout.setSpacing(SPACING["large"])

        if self.ui_support:
            icon_label = self.ui_support.build_icon_label(icon, color or COLORS["primary"], size=22)
        else:
            icon_label = QLabel()
            icon_label.setPixmap(icon.icon(color=color or COLORS["primary"]).pixmap(22, 22))
            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setFixedWidth(30)
        layout.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignTop)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)
        title_label = BodyLabel(title)
        if color:
            title_label.setTextColor(color, color)
            title_font = title_label.font()
            title_font.setWeight(QFont.Weight.DemiBold)
            title_label.setFont(title_font)
        text_layout.addWidget(title_label)
        if subtitle:
            subtitle_label = CaptionLabel(subtitle)
            subtitle_label.setWordWrap(True)
            subtitle_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            subtitle_label.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            text_layout.addWidget(subtitle_label)
        layout.addLayout(text_layout, 1)
        return row

    @staticmethod
    def _separator() -> QFrame:
        """Create a subtle separator without per-widget theme callbacks."""
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.NoFrame)
        separator.setFixedHeight(1)
        separator.setStyleSheet("background-color: rgba(128, 128, 128, 35); border: none;")
        return separator

    @staticmethod
    def _native_range(device, device_type: str, computer):
        """Return a native macOS range for supported core hardware."""
        if device_type == "Processor":
            return native_cpu_macos_range(device)
        if device_type == "Graphics Adapter":
            return native_gpu_macos_range(device)
        if device_type == "Wireless Adapter":
            return native_wifi_macos_range(device, computer)
        return None

    @staticmethod
    def _native_range_style(native_range) -> tuple[FluentIcon, str]:
        """Choose visual state for a native macOS range."""
        if native_range.reason == "Not natively supported":
            return FluentIcon.CLOSE, COLORS["error"]
        if native_range.minimum and native_range.maximum:
            return FluentIcon.COMPLETED, COLORS["success"]
        return FluentIcon.INFO, COLORS["warning"]

    def _section_card(
        self,
        title: str,
        devices: list,
        status: CompatStatus,
        device_type: str,
        computer=None,
    ) -> CardWidget:
        """Render a sectioned hardware card matching the compatibility overview."""
        card = CardWidget()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        heading = StrongBodyLabel(title)
        heading_font = heading.font()
        heading_font.setPixelSize(16)
        heading_font.setWeight(QFont.Weight.DemiBold)
        heading.setFont(heading_font)
        heading.setContentsMargins(SPACING["large"], SPACING["large"], SPACING["large"], SPACING["medium"])
        layout.addWidget(heading)

        if not devices:
            layout.addWidget(self._separator())
            layout.addWidget(self._row(FluentIcon.SEARCH, "Not detected", f"No {device_type.lower()} data was detected"))
            return card

        _, sentence, status_icon, status_color = self._status(status)
        for index, device in enumerate(devices):
            layout.addWidget(self._separator())
            layout.addWidget(
                self._row(
                    FluentIcon.TAG,
                    self._device_title(device, device_type),
                    f"Type: {device_type}",
                )
            )
            layout.addWidget(self._separator())
            native_range = self._native_range(device, device_type, computer)
            if native_range:
                native_icon, native_color = self._native_range_style(native_range)
                layout.addWidget(
                    self._row(
                        native_icon,
                        "Native macOS Compatibility",
                        native_range.label,
                        native_color,
                    )
                )
            else:
                layout.addWidget(self._row(status_icon, "macOS Compatibility", sentence, status_color))
            layout.addWidget(self._separator())
            detail_rows = self._detail_rows(device, device_type)
            for detail_index, (label, value) in enumerate(detail_rows):
                layout.addWidget(self._row(self._detail_icon(label), label, value))
                if detail_index < len(detail_rows) - 1:
                    layout.addWidget(self._separator())
            if index < len(devices) - 1:
                layout.addWidget(self._separator())
        return card

    def _cpu_card(self, cpu, status: CompatStatus, computer) -> CardWidget:
        """Render CPU identity, compatibility, and details."""
        if not cpu:
            return self._section_card("CPU", [], status, "Processor", computer)
        return self._section_card("CPU", [cpu], status, "Processor", computer)

    def _motherboard_device(self, computer):
        """Adapt board and Apple security chip identifiers for display."""
        extra_details = []
        for chip in getattr(computer, "security_chip_details", []) or []:
            chip_type = str(chip.get("type", "Apple Security Chip"))
            extra_details.extend([
                (f"{chip_type} Vendor", self._hex(chip.get("vendor_id"))),
                (f"{chip_type} Device", self._hex(chip.get("device_id"))),
                (f"{chip_type} Source", chip.get("source")),
                (f"{chip_type} Name", chip.get("name")),
            ])
        if getattr(computer, "t1_chip", False) and not any(chip.get("type") == "Apple T1" for chip in getattr(computer, "security_chip_details", []) or []):
            extra_details.append(("Security Chip", "Apple T1"))
        if getattr(computer, "t2_chip", False) and not any(chip.get("type") == "Apple T2" for chip in getattr(computer, "security_chip_details", []) or []):
            extra_details.append(("Security Chip", "Apple T2"))
        return type("Board", (), {
            "name": getattr(computer, "reported_model", None) or getattr(computer, "real_model", None),
            "model": getattr(computer, "real_model", None),
            "vendor_id": None,
            "vendor": getattr(computer, "firmware_vendor", None),
            "device_id": getattr(computer, "reported_board_id", None),
            "architecture": None,
            "chipset": None,
            "class_code": None,
            "acpi_path": None,
            "pci_path": None,
            "extra_details": extra_details,
        })()

    @staticmethod
    def _component_statuses(report) -> dict[str, CompatStatus]:
        """Map aggregate component statuses to hardware sections."""
        return {component.category: component.status for component in report.components}

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

        computer = self.constants.computer
        report = evaluate(computer, self.constants)
        statuses = self._component_statuses(report)
        self.expandLayout.addWidget(SubtitleLabel("Hardware Support"))
        self.expandLayout.addWidget(self._score_panel(report))
        self.expandLayout.addWidget(self._comment_card(report))
        self.expandLayout.addWidget(
            self._cpu_card(
                getattr(computer, "cpu", None),
                statuses.get("CPU", CompatStatus.UNKNOWN),
                computer,
            )
        )
        self.expandLayout.addWidget(
            self._section_card(
                "Graphics",
                list(getattr(computer, "gpus", []) or []),
                statuses.get("GPU", CompatStatus.UNKNOWN),
                "Graphics Adapter",
                computer,
            )
        )
        self.expandLayout.addWidget(
            self._section_card(
                "Wi-Fi",
                [computer.wifi] if getattr(computer, "wifi", None) else [],
                statuses.get("Wi-Fi", CompatStatus.UNKNOWN),
                "Wireless Adapter",
                computer,
            )
        )
        self.expandLayout.addWidget(
            self._section_card(
                "Motherboard",
                [self._motherboard_device(computer)],
                statuses.get("Motherboard", CompatStatus.UNKNOWN),
                "System Board",
            )
        )
        self.expandLayout.addWidget(
            self._section_card(
                "Storage",
                list(getattr(computer, "storage", []) or []),
                statuses.get("Storage", CompatStatus.UNKNOWN),
                "Storage Controller",
            )
        )
        self.expandLayout.addStretch()
