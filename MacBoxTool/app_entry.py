from .qt_gui.gui_go_in import OpenGUI
from .constants import Constants
import sys
from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *
import sys

constants:Constants=Constants()
def main():
    w = OpenGUI(constants)
    w.gui_main_menu()
