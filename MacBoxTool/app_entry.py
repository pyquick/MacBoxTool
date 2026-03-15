import argparse
import sys

# Parse CLI arguments early, before any heavy imports
_cli_parser = argparse.ArgumentParser(description='MacBoxTool - macOS Utility Tool')
_cli_parser.add_argument('--build-efi', metavar='MODEL', help='Build EFI for specified model (e.g., MacPro7,1)')
_cli_parser.add_argument('--install-disk', metavar='DISK', help='Install EFI to disk (use with --build-efi)')
_cli_parser.add_argument('--download-installer', action='store_true', help='Download macOS installer')
_cli_parser.add_argument('--probe-hardware', action='store_true', help='Probe and display hardware information')
_cli_parser.add_argument('--settings', action='store_true', help='Show settings configuration')
_cli_parser.add_argument('--test', action='store_true', help='Run tests and validation')
_cli_parser.add_argument('--validate', action='store_true', help='Validate EFI build for all supported models')
_cli_parser.add_argument('--version', action='store_true', help='Show version information')
_cli_args = _cli_parser.parse_args()

# Handle --validate early (before GUI imports)
if _cli_args.validate:
    from .validation import validate_all_models
    validate_all_models()
    sys.exit(0)

# Only import heavy modules after CLI parsing
from .install import Install
import importlib
Install()

from .qt_gui.gui_go_in import OpenGUI
from .constants import Constants
from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *
from .support.logging_handler import LoggingHandler
from .support.toggle_theme import ThemeManager
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
        self.computer= device_probe.Computer().probe()

        os_data = os_probe.OSProbe()
        self.constants.detected_os = os_data.detect_kernel_major()
        self.constants.detected_os_minor = os_data.detect_kernel_minor()
        self.constants.detected_os_build = os_data.detect_os_build()
        self.constants.detected_os_version = os_data.detect_os_version()
        self.constants.computer = self.computer
        launcher_binary = sys.executable
        if "python" in launcher_binary:
            # We're running from source
            launcher_script =  __file__
            if "main.py" in launcher_script:
                launcher_script = launcher_script.replace("/resources/main.py", "/MaxToolBox_GUI.command")
        self.constants.launcher_binary = launcher_binary
        self.constants.launcher_script = launcher_script
        LoggingHandler(self.constants)
        ThemeManager(self.constants)
        self.settings=GlobalSettings(self.constants)
        self.opengui()


    def opengui(self):
        w = OpenGUI(self.constants,self.settings)
        w.gui_main_menu()

def main():
    # Handle CLI commands using pre-parsed args
    args = _cli_args

    if args.version:
        constants = Constants()
        print(f"MacBoxTool v{constants.patcher_version}")
        return

    if args.validate:
        # Run validation for all models
        from .validation import validate_all_models
        validate_all_models()
        return

    if args.probe_hardware:
        # Run hardware probe and exit
        computer = device_probe.Computer().probe()
        print(f"Hardware: {computer}")
        return

    if args.build_efi:
        # Build EFI for specified model
        print(f"Building EFI for {args.build_efi}...")
        # TODO: Implement EFI build logic
        if args.install_disk:
            print(f"Installing to disk: {args.install_disk}")
        return

    if args.download_installer:
        print("Download installer mode - launching GUI...")
        # Falls through to GUI launch

    if args.settings:
        print("Settings mode - launching GUI...")

    if args.test:
        print("Test mode - launching GUI...")

    # Default: Launch GUI
    MacBoxTool()