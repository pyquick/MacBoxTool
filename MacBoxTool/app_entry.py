from .qt_gui.gui_go_in import OpenGUI
from .constants import Constants
import sys
from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *
from .support.logging_handler import LoggingHandler
from .support.toggle_theme import ThemeManager
import sys
from . import install
constants:Constants=Constants()

class MacBoxTool:
    def __init__(self)-> None:
        self.constants: Constants = Constants()
        LoggingHandler(self.constants)
        install.Install(self.constants)
        ThemeManager(self.constants)
        self.opengui()
        

    def opengui(self):
        w = OpenGUI(constants)
        w.gui_main_menu()

def main():
    MacBoxTool()