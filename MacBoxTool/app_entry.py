import argparse
import logging
import sys
import multiprocessing
import signal
from typing import Optional

# Required for PyInstaller multiprocessing support on macOS
multiprocessing.freeze_support()

# Global flag for graceful shutdown
_shutdown_requested = False
_qt_app: Optional['QApplication'] = None
_qt_window: Optional['QWidget'] = None


def _signal_handler(_signum, _frame):
    """Handle Ctrl+C (SIGINT) through the normal Qt shutdown path."""
    global _shutdown_requested, _qt_app, _qt_window
    if _shutdown_requested:
        return

    _shutdown_requested = True
    logging.info("GUI shutdown requested by user.")

    if _qt_window:
        QTimer.singleShot(0, _qt_window.close)
    elif _qt_app:
        QTimer.singleShot(0, _qt_app.quit)


# Register signal handler
signal.signal(signal.SIGINT, _signal_handler)

# Only import heavy modules after CLI parsing
from .install import Install
import importlib

from .support import (
    utilities,
    reroute_payloads,
    commit_info,
    logging_handler,
    analytics_handler
)
import threading
import time
import os
from pathlib import Path
def _parse_cli_args():
    """
    Parse CLI arguments.
    This function is called explicitly to avoid parsing at module import time,
    which would interfere with other scripts that import MacBoxTool (e.g., Build-Project.command).
    """
    parser = argparse.ArgumentParser(description='MacBoxTool - macOS Utility Tool')
    parser.add_argument('--build-efi', metavar='MODEL', help='Build EFI for specified model (e.g., MacPro7,1)')
    parser.add_argument('--install-disk', metavar='DISK', help='Install EFI to disk (use with --build-efi)')
    parser.add_argument('--download-installer', action='store_true', help='Download macOS installer')
    parser.add_argument('--probe-hardware', action='store_true', help='Probe and display hardware information')
    parser.add_argument('--version', action='store_true', help='Show version information')
    return parser.parse_args()


from .qt_gui.gui_go_in import OpenGUI
from .constants import Constants
from PySide2.QtWidgets import *
from PySide2.QtCore import *
from PySide2.QtGui import *
from .support.logging_handler import LoggingHandler
from .support.global_settings import GlobalSettings
if sys.platform=="darwin":
    from .detections import device_probe
else:
    from .detections import device_probe_win as device_probe

from .detections import os_probe





class MacBoxTool:
    def __init__(self)-> None:
        super().__init__()
        self.constants: Constants = Constants()
        LoggingHandler(self.constants)
        self._generate_base_data()
        self.install_requirements()

        self.settings=GlobalSettings(self.constants)
        self.target_model = self.settings.find_key("MODEL") or "MacPro7,1"
        self.constants.custom_model=self.target_model if self.target_model not in ("", "N/A", None) else None
        self.opengui()
        
    def install_requirements(self):
        if self.constants.qt_variant is False or self.constants.launcher_script:
            Install()
        return

    def hook_model(self):
        import threading
        def set_target():
            self.target_model = self.settings.find_key("MODEL") or "MacPro7,1"
        self.constants.custom_model=self.target_model if self.target_model !=("" or  None) else None
        a=threading.Thread(target=set_target,daemon=True)
        a.start()
        a.join()
    def opengui(self):
        w = OpenGUI(self.constants,self.settings)
        w.gui_main_menu()

    def _generate_base_data(self) -> None:
        """
        Generate base data required for the patcher to run
        """

        self.constants.qt_variant = True

        # Ensure we live after parent process dies (ie. LaunchAgent)
        os.setpgrp()

        # Generate OS data
        os_data = os_probe.OSProbe()
        self.constants.detected_os = os_data.detect_kernel_major()
        self.constants.detected_os_minor = os_data.detect_kernel_minor()
        self.constants.detected_os_build = os_data.detect_os_build()
        self.constants.detected_os_version = os_data.detect_os_version()

        
        # Generate computer data
        self.constants.computer = device_probe.Computer.probe()
        self.computer = self.constants.computer
        self.constants.booted_oc_disk = utilities.find_disk_off_uuid(utilities.clean_device_path(self.computer.opencore_path))
        if self.constants.computer.firmware_vendor:
            if self.constants.computer.firmware_vendor != "Apple":
                self.constants.host_is_hackintosh = True

        # Generate environment data
        self.constants.recovery_status = utilities.check_recovery()
        utilities.disable_cls()
        self._fix_cwd()

        # Generate binary data
        launcher_script = None
        launcher_binary = sys.executable
        if "python" in launcher_binary:
            # We're running from source
            launcher_script =  __file__
            if "main.py" in launcher_script:
                launcher_script = launcher_script.replace("/resources/main.py", "/MaxBoxTool_GUI.command")
        self.constants.launcher_binary = launcher_binary
        self.constants.launcher_script = launcher_script

        # Initialize working directory
        self.constants.unpack_thread = threading.Thread(target=reroute_payloads.RoutePayloadDiskImage, args=(self.constants,))
        self.constants.unpack_thread.start()

        # Generate commit info
        self.constants.commit_info = commit_info.ParseCommitInfo(self.constants.launcher_binary).generate_commit_info()
        if self.constants.commit_info[0] not in ["Running from source", "Built from source"]:
            # Now that we have commit info, update nightly link
            branch = self.constants.commit_info[0]
            branch = branch.replace("refs/heads/", "")
            self.constants.installer_pkg_url_nightly = self.constants.installer_pkg_url_nightly.replace("main", branch)

       
        threading.Thread(target=analytics_handler.Analytics(self.constants).send_analytics).start()

        from .support.on_nightly import CheckNightly
        if CheckNightly(self.constants).check() is True:
            self.constants.allow_nightly_check = True  

       

        logging.info("Detected arguments, switching to CLI mode")
        self.constants.gui_mode = True
    
    def _fix_cwd(self) -> None:
        """
        In some extreme scenarios, our current working directory may disappear
        """
        _test_dir = None
        try:
            _test_dir = Path.cwd()
            logging.info(f"{'Current working directory:'} {_test_dir}")
        except FileNotFoundError:
            _test_dir = Path(__file__).parent.parent.resolve()
            os.chdir(_test_dir)
            logging.warning(f"{'Current working directory was invalid, switched to:'} {_test_dir}")


def main():
    # Handle CLI commands using parsed args
    args = _parse_cli_args()
    
    if args.version:
        constants = Constants()
        print(f"MacBoxTool v{constants.macboxtool_version}")
        return

    if args.probe_hardware:
        # Run hardware probe and exit
        computer = device_probe.Computer().probe()
        print(f"Hardware: {computer}")
        return


    if args.download_installer:
        print("Download installer mode - launching GUI...")
        # Falls through to GUI launch




    # Default: Launch GUI
    MacBoxTool()