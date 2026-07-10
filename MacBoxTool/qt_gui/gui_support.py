"""
gui_support.py: Give custom looks
"""

from ..include import *

# Additional imports for converted wxPython classes
from PySide6.QtWidgets import QMenuBar, QMenu, QMessageBox, QProgressBar, QPlainTextEdit, QTextEdit, QMainWindow, QWidget
from PySide6.QtCore import QMetaObject, Qt, Q_ARG, QTimer, QObject
from PySide6.QtGui import QFont
from shiboken6 import isValid as is_qt_object_valid
import subprocess
import sys
import logging
import threading
import time
import plistlib
import packaging.version
from pathlib import Path


class ThemeAwareCard(CardWidget):
    def __init__(self, get_style_fn, parent=None):
        super().__init__(parent)
        self._get_style = get_style_fn
        self._apply_style()
        qconfig.themeChanged.connect(self._apply_style)

    def _apply_style(self):
        if not is_qt_object_valid(self):
            return
        style = self._get_style()
        self.setStyleSheet(f"""
            CardWidget {{
                background-color: {style["bg"]};
                border: 1px solid {style["border"]};
                border-radius: {RADIUS["card"]}px;
            }}
        """)

class ProgressStatusHelper:
    def __init__(self, status_icon_label, progress_label, progress_bar, progress_container):
        

        logging.info("init gui_support")

        
        self.status_icon_label = status_icon_label
        self.progress_label = progress_label
        self.progress_bar = progress_bar
        self.progress_container = progress_container
        

    
    
    def update(self, status, message, progress=None):
        icon_size = 28
        icon_map = {
            "loading": (FluentIcon.SYNC, COLORS["primary"]),
            "success": (FluentIcon.COMPLETED, COLORS["success"]),
            "error": (FluentIcon.CLOSE, COLORS["error"]),
            "warning": (FluentIcon.INFO, COLORS["warning"]),
        }
        
        if status in icon_map:
            icon, color = icon_map[status]
            pixmap = icon.icon(color=color).pixmap(icon_size, icon_size)
            self.status_icon_label.setPixmap(pixmap)
        
        self.progress_label.setText(message)
        if status == "success":
            self.progress_label.setStyleSheet("color: {}; font-size: 15px; font-weight: 600;".format(COLORS["success"]))
        elif status == "error":
            self.progress_label.setStyleSheet("color: {}; font-size: 15px; font-weight: 600;".format(COLORS["error"]))
        elif status == "warning":
            self.progress_label.setStyleSheet("color: {}; font-size: 15px; font-weight: 600;".format(COLORS["warning"]))
        else:
            self.progress_label.setStyleSheet("color: {}; font-size: 15px; font-weight: 600;".format(COLORS["primary"]))
        
        if progress is not None:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(progress)
        else:
            self.progress_bar.setRange(0, 0)
        
        self.progress_container.setVisible(True)

