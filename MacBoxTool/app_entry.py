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
    """Handle Ctrl+C (SIGINT) for graceful shutdown"""
    global _shutdown_requested, _qt_app, _qt_window
    if _shutdown_requested:
        # Force exit if already requested
        sys.exit(1)
    _shutdown_requested = True

    # Immediately destroy GUI window first
    if _qt_window:
        try:
            _qt_window.close()
            _qt_window.destroy()
        except:
            pass

    # Then quit the application
    if _qt_app:
        try:
            _qt_app.quit()
            _qt_app.processEvents()
        except:
            pass
    
    logging.info("GUI is destroyed by user.")
    sys.exit(0)


# Register signal handler
signal.signal(signal.SIGINT, _signal_handler)

# Only import heavy modules after CLI parsing
from .install import Install
import importlib
if sys.platform=="darwin":
    from .support import (
        utilities,
        reroute_payloads,
        commit_info,
        logging_handler
    )
else:
    from .support import (
        utilities_win as utilities,
        reroute_payloads,
        commit_info,
        logging_handler
    )
import threading
import logging
import time
import os
from pathlib import Path
# CLI parsing moved to support/utilities.check_cli_args()


from .constants import Constants
from .support.logging_handler import LoggingHandler
from .support.global_settings import GlobalSettings
if sys.platform=="darwin":
    from .detections import device_probe
else:
    from .detections import device_probe_win as device_probe

from .detections import os_probe





class MacBoxTool:
    def __init__(self, cli_mode: bool = False, gui_patch: bool = False, gui_unpatch: bool = False, update_installed: bool = False) -> None:
        super().__init__()
        self.constants: Constants = Constants()
        self.constants.cli_mode = cli_mode
        try:
            from .support import crash_report
            crash_report.install()
        except ImportError:
            pass
        LoggingHandler(self.constants)
        self._generate_base_data()
        self.install_requirements()
        self.check_voodoo_patch()

        self.settings=GlobalSettings(self.constants)
        self.target_model = self.settings.find_key("MODEL") or "MacPro7,1"
        self.constants.custom_model=self.target_model if self.target_model not in ("", "N/A", None) else None

        if cli_mode:
            from .support.arguments import arguments
            arguments(self.constants)
        else:
            if gui_patch or gui_unpatch:
                self.constants.start_sys_patch = True
                self.constants.start_sys_patch_now = gui_patch
            if update_installed:
                self.constants.start_update_installed = True
            self.opengui()
        
    def install_requirements(self):
        # Frozen builds already contain their runtime dependencies.  Never invoke
        # pip from a packaged application, which could also create a console window.
        if not getattr(sys, "frozen", False) and (
            self.constants.qt_variant is False or self.constants.launcher_script
        ):
            Install()
        return
    
    def check_voodoo_patch(self) -> None:
        self.constants.voodoo_patch_already=os.path.exists(self.constants.voodoo_kext_path)
        self.constants.hdau_patch_already = os.path.exists(self.constants.hdau_kext_path)

    def hook_model(self):
        import threading
        def set_target():
            self.target_model = self.settings.find_key("MODEL") or "MacPro7,1"
        self.constants.custom_model=self.target_model if self.target_model !=("" or  None) else None
        a=threading.Thread(target=set_target,daemon=True)
        a.start()
        a.join()
    def opengui(self):
        from .qt_gui.gui_entry import OpenGUI
        w = OpenGUI(self.constants,self.settings)
        w.gui_main_menu()

    def _generate_base_data(self) -> None:
        """
        Generate base data required for the patcher to run
        """

        self.constants.qt_variant = True
        if sys.platform=="darwin":
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
        self.constants.unpack_thread = threading.Thread(target=reroute_payloads.RoutePayloadDiskImage, args=(self.constants,),daemon=True)
        self.constants.unpack_thread.start()

        # Generate commit info
        self.constants.commit_info = commit_info.ParseCommitInfo(self.constants.launcher_binary).generate_commit_info()
        if self.constants.commit_info[0] not in ["Running from source", "Built from source"]:
            # Now that we have commit info, update nightly link
            branch = self.constants.commit_info[0]
            branch = branch.replace("refs/heads/", "")
            self.constants.installer_pkg_url_nightly = self.constants.installer_pkg_url_nightly.replace("main", branch)

       
        from .support import analytics_handler
        threading.Thread(target=analytics_handler.Analytics(self.constants).send_analytics, daemon=True).start()

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
        except (FileNotFoundError, OSError, PermissionError):
            try:
                if getattr(sys, "frozen", False):
                    _test_dir = Path(sys.executable).resolve().parent
                else:
                    _test_dir = Path(__file__).parent.parent.resolve()
                os.chdir(str(_test_dir))
                logging.warning(f"{'Current working directory was invalid, switched to:'} {_test_dir}")
            except Exception:
                logging.warning("Failed to switch working directory, continuing anyway")


def main():
    import platform
    if int(platform.release().split(".")[0]) < 20 and sys.platform=="darwin":
        sys.exit(1)

    # Quick-exit flags: no heavy init required
    if "--version" in sys.argv:
        from .constants import Constants
        print(f"MacBoxTool v{Constants().macboxtool_version}")
        return

    if "--probe-hardware" in sys.argv:
        if sys.platform=="darwin":
            from .detections import device_probe
        else:
            from .detections import device_probe_win as device_probe
        print(f"Hardware: {device_probe.Computer().probe()}")
        return

    if "--gui_os_update" in sys.argv:
        idx = sys.argv.index("--gui_os_update")
        os_version = sys.argv[idx + 1] if len(sys.argv) > idx + 1 else None
        os_build = sys.argv[idx + 2] if len(sys.argv) > idx + 2 else None
        from .qt_gui.gui_os_update import show_os_update_popup
        show_os_update_popup(os_version, os_build)
        return

    # Parse CLI args; returns None if no action flag present
    args = utilities.check_cli_args()

    if args is None:
        # No CLI action -> launch GUI, optionally with direct-entry flags
        gui_patch = "--gui_patch" in sys.argv
        gui_unpatch = "--gui_unpatch" in sys.argv
        update_installed = "--update_installed" in sys.argv
        MacBoxTool(gui_patch=gui_patch, gui_unpatch=gui_unpatch, update_installed=update_installed)
        return

    # CLI action flags detected
    MacBoxTool(cli_mode=True)