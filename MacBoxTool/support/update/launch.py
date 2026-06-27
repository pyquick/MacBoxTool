"""
launch.py: Launch the updated MacBoxTool app and close the old process.
"""
import logging
import os
import subprocess
import sys
import threading
from pathlib import Path


class LaunchUpdate:
    """Launch the updated app bundle and terminate the current process shortly after."""

    def __init__(self, delay_seconds: int = 5):
        """Store the delay before terminating the old process."""
        self.delay_seconds = delay_seconds

    def launch_update(self) -> bool:
        """Open the updated application bundle, then schedule old-process exit."""
        launch_target = self._resolve_launch_target()
        if not launch_target:
            logging.warning("[Update] Unable to resolve launch target")
            return False

        logging.info(f"[Update] Launching updated application: {launch_target}")
        subprocess.Popen(["/usr/bin/open", launch_target])
        threading.Timer(self.delay_seconds, self._exit_old_process).start()
        return True

    def _resolve_launch_target(self) -> str:
        """Prefer the installed app bundle over the current Python executable."""
        installed_app = Path("/Applications/MacBoxTool.app")
        if installed_app.exists():
            return str(installed_app)

        executable = os.path.realpath(sys.executable)
        marker = ".app/Contents/MacOS/"
        if marker in executable:
            return executable.split(marker)[0] + ".app"
        return ""

    def _exit_old_process(self) -> None:
        """Terminate the previous running process."""
        logging.info("[Update] Closing old process")
        os._exit(0)
