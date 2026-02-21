"""
gui_build.py: Build OpenCore EFI for unsupported Macs
"""
from ..include import *
from .gui_support import DefGUI, ProgressStatusHelper


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


class BuildWorker(QThread):
    """Background thread for EFI build."""
    log_signal = Signal(str)
    progress_signal = Signal(int)
    finished_signal = Signal(bool, str)

    TOTAL_STEPS = 9

    def __init__(self, model: str, constants):
        super().__init__()
        self.model = model
        self.constants = constants

    def run(self):
        handler = _SignalHandler(self.log_signal, self.progress_signal, self.TOTAL_STEPS)
        handler.setFormatter(logging.Formatter("%(message)s"))
        efi_logger = logging.getLogger("MacBoxTool.efi_mac")
        efi_logger.setLevel(logging.DEBUG)
        efi_logger.addHandler(handler)

        try:
            from ..efi_mac.build import BuildOpenCore
            builder = BuildOpenCore(self.model, self.constants)
            builder.build()
            self.progress_signal.emit(100)
            self.finished_signal.emit(True, str(builder.oc_build))
        except Exception as e:
            import traceback
            self.log_signal.emit(f"[ERROR] {e}")
            self.log_signal.emit(traceback.format_exc())
            self.finished_signal.emit(False, str(e))
        finally:
            efi_logger.removeHandler(handler)


class BuildOCPage(ScrollArea):

    def __init__(self, global_constants: Constants, ui_support: DefGUI = None,
                 global_settings: GlobalSettings = None, parent=None):
        super().__init__(parent=parent)

        logging.info("######################")
        logging.info("#####gui_build:OK#####")
        logging.info("######################")

        self.setObjectName("Build_For_Mac")
        self.constants = global_constants
        self.gui_support = ui_support
        self.settings = global_settings
        self.worker = None

        self.scrollWidget = QWidget()
        self.expandLayout = QVBoxLayout(self.scrollWidget)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)
        self.enableTransparentBackground()
        self.scrollWidget.setStyleSheet("QWidget { background: transparent; }")

        self.settings.add_key("MODEL", "N/A")
        self.physical_model = self.constants.computer.real_model or "Unknown Hardware"
        self.target_model = self.settings.find_key("MODEL") or "MacPro7,1"

        self._init_ui()
        qconfig.themeChanged.connect(self._update_theme)

    def _init_ui(self):
        self.expandLayout.setContentsMargins(
            SPACING["xxlarge"], SPACING["xlarge"],
            SPACING["xxlarge"], SPACING["xlarge"]
        )
        self.expandLayout.setSpacing(SPACING["large"])

        self.expandLayout.addWidget(self._create_title())
        self.expandLayout.addWidget(self._create_model_label())
        self.expandLayout.addWidget(self._create_build_card())
        self.expandLayout.addWidget(self._create_log_card(), 1)

    def _create_title(self):
        lbl = SubtitleLabel("Build OC for Old Macs")
        lbl.setStyleSheet("font-size: 24px; font-weight: bold;")
        return lbl

    def _create_model_label(self):
        target = self.target_model
        self._model_label = StrongBodyLabel(f"Physical: {self.physical_model} → Target: {target}")
        if self.physical_model != "Unknown Hardware" and self.physical_model != target:
            self._model_label.setStyleSheet("font-size: 15px; color: #f5a623;")
        else:
            self._model_label.setStyleSheet("font-size: 15px;")
        return self._model_label

    def _create_build_card(self):
        card = CardWidget()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(SPACING["large"], SPACING["large"],
                                  SPACING["large"], SPACING["large"])
        layout.setSpacing(SPACING["medium"])

        # Build button - always enabled regardless of physical model
        self.build_btn = PrimaryPushButton(FluentIcon.DEVELOPER_TOOLS, "Build OpenCore EFI")
        self.build_btn.setFixedHeight(40)
        self.build_btn.clicked.connect(self._on_build)
        layout.addWidget(self.build_btn)

        # Progress area - vertical layout to avoid overlap
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

        # Progress bar on its own row
        self.progress_bar = ProgressBar()
        prog_layout.addWidget(self.progress_bar)

        self.progress_container.setVisible(False)
        layout.addWidget(self.progress_container)

        self.progress_helper = ProgressStatusHelper(
            self.status_icon, self.progress_label,
            self.progress_bar, self.progress_container
        )
        return card

    def _create_log_card(self):
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

    def _on_build(self):
        model = self.settings.find_key("MODEL")
        if not model or model == "N/A":
            model = self.constants.computer.real_model or "MacPro7,1"

        self.log_text.clear()
        self.build_btn.setEnabled(False)
        self.progress_helper.update("loading", f"Building EFI for {model}...")

        self.worker = BuildWorker(model, self.constants)
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
        self.build_btn.setEnabled(True)
        if success:
            self.progress_helper.update("success", f"Build complete: {info}", 100)
        else:
            self.progress_helper.update("error", f"Build failed: {info}")
        self.worker = None

    def _update_theme(self):
        pass

    def refresh(self):
        target = self.settings.find_key("MODEL") or "Not Selected"
        self._model_label.setText(f"Physical: {self.physical_model} → Target: {target}")
        if self.physical_model != "Unknown Hardware" and self.physical_model != target:
            self._model_label.setStyleSheet("font-size: 15px; color: #f5a623;")
        else:
            self._model_label.setStyleSheet("font-size: 15px;")
