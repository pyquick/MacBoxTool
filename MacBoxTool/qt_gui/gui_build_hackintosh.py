"""
gui_build_hackintosh.py: Build OpenCore EFI for Hackintosh

Uses efi_hack module (not efi_mac) to build EFI based on detected hardware.
UI pattern unified with gui_build.py (BuildOCPage).
"""
from ..include import *
from .gui_support import DefGUI, ProgressStatusHelper
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl

import sys
if sys.platform == "darwin":
    try:
        from ..support.install_helper import check_helper_installed
    except ImportError:
        check_helper_installed = None
else:
    check_helper_installed = None


class _SignalHandler(logging.Handler):
    """Logging handler that emits Qt signals for real-time log display."""
    def __init__(self, log_signal, progress_signal=None, total_steps=1):
        super().__init__()
        self._log_signal = log_signal
        self._progress_signal = progress_signal
        self._total_steps = total_steps
        self._step_count = 0

    def emit(self, record):
        msg = self.format(record)
        self._log_signal.emit(msg)
        if self._progress_signal and msg.startswith("[STEP]"):
            self._step_count += 1
            pct = min(int(self._step_count / self._total_steps * 100), 99)
            self._progress_signal.emit(pct)


class HackBuildWorker(QThread):
    """Background thread for Hackintosh EFI build using efi_hack."""
    log_signal = Signal(str)
    progress_signal = Signal(int)
    finished_signal = Signal(bool, str)

    TOTAL_STEPS = 10  # base + acpi + kexts + drivers + quirks + nvram + pi + cleanup + save + validate

    def __init__(self, smbios_model: str, constants, target_macos_versions: list = None, target_macos: str = ""):
        super().__init__()
        self.smbios_model = smbios_model
        self.constants = constants
        self.target_macos_versions = target_macos_versions or []
        self.target_macos = target_macos

    def run(self):
        handler = _SignalHandler(self.log_signal, self.progress_signal, self.TOTAL_STEPS)
        handler.setFormatter(logging.Formatter("%(message)s"))
        hack_logger = logging.getLogger("MacBoxTool.efi_hack")
        hack_logger.setLevel(logging.DEBUG)
        hack_logger.addHandler(handler)

        try:
            from ..efi_hack.builder import HackintoshBuilder
            builder = HackintoshBuilder(self.smbios_model, self.constants,
                                         target_macos=self.target_macos,
                                         target_macos_versions=self.target_macos_versions)
            builder.build()
            self.progress_signal.emit(100)
            self.finished_signal.emit(True, str(builder.paths["oc_build"]))
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            # Print to console for debugging
            print(f"[BUILD ERROR] {e}", flush=True)
            print(tb, flush=True)
            self.log_signal.emit(f"[ERROR] {e}")
            self.log_signal.emit(tb)
            self.finished_signal.emit(False, str(e))
        finally:
            hack_logger.removeHandler(handler)


