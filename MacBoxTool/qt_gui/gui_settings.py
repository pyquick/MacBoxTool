"""
gui_settings.py: Settings page using Fluent Design components
"""
from ..include import *
from ..support import generate_smbios
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

        self.sw_drm = SwitchSettingCard(FIF.VIDEO, "DRM Support", "Enable iMac14,x DRM patches", parent=group)
        self.sw_amd_gop = SwitchSettingCard(FIF.PROJECTOR, "AMD GOP Injection", "Inject AMD GCN GOP driver", parent=group)
        self.sw_nv_gop = SwitchSettingCard(FIF.PROJECTOR, "Nvidia Kepler GOP", "Inject Nvidia Kepler GOP driver", parent=group)

        for card in (self.sw_drm, self.sw_amd_gop, self.sw_nv_gop):
            group.addSettingCard(card)

        self.sw_drm.checkedChanged.connect(lambda v: self._save("drm_support", v))
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

        self.sip_label_card = SettingCard(FIF.FRIGID, "Current SIP Value", f"{hex(self._sip_value)}", parent=group)
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

    def _on_sip_bit_changed(self, key: str, checked: bool):
        bit_val = sip_data.system_integrity_protection.csr_values_extended[key]["value"]
        if checked:
            self._sip_value |= bit_val
        else:
            self._sip_value &= ~bit_val

        self.sip_label_card.setContent(f"{hex(self._sip_value)}")
        self.sip_label_card.contentLabel.setText(f"{hex(self._sip_value)}")

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

        self.cb_serial = SettingCard(FIF.PEOPLE, "SMBIOS Spoof Level", "Serial number spoofing level", parent=group)
        self.cb_serial.comboBox = ComboBox(self.cb_serial)
        for t in ("None", "Minimal", "Moderate", "Advanced"):
            self.cb_serial.comboBox.addItem(t)
        self.cb_serial.hBoxLayout.addWidget(self.cb_serial.comboBox, 0, Qt.AlignmentFlag.AlignRight)
        self.cb_serial.hBoxLayout.addSpacing(16)
        self.sw_native_spoof = SwitchSettingCard(FIF.SYNC, "Allow Native Spoofs", "Allow spoofing on native models", parent=group)

        group.addSettingCard(self.cb_serial)
        group.addSettingCard(self.sw_native_spoof)

        self.cb_serial.comboBox.currentTextChanged.connect(lambda v: self._save("serial_settings", v))
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

        self.sn_gen_card = SettingCard(FIF.SYNC, "Generate Serial", "Generate serial for target model via macserial", parent=sn_group)
        self.sn_gen_btn = PrimaryPushButton("Generate")
        self.sn_gen_btn.clicked.connect(self._on_generate_serial)
        self.sn_gen_card.hBoxLayout.addWidget(self.sn_gen_btn, 0, Qt.AlignmentFlag.AlignRight)
        self.sn_gen_card.hBoxLayout.addSpacing(16)
        sn_group.addSettingCard(self.sn_gen_card)

        self.sn_serial_edit.textChanged.connect(lambda v: self._save("custom_serial_number", v))
        self.sn_board_edit.textChanged.connect(lambda v: self._save("custom_board_serial_number", v))

        self.tab_smbios._layout.addWidget(sn_group)

    def _on_generate_serial(self):
        model = self._current_model()
        if not model:
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
        except Exception:
            pass

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

        self.sw_drm.setChecked(_get("drm_support", False))
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

        # DRM: iMac13/14 with Nvidia
        self._set_card_enabled(self.sw_drm, model in model_array.IntelNvidiaDRM)

    def _set_card_enabled(self, card, enabled: bool):
        card.setEnabled(enabled)
        if not enabled and hasattr(card, 'setChecked'):
            card.setChecked(False)

    def refresh(self):
        self._load_settings()
        self._apply_hardware_conditions(self._current_model())
