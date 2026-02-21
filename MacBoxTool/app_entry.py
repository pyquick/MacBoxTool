from .install import Install
import importlib
Install()



from .qt_gui.gui_go_in import OpenGUI
from .constants import Constants
import sys
from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *
from .support.logging_handler import LoggingHandler
from .support.toggle_theme import ThemeManager
import sys
from .support.global_settings import GlobalSettings
from .detections import device_probe




class MacBoxTool:
    def __init__(self)-> None:
        super().__init__()
        self.constants: Constants = Constants()
        self.computer= device_probe.Computer().probe()
        
        self.constants.computer = self.computer
        launcher_binary = sys.executable
        if "python" in launcher_binary:
            # We're running from source
            launcher_script =  __file__
            if "main.py" in launcher_script:
                launcher_script = launcher_script.replace("/resources/main.py", "/OCLP-R-GUI.command")
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
    MacBoxTool()