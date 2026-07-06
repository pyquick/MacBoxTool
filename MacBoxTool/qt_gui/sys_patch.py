"""
sys_patch.py: Root patching interface
"""

from ..include import *
from .gui_support import AutoUpdateStages, DefGUI, PayloadMount, RestartHost, ThreadHandler

from ..datasets import os_data
from ..support import kdk_handler, metallib_handler
from ..support.network_handler import DownloadStatus, DownloadWorker
from ..sys_patch import sys_patch as sys_patch_module
from ..sys_patch.patchsets import (
    HardwarePatchsetDetection,
    HardwarePatchsetSettings,
    HardwarePatchsetValidation,
)


class PatchDetectionWorker(QThread):
    finished_signal = Signal(dict)
    error_signal = Signal(str)

    def __init__(self, constants: Constants, parent=None):
        super().__init__(parent)
        self.constants = constants

    def run(self):
        try:
            patches = HardwarePatchsetDetection(constants=self.constants).device_properties
            self.finished_signal.emit(patches)
        except Exception:
            self.error_signal.emit(traceback.format_exc())


class PatchRunWorker(QThread):
    finished_signal = Signal(bool)

    def __init__(self, constants: Constants, patches: dict, revert: bool = False, parent=None):
        super().__init__(parent)
        self.constants = constants
        self.patches = patches
        self.revert = revert

    def run(self):
        try:
            patcher = sys_patch_module.PatchSysVolume(
                self.constants.computer.real_model,
                self.constants,
                self.patches,
            )
            if self.revert:
                patcher.start_unpatch()
            else:
                patcher.start_patch()
            self.finished_signal.emit(self.constants.root_patcher_succeeded is True)
        except Exception:
            logging.error("An internal error occurred while running the Root Patcher:\n")
            logging.error(traceback.format_exc())
            self.finished_signal.emit(False)


