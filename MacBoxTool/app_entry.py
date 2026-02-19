from .install import Install
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
if sys.platform=="darwin":
    from .detections import device_probe
else:
    from .detections import device_probe_win as device_probe



class MacBoxTool:
    def __init__(self)-> None:
        super().__init__()
        self.constants: Constants = Constants()
        self.computer= device_probe.Computer().probe()
        
        self.constants.computer = self.computer
        LoggingHandler(self.constants)
        ThemeManager(self.constants)
        self.settings=GlobalSettings(self.constants)
        self.opengui()
        

    def opengui(self):
        w = OpenGUI(self.constants,self.settings)
        w.gui_main_menu()

def main():
    MacBoxTool()