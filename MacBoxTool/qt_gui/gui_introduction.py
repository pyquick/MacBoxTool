"""
gui_introduction.py: Give introduction on GUI
"""
from ..UIkit import *
from ..UIkit import FluentIcon as FIF
from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *
from ..constants import Constants

class Introduction(ScrollArea):
    def __init__(self,global_constants:Constants,parent=None):
        super.__init__()
        self.setObjectName("Introduction")
        self.setWidgetResizable(True)
        self.parent = parent
        self.global_constants = global_constants
        self.scrollWidget = QWidget()
        self.expandLayout = QVBoxLayout(self.scrollWidget)
    def _init_ui(self):
        ...
    def show_welcome(self):