class DefGUI():
    def __init__(self,global_constants:Constants):
        self.constants:Constants=global_constants
        if qconfig.theme == Theme.DARK:
            self.card_styles = self.card_styles_dark()
        else:
            self.card_styles = self.card_styles_light()
        qconfig.themeChanged.connect(self.update_theme)

    def build_icon_label(self, icon: FluentIcon, color: str, size: int = 32) -> QLabel:
        label = QLabel()
        label.setPixmap(icon.icon(color=color).pixmap(size, size))
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setFixedSize(size + 12, size + 12)
        return label
    
    

    
    def create_info_widget(self, text: str, color: Optional[str] = None) -> QWidget:
        if not text:
            return QWidget()
        
        label = BodyLabel(text)
        label.setWordWrap(True)
        if color:
            label.setStyleSheet("color: {};".format(color))
        return label
    
    def colored_icon(self, icon: FluentIcon, color_hex: str) -> FluentIcon:
        if not icon or not color_hex:
            return icon
        
        tint = QColor(color_hex)
        return icon.colored(tint, tint)

    def get_compatibility_icon(self, compat_tuple: Optional[Tuple[Optional[str], Optional[str]]]) -> FluentIcon:
        if not compat_tuple or compat_tuple == (None, None):
            return self.colored_icon(FluentIcon.CLOSE, COLORS["error"])
        return self.colored_icon(FluentIcon.ACCEPT, COLORS["success"])
    
    def update_theme(self):
        if qconfig.theme == Theme.DARK:
            self.card_styles = self.card_styles_dark()
        else:
            self.card_styles = self.card_styles_light()

    
    def card_styles_light(self):
        return  {
            "note": {
                "bg": COLORS["note_bg"],
                "text": COLORS["note_text"],
                "border": "rgba(21, 101, 192, 0.2)",
                "default_icon": FluentIcon.INFO
            },
            "warning": {
                "bg": COLORS["warning_bg"],
                "text": COLORS["warning_text"],
                "border": "rgba(245, 124, 0, 0.25)",
                "default_icon": FluentIcon.MEGAPHONE
            },
            "success": {
                "bg": COLORS["success_bg"],
                "text": COLORS["success"],
                "border": "rgba(16, 124, 16, 0.2)",
                "default_icon": FluentIcon.COMPLETED
            },
            "error": {
                "bg": "#FFEBEE",
                "text": COLORS["error"],
                "border": "rgba(232, 17, 35, 0.25)",
                "default_icon": FluentIcon.CLOSE
            },
            "info": {
                "bg": COLORS["note_bg"],
                "text": COLORS["info"],
                "border": "rgba(0, 120, 212, 0.2)",
                "default_icon": FluentIcon.INFO
            }
        }

    def card_styles_dark(self):
        return {
            "note": {
                "bg": "rgba(33, 90, 160, 0.18)",
                "text": "#82B4F0",
                "border": "rgba(66, 133, 244, 0.35)",
                "default_icon": FluentIcon.INFO
            },
            "warning": {
                "bg": "rgba(160, 90, 0, 0.18)",
                "text": "#FFB74D",
                "border": "rgba(255, 152, 0, 0.35)",
                "default_icon": FluentIcon.MEGAPHONE
            },
            "success": {
                "bg": "rgba(16, 100, 16, 0.18)",
                "text": "#6DBF6D",
                "border": "rgba(16, 124, 16, 0.35)",
                "default_icon": FluentIcon.COMPLETED
            },
            "error": {
                "bg": "rgba(180, 20, 30, 0.18)",
                "text": "#F28B82",
                "border": "rgba(232, 17, 35, 0.35)",
                "default_icon": FluentIcon.CLOSE
            },
            "info": {
                "bg": "rgba(0, 90, 158, 0.18)",
                "text": "#4CC2FF",
                "border": "rgba(0, 120, 212, 0.35)",
                "default_icon": FluentIcon.INFO
            }
        }
    
    def custom_card(self, card_type: str = "note", icon: Optional[FluentIcon] = None, title: str = "", body: str = "", custom_widget: Optional[QWidget] = None, parent: Optional[QWidget] = None) -> CardWidget:
        resolved_icon = icon
        get_style = lambda: self.card_styles.get(card_type, self.card_styles["note"])

        def apply_style_if_valid(widget: QWidget, style_sheet: str):
            if is_qt_object_valid(widget):
                widget.setStyleSheet(style_sheet)

        if resolved_icon is None:
            resolved_icon = get_style()["default_icon"]

        card = ThemeAwareCard(get_style, parent)

        main_layout = QHBoxLayout(card)
        main_layout.setContentsMargins(SPACING["large"], SPACING["large"], SPACING["large"], SPACING["large"])
        main_layout.setSpacing(SPACING["large"])

        icon_label = self.build_icon_label(resolved_icon, get_style()["text"], size=40)
        def _refresh_icon():
            if is_qt_object_valid(icon_label):
                icon_label.setPixmap(resolved_icon.icon(color=get_style()["text"]).pixmap(40, 40))
        _refresh_icon()
        qconfig.themeChanged.connect(_refresh_icon)
        main_layout.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignVCenter)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(SPACING["small"])

        if title:
            title_label = StrongBodyLabel(title)
            title_style = lambda: "color: {}; font-size: 16px;".format(get_style()["text"])
            apply_style_if_valid(title_label, title_style())

            # Create proper callback function for theme changes
            def update_title_with_delay():
                QTimer.singleShot(40, lambda: apply_style_if_valid(title_label, title_style()))

            qconfig.themeChanged.connect(update_title_with_delay)
            text_layout.addWidget(title_label)

        if body:
            body_label = BodyLabel(body)
            body_label.setWordWrap(True)
            body_label.setOpenExternalLinks(True)
            apply_style_if_valid(body_label, "line-height: 1.6;")
            text_layout.addWidget(body_label)

        if custom_widget:
            text_layout.addWidget(custom_widget)

        main_layout.addLayout(text_layout)
        return card
    
    def add_group_with_indent(self, card: "GroupHeaderCardWidget", icon: FluentIcon, title: str, content: str, widget: Optional[QWidget] = None, indent_level: int = 0) -> "CardGroupWidget":
        if widget is None:
            widget = QWidget()
        
        group = card.addGroup(icon, title, content, widget)
        
        if indent_level > 0:
            base_margin = 24
            indent = 20 * indent_level
            group.hBoxLayout.setContentsMargins(base_margin + indent, 10, 24, 10)
        
        return group

    def create_step_indicator(self, step_number: int, total_steps: int = 4, color: str = "#0078D4") -> BodyLabel:
        label = BodyLabel("STEP {} OF {}".format(step_number, total_steps))
        label.setStyleSheet("color: {}; font-weight: bold;".format(color))
        return label

    def create_vertical_spacer(self, spacing: int = SPACING["medium"]) -> QWidget:
        spacer = QWidget()
        spacer.setFixedHeight(spacing)
        return spacer
        

