"""
gui_settings.py: Settings page using Fluent Design components
"""
from ..include import *
from ..support import generate_smbios
from ..support import utilities
from .gui_support import DefGUI


class SettingsInterface(QWidget):

    def __init__(self, global_constants: Constants, ui_support: DefGUI = None, global_settings: GlobalSettings = None, parent=None):
        super().__init__(parent)
        self.setObjectName("Settings")
        self.constants = global_constants
        self.gui_support = ui_support
        self.settings = global_settings

        self.mainLayout = QVBoxLayout(self)
        self.mainLayout.setContentsMargins(36, 28, 36, 28)
        self.mainLayout.setSpacing(12)

        self._init_ui()
        self._load_settings()
        self._apply_hardware_conditions(self._current_model())

    def _current_model(self) -> str:
        saved = self.settings.find_key("MODEL")
        if saved and saved != "N/A" and saved in model_array.SupportedSMBIOS:
            return saved
        return self.constants.computer.real_model if self.constants.computer else ""

    def _init_ui(self):
        title = SubtitleLabel("Settings")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        self.mainLayout.addWidget(title)

        self._build_model_selector()
        self._build_tabs()

    # ── Model Selector ──

    def _build_model_selector(self):
        row = QHBoxLayout()
        row.setSpacing(12)
        lbl = StrongBodyLabel("Target Model:")
        self.model_combo = ComboBox()
        self.model_combo.addItem("Host Model")
        for m in model_array.SupportedSMBIOS:
            self.model_combo.addItem(m)

        saved = self.settings.find_key("MODEL")
        if saved and saved in model_array.SupportedSMBIOS:
            self.model_combo.setCurrentText(saved)
        else:
            self.model_combo.setCurrentText("Host Model")

        physical = self.constants.computer.real_model if self.constants.computer else "Unknown"
        self.model_info_label = BodyLabel(f"Physical: {physical}")

        row.addWidget(lbl)
        row.addWidget(self.model_combo, 1)
        row.addWidget(self.model_info_label)
        self.mainLayout.addLayout(row)
        self.model_combo.currentTextChanged.connect(self._on_model_changed)

    def _on_model_changed(self, text: str):
        if text == "Host Model":
            self.constants.custom_model = None
            model = self.constants.computer.real_model if self.constants.computer else ""
        else:
            self.constants.custom_model = text
            model = text
        self._save("MODEL", model if model else "N/A")
        self._apply_hardware_conditions(model)

    # ── Pivot Tabs ──

    def _build_tabs(self):
        self.pivot = Pivot(self)
        self.stack = QStackedWidget(self)

        self.tab_build = self._create_tab_scroll()
        self.tab_security = self._create_tab_scroll()
        self.tab_sip = self._create_tab_scroll()
        self.tab_smbios = self._create_tab_scroll()
        self.tab_misc = self._create_tab_scroll()
        self.tab_debug = self._create_tab_scroll()

        self._build_boot_group()
        self._build_graphics_group()
        self._build_security_group()
        self._build_sip_group()
        self._build_smbios_group()
        self._build_misc_group()
        self._build_debug_group()

        for tab in (self.tab_build, self.tab_security, self.tab_sip,
                    self.tab_smbios, self.tab_misc, self.tab_debug):
            tab._layout.addStretch()

        self._add_tab("build", "Build", self.tab_build)
        self._add_tab("security", "Security", self.tab_security)
        self._add_tab("sip", "SIP", self.tab_sip)
        self._add_tab("smbios", "SMBIOS", self.tab_smbios)
        self._add_tab("misc", "Misc", self.tab_misc)
        self._add_tab("debug", "Debug", self.tab_debug)
        self.pivot.setCurrentItem("build")

        self.mainLayout.addWidget(self.pivot)
        self.mainLayout.addWidget(self.stack, 1)

    def _create_tab_scroll(self):
        scroll = ScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.enableTransparentBackground()
        container = QWidget()
        container.setStyleSheet("QWidget { background: transparent; }")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 12, 0, 12)
        layout.setSpacing(12)
        scroll.setWidget(container)
        scroll._layout = layout
        scroll._container = container
        return scroll

    def _add_tab(self, key, label, widget):
        self.stack.addWidget(widget)
        self.pivot.addItem(
            routeKey=key, text=label,
            onClick=lambda checked, w=widget: self.stack.setCurrentWidget(w)
        )

    # ── Boot ──

    def _build_boot_group(self):
        group = SettingCardGroup("Boot", self.tab_build._container)

        self.sw_firewire = SwitchSettingCard(FIF.CONNECT, "FireWire Boot", "Boot macOS from FireWire drives", parent=group)
        self.sw_nvme = SwitchSettingCard(FIF.SPEED_HIGH, "NVMe Boot", "UEFI NVMe boot driver", parent=group)
        self.sw_xhci = SwitchSettingCard(FIF.LINK, "USB 3.0 Boot", "UEFI XHCI boot driver", parent=group)
        self.sw_showpicker = SwitchSettingCard(FIF.VIEW, "Show Boot Picker", "Display OpenCore boot menu", parent=group)
        self.sw_verbose = SwitchSettingCard(FIF.COMMAND_PROMPT, "Verbose Boot", "Enable -v boot flag", parent=group)

        for card in (self.sw_firewire, self.sw_nvme, self.sw_xhci, self.sw_showpicker, self.sw_verbose):
            group.addSettingCard(card)

        self.sw_firewire.checkedChanged.connect(lambda v: self._save("firewire_boot", v))
        self.sw_nvme.checkedChanged.connect(lambda v: self._save("nvme_boot", v))
        self.sw_xhci.checkedChanged.connect(lambda v: self._save("xhci_boot", v))
        self.sw_showpicker.checkedChanged.connect(lambda v: self._save("showpicker", v))
        self.sw_verbose.checkedChanged.connect(lambda v: self._save("verbose_debug", v))

        self.tab_build._layout.addWidget(group)

    # ── Graphics ──

    def _build_graphics_group(self):
        group = SettingCardGroup("Graphics", self.tab_build._container)

        # Graphics Override combo box
        self.cb_gpu_override = SettingCard(FIF.PROJECTOR, "Graphics Override", "Override detected GPU for socketed MXM iMacs", parent=group)
        self.cb_gpu_override.comboBox = ComboBox(self.cb_gpu_override)
        gpu_options = ["None", "Nvidia Kepler", "AMD GCN", "AMD Polaris", "AMD Lexa", "AMD Navi"]
        self.cb_gpu_override.comboBox.addItems(gpu_options)
        self.cb_gpu_override.hBoxLayout.addWidget(self.cb_gpu_override.comboBox, 0, Qt.AlignmentFlag.AlignRight)
        self.cb_gpu_override.hBoxLayout.addSpacing(16)
        group.addSettingCard(self.cb_gpu_override)

        self.sw_amd_gop = SwitchSettingCard(FIF.PROJECTOR, "AMD GOP Injection", "Inject AMD GCN GOP driver", parent=group)
        self.sw_nv_gop = SwitchSettingCard(FIF.PROJECTOR, "Nvidia Kepler GOP", "Inject Nvidia Kepler GOP driver", parent=group)

        for card in (self.cb_gpu_override, self.sw_amd_gop, self.sw_nv_gop):
            group.addSettingCard(card)

        self.cb_gpu_override.comboBox.currentTextChanged.connect(self._on_gpu_override_changed)
        self.sw_amd_gop.checkedChanged.connect(lambda v: self._save("amd_gop_injection", v))
        self.sw_nv_gop.checkedChanged.connect(lambda v: self._save("nvidia_kepler_gop_injection", v))

        self.tab_build._layout.addWidget(group)

    # ── Security ──

    def _build_security_group(self):
        group = SettingCardGroup("Security", self.tab_security._container)

        self.sw_sip = SwitchSettingCard(FIF.FRIGID, "Lower SIP", "Disable System Integrity Protection", parent=group)
        self.sw_secureboot = SwitchSettingCard(FIF.CERTIFICATE, "Secure Boot Model", "Enable Apple Secure Boot", parent=group)
        self.sw_amfi = SwitchSettingCard(FIF.FINGERPRINT, "Disable AMFI", "Set amfi=0x80 (breaks TCC)", parent=group)
        self.sw_cslv = SwitchSettingCard(FIF.TRANSPARENT, "Disable Library Validation", "Allow unsigned libraries", parent=group)
        self.sw_vault = SwitchSettingCard(FIF.SAVE, "Vault", "Enable EFI Vault signing", parent=group)

        for card in (self.sw_sip, self.sw_secureboot, self.sw_amfi, self.sw_cslv, self.sw_vault):
            group.addSettingCard(card)

        self.sw_sip.checkedChanged.connect(lambda v: self._save("sip_status", not v))
        self.sw_secureboot.checkedChanged.connect(lambda v: self._save("secure_status", v))
        self.sw_amfi.checkedChanged.connect(lambda v: self._save("disable_amfi", v))
        self.sw_cslv.checkedChanged.connect(lambda v: self._save("disable_cs_lv", v))
        self.sw_vault.checkedChanged.connect(lambda v: self._save("vault", v))

        self.tab_security._layout.addWidget(group)

    # ── SIP ──

    def _build_sip_group(self):
        group = SettingCardGroup("System Integrity Protection", self.tab_sip._container)

        # Current SIP value display
        if self.constants.custom_sip_value is not None:
            self._sip_value = int(self.constants.custom_sip_value, 16) if isinstance(self.constants.custom_sip_value, str) else int(self.constants.custom_sip_value)
        elif self.constants.sip_status is True:
            self._sip_value = 0x00
        else:
            self._sip_value = 0x803

        # Calculate flipped value: 0x803 -> 03080000
        flipped_value = self._calculate_sip_flipped(self._sip_value)
        self.sip_label_card = SettingCard(FIF.FRIGID, "Current SIP Value", f"{hex(self._sip_value)} -> {flipped_value}", parent=group)
        # Make the flipped part clickable to copy
        self.sip_label_card.contentLabel.setCursor(Qt.PointingHandCursor)
        self.sip_label_card.contentLabel.mousePressEvent = lambda _: self._copy_sip_flipped(flipped_value)
        group.addSettingCard(self.sip_label_card)

        self.sip_checks = {}
        for key, info in sip_data.system_integrity_protection.csr_values_extended.items():
            short = key.replace("CSR_", "")
            desc = f"{info['description']} (Introduced: {info['introduced_friendly']})"
            card = SwitchSettingCard(FIF.FRIGID, short, desc, parent=group)
            card.setChecked(bool(self._sip_value & info["value"]))
            card.checkedChanged.connect(lambda v, k=key: self._on_sip_bit_changed(k, v))
            group.addSettingCard(card)
            self.sip_checks[key] = card

        self.tab_sip._layout.addWidget(group)

    def _calculate_sip_flipped(self, sip_value: int) -> str:
        """Calculate flipped SIP value: remove 0x, reverse hex pairs, add 4 zeros"""
        hex_str = hex(sip_value).replace("0x", "")
        # Pad to even length if needed
        if len(hex_str) % 2:
            hex_str = "0" + hex_str
        # Use hexswap from utilities to reverse pairs
        flipped = utilities.hexswap(hex_str)
        # Add 4 zeros at the end
        return flipped + "0000"

    def _copy_sip_flipped(self, flipped_value: str):
        """Copy flipped value to clipboard"""
        clipboard = QApplication.clipboard()
        clipboard.setText(flipped_value)
        # Show feedback
        original_text = self.sip_label_card.contentLabel.text()
        self.sip_label_card.contentLabel.setText(f"Copied: {flipped_value}")
        QTimer.singleShot(1500, lambda: self.sip_label_card.contentLabel.setText(original_text))

    def _on_gpu_override_changed(self, text: str):
        """Handle GPU override selection change"""
        if text == "None":
            self.constants.imac_vendor = "None"
            self.constants.imac_model = ""
            self.constants.metal_build = False
            self._save("imac_vendor", "None")
            self._save("imac_model", "")
            self._save("metal_build", False)
        elif "AMD" in text:
            self.constants.imac_vendor = "AMD"
            self.constants.metal_build = True
            if "Polaris" in text:
                self.constants.imac_model = "Polaris"
            elif "GCN" in text:
                self.constants.imac_model = "GCN"
            elif "Lexa" in text:
                self.constants.imac_model = "Lexa"
            elif "Navi" in text:
                self.constants.imac_model = "Navi"
            else:
                self.constants.imac_model = ""
            self._save("imac_vendor", "AMD")
            self._save("imac_model", self.constants.imac_model)
            self._save("metal_build", True)
        elif "Nvidia" in text:
            self.constants.imac_vendor = "Nvidia"
            self.constants.metal_build = True
            if "Kepler" in text:
                self.constants.imac_model = "Kepler"
            else:
                self.constants.imac_model = ""
            self._save("imac_vendor", "Nvidia")
            self._save("imac_model", self.constants.imac_model)
            self._save("metal_build", True)
        logging.info(f"Updating GPU Selection: {text}")

    def _update_metal_build(self, vendor: str):
        """Update metal_build based on vendor selection"""
        self.constants.metal_build = vendor != "None"

    def _on_sip_bit_changed(self, key: str, checked: bool):
        bit_val = sip_data.system_integrity_protection.csr_values_extended[key]["value"]
        if checked:
            self._sip_value |= bit_val
        else:
            self._sip_value &= ~bit_val

        # Update flipped value
        flipped_value = self._calculate_sip_flipped(self._sip_value)
        combined_text = f"{hex(self._sip_value)} -> {flipped_value}"
        self.sip_label_card.setContent(combined_text)
        self.sip_label_card.contentLabel.setText(combined_text)
        # Re-bind click event with new value
        self.sip_label_card.contentLabel.mousePressEvent = lambda _: self._copy_sip_flipped(flipped_value)

        if self._sip_value == 0x0:
            self.constants.custom_sip_value = None
            self.constants.sip_status = True
        elif self._sip_value == 0x803:
            self.constants.custom_sip_value = None
            self.constants.sip_status = False
        else:
            self.constants.custom_sip_value = hex(self._sip_value)
        self._save("custom_sip_value", self.constants.custom_sip_value)
        self._save("sip_status", self.constants.sip_status)

    def _build_smbios_group(self):
        group = SettingCardGroup("SMBIOS Spoofing", self.tab_smbios._container)

        # Spoof Level
        self.cb_serial = SettingCard(FIF.PEOPLE, "SMBIOS Spoof Level", "Serial number spoofing level", parent=group)
        self.cb_serial.comboBox = ComboBox(self.cb_serial)
        for t in ("None", "Minimal", "Moderate", "Advanced"):
            self.cb_serial.comboBox.addItem(t)
        self.cb_serial.hBoxLayout.addWidget(self.cb_serial.comboBox, 0, Qt.AlignmentFlag.AlignRight)
        self.cb_serial.hBoxLayout.addSpacing(16)

        # Spoof Model
        self.cb_spoof_model = SettingCard(FIF.PEOPLE, "Spoof Model", "Override SMBIOS model for spoofing", parent=group)
        self.cb_spoof_model.comboBox = ComboBox(self.cb_spoof_model)
        self.cb_spoof_model.comboBox.addItem("Default")
        spoof_models = [
            model for model in smbios_data.smbios_dictionary
            if "_" not in model and " " not in model
            and smbios_data.smbios_dictionary[model]["Board ID"] is not None
        ]
        for m in spoof_models:
            self.cb_spoof_model.comboBox.addItem(m)
        self.cb_spoof_model.hBoxLayout.addWidget(self.cb_spoof_model.comboBox, 0, Qt.AlignmentFlag.AlignRight)
        self.cb_spoof_model.hBoxLayout.addSpacing(16)

        self.sw_native_spoof = SwitchSettingCard(FIF.SYNC, "Allow Native Spoofs", "Allow spoofing on native models", parent=group)

        group.addSettingCard(self.cb_serial)
        group.addSettingCard(self.cb_spoof_model)
        group.addSettingCard(self.sw_native_spoof)

        self.cb_serial.comboBox.currentTextChanged.connect(lambda v: self._save("serial_settings", v))
        self.cb_spoof_model.comboBox.currentTextChanged.connect(self._on_spoof_model_changed)
        self.sw_native_spoof.checkedChanged.connect(lambda v: self._save("allow_native_spoofs", v))

        self.tab_smbios._layout.addWidget(group)

        # Serial generation group
        sn_group = SettingCardGroup("Serial Number", self.tab_smbios._container)

        self.sn_serial_card = SettingCard(FIF.EDIT, "Custom Serial Number", "Override SMBIOS serial", parent=sn_group)
        self.sn_serial_edit = LineEdit(self.sn_serial_card)
        self.sn_serial_edit.setPlaceholderText("Serial Number")
        self.sn_serial_edit.setClearButtonEnabled(True)
        self.sn_serial_edit.setText(self.constants.custom_serial_number)
        self.sn_serial_card.hBoxLayout.addWidget(self.sn_serial_edit, 0, Qt.AlignmentFlag.AlignRight)
        self.sn_serial_card.hBoxLayout.addSpacing(16)
        sn_group.addSettingCard(self.sn_serial_card)

        self.sn_board_card = SettingCard(FIF.EDIT, "Custom Board Serial", "Override SMBIOS board serial", parent=sn_group)
        self.sn_board_edit = LineEdit(self.sn_board_card)
        self.sn_board_edit.setPlaceholderText("Board Serial")
        self.sn_board_edit.setClearButtonEnabled(True)
        self.sn_board_edit.setText(self.constants.custom_board_serial_number)
        self.sn_board_card.hBoxLayout.addWidget(self.sn_board_edit, 0, Qt.AlignmentFlag.AlignRight)
        self.sn_board_card.hBoxLayout.addSpacing(16)
        sn_group.addSettingCard(self.sn_board_card)

        self.sn_gen_card = SettingCard(FIF.SYNC, "Generate Serial", "Generate serial for spoof/target model via macserial", parent=sn_group)
        self.sn_gen_btn = PrimaryPushButton("Generate")
        self.sn_gen_btn.clicked.connect(self._on_generate_serial)
        self.sn_gen_card.hBoxLayout.addWidget(self.sn_gen_btn, 0, Qt.AlignmentFlag.AlignRight)
        self.sn_gen_card.hBoxLayout.addSpacing(16)
        sn_group.addSettingCard(self.sn_gen_card)

        self.sn_serial_edit.textChanged.connect(lambda v: self._save("custom_serial_number", v))
        self.sn_board_edit.textChanged.connect(lambda v: self._save("custom_board_serial_number", v))

        self.tab_smbios._layout.addWidget(sn_group)

    def _on_spoof_model_changed(self, text: str):
        if text == "Default":
            self.constants.override_smbios = "Default"
        else:
            self.constants.override_smbios = text
        self._save("override_smbios", self.constants.override_smbios)

    def _get_serial_target_model(self) -> str:
        """Get the model to use for serial generation: spoof model > target model."""
        if self.constants.override_smbios != "Default":
            return self.constants.override_smbios
        return self.constants.custom_model or (
            self.constants.computer.real_model if self.constants.computer else ""
        )

    def _on_generate_serial(self):
        model = self._get_serial_target_model()
        if not model:
            return

        # Warning dialog
        w = MessageBox(
            "Warning",
            "Please take caution when using serial spoofing. "
            "This should only be used on machines that were legally obtained and require reserialization.\n\n"
            "Note: new serials are only overlayed through OpenCore and are not permanently installed into ROM.\n\n"
            "Misuse of this setting can break power management and other aspects of the OS "
            "if the system does not need spoofing.\n\n"
            "Are you certain you want to continue?",
            self.window()
        )
        w.yesButton.setText("Continue")
        w.cancelButton.setText("Cancel")
        if w.exec() != 1:
            return

        try:
            result = subprocess.run(
                [str(self.constants.macserial_path), "--generate", "--model", model, "--num", "1"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=10
            )
            parts = result.stdout.decode().strip().split(" | ")
            if len(parts) == 2:
                self.sn_serial_edit.setText(parts[0])
                self.sn_board_edit.setText(parts[1])
            else:
                err = MessageBox("Error", f"Failed to generate serial number:\n\n{result.stdout.decode().strip()}", self.window())
                err.cancelButton.hide()
                err.exec()
        except Exception as e:
            err = MessageBox("Error", f"Failed to generate serial number:\n\n{e}", self.window())
            err.cancelButton.hide()
            err.exec()

    # ── Misc ──

    def _build_misc_group(self):
        group = SettingCardGroup("Miscellaneous", self.tab_misc._container)

        self.sw_wowl = SwitchSettingCard(FIF.WIFI, "Wake on WLAN", "Enable Wake on Wireless LAN", parent=group)
        self.sw_tb = SwitchSettingCard(FIF.REMOVE, "Disable Thunderbolt", "Disable TB controller (MacBookPro11,x)", parent=group)
        self.sw_cpufriend = SwitchSettingCard(FIF.SPEED_OFF, "Disable CPUFriend", "Skip CPUFriend kext", parent=group)
        self.sw_fw_throttle = SwitchSettingCard(FIF.SPEED_HIGH, "Disable FW Throttle", "Disable firmware power throttling", parent=group)
        self.sw_media = SwitchSettingCard(FIF.PHOTO, "Disable mediaanalysisd", "Block via RestrictEvents", parent=group)

        for card in (self.sw_wowl, self.sw_tb, self.sw_cpufriend, self.sw_fw_throttle, self.sw_media):
            group.addSettingCard(card)

        self.sw_wowl.checkedChanged.connect(lambda v: self._save("enable_wake_on_wlan", v))
        self.sw_tb.checkedChanged.connect(lambda v: self._save("disable_tb", v))
        self.sw_cpufriend.checkedChanged.connect(lambda v: self._save("disallow_cpufriend", v))
        self.sw_fw_throttle.checkedChanged.connect(lambda v: self._save("disable_fw_throttle", v))
        self.sw_media.checkedChanged.connect(lambda v: self._save("disable_mediaanalysisd", v))

        self.tab_misc._layout.addWidget(group)

    # ── Debug ──

    def _build_debug_group(self):
        group = SettingCardGroup("Debug", self.tab_debug._container)

        self.sw_oc_debug = SwitchSettingCard(FIF.COMMAND_PROMPT, "OpenCore Debug", "Enable OpenCore debug mode", parent=group)
        self.sw_kext_debug = SwitchSettingCard(FIF.CODE, "Kext Debug", "Enable Lilu debug + DebugEnhancer", parent=group)

        group.addSettingCard(self.sw_oc_debug)
        group.addSettingCard(self.sw_kext_debug)

        self.sw_oc_debug.checkedChanged.connect(lambda v: self._save("opencore_debug", v))
        self.sw_kext_debug.checkedChanged.connect(lambda v: self._save("kext_debug", v))

        self.tab_debug._layout.addWidget(group)

        # Add Global Settings viewer
        settings_group = SettingCardGroup("Global Settings", self.tab_debug._container)

        # Key input field using SearchLineEdit - placed more to the left
        self.settings_key_input = SearchLineEdit(self)
        self.settings_key_input.setPlaceholderText("Enter key to search...")
        settings_key_card = SettingCard(FIF.SEARCH, "Search Key", parent=settings_group)
        settings_key_card.hBoxLayout.addWidget(self.settings_key_input, 0, Qt.AlignmentFlag.AlignLeft)
        settings_key_card.hBoxLayout.addStretch(1)

        # Result display using ExpandGroupSettingCard with addGroup
        self.settings_expand_card = ExpandGroupSettingCard(
            FIF.INFO,
            "Search Result",
            "Click to expand",
            parent=settings_group
        )
        self.settings_key_label = BodyLabel("No key searched yet")
        self.settings_value_label = BodyLabel("Enter a key above and press Enter or click search button")
        self.settings_key_label.setWordWrap(True)
        self.settings_value_label.setWordWrap(True)

        # Use addGroup to add key-value pairs
        self.settings_expand_card.addGroup(FIF.INFO, "Key", "", self.settings_key_label)
        self.settings_expand_card.addGroup(FIF.CODE, "Value", "", self.settings_value_label)

        settings_group.addSettingCard(settings_key_card)
        settings_group.addSettingCard(self.settings_expand_card)

        # Connect search on Enter key or search button click
        self.settings_key_input.searchSignal.connect(lambda text: self._search_settings_key(text))

        self.tab_debug._layout.addWidget(settings_group)

    def _search_settings_key(self, key: str):
        """Search for a key in global settings and display its value"""
        if not key:
            self.settings_key_label.setText("No key searched yet")
            self.settings_value_label.setText("Enter a key above and press Enter or click search button")
            return

        value = self.settings.find_key(key)
        if value is not None:
            # Format the value for display
            if isinstance(value, dict):
                value_str = json.dumps(value, indent=2)
            elif isinstance(value, list):
                value_str = str(value)
            else:
                value_str = str(value)
            self.settings_key_label.setText(key)
            self.settings_value_label.setText(value_str)
        else:
            self.settings_key_label.setText("Not found")
            self.settings_value_label.setText("N/A")

        # Expand the card to show results
        self.settings_expand_card.setExpand(True)

    # ── Persistence ──

    def _save(self, key: str, value):
        setattr(self.constants, key, value)
        if self.settings.check_key(key):
            self.settings.edit_key(key, value)
        else:
            self.settings.add_key(key, value)

    def _load_settings(self):
        def _get(key, default):
            v = self.settings.find_key(key)
            if v is not None:
                setattr(self.constants, key, v)
                return v
            return getattr(self.constants, key, default)

        self.sw_firewire.setChecked(_get("firewire_boot", False))
        self.sw_nvme.setChecked(_get("nvme_boot", False))
        self.sw_xhci.setChecked(_get("xhci_boot", False))
        self.sw_showpicker.setChecked(_get("showpicker", True))
        self.sw_verbose.setChecked(_get("verbose_debug", False))

        self.sw_sip.setChecked(not _get("sip_status", True))
        self.sw_secureboot.setChecked(_get("secure_status", False))
        self.sw_amfi.setChecked(_get("disable_amfi", False))
        self.sw_cslv.setChecked(_get("disable_cs_lv", False))
        self.sw_vault.setChecked(_get("vault", False))

        level = _get("serial_settings", "None")
        idx = self.cb_serial.comboBox.findText(level)
        if idx >= 0:
            self.cb_serial.comboBox.setCurrentIndex(idx)
        self.sw_native_spoof.setChecked(_get("allow_native_spoofs", False))

        # Spoof Model
        spoof_model = _get("override_smbios", "Default")
        idx = self.cb_spoof_model.comboBox.findText(spoof_model)
        if idx >= 0:
            self.cb_spoof_model.comboBox.setCurrentIndex(idx)

        # Graphics Override
        gpu_override = _get("imac_vendor", "None")
        if gpu_override != "None":
            # Restore full selection (e.g., "AMD Polaris")
            model = _get("imac_model", "")
            full_selection = f"{gpu_override} {model}" if model else gpu_override
            idx = self.cb_gpu_override.comboBox.findText(full_selection)
            if idx >= 0:
                self.cb_gpu_override.comboBox.setCurrentIndex(idx)
        self._update_metal_build(gpu_override)

        self.sw_amd_gop.setChecked(_get("amd_gop_injection", False))
        self.sw_nv_gop.setChecked(_get("nvidia_kepler_gop_injection", False))

        self.sn_serial_edit.setText(_get("custom_serial_number", ""))
        self.sn_board_edit.setText(_get("custom_board_serial_number", ""))

        self.sw_wowl.setChecked(_get("enable_wake_on_wlan", False))
        self.sw_tb.setChecked(_get("disable_tb", False))
        self.sw_cpufriend.setChecked(_get("disallow_cpufriend", False))
        self.sw_fw_throttle.setChecked(_get("disable_fw_throttle", False))
        self.sw_media.setChecked(_get("disable_mediaanalysisd", False))

        self.sw_oc_debug.setChecked(_get("opencore_debug", False))
        self.sw_kext_debug.setChecked(_get("kext_debug", False))

    # ── Hardware Conditions ──

    # Socketed GPU models that support Graphics Override
    SOCKETED_GPU_MODELS = ["iMac9,1", "iMac10,1", "iMac11,1", "iMac11,2", "iMac11,3", "iMac12,1", "iMac12,2"]

    def _apply_hardware_conditions(self, model: str):
        info = smbios_data.smbios_dictionary.get(model, {})
        cpu_gen = info.get("CPU Generation", 99)

        # FireWire: use generate_smbios.check_firewire
        self._set_card_enabled(self.sw_firewire,
            generate_smbios.check_firewire(model) is not False if model else False)

        # NVMe/XHCI: pre-Ivy Bridge only
        pre_ivy = cpu_gen < cpu_data.CPUGen.ivy_bridge.value
        self._set_card_enabled(self.sw_nvme, pre_ivy)
        self._set_card_enabled(self.sw_xhci, pre_ivy)

        # Thunderbolt: MacBookPro11,x only
        self._set_card_enabled(self.sw_tb,
            model in ("MacBookPro11,1", "MacBookPro11,2", "MacBookPro11,3"))

        # GOP injection: socketed GPU models only
        has_socketed = "Socketed GPUs" in info
        self._set_card_enabled(self.sw_amd_gop, has_socketed)
        self._set_card_enabled(self.sw_nv_gop, has_socketed)

        # Graphics Override: only for socketed GPU models
        is_socketed_gpu = model in self.SOCKETED_GPU_MODELS
        self._set_card_enabled(self.cb_gpu_override, is_socketed_gpu)

    def _set_card_enabled(self, card, enabled: bool):
        card.setEnabled(enabled)
        if not enabled and hasattr(card, 'setChecked'):
            card.setChecked(False)

    def refresh(self):
        self._load_settings()
        self._apply_hardware_conditions(self._current_model())
