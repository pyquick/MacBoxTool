"""
gui_os_update.py: GUI popup notifying the user of a detected macOS system update
"""

import sys
import logging

from pathlib import Path

from PySide2.QtWidgets import QApplication, QMessageBox
from PySide2.QtGui import QIcon

from ..constants import Constants


def show_os_update_popup(os_version: str = None, os_build: str = None) -> None:
    """
    Display a popup notifying the user that a macOS system update was detected
    and the required KDK/MetallibSupportPkg will be downloaded in the background.
    """

    app = QApplication.instance() or QApplication(sys.argv)

    if os_version and os_build:
        detected = f"MacBoxTool has detected that a macOS system update is being downloaded:\n{os_version} ({os_build})"
    else:
        detected = "MacBoxTool has detected that a macOS system update is being downloaded."

    body = (
        f"{detected}\n\n"
        "The patcher needs to prepare the system for the update, and will download any additional resources "
        "(Kernel Debug Kit, MetallibSupportPkg) it may need post-update.\n\n"
        "This may take a few minutes, the patcher will exit when it is done."
    )

    try:
        icon_path = Path(Constants().app_icon_path)
        if icon_path.exists():
            app.setWindowIcon(QIcon(str(icon_path)))
    except Exception as e:
        logging.warning(f"Failed to load app icon: {e}")

    QMessageBox.information(None, "macOS Update Detected", body)