def wait_for_thread(thread: threading.Thread, sleep_interval=None):
    """
    Waits for a thread to finish while processing UI events at regular intervals
    to prevent UI freezing and excessive CPU usage.

    Args:
        thread: The thread to wait for
        sleep_interval: Optional sleep interval in seconds, defaults to 0.01
    """
    interval = sleep_interval if sleep_interval is not None else 0.01

    while thread.is_alive():
        QApplication.processEvents()  # Process Qt events instead of wx.Yield()
        thread.join(timeout=interval)


# =============================================================================
# Converted wxPython Classes from nd.py
# =============================================================================

class AutoUpdateStages:
    """Auto-update stage constants"""
    INACTIVE = 0
    CHECKING = 1
    BUILDING = 2
    INSTALLING = 3
    ROOT_PATCHING = 4
    FINISHED = 5


class CheckModernAudio:
    """Check if modern audio (AppleALC) is in use"""
    def __init__(self, global_constants: Constants = None):
        self.constants: Constants = global_constants

    def audio_check(self):
        """Returns True if AppleALC, False if VoodooHDA"""
        audio_type = self.constants.audio_type if self.constants else "AppleALC"
        if audio_type == "VoodooHDA":
            return False
        if audio_type == "AppleALC":
            return True
        return False


class CheckProperties:
    """Property checking utilities for host system"""

    def __init__(self, global_constants: Constants) -> None:
        self.constants: Constants = global_constants

    def host_can_build(self):
        """
        Check if host supports building OpenCore configs
        """
        if self.constants.custom_model:
            return True
        if self.constants.host_is_hackintosh is True:
            return False
        if self.constants.allow_oc_everywhere is True:
            return True
        if self.constants.computer.real_model in model_array.SupportedSMBIOS:
            return True

        return False

    def host_is_non_metal(self, general_check: bool = False):
        """
        Check if host is non-metal
        Primarily for QProgressBar workaround on macOS
        """
        if self.constants.detected_os < os_data.os_data.monterey and general_check is False:
            return False
        if self.constants.detected_os < os_data.os_data.big_sur and general_check is True:
            return False
        if not Path("/System/Library/PrivateFrameworks/SkyLight.framework/Versions/A/SkyLightOld.dylib").exists():
            # SkyLight stubs are only used on non-Metal
            return False

        return True

    def host_is_solarium(self) -> bool:
        """Check if host is Solarium or later"""
        if self.constants.detected_os < os_data.os_data.tahoe:
            return False
        return True

    def host_has_cpu_gen(self, gen: int) -> bool:
        """
        Check if host has a CPU generation equal to or greater than the specified generation
        """
        model = self.constants.custom_model if self.constants.custom_model else self.constants.computer.real_model
        if model in smbios_data.smbios_dictionary:
            if smbios_data.smbios_dictionary[model]["CPU Generation"] >= gen:
                return True
        return False

    def host_psp_version(self) -> packaging.version.Version:
        """
        Grab PatcherSupportPkg version from MacBoxTool.plist
        """
        mbt_plist_path = "/System/Library/CoreServices/MacBoxTool.plist"
        if not Path(mbt_plist_path).exists():
            return packaging.version.Version("0.0.0")

        mbt_plist = plistlib.load(open(mbt_plist_path, "rb"))
        if "PatcherSupportPkg" not in mbt_plist:
            return packaging.version.Version("0.0.0")

        if mbt_plist["PatcherSupportPkg"].startswith("v"):
            mbt_plist["PatcherSupportPkg"] = mbt_plist["PatcherSupportPkg"][1:]

        return packaging.version.parse(mbt_plist["PatcherSupportPkg"])

    def host_has_3802_gpu(self) -> bool:
        """
        Check if either host, or override model, has a 3802 GPU
        """
        gpu_archs = []
        if self.constants.custom_model:
            model = self.constants.custom_model
        else:
            model = self.constants.computer.real_model
            gpu_archs = [gpu.arch for gpu in self.constants.computer.gpus]

        if not gpu_archs:
            gpu_archs = smbios_data.smbios_dictionary.get(model, {}).get("Stock GPUs", [])

        for arch in gpu_archs:
            if arch in [
                device_probe.Intel.Archs.Ivy_Bridge,
                device_probe.Intel.Archs.Haswell,
                device_probe.NVIDIA.Archs.Kepler,
            ]:
                return True

        return False


