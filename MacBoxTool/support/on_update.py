import subprocess
import logging
import sys
import threading
from PySide6.QtCore import *
from PySide6.QtWidgets import *
from PySide6.QtGui import *
from ..UIkit import *
from ..UIkit import FluentIcon as FIF
from ..UIWindow.utils import *
from ..support.colors import *
from ..constants import Constants
from .platform_check import platfrom_check
from ..support import subprocess_wrapper



class UpdateAction:
    def __init__(self,global_constants:Constants,url:str):
        self.constants:Constants=global_constants
        self.url=url
        self.pkg_name=f"MacBoxTool-{platfrom_check()}.pkg"
        self.pkg_download_path=self.constants.payload_path / self.pkg_name

    def _extract_update(self) -> int:
        """
        Extracts the update

        Logic:
        - Distributed through GitHub Actions: Requires extraction
        - Distributed through GitHub Releases: No extraction required

        Only for Nightly Users
    
        """
        # GitHub Release
        if not self.url.endswith(".zip"):
            return
        logging.info("Extracting Nightly update...")
        if Path(self.pkg_download_path).exists():
            subprocess.run(["/bin/rm", "-rf", str(self.pkg_download_path)])
        result = subprocess.run(
            ["/usr/bin/ditto", "-xk", str(self.constants.payload_path / f"{self.pkg_name}.zip"), str(self.constants.payload_path)], capture_output=True
        )
        if result.returncode != 0:
            logging.error("Failed to extract update.")
            subprocess_wrapper.log(result)