class SysPatch(ScrollArea):
    def __init__(self, global_constants: Constants, ui_support: DefGUI = None, global_settings: GlobalSettings = None, parent=None):
        super().__init__(parent)

        logging.info("init sys_patch")

        self.setObjectName("SysPatch")
        self.constants = global_constants
        self.gui_support = ui_support or DefGUI(self.constants)
        self.settings = global_settings

        self.patches = {}
        self.available_patches = False
        self.no_new_patches = False
        self.can_unpatch = False
        self.detection_worker = None
        self.patch_worker = None
        self.download_worker = None
        self.log_handler = None

        self.scrollWidget = QWidget()
        self.expandLayout = QVBoxLayout(self.scrollWidget)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)
        self.enableTransparentBackground()

        self.init_ui()
        self.refresh()

    def init_ui(self):
        self.expandLayout.setContentsMargins(
            SPACING["xxlarge"], SPACING["xlarge"],
            SPACING["xxlarge"], SPACING["xlarge"]
        )
        self.expandLayout.setSpacing(SPACING["large"])

        title = SubtitleLabel("Post-Install Menu")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        self.expandLayout.addWidget(title)

        self.status_card = self.gui_support.custom_card(
            card_type="info",
            title="Root Patching",
            body="Fetching patches for host...",
        )
        self.expandLayout.addWidget(self.status_card)

        self.patch_container = QWidget()
        self.patch_layout = QVBoxLayout(self.patch_container)
        self.patch_layout.setContentsMargins(0, 0, 0, 0)
        self.patch_layout.setSpacing(SPACING["medium"])
        self.expandLayout.addWidget(self.patch_container)

        button_row = QWidget()
        button_layout = QHBoxLayout(button_row)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(SPACING["medium"])

        self.start_button = PrimaryPushButton("Start Root Patching")
        self.start_button.clicked.connect(self.start_root_patching)
        button_layout.addWidget(self.start_button)

        self.revert_button = PushButton("Revert Root Patches")
        self.revert_button.clicked.connect(self.revert_root_patching)
        button_layout.addWidget(self.revert_button)

        self.refresh_button = PushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh)
        button_layout.addWidget(self.refresh_button)
        button_layout.addStretch()
        self.expandLayout.addWidget(button_row)

        self.progress_ring = IndeterminateProgressRing(self)
        self.progress_ring.setFixedSize(36, 36)
        self.progress_ring.hide()
        self.expandLayout.addWidget(self.progress_ring, 0, Qt.AlignmentFlag.AlignCenter)

        self.log_box = TextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMinimumHeight(320)
        self.log_box.hide()
        self.expandLayout.addWidget(self.log_box)

        self.expandLayout.addStretch()

    def _set_status(self, title: str, body: str, card_type: str = "info"):
        index = self.expandLayout.indexOf(self.status_card)
        self.expandLayout.removeWidget(self.status_card)
        self.status_card.deleteLater()
        self.status_card = self.gui_support.custom_card(card_type=card_type, title=title, body=body)
        self.expandLayout.insertWidget(index, self.status_card)

    def _set_busy(self, busy: bool):
        self.progress_ring.setVisible(busy)
        if busy:
            self.progress_ring.start()
        else:
            self.progress_ring.stop()
        self.refresh_button.setEnabled(not busy)
        self.start_button.setEnabled(not busy and self.available_patches and not self.no_new_patches)
        self.revert_button.setEnabled(not busy and self.can_unpatch)

    def _clear_layout(self, layout: QLayout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def refresh(self):
        self._clear_layout(self.patch_layout)
        self._set_status("Root Patching", "Fetching patches for host...")
        self.available_patches = False
        self.no_new_patches = False
        self.can_unpatch = False
        self._set_busy(True)

        self.detection_worker = PatchDetectionWorker(self.constants, self)
        self.detection_worker.finished_signal.connect(self._on_patches_detected)
        self.detection_worker.error_signal.connect(self._on_detection_error)
        self.detection_worker.finished.connect(self.detection_worker.deleteLater)
        self.detection_worker.start()

    def _on_detection_error(self, error: str):
        logging.error(error)
        self._set_status("Detection Failed", error, "error")
        self._set_busy(False)

    def _on_patches_detected(self, patches: dict):
        self.patches = patches or {}
        self.can_unpatch = bool(self.patches) and not self.patches[HardwarePatchsetValidation.UNPATCHING_NOT_POSSIBLE]

        if not any(
            not patch.startswith("Settings") and not patch.startswith("Validation") and self.patches[patch] is True
            for patch in self.patches
        ):
            logging.info("No applicable patches available")
            self.patches = {}

        self.no_new_patches = not self._check_if_new_patches_needed(self.patches) if self.patches else False
        self._render_patch_list()
        self._set_busy(False)

        if self.constants.update_stage != AutoUpdateStages.INACTIVE and self.available_patches is False:
            RestartHost(self.window(), self.constants).restart(
                message="No root patch updates needed!\n\nWould you like to reboot to apply the new OpenCore build?"
            )

    def _render_patch_list(self):
        self._clear_layout(self.patch_layout)

        if not self.patches:
            self._set_status("Available patches for your system", "No patches required", "success")
            self.available_patches = False
            return

        patch_names = [
            patch for patch, enabled in self.patches.items()
            if not patch.startswith("Settings") and not patch.startswith("Validation") and enabled is True
        ]

        if self.no_new_patches:
            self._set_status("Available patches for your system", "All applicable patches already installed", "success")
        else:
            self._set_status("Available patches for your system", "Root patching can patch the following items:", "info")
            logging.info("Available patches:")
            for patch in patch_names:
                logging.info(f"- {patch}")
                self.patch_layout.addWidget(BodyLabel(f"- {patch}"))

        if self.patches[HardwarePatchsetValidation.PATCHING_NOT_POSSIBLE] is True:
            self.patch_layout.addWidget(StrongBodyLabel("Cannot patch due to the following reasons:"))
            for patch, enabled in self.patches.items():
                if not patch.startswith("Validation"):
                    continue
                if enabled is False:
                    continue
                if patch in [HardwarePatchsetValidation.PATCHING_NOT_POSSIBLE, HardwarePatchsetValidation.UNPATCHING_NOT_POSSIBLE]:
                    continue
                self.patch_layout.addWidget(BodyLabel(f"- {patch.split('Validation: ')[1]}"))

        elif self.constants.computer.mbt_sys_version and self.constants.computer.oclp_sys_date:
            date = self.constants.computer.oclp_sys_date.split(" @")
            date = date[0] if len(date) == 2 else ""
            self.patch_layout.addWidget(StrongBodyLabel("Root Volume last patched:"))
            self.patch_layout.addWidget(BodyLabel(f"{self.constants.computer.mbt_sys_version}, {date}"))

        self.available_patches = self.patches[HardwarePatchsetValidation.PATCHING_NOT_POSSIBLE] is False

    def _run_download_worker(self, download_obj) -> bool:
        loop = QEventLoop()
        result = {"success": False, "message": ""}
        self.download_worker = DownloadWorker(download_obj, self.constants)
        self.download_worker.finished_signal.connect(lambda success, message: (result.update(success=success, message=message), loop.quit()))
        self.download_worker.start()
        loop.exec()
        self.download_worker.deleteLater()
        self.download_worker = None
        if result["success"] is False:
            logging.error(result["message"])
        return result["success"]

    def _kdk_download(self) -> bool:
        logging.info("KDK missing, fetching KDK information")
        self._set_status("Downloading Kernel Debug Kit", "Fetching KDK database...")
        QApplication.processEvents()

        self.kdk_obj = kdk_handler.KernelDebugKitObject(
            self.constants,
            self.constants.detected_os_build,
            self.constants.detected_os_version,
        )
        if self.kdk_obj.success is False:
            QMessageBox.critical(self.window(), "Error", f"KDK download failed: {self.kdk_obj.error_msg}")
            return False

        kdk_download_obj = self.kdk_obj.retrieve_download()
        if not kdk_download_obj:
            return True

        if self._run_download_worker(kdk_download_obj) is False:
            return False

        self._set_status("Validating KDK", "Checking if checksum is valid...")
        QApplication.processEvents()
        if self.kdk_obj.validate_kdk_checksum() is False:
            logging.error("KDK checksum validation failed")
            logging.error(self.kdk_obj.error_msg)
            QMessageBox.critical(self.window(), "Error", f"KDK checksum validation failed: {self.kdk_obj.error_msg}")
            return False

        logging.info("KDK download complete")
        return True

    def _metallib_download(self) -> bool:
        logging.info("MetallibSupportPkg missing, fetching MetallibSupportPkg information")
        self._set_status("Downloading Metal Libraries", "Finding available MetallibSupportPkg database...")
        QApplication.processEvents()

        self.metallib_obj = metallib_handler.MetalLibraryObject(
            self.constants,
            self.constants.detected_os_build,
            self.constants.detected_os_version,
        )
        if self.metallib_obj.success is False:
            QMessageBox.critical(self.window(), "Error", f"MetallibSupportPkg download failed: {self.metallib_obj.error_msg}")
            return False

        metallib_download_obj = self.metallib_obj.retrieve_download()
        if not metallib_download_obj:
            return True

        if self._run_download_worker(metallib_download_obj) is False:
            return False

        self._set_status("Installing Metallib", "Installing MetallibSupportPkg PKG...")
        QApplication.processEvents()
        if self.metallib_obj.install_metallib() is False:
            QMessageBox.critical(self.window(), "Error", f"Metallib installation failed: {self.metallib_obj.error_msg}")
            return False

        logging.info("Metallib installation complete")
        return True

    def _prepare_patch_run(self, title: str, body: str):
        self.log_box.clear()
        self.log_box.show()
        self._set_status(title, body)
        self._set_busy(True)
        self.log_handler = ThreadHandler(self.log_box)
        logging.getLogger().addHandler(self.log_handler)

    def _finish_patch_run(self, success: bool):
        logger = logging.getLogger()
        if self.log_handler in logger.handlers:
            logger.removeHandler(self.log_handler)
        self.log_handler = None
        self._set_busy(False)

        if self.constants.root_patcher_succeeded is False:
            if success is False:
                self._set_status("Root Patcher", "Root patching did not complete successfully.", "error")
            return

        self._post_patch()

    def start_root_patching(self):
        logging.info("Starting root patching")
        self._set_busy(True)
        while PayloadMount(self.constants, self.window()).is_unpack_finished() is False:
            QApplication.processEvents()
            time.sleep(self.constants.thread_sleep_interval)

        if self.patches[HardwarePatchsetSettings.KERNEL_DEBUG_KIT_REQUIRED] is True:
            if self._kdk_download() is False:
                self._set_busy(False)
                return

        if self.patches[HardwarePatchsetSettings.METALLIB_SUPPORT_PKG_REQUIRED] is True:
            if self._metallib_download() is False:
                self._set_busy(False)
                return

        self._prepare_patch_run("Root Patching", self._patch_summary("Root Patching will patch the following:"))
        self.patch_worker = PatchRunWorker(self.constants, self.patches, revert=False, parent=self)
        self.patch_worker.finished_signal.connect(self._finish_patch_run)
        self.patch_worker.finished.connect(self.patch_worker.deleteLater)
        self.patch_worker.start()

    def revert_root_patching(self):
        logging.info("Reverting root patches")
        self._prepare_patch_run("Revert Root Patches", "Reverting to last sealed snapshot")
        self.patch_worker = PatchRunWorker(self.constants, self.patches, revert=True, parent=self)
        self.patch_worker.finished_signal.connect(self._finish_patch_run)
        self.patch_worker.finished.connect(self.patch_worker.deleteLater)
        self.patch_worker.start()

    def _patch_summary(self, header: str) -> str:
        patch_names = [
            patch for patch, enabled in self.patches.items()
            if not patch.startswith("Settings") and not patch.startswith("Validation") and enabled is True
        ]
        if not patch_names:
            return "No patches to apply"
        return header + "\n" + "\n".join(f"- {patch}" for patch in patch_names)

    def _post_patch(self):
        if self.constants.needs_to_open_preferences is False:
            RestartHost(self.window(), self.constants).restart(
                message="Root Patcher finished successfully!\n\nWould you like to reboot now?"
            )
            return

        if self.constants.detected_os >= os_data.os_data.ventura:
            RestartHost(self.window(), self.constants).restart(
                message="Root Patcher finished successfully!\nIf you were prompted to open System Settings to authorize new kexts, this can be ignored. Your system is ready once restarted.\n\nWould you like to reboot now?"
            )
            return

        answer = QMessageBox.question(
            self.window(),
            "Open System Preferences?",
            "We just finished installing the patches to your Root Volume!\n\nHowever, Apple requires users to manually approve the kernel extensions installed before they can be used next reboot.\n\nWould you like to open System Preferences?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if answer == QMessageBox.StandardButton.Yes:
            output = subprocess.run(
                [
                    "/usr/bin/osascript", "-e",
                    'tell app "System Preferences" to activate',
                    "-e", 'tell app "System Preferences" to reveal anchor "General" of pane id "com.apple.preference.security"',
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            if output.returncode != 0:
                subprocess.run(["/usr/bin/open", "-a", "System Preferences"])
            time.sleep(5)
            sys.exit(0)

    def _check_if_new_patches_needed(self, patches: dict) -> bool:
        """
        Checks if any new patches are needed for the user to install.
        """
        logging.info("Checking if new patches are needed")
        if self.constants.commit_info[0] in ["Running from source", "Built from source"] or self.constants.commit_info[2] is None or self.constants.commit_info[2] == "":
            logging.info("Built from source, running from source")
            return True

        if self.constants.computer.oclp_sys_url != self.constants.commit_info[2]:
            logging.info("- Commit URLs differ")
            logging.info(f"- Commit URLs: {self.constants.commit_info[2]}")
            return True

        macboxtool_plist = "/System/Library/CoreServices/MacBoxTool.plist"
        if not Path(macboxtool_plist).exists():
            return True

        macboxtool_plist_data = plistlib.load(open(macboxtool_plist, "rb"))
        for patch in patches:
            if not patch.startswith("Settings") and not patch.startswith("Validation") and patches[patch] is True:
                if patch.split(": ")[1] not in macboxtool_plist_data:
                    logging.info("- Patch {patch} not installed".format(patch=patch))
                    return True

        logging.info("No new patches detected for system")
        return False

    def cleanup_workers(self):
        for worker in (self.detection_worker, self.patch_worker, self.download_worker):
            if worker and worker.isRunning():
                worker.requestInterruption()
                if hasattr(worker, "cancel"):
                    worker.cancel()
                if not worker.wait(2000):
                    worker.terminate()
                    worker.wait(1000)
        if self.log_handler in logging.getLogger().handlers:
            logging.getLogger().removeHandler(self.log_handler)