def get_font_face():
    """Get system default font family name"""
    if not get_font_face.font_face:
        default_font = QApplication.font()
        get_font_face.font_face = default_font.family() or "SF Pro Display"
    return get_font_face.font_face

get_font_face.font_face = None


def font_factory(size: int, weight: QFont.Weight) -> QFont:
    """Create QFont with specified size and weight"""
    font = QFont(get_font_face(), size)
    font.setWeight(weight)
    return font


class GenerateMenubar:
    """Generate menu bar for Qt windows"""

    def __init__(self, window: QMainWindow, global_constants: Constants) -> None:
        self.window: QMainWindow = window
        self.constants: Constants = global_constants

    def generate(self) -> QMenuBar:
        """Generate and attach menu bar to window"""
        menubar = self.window.menuBar()
        fileMenu = menubar.addMenu("&File")

        aboutAction = fileMenu.addAction("&About MacBoxTool")
        fileMenu.addSeparator()
        revealLogAction = fileMenu.addAction("&Reveal Log File")

        aboutAction.triggered.connect(lambda: self._show_about())
        revealLogAction.triggered.connect(
            lambda: subprocess.run(["/usr/bin/open", "--reveal", self.constants.log_filepath])
        )

        return menubar

    def _show_about(self):
        """Launch about dialog"""
        try:
            from .gui_about import AboutInterface
            about_dialog = AboutInterface(self.constants)
            about_dialog.exec()
        except Exception as e:
            logging.error(f"Failed to show about dialog: {e}")


