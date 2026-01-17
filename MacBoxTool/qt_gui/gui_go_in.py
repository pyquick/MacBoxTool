"""
gui_go_in.py: Go to Gui
"""


from ..UIkit import *
from ..UIkit import FluentIcon as FIF
from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *
import sys
from ..constants import Constants

class OpenGUI:
    def __init__(self,global_constants:Constants):
        self.constants:Constants = global_constants
    def gui_main_menu(self):
        from .gui_main_menu import Window
        app = QApplication(sys.argv)
        w = Window(self.constants)
        w.show()
        app.exec()