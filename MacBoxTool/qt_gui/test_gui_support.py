#!/usr/bin/env python3.14
"""
test_gui_support.py: Comprehensive test GUI for all converted gui_support classes

Tests all classes converted from wxPython to PySide6:
- AutoUpdateStages
- CheckModernAudio
- CheckProperties
- GenerateMenubar
- GaugePulseCallback
- PayloadMount
- ThreadHandler
- RestartHost
- Font utilities
"""

import sys
import logging
import threading
import time
from pathlib import Path

# Add MacBoxTool root to path
test_file_path = Path(__file__).resolve()
# Go up from qt_gui to MacBoxTool directory, then to project root
sys.path.insert(0, str(test_file_path.parent.parent.parent))

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QPlainTextEdit, QProgressBar, QMessageBox,
    QGroupBox, QFrame
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont

from MacBoxTool.qt_gui.gui_support import (
    AutoUpdateStages,
    CheckModernAudio,
    CheckProperties,
    GenerateMenubar,
    GaugePulseCallback,
    PayloadMount,
    ThreadHandler,
    RestartHost,
    get_font_face,
    font_factory,
)
from MacBoxTool.constants import Constants


class TestGUI(QMainWindow):
    """Test GUI for all converted classes"""

    def __init__(self):
        super().__init__()
        self.constants = Constants()
        self.setWindowTitle("gui_support.py Test GUI")
        self.setMinimumSize(900, 700)

        # Main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setSpacing(20)

        # Title
        title = QLabel("GUI Support Classes Test")
        title.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title)

        # Create test sections
        self._create_constants_tests(main_layout)
        self._create_font_tests(main_layout)
        self._create_menu_test(main_layout)
        self._create_progress_bar_test(main_layout)
        self._create_dialog_tests(main_layout)
        self._create_logging_test(main_layout)

        # Status bar
        self.statusBar().showMessage("Ready to test")

        # Add menu bar
        menu_generator = GenerateMenubar(self, self.constants)
        menu_generator.generate()

        logging.info("Test GUI initialized successfully")

    def _create_constants_tests(self, layout):
        """Create section for constants-based tests"""
        group = QGroupBox("Constants-Based Tests")
        group_layout = QVBoxLayout()

        # AutoUpdateStages test
        btn_autoupdate = QPushButton("Test AutoUpdateStages")
        btn_autoupdate.clicked.connect(self._test_autoupdate_stages)
        group_layout.addWidget(btn_autoupdate)

        # CheckModernAudio test
        btn_audio = QPushButton("Test CheckModernAudio")
        btn_audio.clicked.connect(self._test_check_modern_audio)
        group_layout.addWidget(btn_audio)

        # CheckProperties test
        btn_properties = QPushButton("Test CheckProperties")
        btn_properties.clicked.connect(self._test_check_properties)
        group_layout.addWidget(btn_properties)

        group.setLayout(group_layout)
        layout.addWidget(group)

    def _create_font_tests(self, layout):
        """Create section for font utility tests"""
        group = QGroupBox("Font Utility Tests")
        group_layout = QVBoxLayout()

        # Test get_font_face
        self.lbl_font_face = QLabel("System font: Loading...")
        group_layout.addWidget(self.lbl_font_face)

        btn_font_face = QPushButton("Test get_font_face()")
        btn_font_face.clicked.connect(self._test_get_font_face)
        group_layout.addWidget(btn_font_face)

        # Test font_factory
        btn_font_factory = QPushButton("Test font_factory()")
        btn_font_factory.clicked.connect(self._test_font_factory)
        group_layout.addWidget(btn_font_factory)

        # Test label with custom font
        self.lbl_test_font = QLabel("This text uses custom font (16pt, Bold)")
        group_layout.addWidget(self.lbl_test_font)

        group.setLayout(group_layout)
        layout.addWidget(group)

    def _create_menu_test(self, layout):
        """Create section for menu bar test"""
        group = QGroupBox("Menu Bar Test")
        group_layout = QVBoxLayout()

        lbl = QLabel("Check the 'File' menu in the menu bar above")
        lbl.setWordWrap(True)
        group_layout.addWidget(lbl)

        info = QLabel("It should have 'About OCLP-R' and 'Reveal Log File' options")
        info.setStyleSheet("color: gray; font-size: 11px;")
        info.setWordWrap(True)
        group_layout.addWidget(info)

        group.setLayout(group_layout)
        layout.addWidget(group)

    def _create_progress_bar_test(self, layout):
        """Create section for progress bar animation test"""
        group = QGroupBox("Progress Bar Pulse Animation Test")
        group_layout = QVBoxLayout()

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        group_layout.addWidget(self.progress_bar)

        btn_layout = QHBoxLayout()
        btn_start_pulse = QPushButton("Start Pulse")
        btn_start_pulse.clicked.connect(self._start_pulse_animation)
        btn_layout.addWidget(btn_start_pulse)

        btn_stop_pulse = QPushButton("Stop Pulse")
        btn_stop_pulse.clicked.connect(self._stop_pulse_animation)
        btn_layout.addWidget(btn_stop_pulse)

        group_layout.addLayout(btn_layout)

        info = QLabel("Tests GaugePulseCallback with QTimer-based animation")
        info.setStyleSheet("color: gray; font-size: 11px;")
        group_layout.addWidget(info)

        group.setLayout(group_layout)
        layout.addWidget(group)

    def _create_dialog_tests(self, layout):
        """Create section for dialog tests"""
        group = QGroupBox("Dialog Tests")
        group_layout = QVBoxLayout()

        btn_restart = QPushButton("Test RestartHost Dialog")
        btn_restart.clicked.connect(self._test_restart_dialog)
        group_layout.addWidget(btn_restart)

        info = QLabel("Warning: RestartHost will ask for system reboot!")
        info.setStyleSheet("color: orange; font-size: 11px;")
        info.setWordWrap(True)
        group_layout.addWidget(info)

        group.setLayout(group_layout)
        layout.addWidget(group)

    def _create_logging_test(self, layout):
        """Create section for logging handler test"""
        group = QGroupBox("ThreadHandler Logging Test")
        group_layout = QVBoxLayout()

        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        group_layout.addWidget(self.log_text)

        btn_test_log = QPushButton("Test ThreadHandler with Background Thread")
        btn_test_log.clicked.connect(self._test_thread_handler)
        group_layout.addWidget(btn_test_log)

        info = QLabel("ThreadHandler routes logging to QPlainTextEdit safely from background threads")
        info.setStyleSheet("color: gray; font-size: 11px;")
        info.setWordWrap(True)
        group_layout.addWidget(info)

        group.setLayout(group_layout)
        layout.addWidget(group)

    def _test_autoupdate_stages(self):
        """Test AutoUpdateStages constants"""
        stages = [
            ("INACTIVE", AutoUpdateStages.INACTIVE),
            ("CHECKING", AutoUpdateStages.CHECKING),
            ("BUILDING", AutoUpdateStages.BUILDING),
            ("INSTALLING", AutoUpdateStages.INSTALLING),
            ("ROOT_PATCHING", AutoUpdateStages.ROOT_PATCHING),
            ("FINISHED", AutoUpdateStages.FINISHED),
        ]

        msg = "AutoUpdateStages Values:\n\n"
        for name, value in stages:
            msg += f"{name} = {value}\n"

        QMessageBox.information(self, "AutoUpdateStages Test", msg)
        logging.info("AutoUpdateStages test completed")

    def _test_check_modern_audio(self):
        """Test CheckModernAudio"""
        checker = CheckModernAudio()
        result = checker.audio_check()

        msg = f"Audio Check Result:\n\n"
        msg += f"audio_type: {checker.constants.audio_type}\n"
        msg += f"audio_check() returns: {result}\n"
        msg += f"({'✓ AppleALC' if result else '✗ VoodooHDA or other'})"

        QMessageBox.information(self, "CheckModernAudio Test", msg)
        logging.info(f"CheckModernAudio test: {result}")

    def _test_check_properties(self):
        """Test CheckProperties"""
        checker = CheckProperties(self.constants)

        results = []
        results.append(f"host_can_build: {checker.host_can_build()}")
        results.append(f"host_is_non_metal: {checker.host_is_non_metal()}")
        results.append(f"host_is_solarium: {checker.host_is_solarium()}")
        results.append(f"host_has_cpu_gen(3): {checker.host_has_cpu_gen(3)}")
        results.append(f"host_psp_version: {checker.host_psp_version()}")

        msg = "CheckProperties Results:\n\n" + "\n".join(results)

        QMessageBox.information(self, "CheckProperties Test", msg)
        logging.info("CheckProperties test completed")

    def _test_get_font_face(self):
        """Test get_font_face()"""
        font_face = get_font_face()
        self.lbl_font_face.setText(f"System font: {font_face}")

        QMessageBox.information(
            self,
            "get_font_face() Test",
            f"System font face:\n\n{font_face}"
        )
        logging.info(f"get_font_face test: {font_face}")

    def _test_font_factory(self):
        """Test font_factory()"""
        font = font_factory(16, QFont.Weight.Bold)
        self.lbl_test_font.setFont(font)

        QMessageBox.information(
            self,
            "font_factory() Test",
            f"Created QFont:\n\nFamily: {font.family()}\nSize: {font.pointSize()}\nWeight: {font.weight()}"
        )
        logging.info(f"font_factory test: {font.family()} {font.pointSize()}pt")

    def _start_pulse_animation(self):
        """Start progress bar pulse animation"""
        self.gauge_callback = GaugePulseCallback(self.constants, self.progress_bar)
        self.gauge_callback.start_pulse()
        self.statusBar().showMessage("Pulse animation started")

    def _stop_pulse_animation(self):
        """Stop progress bar pulse animation"""
        if hasattr(self, 'gauge_callback'):
            self.gauge_callback.stop_pulse()
            self.statusBar().showMessage("Pulse animation stopped")

    def _test_restart_dialog(self):
        """Test RestartHost dialog"""
        restart_handler = RestartHost(self)
        test_message = "This is a test message for the restart dialog.\n\nThe application will NOT actually restart in this test."
        restart_handler.restart(test_message)

    def _test_thread_handler(self):
        """Test ThreadHandler with background logging"""
        # Setup logging handler
        handler = ThreadHandler(self.log_text)
        handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

        # Add to root logger temporarily
        root_logger = logging.getLogger()
        old_handlers = root_logger.handlers[:]
        root_logger.handlers = [handler]
        root_logger.setLevel(logging.INFO)

        def background_task():
            """Simulate background task with logging"""
            logging.info("Background task started")
            time.sleep(0.5)
            logging.info("Processing step 1...")
            time.sleep(0.5)
            logging.info("Processing step 2...")
            time.sleep(0.5)
            logging.warning("This is a warning message")
            time.sleep(0.5)
            logging.info("Background task completed")

        # Clear log text
        self.log_text.clear()

        # Start background thread
        thread = threading.Thread(target=background_task)
        thread.start()

        # Restore original handlers after thread completes
        def restore_handlers():
            thread.join()
            root_logger.handlers = old_handlers
            self.statusBar().showMessage("ThreadHandler test completed")

        QTimer.singleShot(3000, restore_handlers)
        self.statusBar().showMessage("ThreadHandler test running... (check log window)")


def main():
    """Main entry point"""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Create application
    app = QApplication(sys.argv)
    app.setApplicationName("GUI Support Test")

    # Create and show main window
    window = TestGUI()
    window.show()

    logging.info("Test GUI started")

    # Run application
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