class GaugePulseCallback(QObject):
    """
    Uses QTimer for smooth progress bar animation on macOS
    Alternative to setRange(0, 0) for indeterminate progress

    Note: This work-around is no longer needed on hosts using PatcherSupportPkg 1.1.2 or newer
    """

    def __init__(self, global_constants: Constants, progress_bar: IndeterminateProgressRing|ProgressBar|QProgressBar|IndeterminateProgressBar) -> None:
        super().__init__()
        self.progress_bar: IndeterminateProgressRing|ProgressBar|QProgressBar|IndeterminateProgressBar = progress_bar
        self.timer = QTimer()
        self.timer.timeout.connect(self._pulse)

        self.gauge_value: int = 0
        self.pulse_forward: bool = True
        self.max_value: int = 100

        # Check if we need the workaround
        self.non_metal_alternative: bool = CheckProperties(global_constants).host_is_non_metal()
        if self.non_metal_alternative:
            if CheckProperties(global_constants).host_psp_version() >= packaging.version.Version("1.1.2"):
                self.non_metal_alternative = False

    def start_pulse(self) -> None:
        """Start the pulse animation"""
        if not self.non_metal_alternative:
            # Use Qt's built-in indeterminate progress
            self.progress_bar.setRange(0, 0)
            return

        # Use custom pulse animation
        self.progress_bar.setRange(0, self.max_value)
        self.timer.start(5)  # 5ms interval for smooth animation

    def stop_pulse(self) -> None:
        """Stop the pulse animation"""
        if not self.non_metal_alternative:
            self.progress_bar.setRange(0, 100)  # Reset to determinate
            return

        self.timer.stop()

    def _pulse(self) -> None:
        """Update progress bar value"""
        if self.gauge_value == 0:
            self.pulse_forward = True
        elif self.gauge_value == self.max_value:
            self.pulse_forward = False

        if self.pulse_forward:
            self.gauge_value += 1
        else:
            self.gauge_value -= 1

        self.progress_bar.setValue(self.gauge_value)


class PayloadMount:
    """Check if payload unpacking is complete"""

    def __init__(self, global_constants: Constants, parent: QWidget) -> None:
        self.constants: Constants = global_constants
        self.trans = self._get_translations()
        self.parent: QWidget = parent

    def _get_translations(self):
        """Get translation dictionary"""
        return {
            "During unpacking of our internal files, we seemed to have encountered an error.\n\nIf you keep seeing this error, please try rebooting and redownloading the application.": "During unpacking of our internal files, we seemed to have encountered an error.\n\nIf you keep seeing this error, please try rebooting and redownloading the application.",
            "Internal Error occurred!": "Internal Error occurred!"
        }

    def is_unpack_finished(self):
        """Check if payload unpacking is complete"""
        if self.constants.unpack_thread.is_alive():
            return False

        if Path(self.constants.payload_kexts_path).exists():
            return True

        # Show error dialog
        QMessageBox.critical(
            self.parent,
            "Internal Error occurred!",
            "During unpacking of our internal files, we seemed to have encountered an error.\n\nIf you keep seeing this error, please try rebooting and redownloading the application."
        )
        sys.exit(1)


class ThreadHandler(logging.Handler):
    """
    Reroutes logging output to a Qt text widget using UI callbacks
    Thread-safe for Qt GUI updates
    """

    def __init__(self, text_edit: QPlainTextEdit | QTextEdit):
        logging.Handler.__init__(self)
        self.text_edit = text_edit

    def emit(self, record: logging.LogRecord):
        """Thread-safe emit using Qt's signal/slot mechanism"""
        msg = self.format(record)
        if isinstance(self.text_edit, QPlainTextEdit):
            method = "appendPlainText"
        else:
            method = "append"

        QMetaObject.invokeMethod(
            self.text_edit,
            method,
            Qt.ConnectionType.QueuedConnection,
            Q_ARG(str, msg)
        )


class RestartHost:
    """
    Restarts the host machine with user confirmation
    """

    def __init__(self, parent: QWidget, global_constants: Constants = None) -> None:
        self.parent: QWidget = parent
        self.constants: Constants = global_constants
        self.trans = self._get_translations()

    def _get_translations(self):
        """Get translation dictionary"""
        return {
            "Reboot to apply?": "Reboot to apply?",
            "Reboot": "Reboot",
            "Ignore": "Ignore",
            "Error while trying to reboot:": "Error while trying to reboot:"
        }

    def restart(self, message: str = ""):
        """Prompt user for restart confirmation"""
        reply = QMessageBox.question(
            self.parent,
            "Reboot to apply?",
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.parent.hide()
            QApplication.processEvents()
            try:
                import applescript
                applescript.AppleScript('tell app "loginwindow" to «event aevtrrst»').run()
            except Exception as e:
                logging.error(f"{'Error while trying to reboot:'} {e}")
            sys.exit(0)