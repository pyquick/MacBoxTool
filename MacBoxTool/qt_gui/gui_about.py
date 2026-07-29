"""
gui_about.py: Show about UI
"""

from ..include import *
from .gui_support import DefGUI


def _wrap_text(items: list, width: int = 50) -> str:
    """Join items and insert line breaks at a readable card width."""
    if not items:
        return "N/A"
    result = []
    current_line = ""
    for item in items:
        item = str(item)
        candidate = f"{current_line}  {item}" if current_line else item
        if len(candidate) > width and current_line:
            result.append(current_line)
            current_line = item
        else:
            current_line = candidate
    if current_line:
        result.append(current_line)
    return "\n".join(result)


class AboutInterface(ScrollArea):

    def __init__(self, global_constants: Constants, ui_support: DefGUI = None,
                 global_settings: GlobalSettings = None, parent=None):
        super().__init__(parent)
        logging.info("init gui_about")
        self.setObjectName("About")
        self.constants = global_constants
        self.gui_support = ui_support
        self.settings = global_settings
        self.scrollWidget = QWidget()
        self.expandLayout = QVBoxLayout(self.scrollWidget)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)
        self.enableTransparentBackground()
        self.init_ui()

    def init_ui(self):
        self.expandLayout.setContentsMargins(
            SPACING["xxlarge"], SPACING["xlarge"],
            SPACING["xxlarge"], SPACING["xlarge"]
        )
        self.expandLayout.setSpacing(SPACING["large"])
        self.expandLayout.addWidget(self.show_about_label())
        self.expandLayout.addWidget(self.show_your_model())
        self.expandLayout.addWidget(self.show_your_custom_model())
        self.expandLayout.addWidget(self.show_your_board_id())
        self.expandLayout.addSpacing(26)
        self.expandLayout.addWidget(self.app_information())
        self.expandLayout.addSpacing(13)
        self.expandLayout.addWidget(self.hardware_information())
        self.expandLayout.addSpacing(13)
        self.expandLayout.addWidget(self.show_commit_information())
        self.expandLayout.addSpacing(13)
        self.expandLayout.addWidget(self.show_booted_information())
        self.expandLayout.addStretch()

    def show_about_label(self):
        title_label = SubtitleLabel("About MacBoxTool")
        title_label.setStyleSheet("font-size: 24px; font-weight: bold;")
        title_label.setAlignment(Qt.AlignCenter)
        return title_label

    def show_your_model(self):
        model = getattr(self.constants.computer, "real_model", "N/A") or "N/A"
        model_label = BodyLabel("Model: " + model)
        model_label.setAlignment(Qt.AlignCenter)
        return model_label

    def show_your_custom_model(self):
        model_label = BodyLabel("Custom Model: " + str(self.constants.custom_model))
        model_label.setAlignment(Qt.AlignCenter)
        return model_label

    def show_your_board_id(self):
        board_id = getattr(self.constants.computer, "real_board_id", "N/A") or "N/A"
        board_label = BodyLabel("Board id: " + board_id)
        board_label.setAlignment(Qt.AlignCenter)
        return board_label

    def app_information(self):
        widgets = QWidget()
        layout = QVBoxLayout(widgets)
        label = BodyLabel("Application Information")
        label.setAlignment(Qt.AlignLeft)
        layout.addWidget(label)
        layout.addWidget(SettingCard(FIF.APPLICATION, "MacBoxTool", f"Version {self.constants.macboxtool_version}", self))
        layout.addWidget(SettingCard(FIF.DEVELOPER_TOOLS, "Nightly Build", str(self.constants.nightly_build), self))
        layout.addWidget(SettingCard(FIF.ZIP_FOLDER, "PatcherSupportPkg Version", f"Version {self.constants.patcher_support_pkg_version}", self))
        layout.addWidget(SettingCard(FIF.PASTE, "Launcher Path", str(self.constants.launcher_binary), self))
        layout.addWidget(SettingCard(FIF.PASTE, "Payload Mount", str(self.constants.payload_path)))
        return widgets

    def show_commit_information(self):
        widgets = QWidget()
        layout = QVBoxLayout(widgets)
        commit_info = self.constants.commit_info or ("N/A", "N/A", "N/A")
        layout.addWidget(BodyLabel("Commit Information"))
        layout.addWidget(SettingCard(FIF.BRUSH, "Branch", str(commit_info[0])))
        layout.addWidget(SettingCard(FIF.DATE_TIME, "Date", str(commit_info[1])))
        layout.addWidget(SettingCard(FIF.WIFI, "URL", str(commit_info[2])))
        return widgets

    def show_booted_information(self):
        widgets = QWidget()
        layout = QVBoxLayout(widgets)
        computer = self.constants.computer
        layout.addWidget(BodyLabel("Booted Information"))
        layout.addWidget(SettingCard(FIF.CERTIFICATE, "Booted OS", f"XNU {self.constants.detected_os} ({self.constants.detected_os_version})"))
        layout.addWidget(SettingCard(FIF.ZIP_FOLDER, "Booted Patcher Version (MBT)", str(getattr(computer, "mbt_version", "N/A"))))
        layout.addWidget(SettingCard(FIF.ROTATE, "Booted OpenCore Version", str(getattr(computer, "opencore_version", "N/A"))))
        layout.addWidget(SettingCard(FIF.ROTATE, "Booted OpenCore Disk", str(getattr(self.constants, "booted_oc_disk", "N/A"))))
        return widgets

    @staticmethod
    def _device_cards(layout, title, device, extra_label=None, extra_value=None):
        if not device:
            return
        layout.addWidget(BodyLabel(title))
        layout.addWidget(SettingCard(FIF.TAG, "Name", str(getattr(device, "name", None) or "N/A")))
        vendor_id = getattr(device, "vendor_id", None)
        device_id = getattr(device, "device_id", None)
        layout.addWidget(SettingCard(FIF.CERTIFICATE, "Vendor ID", hex(vendor_id) if vendor_id else "N/A"))
        layout.addWidget(SettingCard(FIF.CODE, "Device ID", hex(device_id) if device_id else "N/A"))
        if extra_label and extra_value and str(extra_value) != "Unknown":
            layout.addWidget(SettingCard(FIF.DEVELOPER_TOOLS, extra_label, str(extra_value)))

    def hardware_information(self):
        widgets = QWidget()
        layout = QVBoxLayout(widgets)
        layout.setSpacing(SPACING["medium"])
        layout.addWidget(BodyLabel("Hardware Information"))
        computer = self.constants.computer
        cpu = getattr(computer, "cpu", None)
        layout.addWidget(BodyLabel("CPU"))
        if cpu:
            layout.addWidget(SettingCard(FIF.TAG, "Name", str(getattr(cpu, "name", None) or "N/A")))
            layout.addWidget(SettingCard(FIF.CERTIFICATE, "Vendor ID", str(getattr(cpu, "vendor_id", None) or "N/A")))
            device_id = getattr(cpu, "device_id", None)
            layout.addWidget(SettingCard(FIF.CODE, "Device ID (CPUID Model)", hex(device_id) if device_id else "N/A"))
            layout.addWidget(SettingCard(FIF.DEVELOPER_TOOLS, "Architecture", str(getattr(cpu, "architecture", None) or "N/A")))
            for title, icon, values in (("Leafs", FIF.LEAF, getattr(cpu, "leafs", None)), ("Flags", FIF.FLAG, getattr(cpu, "flags", None))):
                card = SettingCard(icon, title, _wrap_text(values or []))
                card.contentLabel.setWordWrap(True)
                card.contentLabel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                card.setMinimumHeight(70)
                layout.addWidget(card)
        else:
            layout.addWidget(SettingCard(FIF.INFO, "CPU", "No CPU data available"))

        self._device_cards(layout, "Integrated GPU", getattr(computer, "igpu", None), "Architecture", getattr(getattr(computer, "igpu", None), "arch", None))
        self._device_cards(layout, "Discrete GPU", getattr(computer, "dgpu", None), "Architecture", getattr(getattr(computer, "dgpu", None), "arch", None))
        igpu, dgpu = getattr(computer, "igpu", None), getattr(computer, "dgpu", None)
        for index, gpu in enumerate(getattr(computer, "gpus", None) or []):
            if gpu is not igpu and gpu is not dgpu:
                self._device_cards(layout, f"GPU #{index + 1}", gpu, "Architecture", getattr(gpu, "arch", None))
        self._device_cards(layout, "WiFi", getattr(computer, "wifi", None), "Chipset", getattr(getattr(computer, "wifi", None), "chipset", None))
        ethernet = getattr(computer, "ethernet", None) or []
        for index, adapter in enumerate(ethernet):
            suffix = f" #{index + 1}" if len(ethernet) > 1 else ""
            self._device_cards(layout, f"Ethernet{suffix}", adapter, "Chipset", getattr(adapter, "chipset", None))
        storage = getattr(computer, "storage", None) or []
        for index, device in enumerate(storage):
            suffix = f" #{index + 1}" if len(storage) > 1 else ""
            self._device_cards(layout, f"Storage{suffix}", device)
            class_code = getattr(device, "class_code", None)
            storage_type = "NVMe" if class_code in (0x010802, 0x018002) else "SATA" if class_code == 0x010601 else hex(class_code) if class_code else "N/A"
            layout.addWidget(SettingCard(FIF.ALBUM, "Type", storage_type))

        layout.addWidget(BodyLabel("Board / Model"))
        layout.addWidget(SettingCard(FIF.TAG, "Board ID", str(getattr(computer, "reported_board_id", None) or "N/A")))
        layout.addWidget(SettingCard(FIF.TAG, "Model", str(getattr(computer, "real_model", None) or "N/A")))
        return widgets
