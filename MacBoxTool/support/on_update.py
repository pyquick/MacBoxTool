import subprocess
import logging
import sys
from PySide6.QtCore import *
from PySide6.QtWidgets import *
from PySide6.QtGui import *
from ..UIkit import *
from ..UIkit import FluentIcon as FIF
from ..UIWindow.utils import *
from ..support.colors import *
from ..constants import Constants

class UpdateAction:
    def __init__(self,global_constants:Constants,url:str):
        self.constants:Constants=global_constants
        self.url=url
        self.pkg_download_path=self.constants.payload_path / "OCLP-R.pkg"

    def _extract_update(self) -> None:
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
        
