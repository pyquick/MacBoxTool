"""
logging_handler.py: A logging handler to log messages to a file and the console.
"""

import logging
import sys
import os
import threading
import logging
import pprint
import traceback
import subprocess
if sys.platform == "darwin":
    import applescript

from pathlib import Path
from datetime import datetime

from ..constants import Constants

DATE_FORMAT:      str = "%Y-%m-%d %H-%M-%S"

class LoggingHandler:
    def __init__(self, global_constants: Constants) -> None:

        self.constants:Constants  = global_constants
        log_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")

        self.log_filename: str  = f"MacBoxTool_{self.constants.macboxtool_version}_{log_time}.log"
        self.log_filepath: Path = None

        self.original_excepthook:        sys       = sys.excepthook
        self.original_thread_excepthook: threading = threading.excepthook

        self.max_file_size:     int = 1024 * 1024               # 1 MB
        self.file_size_redline: int = 1024 * 1024 - 1024 * 100  # 900 KB, when to start cleaning log file

        self._initialize_logging_path()
        self._attempt_initialize_logging_configuration()
        self._start_logging()
        self._implement_custom_traceback_handler()
        self._clean_prior_version_logs()



    def _initialize_logging_path(self) -> None:
        """
        Initialize logging framework storage path
        """
        if sys.platform == "win32":
            self._initialize_logging_path_windows()
            return

        base_path = Path("~/Library/Logs").expanduser()
        if not base_path.exists() or str(base_path).startswith("/var/root/"):
            # Likely in an installer environment, store in /Users/Shared
            base_path = Path("/Users/Shared")
        else:
            # create Pyquick folder if it doesn't exist
            base_path = base_path / "Pyquick"
            if not base_path.exists():
                try:
                    base_path.mkdir()
                except Exception as e:
                    print("Failed to create Pyquick folder: {0}".format(e))
                    base_path = Path("/Users/Shared")

        self.log_filepath = Path(f"{base_path}/{self.log_filename}").expanduser()
        self.constants.log_filepath = self.log_filepath

    def _initialize_logging_path_windows(self) -> None:
        """
        Initialize logging framework storage path for Windows.
        Logs are stored in ~/.macboxtool/logs/
        """
        # Use ~/.macboxtool/logs/ for Windows
        base_path = Path("~/.macboxtool").expanduser()

        if not base_path.exists():
            try:
                base_path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                print("Failed to create .macboxtool folder: {0}".format(e))
                # Fallback to temp directory
                import tempfile
                base_path = Path(tempfile.gettempdir()) / "MacBoxTool"
                try:
                    base_path.mkdir(parents=True, exist_ok=True)
                except Exception:
                    base_path = Path(tempfile.gettempdir())

        # Create logs subdirectory
        logs_path = base_path / "logs"
        if not logs_path.exists():
            try:
                logs_path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                print("Failed to create logs folder: {0}".format(e))
                logs_path = base_path

        self.log_filepath = logs_path / self.log_filename
        self.constants.log_filepath = self.log_filepath
    

    def _clean_prior_version_logs(self) -> None:
        """
        Clean logs from old Patcher versions

        Keep 10 latest logs
        """
        if sys.platform == "win32":
            # Windows: only clean from ~/.macboxtool/logs/
            paths = [self.log_filepath.parent]
        else:
            # macOS: clean from Pyquick and old location
            paths = [
                self.log_filepath.parent,        # ~/Library/Logs/Pyquick
                self.log_filepath.parent.parent, # ~/Library/Logs (old location)
            ]

        logs = []

        for path in paths:
            if not path.exists():
                continue
            for file in path.glob("MacBoxTool*"):
                if not file.is_file():
                    continue

                if not file.name.endswith(".log"):
                    continue

                if file.name == self.log_filename:
                    continue

                logs.append(file)

        logs.sort(key=lambda x: x.stat().st_mtime, reverse=True)

        for log in logs[9:]:
            try:
                log.unlink()
            except Exception as e:
                logging.error("Failed to delete log file: {0}".format(e))

    def _initialize_logging_configuration(self, log_to_file: bool = True) -> None:
        """
        Initialize logging framework configuration

        StreamHandler's format is used to mimic the default behavior of print()
        While FileHandler's format is for more in-depth logging

        Parameters:
            log_to_file (bool): Whether to log to file or not

        """

        logging.basicConfig(
            level=logging.NOTSET,
            format="[%(asctime)s] [%(filename)-32s] [%(lineno)-4d]: %(message)s",
            handlers=[
                logging.StreamHandler(stream = sys.stdout),
                logging.FileHandler(self.log_filepath, encoding="utf-8") if log_to_file is True else logging.NullHandler()
            ],
            force=True,
        )
        logging.getLogger().setLevel(logging.INFO)
        logging.getLogger().handlers[0].setFormatter(logging.Formatter("%(message)s"))
        if  len(logging.getLogger().handlers) > 1:
            logging.getLogger().handlers[1].maxBytes = self.max_file_size
        
    def _attempt_initialize_logging_configuration(self) -> None:
        """
        Attempt to initialize logging framework configuration

        If we fail to initialize the logging framework, we will disable logging to file
        """

        try:
            self._initialize_logging_configuration()
        except Exception as e:
            print("Failed to initialize logging framework: {0}".format(e))
            print("Retrying without logging to file...")
            self._initialize_logging_configuration(log_to_file=False)
    
    def _start_logging(self):
        """
        Start logging, used as easily identifiable start point in logs
        """

        str_msg = f"# MacBoxTool ({self.constants.macboxtool_version}) #"
        str_len = len(str_msg)

        logging.info('#' * str_len)
        logging.info(str_msg)
        logging.info('#' * str_len)

        logging.info("Log file set:")
        logging.info(f"  {self.log_filepath}")
        # Display relative path to avoid disclosing user's username
        try:
            path = self.log_filepath.relative_to(Path.home())
            logging.info(f"~/{path}")
        except ValueError:
            logging.info(self.log_filepath)

    def _implement_custom_traceback_handler(self) -> None:
        """
        Reroute traceback to logging module
        """

        def custom_excepthook_macos(type, value, tb) -> None:
            """
            Reroute traceback in main thread to logging module (macOS)
            """
            logging.error("Uncaught exception in main thread", exc_info=(type, value, tb))

            
            self._display_debug_properties()
            error_msg = "MacBoxTool encountered the following internal error:\n\n"
            error_msg += f"{type.__name__}: {value}"
            if tb:
                error_msg += f"\n\n{traceback.extract_tb(tb)[-1]}"

            error_msg += "\n\nReveal log file?"

            # Ask user if they want to send crash report
            try:
                result=applescript.AppleScript(f'display dialog "{error_msg}" with title "MacBoxTool ({self.constants.macboxtool_version})" buttons {{"Yes", "No"}} default button "Yes" with icon caution').run()
            except Exception as e:
                logging.error("Failed to display crash report dialog: {0}".format(e))
                return

            if result[applescript.AEType(b'bhit')] != "Yes":
                return

            subprocess.run(["/usr/bin/open", "--reveal", self.log_filepath])


        def custom_excepthook_win(type, value, tb) -> None:
            """
            Reroute traceback in main thread to logging module (Windows)
            """
            logging.error("Uncaught exception in main thread", exc_info=(type, value, tb))

            if self.constants.cli_mode is True:
                return
            self._display_debug_properties()
            from PySide2.QtWidgets import QApplication
            from ..UIkit.components.dialog_box import Dialog

            error_msg = "MacBoxTool encountered the following internal error:\n\n"
            error_msg += f"{type.__name__}: {value}"
            if tb:
                error_msg += f"\n\n{traceback.extract_tb(tb)[-1]}"

            error_msg += "\n\nReveal log file?"

            try:
                app = QApplication.instance()
                if app is None:
                    return

                # Get active window as parent, or use None
                parent = app.activeWindow()
                title = f"MacBoxTool ({self.constants.macboxtool_version})"
                message_box = Dialog(title, error_msg, parent)

                # Connect signals
                message_box.yesSignal.connect(lambda: self._reveal_log_file_windows())
                message_box.cancelSignal.connect(lambda: None)

                message_box.exec_()
            except Exception as e:
                logging.error("Failed to display crash report dialog: {0}".format(e))


        def custom_thread_excepthook(args) -> None:
                """
                Reroute traceback in spawned thread to logging module
                """
                logging.error("Uncaught exception in spawned thread", exc_info=(args))


        # Select platform-specific excepthook
        if sys.platform == "darwin":
            sys.excepthook = custom_excepthook_macos
        else:  # Windows
            sys.excepthook = custom_excepthook_win

        threading.excepthook = custom_thread_excepthook
    def _restore_original_excepthook(self) -> None:
        """
        Restore original traceback handlers
        """

        sys.excepthook = self.original_excepthook
        threading.excepthook = self.original_thread_excepthook

    def _reveal_log_file_windows(self) -> None:
        """
        Reveal log file in Windows Explorer
        """
        try:
            import subprocess
            subprocess.run(["explorer", "/select,", str(self.log_filepath)])
        except Exception as e:
            logging.error("Failed to reveal log file: {0}".format(e))

    def _display_debug_properties(self) -> None:
        """
        Display debug properties, primarily after main thread crash
        """
        logging.info("Host Properties:")
        logging.info(f"  XNU Version: {self.constants.detected_os}.{self.constants.detected_os_minor}")
        logging.info(f"  XNU Build: {self.constants.detected_os_build}")
        logging.info(f"  macOS Version: {self.constants.detected_os_version}")
        logging.info("Debug Properties:")
        logging.info(f"  Process ID: {os.getpid()}")
        logging.info("  Arguments passed to Patcher:")
        for arg in sys.argv:
            logging.info(f"    {arg}")

        logging.info(f"Host Properties:\n{pprint.pformat(self.constants.computer.__dict__, indent=4)}")

