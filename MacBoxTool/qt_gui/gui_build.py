"""
gui_build.py: Build OpenCore EFI for unsupported Macs
"""
from ..include import *
from .gui_support import DefGUI, ProgressStatusHelper, AutoUpdateStages
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl

import sys
import threading
# Import install_helper only on macOS
if sys.platform == "darwin":
    try:
        from ..support.install_helper import check_helper_installed
    except ImportError:
        check_helper_installed = None
else:
    check_helper_installed = None


from ..support.scan_disk_efi import get_efi_partitions, list_disks, list_partitions


class _SignalHandler(logging.Handler):
    """Logging handler that emits Qt signals for real-time log display."""
    STAGE_MAP = [
        ("Building Configuration", 8, "Preparing build"),
        ("Creating build folder", 18, "Preparing build folder"),
        ("Build folder already present", 18, "Preparing build folder"),
        ("Deleting old copy of OpenCore", 22, "Cleaning previous build"),
        ("- Adding OpenCore v", 32, "Extracting OpenCore"),
        ("- Adding config.plist for OpenCore", 42, "Preparing config"),
        ("- Adding Lilu.kext", 50, "Loading base components"),
        ("- Cleaning up files", 88, "Cleaning build output"),
        ("- Vaulting EFI", 93, "Signing EFI"),
        ("- Validating generated config", 96, "Validating EFI"),
        ("Your OpenCore EFI for", 100, "Build complete"),
        ("- Adding ", 72, "Configuring components"),
    ]

    def __init__(self, log_signal, progress_signal=None, total_steps=1, thread_id=None):
        super().__init__()
        self._log_signal = log_signal
        self._progress_signal = progress_signal
        self._thread_id = thread_id
        self._last_progress = 0
        self._last_stage = None

    def _emit_stage_progress(self, msg):
        for pattern, pct, stage_name in self.STAGE_MAP:
            if pattern not in msg:
                continue

            if stage_name != self._last_stage:
                self._last_stage = stage_name
                self._log_signal.emit(f"[STEP] {stage_name}")

            if self._progress_signal and pct > self._last_progress:
                self._last_progress = pct
                self._progress_signal.emit(pct)
            return

    def emit(self, record):
        if self._thread_id is not None and record.thread != self._thread_id:
            return
        msg = self.format(record)
        self._emit_stage_progress(msg)
        self._log_signal.emit(msg)


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
        handler = _SignalHandler(self.log_signal, self.progress_signal, self.TOTAL_STEPS, threading.get_ident())
        handler.setFormatter(logging.Formatter("%(message)s"))
        root_logger = logging.getLogger()
        previous_level = root_logger.level
        root_logger.setLevel(min(previous_level, logging.INFO) if previous_level else logging.INFO)
        root_logger.addHandler(handler)

        try:
            from ..efi_builder.build import BuildOpenCore

            BuildOpenCore(self.model, self.constants)
            self.progress_signal.emit(100)
            self.finished_signal.emit(True, str(self.constants.opencore_release_folder))
        except Exception as e:
            import traceback
            stack_trace = traceback.format_exc()
            send_error_report_async(
                exception_type=type(e).__name__,
                exception_message=str(e),
                stack_trace=stack_trace,
                operation="build_efi",
            )
            self.log_signal.emit(f"[ERROR] {e}")
            self.log_signal.emit(stack_trace)
            self.finished_signal.emit(False, str(e))
        finally:
            root_logger.removeHandler(handler)
            root_logger.setLevel(previous_level)


class DiskScannerThread(QThread):
    finished_signal = Signal(list)

    def run(self):
        partitions = get_efi_partitions()
        self.finished_signal.emit(partitions)


class DiskListScannerThread(QThread):
    """Thread to scan all disks"""
    finished_signal = Signal(dict)

    def run(self):
        disks = list_disks()
        self.finished_signal.emit(disks)