class BuildHackintosh(ScrollArea):

    def __init__(self, global_constants: Constants, ui_support: DefGUI = None,
                 global_settings: GlobalSettings = None, parent=None):
        super().__init__(parent)

        logging.info("######################")
        logging.info("##gui_hack_build:OK##")
        logging.info("######################")

        self.setObjectName("Build_Hackintosh")
        self.constants = global_constants
        self.gui_support = ui_support
        self.settings = global_settings
        self.worker = None
        self.last_output_path = None
        self.last_smbios = None

        self.scrollWidget = QWidget()
        self.expandLayout = QVBoxLayout(self.scrollWidget)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)
        self.enableTransparentBackground()
        self.scrollWidget.setStyleSheet("QWidget { background: transparent; }")

        self._init_ui()
        qconfig.themeChanged.connect(self._update_theme)

    def _init_ui(self):
        self.expandLayout.setContentsMargins(
            SPACING["xxlarge"], SPACING["xlarge"],
            SPACING["xxlarge"], SPACING["xlarge"]
        )
        self.expandLayout.setSpacing(SPACING["large"])

        self.expandLayout.addWidget(self._create_title())
        hw_label = self._create_hardware_label()
        self.expandLayout.addWidget(hw_label)
        self.expandLayout.addWidget(self._create_airport_itlwm_card())
        self.expandLayout.addWidget(self._create_build_card())
        self.expandLayout.addWidget(self._create_log_card(), 1)

    def _create_title(self):
        lbl = SubtitleLabel("Build OpenCore for Hackintosh")
        lbl.setStyleSheet("font-size: 24px; font-weight: bold;")
        return lbl

    def _create_airport_itlwm_card(self):
        """Create AirportItlwm version selection card."""
        from ..efi_hack.kexts import AIRPORTITLWM_MAP

        # Track selected AirportItlwm versions (default: Monterey, Ventura, Sonoma)
        self._selected_airport_versions = set(["12", "13", "14.0", "14.4"])

        # Use ExpandGroupSettingCard for AirportItlwm version selection
        card = ExpandGroupSettingCard(
            FluentIcon.WIFI,
            "AirportItlwm",
            "Select macOS versions for Intel WiFi (AirportItlwm)",
            parent=None
        )

        # Adjust internal layout
        card.viewLayout.setContentsMargins(0, 0, 0, 0)
        card.viewLayout.setSpacing(10)

        # Add groups for each macOS version with CheckBox
        for ver_code, info in AIRPORTITLWM_MAP.items():
            checkbox = CheckBox(info["display"], card)
            checkbox.setChecked(ver_code in self._selected_airport_versions)
            checkbox.toggled.connect(lambda checked, v=ver_code: self._on_airport_checkbox_toggled(v, checked))
            card.addGroup(FluentIcon.INFO, info["display"], f"{info['kext']}", checkbox)

        return card

    def _on_airport_checkbox_toggled(self, ver_code: str, checked: bool):
        """Handle AirportItlwm version checkbox toggle."""
        if checked:
            self._selected_airport_versions.add(ver_code)
        else:
            self._selected_airport_versions.discard(ver_code)

    def _get_selected_airport_versions(self) -> list:
        """Return list of selected AirportItlwm version codes."""
        return list(self._selected_airport_versions)

    def _create_hardware_label(self):
        """Hardware info label matching gui_build.py pattern"""
        computer = self.constants.computer
        if computer and computer.cpu:
            cpu_name = computer.cpu.name
            gpu_name = computer.gpus[0].name if computer.gpus else "None"
            self._hw_label = StrongBodyLabel(f"CPU: {cpu_name}  |  GPU: {gpu_name}")
        else:
            self._hw_label = StrongBodyLabel("Hardware: Not detected")

        self._hw_label.setStyleSheet("font-size: 15px;")
        return self._hw_label

    def _create_build_card(self):
        """Build card matching gui_build.py (BuildOCPage) pattern"""
        # Card container
        card = CardWidget()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(SPACING["large"], SPACING["large"],
                                  SPACING["large"], SPACING["large"])
        layout.setSpacing(SPACING["medium"])

        # Wizard button (primary action)
        self.wizard_btn = PrimaryPushButton(FluentIcon.ROBOT, "Wizard Mode (Recommended)")
        self.wizard_btn.setFixedHeight(40)
        self.wizard_btn.clicked.connect(self._on_wizard_build)
        layout.addWidget(self.wizard_btn)

        # Open folder button - hidden until build succeeds
        self.open_folder_btn = PushButton(FIF.FOLDER, "Open folder in Finder")
        self.open_folder_btn.setFixedHeight(36)
        self.open_folder_btn.clicked.connect(self._open_output_folder)
        self.open_folder_btn.setVisible(False)
        layout.addWidget(self.open_folder_btn)

        # Install to disk button - hidden until build succeeds (macOS only)
        self.install_btn = PrimaryPushButton(FIF.SAVE, "Install to disk")
        self.install_btn.setFixedHeight(36)
        self.install_btn.clicked.connect(self._on_install_clicked)
        self.install_btn.setVisible(False)
        layout.addWidget(self.install_btn)

        # Progress area (matches gui_build.py layout)
        self.progress_container = QWidget()
        prog_layout = QVBoxLayout(self.progress_container)
        prog_layout.setContentsMargins(0, 4, 0, 0)
        prog_layout.setSpacing(6)

        # Status row: icon + label
        status_row = QHBoxLayout()
        status_row.setContentsMargins(0, 0, 0, 0)
        self.status_icon = QLabel()
        self.progress_label = BodyLabel("")
        status_row.addWidget(self.status_icon)
        status_row.addWidget(self.progress_label, 1)
        prog_layout.addLayout(status_row)

        # Progress bar
        self.progress_bar = ProgressBar()
        prog_layout.addWidget(self.progress_bar)

        self.progress_container.setVisible(False)
        layout.addWidget(self.progress_container)

        self.progress_helper = ProgressStatusHelper(
            self.status_icon, self.progress_label,
            self.progress_bar, self.progress_container
        )
        return card

    def _on_airport_checkbox_toggled(self, ver_code: str, checked: bool):
        """Handle AirportItlwm version checkbox toggle."""
        if checked:
            self._selected_airport_versions.add(ver_code)
        else:
            self._selected_airport_versions.discard(ver_code)

    def _get_selected_airport_versions(self) -> list:
        """Return list of selected AirportItlwm version codes."""
        return list(self._selected_airport_versions)

    def _create_log_card(self):
        """Build log display matching gui_build.py pattern"""
        card = CardWidget()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(SPACING["large"], SPACING["large"],
                                  SPACING["large"], SPACING["large"])

        lbl = StrongBodyLabel("Build Log")
        layout.addWidget(lbl)

        self.log_text = TextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(300)
        layout.addWidget(self.log_text)
        return card

    # ── Build actions ──

    def _on_wizard_build(self):
        """Launch wizard and build using efi_hack"""
        from .gui_build_wizard import BuildWizard

        wizard = BuildWizard(self.constants, self)
        result = wizard.run()
        if not isinstance(result, tuple) or len(result) < 3:
            # Legacy support: assume (success, smbios_model)
            success, smbios_model = result if isinstance(result, tuple) else (result, None)
            target_macos = ""  # Default
        else:
            success, smbios_model, target_macos = result[:3]

        if success and smbios_model:
            self.last_smbios = smbios_model
            self._hw_label.setText(
                f"CPU: {self.constants.computer.cpu.name}  →  SMBIOS: {smbios_model}"
                if self.constants.computer and self.constants.computer.cpu
                else f"SMBIOS: {smbios_model}"
            )
            self._hw_label.setStyleSheet("font-size: 15px; color: #f5a623;")

            # Start build
            self.log_text.clear()
            self.wizard_btn.setEnabled(False)
            self.open_folder_btn.setVisible(False)
            self.install_btn.setVisible(False)
            self.progress_helper.update("loading", f"Building EFI for {smbios_model}...")

            # Get selected AirportItlwm versions
            airport_itlwm_versions = self._get_selected_airport_versions()

            self.worker = HackBuildWorker(smbios_model, self.constants,
                                          target_macos_versions=airport_itlwm_versions,
                                          target_macos=target_macos)
            self.worker.log_signal.connect(self._append_log)
            self.worker.progress_signal.connect(self._on_progress)
            self.worker.finished_signal.connect(self._on_build_done)
            self.worker.start()

    def _append_log(self, msg: str):
        self.log_text.append(msg)
        # Auto-scroll to bottom
        sb = self.log_text.verticalScrollBar()
        sb.setValue(sb.maximum())
        # Update progress label with current step
        if msg.startswith("[STEP]"):
            step_name = msg.replace("[STEP] ", "")
            self.progress_label.setText(step_name)

    def _on_progress(self, pct: int):
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(pct)

    def _on_build_done(self, success: bool, info: str):
        self.wizard_btn.setEnabled(True)
        if success:
            self.last_output_path = info
            self.progress_helper.update("success", f"Build complete: {info}", 100)
            self.open_folder_btn.setVisible(True)
            self.install_btn.setVisible(
                sys.platform == "darwin" and check_helper_installed and check_helper_installed()
            )
        else:
            self.progress_helper.update("error", f"Build failed: {info}")
            self.open_folder_btn.setVisible(False)
            self.install_btn.setVisible(False)
        self.worker = None

    def _open_output_folder(self):
        if self.last_output_path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.last_output_path))

    def _on_install_clicked(self):
        """Reuse EFI disk selection from gui_build.py"""
        from .gui_build import EFIDiskSelectionMessageBox, InstallWorker

        w = EFIDiskSelectionMessageBox(self.window())
        if w.exec():
            selected = w.selected_partition
            if selected:
                ident = selected['identifier']
                self.log_text.clear()
                self.install_btn.setEnabled(False)
                self.wizard_btn.setEnabled(False)

                self.install_worker = InstallWorker(ident, self.last_output_path, self.constants)
                self.install_worker.log_signal.connect(self._append_log)
                self.install_worker.finished_signal.connect(self._on_install_done)
                self.install_worker.start()

    def _on_install_done(self, success, info):
        self.install_btn.setEnabled(True)
        self.wizard_btn.setEnabled(True)
        if success:
            InfoBar.success(
                title="Install Success",
                content=f"Successfully installed EFI to {info}",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=4000,
                parent=self.window()
            )
        else:
            InfoBar.error(
                title="Install Failed",
                content=info,
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=8000,
                parent=self.window()
            )
        self.install_worker = None

    def _update_theme(self):
        pass
