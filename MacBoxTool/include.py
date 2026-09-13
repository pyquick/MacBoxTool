# GUI Include
from .UIkit import *
from .UIkit import FluentIcon as FIF
from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *
from .support.colors import *
from .UIWindow.utils import *
from PySide6.QtCore import QTimer,QObject
from .support.toggle_theme import ThemeManager

from .support import subprocess_wrapper
from .support.network_handler import *
try:
    from .support.crash_report import *
except Exception:
    # crash_report.py is a dev-only module; skip silently when unavailable
    pass
#constants
from .constants import *

#detect
if sys.platform=="darwin":
    from .detections import device_probe
from .detections import os_probe
if sys.platform=="win32":
    from .detections import device_probe_win as device_probe
#dataset
from .datasets import model_array,amfi_data,bluetooth_data,cpu_data,os_data,pci_data,sip_data,smbios_data,ssdt_data,usb_data

# Misc
import os
import sys
import json
import logging
import traceback
import subprocess
import platform
import webbrowser
import threading
import time
import datetime
import random
import requests
import re
import shutil
import psutil
import ctypes
import ctypes.wintypes
from typing import Optional, Tuple, TYPE_CHECKING
from pathlib import Path
import plistlib
from datetime import datetime
from .support.global_settings import GlobalSettings


def is_apple_silicon_runtime() -> bool:
    """
    Determine if the process is running on an Apple Silicon Mac.
    Returns True when running natively (arm64/arm64e) or under Rosetta 2 translation.
    """
    if platform.machine().lower().startswith("arm64"):
        return True
    if sys.platform != "darwin":
        return False
    try:
        result = subprocess.run(
            ["/usr/sbin/sysctl", "-n", "sysctl.proc_translated"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        if result.returncode != 0:
            return False
        return result.stdout.decode().strip() == "1"
    except Exception:
        return False