class InstallWorker(QThread):
    """Background thread for EFI installation."""
    log_signal = Signal(str)
    finished_signal = Signal(bool, str)

    def __init__(self, partition_ident, source_path, constants):
        super().__init__()
        self.partition_ident = partition_ident
        self.source_path = source_path
        self.constants = constants

    def run(self):
        import shutil
        import os

        from ..support.mount import EFIPartitionMount

        ident = self.partition_ident

        try:
            # Mount
            self.log_signal.emit(f"=== Installing EFI to {ident} ===")
            self.log_signal.emit(f"Mounting {ident}...")

            efi_mount = EFIPartitionMount(ident)
            mount_point = efi_mount.mount()

            if not mount_point:
                self.log_signal.emit(f"[ERROR] Failed to mount {ident}")
                self.log_signal.emit(f"[ERROR] The EFI partition may be corrupted or unformatted.")
                self.log_signal.emit(f"[ERROR] Attempting to reformat the EFI partition...")

                # Try to format the EFI partition
                if efi_mount.format_efi("EFI"):
                    self.log_signal.emit(f"EFI partition formatted successfully. Retrying mount...")
                    mount_point = efi_mount.mount()
                    if not mount_point:
                        self.log_signal.emit(f"[ERROR] Still failed to mount after format")
                        self.finished_signal.emit(False, f"Failed to mount after formatting")
                        return
                else:
                    self.log_signal.emit(f"[ERROR] Failed to format EFI partition")
                    self.finished_signal.emit(False, f"Failed to format {ident}")
                    return

            self.log_signal.emit(f"Mounted {ident} successfully.")
            self.log_signal.emit(f"Mount point: {mount_point}")

            # Copy EFI
            src_efi = os.path.join(self.source_path, "EFI")
            if not os.path.exists(src_efi):
                src_efi = self.source_path
            dest_efi = os.path.join(mount_point, "EFI")

            if not os.path.exists(src_efi):
                self.log_signal.emit(f"[WARN] EFI source not found at {src_efi}")
                self.finished_signal.emit(False, f"EFI source not found")
                return

            self.log_signal.emit(f"Copying EFI: {src_efi} -> {dest_efi}")
            if os.path.exists(dest_efi):
                shutil.rmtree(dest_efi)
            shutil.copytree(src_efi, dest_efi)
            self.log_signal.emit("EFI copied successfully.")

            # Copy System folder if exists
            src_system = os.path.join(self.source_path, "System")
            if os.path.exists(src_system):
                dest_system = os.path.join(mount_point, "System")
                self.log_signal.emit(f"Copying System: {src_system} -> {dest_system}")
                if os.path.exists(dest_system):
                    shutil.rmtree(dest_system)
                shutil.copytree(src_system, dest_system)
                self.log_signal.emit("System copied successfully.")

            # Add drive icon
            self._copy_drive_icon(ident, mount_point)

            self.log_signal.emit(f"\n=== Install Complete ===")
            self.finished_signal.emit(True, mount_point)

        except Exception as e:
            self.log_signal.emit(f"[ERROR] {e}")
            self.finished_signal.emit(False, str(e))

    def _copy_drive_icon(self, ident, mount_point):
        """Determine disk type and copy appropriate drive icon."""
        import os

        from ..support.mount import EFIPartitionMount

        icon_path = None
        try:
            disk_info = EFIPartitionMount(ident).get_disk_info()

            if disk_info is None:
                raise RuntimeError("Could not get disk info")

            is_internal = disk_info.get("Internal", False)
            is_ssd = disk_info.get("SolidState", False)
            bus_protocol = disk_info.get("BusProtocol", "")
            media_name = disk_info.get("MediaName", "").lower()

            if "sd" in media_name or "card" in media_name:
                self.log_signal.emit("Adding SD Card icon...")
                icon_path = self.constants.icon_path_sd
            elif is_ssd:
                self.log_signal.emit("Adding SSD icon...")
                icon_path = self.constants.icon_path_ssd
            elif bus_protocol == "USB" or not is_internal:
                self.log_signal.emit("Adding External USB Drive icon...")
                icon_path = self.constants.icon_path_external
            else:
                self.log_signal.emit("Adding Internal Drive icon...")
                icon_path = self.constants.icon_path_internal

        except Exception as e:
            self.log_signal.emit(f"[WARN] Could not determine disk type: {e}")
            icon_path = self.constants.icon_path_internal

        if icon_path and os.path.exists(str(icon_path)):
            dest_icon = os.path.join(mount_point, ".VolumeIcon.icns")
            subprocess.run(
                ["/bin/cp", str(icon_path), dest_icon],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            self.log_signal.emit("Drive icon added.")
        else:
            self.log_signal.emit("[WARN] Icon file not found, skipping.")


class EFIDiskSelectionMessageBox(MessageBoxBase):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel("Select Target Disk")

        # Loading State
        self.loadingWidget = QWidget()
        self.loadingLayout = QHBoxLayout(self.loadingWidget)

        self.progressRing = IndeterminateProgressRing()
        self.progressRing.setFixedSize(50, 50)
        self.progressRing.setStrokeWidth(4)

        self.progressLabel = BodyLabel("Scanning disks...")

        self.loadingLayout.addWidget(self.progressRing)
        self.loadingLayout.addWidget(self.progressLabel)
        self.loadingLayout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Disk Selection State
        self.diskSelectionWidget = QWidget()
        self.diskSelectionLayout = QVBoxLayout(self.diskSelectionWidget)
        self.diskButtonGroup = QButtonGroup(self)
        self.diskSelectionWidget.hide()

        # Partition Selection State
        self.partitionSelectionWidget = QWidget()
        self.partitionSelectionLayout = QVBoxLayout(self.partitionSelectionWidget)
        self.partitionButtonGroup = QButtonGroup(self)
        self.partitionSelectionWidget.hide()

        # Back button
        self.backButton = PrimaryPushButton("← Back")
        self.backButton.clicked.connect(self._on_back_clicked)
        self.backButton.hide()

        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.loadingWidget)
        self.viewLayout.addWidget(self.diskSelectionWidget)
        self.viewLayout.addWidget(self.partitionSelectionWidget)
        self.viewLayout.addWidget(self.backButton)

        self.widget.setMinimumWidth(350)
        self.yesButton.setEnabled(False)
        self.yesButton.setText("Install")

        self.selected_disk = None
        self.selected_partition = None
        self.efi_partitions = None
        self.all_disks = {}

        # Start scan
        self.progressRing.start()
        self.scanner_thread = DiskListScannerThread(self)
        self.scanner_thread.finished_signal.connect(self._on_disks_scanned)
        self.scanner_thread.finished.connect(self.scanner_thread.deleteLater)
        self.scanner_thread.start()

    def _on_disks_scanned(self, disks):
        self.all_disks = disks
        self.progressRing.stop()
        self.loadingWidget.hide()
        self.diskSelectionWidget.show()

        if not disks:
            self.diskSelectionLayout.addWidget(BodyLabel("No disks with EFI partitions found."))
            return

        for disk_ident, disk_data in disks.items():
            rb = RadioButton(f"{disk_data['name']} ({disk_ident})")
            self.diskButtonGroup.addButton(rb, list(disks.keys()).index(disk_ident))
            self.diskSelectionLayout.addWidget(rb)
            # Add spacing between RadioButtons
            spacer = QWidget()
            spacer.setFixedHeight(8)
            self.diskSelectionLayout.addWidget(spacer)

        self.diskButtonGroup.buttonClicked.connect(self._on_disk_selected)

    def _on_disk_selected(self, btn):
        disk_keys = list(self.all_disks.keys())
        idx = self.diskButtonGroup.id(btn)
        disk_ident = disk_keys[idx]
        self.selected_disk = self.all_disks[disk_ident]

        # Show partition selection
        self.diskSelectionWidget.hide()
        self.titleLabel.setText("Select Target Partition")
        self.partitionSelectionWidget.show()
        self.backButton.show()

        # Clear previous partition buttons
        while self.partitionSelectionLayout.count():
            item = self.partitionSelectionLayout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        partitions = self.selected_disk.get("partitions", {})

        # Filter to only show EFI partitions
        self.efi_partitions = {
            part_ident: part_data
            for part_ident, part_data in partitions.items()
            if part_data.get("fs") == "EFI" or part_data.get("fs") == "msdos" or part_data.get("type") == "EFI"
        }

        if not self.efi_partitions:
            # No EFI partition found
            self.partitionSelectionLayout.addWidget(BodyLabel("No EFI partition found on this disk."))
            return

        for part_ident, part_data in self.efi_partitions.items():
            part_name = part_data.get("name", "")
            part_type = part_data.get("type", "")
            part_size = part_data.get("size", 0)

            # Format size
            size_str = self._format_size(part_size)

            # Create label
            if part_name:
                label = f"{part_name} ({part_ident}) - {part_type} - {size_str}"
            else:
                label = f"{part_ident} - {part_type} - {size_str}"

            rb = RadioButton(label)
            self.partitionButtonGroup.addButton(rb, list(self.efi_partitions.keys()).index(part_ident))
            self.partitionSelectionLayout.addWidget(rb)

            # Add spacing between RadioButtons
            spacer = QWidget()
            spacer.setFixedHeight(8)
            self.partitionSelectionLayout.addWidget(spacer)

        self.partitionButtonGroup.buttonClicked.connect(self._on_partition_selected)

    def _on_partition_selected(self, btn):
        # Use EFI partitions list to get the correct partition identifier
        part_keys = list(self.efi_partitions.keys())
        idx = self.partitionButtonGroup.id(btn)
        part_ident = part_keys[idx]

        self.selected_partition = {
            "identifier": part_ident,
            "disk_name": self.selected_disk["name"],
            "name": f"{self.selected_disk['name']} - {part_ident}"
        }
        self.yesButton.setEnabled(True)

    def _on_back_clicked(self):
        # If we're in partition selection, go back to disk selection
        if self.partitionSelectionWidget.isVisible():
            self.titleLabel.setText("Select Target Disk")
            self.partitionSelectionWidget.hide()
            self.backButton.hide()
            self.diskSelectionWidget.show()
            self.selected_disk = None
            self.selected_partition = None
            self.yesButton.setEnabled(False)
        # If we're in disk selection, just clear selection
        else:
            self.selected_disk = None
            self.selected_partition = None
            self.yesButton.setEnabled(False)

    def _format_size(self, size_bytes):
        """Format size in bytes to human readable string."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} PB"

    def validate(self):
        return self.selected_partition is not None


class BuildOCPage(ScrollArea):

    def __init__(self, global_constants: Constants, ui_support: DefGUI = None,
                 global_settings: GlobalSettings = None, parent=None):
        super().__init__(parent=parent)


        logging.info("init gui_build")


        self.setObjectName("Build_For_Mac")
        self.constants = global_constants
        self.gui_support = ui_support
        self.settings = global_settings
        self.worker = None
        self.install_worker = None
        self.last_output_path = None  # Store last build output path

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

    def _init_ui(self):
        self.expandLayout.setContentsMargins(
            SPACING["xxlarge"], SPACING["xlarge"],
            SPACING["xxlarge"], SPACING["xlarge"]
        )
        self.expandLayout.setSpacing(SPACING["large"])
        self.expandLayout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.expandLayout.addWidget(self._create_title())
        self.expandLayout.addWidget(self._create_model_label())
        self.expandLayout.addWidget(self._create_build_card())

        self.log_card = self._create_log_card()
        if self.constants.show_logs:
            self.expandLayout.addWidget(self.log_card)
        self.expandLayout.addStretch(1)

    def _create_title(self):
        lbl = SubtitleLabel("Build OpenCore for Macs")
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
        self.build_btn = PushButton(FluentIcon.DEVELOPER_TOOLS, "Build OpenCore EFI")
        self.build_btn.setFixedHeight(40)
        setCustomStyleSheet(self.build_btn,"PushButton { border-radius: 20px; }","PushButton { border-radius: 20px; }")
        self.build_btn.clicked.connect(self._on_build)
        layout.addWidget(self.build_btn)

        # Open folder button - hidden until build succeeds
        self.open_folder_btn = PushButton(FIF.FOLDER, "Open folder in Finder")
        self.open_folder_btn.setFixedHeight(36)
        self.open_folder_btn.clicked.connect(self._open_output_folder)
        self.open_folder_btn.setVisible(False)
        layout.addWidget(self.open_folder_btn)

        # Install to disk button - hidden until build succeeds
        self.install_btn = PrimaryPushButton(FIF.SAVE, "Install to disk")
        self.install_btn.setFixedHeight(36)
        self.install_btn.clicked.connect(self._on_install_clicked)
        self.install_btn.setVisible(False)
        layout.addWidget(self.install_btn)

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
        card.setVisible(self.constants.show_logs)
        return card

    

    def _on_build(self):
        model = self.settings.find_key("MODEL")
        if not model or model == "N/A":
            model = self.constants.computer.real_model or "MacPro7,1"
        self.log_text.clear()
        self.build_btn.setEnabled(False)
        self.open_folder_btn.setVisible(False)  # Hide open folder button during build
        self.install_btn.setVisible(False)      # Hide install button during build
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
            self.last_output_path = info
            self.progress_helper.update("success", f"Build complete: {info}", 100)
            self.open_folder_btn.setVisible(True)
            # Show install button only if helper is installed
            self.install_btn.setVisible(
                sys.platform == "darwin" and check_helper_installed and check_helper_installed()
            )
            # Auto-update flow: auto-trigger install after build
            if getattr(self.constants, "update_stage", AutoUpdateStages.INACTIVE) != AutoUpdateStages.INACTIVE:
                self.constants.update_stage = AutoUpdateStages.INSTALLING
                QTimer.singleShot(200, self._on_install_clicked)
        else:
            self.progress_helper.update("error", f"Build failed: {info}")
            self.open_folder_btn.setVisible(False)
            self.install_btn.setVisible(False)
        self.worker = None

    def _open_output_folder(self):
        if self.last_output_path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.last_output_path))

    def _on_install_clicked(self):
        w = EFIDiskSelectionMessageBox(self.window())
        if w.exec():
            selected = w.selected_partition
            if selected:
                ident = selected['identifier']
                self.log_text.clear()
                self.install_btn.setEnabled(False)
                self.build_btn.setEnabled(False)

                self.install_worker = InstallWorker(ident, self.last_output_path, self.constants)
                self.install_worker.log_signal.connect(self._append_log)
                self.install_worker.finished_signal.connect(self._on_install_done)
                self.install_worker.start()

    def _on_install_done(self, success, info):
        self.install_btn.setEnabled(True)
        self.build_btn.setEnabled(True)
        if success:
            InfoBar.success(
                title="Install Success",
                content=f"Successfully installed EFI to {info}",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM_RIGHT,
                duration=4000,
                parent=self
            )
            # Auto-update flow: navigate to sys_patch after install
            if getattr(self.constants, "update_stage", AutoUpdateStages.INACTIVE) != AutoUpdateStages.INACTIVE:
                self.constants.update_stage = AutoUpdateStages.ROOT_PATCHING
                self.constants.start_sys_patch = True
                self.constants.start_sys_patch_now = True
                win = self.window()
                if hasattr(win, "navigate_to_sys_patch"):
                    QTimer.singleShot(500, win.navigate_to_sys_patch)
        else:
            InfoBar.error(
                title="Install Failed",
                content=info,
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM_RIGHT,
                duration=8000,
                parent=self
            )
        self.install_worker = None

    def _stop_worker(self, worker, timeout: int = 5000):
        if not worker:
            return
        try:
            if hasattr(worker, "requestInterruption"):
                worker.requestInterruption()
            if worker.isRunning() and not worker.wait(timeout):
                logging.warning(f"{worker.__class__.__name__} did not stop in {timeout}ms; terminating")
                worker.terminate()
                worker.wait(1000)
            if not worker.isRunning():
                worker.deleteLater()
        except RuntimeError:
            pass

    def cleanup_workers(self):
        """Stop build/install workers before this page is destroyed."""
        self._stop_worker(self.worker, 10000)
        self.worker = None
        self._stop_worker(self.install_worker, 10000)
        self.install_worker = None

    def closeEvent(self, event):
        self.cleanup_workers()
        super().closeEvent(event)

    def refresh(self):
        target = self.settings.find_key("MODEL") or "Not Selected"
        self._model_label.setText(f"Physical: {self.physical_model} → Target: {target}")
        if self.physical_model != "Unknown Hardware" and self.physical_model != target:
            self._model_label.setStyleSheet("font-size: 15px; color: #f5a623;")
        else:
            self._model_label.setStyleSheet("font-size: 15px;")
