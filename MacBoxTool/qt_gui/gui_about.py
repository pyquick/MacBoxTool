"""
gui_about.py: Show about UI
"""

from ..include import *
from .gui_support import DefGUI

def _wrap_text(items: list, width: int = 50) -> str:
    """Join items and insert line breaks every `width` characters."""
    if not items:
        return "N/A"
    result = []
    current_line = ""
    for item in items:
        if current_line:
            candidate = current_line + "  " + item
        else:
            candidate = item
        if len(candidate) > width and current_line:
            result.append(current_line)
            current_line = item
        else:
            current_line = candidate
    if current_line:
        result.append(current_line)
    return "\n".join(result)

class AboutInterface(ScrollArea):

    def __init__(self, global_constants:Constants,ui_support:DefGUI=None,global_settings:GlobalSettings=None,parent=None):
        super().__init__(parent)


        logging.info("init gui_about")


        # SetObject
        self.setObjectName("About")
        # Add constants
        self.constants=global_constants
        self.gui_support=ui_support
        self.settings=global_settings
        #Add QWidgets
        self.scrollWidget = QWidget()
        self.expandLayout = QVBoxLayout(self.scrollWidget)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # Interface
        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)
        self.enableTransparentBackground()

        #self.settings.add_key("MODEL","N/A")

        self.init_ui()

    def init_ui(self):

        self.expandLayout.setContentsMargins(
            SPACING["xxlarge"], SPACING["xlarge"],
            SPACING["xxlarge"], SPACING["xlarge"]
        )
        self.expandLayout.setSpacing(SPACING["large"])

        #Gen
        self.expandLayout.addWidget(self.show_about_label())
        self.expandLayout.addWidget(self.show_your_model())
        self.expandLayout.addWidget(self.show_your_custom_model())
        self.expandLayout.addWidget(self.show_your_board_id())
        self.expandLayout.addSpacing(26)
        # App Information
        self.expandLayout.addWidget(self.app_information())

        self.expandLayout.addSpacing(13)
        self.expandLayout.addWidget(self.hardware_information())
        self.expandLayout.addSpacing(13)
        self.expandLayout.addWidget(self.show_commit_information())
        self.expandLayout.addSpacing(13)
        self.expandLayout.addWidget(self.show_booted_information())
        self.expandLayout.addStretch()


    def show_about_label(self):
        self.label="About MacBoxTool"
        title_label = SubtitleLabel(self.label)
        title_label.setStyleSheet("font-size: 24px; font-weight: bold;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return title_label

    def show_custom_label(self):
        self.label="Custom Label"
        title_label = SubtitleLabel(self.label)
        title_label.setStyleSheet("font-size: 24px; font-weight: bold;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return title_label

    def show_your_model(self):
        self.model= self.constants.computer.real_model
        model_label = BodyLabel("Model:"+" "+self.model)
        model_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return model_label

    def show_your_custom_model(self):
        self.model= str(self.constants.custom_model)
        model_label = BodyLabel("Custom Model:"+" "+self.model)
        model_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return model_label

    def show_your_board_id(self):
        self.board_id= self.constants.computer.real_board_id
        board_label = BodyLabel("Board id:"+" "+self.board_id)
        board_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return board_label


    def app_information(self):
        widgets=QWidget()
        expandLayout = QVBoxLayout(widgets)
        self.model= self.constants.computer.real_model
        model_label = BodyLabel("Application Information")
        model_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        version_card=SettingCard(
            FIF.APPLICATION,
            "MacBoxTool",
            f"Version {self.constants.macboxtool_version}",
            self
        )
        nbuild_card=SettingCard(
            FIF.DEVELOPER_TOOLS,
            "Nightly Build",
            f"{self.constants.nightly_build}",
            self
        )
        pversion_card=SettingCard(
            FIF.ZIP_FOLDER,
            "PatcherSupportPkg Version",
            f"Version {self.constants.patcher_support_pkg_version}",
            self
        )

        path_card=SettingCard(
            FIF.PASTE,
            "Luancher Path",
            f"{self.constants.launcher_binary}",
            self
        )
        mount_card= SettingCard(
            FIF.PASTE,
            "Payload Mount",
            f"{self.constants.payload_path}"
        )
        expandLayout.addWidget(version_card)
        expandLayout.addWidget(nbuild_card)
        expandLayout.addWidget(pversion_card)
        expandLayout.addWidget(path_card)
        expandLayout.addWidget(mount_card)

        return widgets


    def show_commit_information(self):
        widgets=QWidget()
        expandLayout = QVBoxLayout(widgets)
        commit_label = BodyLabel("Commit Information")
        branch_card=SettingCard(
            FIF.BRUSH,
            "Branch",
            f"{self.constants.commit_info[0]}",
        )
        date_card=SettingCard(
            FIF.DATE_TIME,
            "Date",
            f"{self.constants.commit_info[1]}",
        )
        url_card=SettingCard(
            FIF.WIFI,
            "URL",
            f"{self.constants.commit_info[2]}",
        )
        expandLayout.addWidget(commit_label)
        expandLayout.addWidget(branch_card)
        expandLayout.addWidget(date_card)
        expandLayout.addWidget(url_card)
        return widgets

    def show_booted_information(self):
        widgets=QWidget()
        expandLayout = QVBoxLayout(widgets)
        booted_label = BodyLabel("Booted Information")
        btos_card=SettingCard(
            FIF.CERTIFICATE,
            "Booted OS",
            f"XNU {self.constants.detected_os} ({self.constants.detected_os_version})",
        )
        btpv_card=SettingCard(
            FIF.ZIP_FOLDER,
            "Booted Patcher Version (MBT)",
            f"{self.constants.computer.mbt_version}",
        )
        btoc_card=SettingCard(
            FIF.ROTATE,
            "Booted Opencore Version",
            f"{self.constants.computer.opencore_version}",
        )
        btod_card=SettingCard(
            FIF.ROTATE,
            "Booted Opencore Disk",
            f"{self.constants.booted_oc_disk}",
        )
        expandLayout.addWidget(booted_label)
        expandLayout.addWidget(btos_card)
        expandLayout.addWidget(btpv_card)
        expandLayout.addWidget(btoc_card)
        expandLayout.addWidget(btod_card)

        return widgets

    def hardware_information(self):
        widgets = QWidget()
        expandLayout = QVBoxLayout(widgets)
        expandLayout.setSpacing(SPACING["medium"])

        label = BodyLabel("Hardware Information")
        expandLayout.addWidget(label)

        cpu = self.constants.computer.cpu
        igpu = self.constants.computer.igpu
        dgpu = self.constants.computer.dgpu
        gpus = self.constants.computer.gpus or []
        wifi = self.constants.computer.wifi
        ethernet_list = self.constants.computer.ethernet or []
        storage_list = self.constants.computer.storage or []
        board_id = self.constants.computer.reported_board_id or ""
        model = self.constants.computer.real_model or ""

        # --- CPU section ---

        expandLayout.addWidget(BodyLabel("CPU"))

        if cpu:
            expandLayout.addWidget(SettingCard(FIF.TAG, "Name", cpu.name or "N/A"))
            expandLayout.addWidget(SettingCard(FIF.CERTIFICATE, "Vendor ID", cpu.vendor_id or "N/A"))
            did = hex(cpu.device_id) if cpu.device_id else "N/A"
            expandLayout.addWidget(SettingCard(FIF.CODE, "Device ID (CPUID Model)", did))
            expandLayout.addWidget(SettingCard(FIF.DEVELOPER_TOOLS, "Architecture", cpu.architecture or "N/A"))
            leafs = cpu.leafs if cpu.leafs else []
            leafs_text = _wrap_text(leafs, 50)
            leafs_card = SettingCard(FIF.LEAF, "Leafs", leafs_text)
            leafs_card.contentLabel.setWordWrap(True)
            leafs_card.contentLabel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            leafs_card.setMinimumHeight(70)
            leafs_card.setMaximumHeight(16777215)
            expandLayout.addWidget(leafs_card)
            flags = cpu.flags if cpu.flags else []
            flags_text = _wrap_text(flags, 50)
            flags_card = SettingCard(FIF.FLAG, "Flags", flags_text)
            flags_card.contentLabel.setWordWrap(True)
            flags_card.contentLabel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            flags_card.setMinimumHeight(70)
            flags_card.setMaximumHeight(16777215)
            expandLayout.addWidget(flags_card)
        else:
            expandLayout.addWidget(SettingCard(FIF.INFO, "CPU", "No CPU data available"))

        # --- IGPU section ---

        if igpu:
            expandLayout.addWidget(BodyLabel("Integrated GPU"))
            expandLayout.addWidget(SettingCard(FIF.TAG, "Name", igpu.name or "N/A"))
            expandLayout.addWidget(SettingCard(FIF.CERTIFICATE, "Vendor ID", hex(igpu.vendor_id) if igpu.vendor_id else "N/A"))
            expandLayout.addWidget(SettingCard(FIF.CODE, "Device ID", hex(igpu.device_id) if igpu.device_id else "N/A"))
            if hasattr(igpu, "arch") and igpu.arch and str(igpu.arch) != "Unknown":
                expandLayout.addWidget(SettingCard(FIF.DEVELOPER_TOOLS, "Architecture", str(igpu.arch)))

        # --- dGPU section ---

        if dgpu:
            expandLayout.addWidget(BodyLabel("Discrete GPU"))
            expandLayout.addWidget(SettingCard(FIF.TAG, "Name", dgpu.name or "N/A"))
            expandLayout.addWidget(SettingCard(FIF.CERTIFICATE, "Vendor ID", hex(dgpu.vendor_id) if dgpu.vendor_id else "N/A"))
            expandLayout.addWidget(SettingCard(FIF.CODE, "Device ID", hex(dgpu.device_id) if dgpu.device_id else "N/A"))
            if hasattr(dgpu, "arch") and dgpu.arch and str(dgpu.arch) != "Unknown":
                expandLayout.addWidget(SettingCard(FIF.DEVELOPER_TOOLS, "Architecture", str(dgpu.arch)))

        # --- remaining GPUs (not igpu/dgpu) ---

        for i, gpu in enumerate(gpus):
            if (igpu and gpu is igpu) or (dgpu and gpu is dgpu):
                continue
            expandLayout.addWidget(BodyLabel(f"GPU #{i + 1}"))
            expandLayout.addWidget(SettingCard(FIF.TAG, "Name", gpu.name or "N/A"))
            expandLayout.addWidget(SettingCard(FIF.CERTIFICATE, "Vendor ID", hex(gpu.vendor_id) if gpu.vendor_id else "N/A"))
            expandLayout.addWidget(SettingCard(FIF.CODE, "Device ID", hex(gpu.device_id) if gpu.device_id else "N/A"))
            if hasattr(gpu, "arch") and gpu.arch and str(gpu.arch) != "Unknown":
                expandLayout.addWidget(SettingCard(FIF.DEVELOPER_TOOLS, "Architecture", str(gpu.arch)))

        # --- WiFi section ---

        if wifi:
            expandLayout.addWidget(BodyLabel("WiFi"))
            expandLayout.addWidget(SettingCard(FIF.TAG, "Name", wifi.name or "N/A"))
            expandLayout.addWidget(SettingCard(FIF.CERTIFICATE, "Vendor ID", hex(wifi.vendor_id) if wifi.vendor_id else "N/A"))
            expandLayout.addWidget(SettingCard(FIF.CODE, "Device ID", hex(wifi.device_id) if wifi.device_id else "N/A"))
            if hasattr(wifi, "chipset") and wifi.chipset and str(wifi.chipset) != "Unknown":
                expandLayout.addWidget(SettingCard(FIF.DEVELOPER_TOOLS, "Chipset", str(wifi.chipset)))

        # --- Ethernet section ---

        for i, eth in enumerate(ethernet_list):
            label_suffix = f" #{i + 1}" if len(ethernet_list) > 1 else ""
            expandLayout.addWidget(BodyLabel(f"Ethernet{label_suffix}"))
            expandLayout.addWidget(SettingCard(FIF.TAG, "Name", eth.name or "N/A"))
            expandLayout.addWidget(SettingCard(FIF.CERTIFICATE, "Vendor ID", hex(eth.vendor_id) if eth.vendor_id else "N/A"))
            expandLayout.addWidget(SettingCard(FIF.CODE, "Device ID", hex(eth.device_id) if eth.device_id else "N/A"))
            if hasattr(eth, "chipset") and eth.chipset and str(eth.chipset) != "Unknown":
                expandLayout.addWidget(SettingCard(FIF.DEVELOPER_TOOLS, "Chipset", str(eth.chipset)))

        # --- Storage section ---

        for i, stor in enumerate(storage_list):
            label_suffix = f" #{i + 1}" if len(storage_list) > 1 else ""
            expandLayout.addWidget(BodyLabel(f"Storage{label_suffix}"))
            expandLayout.addWidget(SettingCard(FIF.TAG, "Name", stor.name or "N/A"))
            expandLayout.addWidget(SettingCard(FIF.CERTIFICATE, "Vendor ID", hex(stor.vendor_id) if stor.vendor_id else "N/A"))
            expandLayout.addWidget(SettingCard(FIF.CODE, "Device ID", hex(stor.device_id) if stor.device_id else "N/A"))
            stor_type = "NVMe" if stor.class_code in (0x010802, 0x018002) else "SATA" if stor.class_code == 0x010601 else hex(stor.class_code) if stor.class_code else "N/A"
            expandLayout.addWidget(SettingCard(FIF.ALBUM, "Type", stor_type))

        # --- Board / Model section ---

        expandLayout.addWidget(BodyLabel("Board / Model"))
        expandLayout.addWidget(SettingCard(FIF.TAG, "Board ID", board_id if board_id else "N/A"))
        expandLayout.addWidget(SettingCard(FIF.TAG, "Model", model if model else "N/A"))

        return widgets
