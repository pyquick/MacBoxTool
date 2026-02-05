"""toggle_theme.py: A script to toggle between light and dark theme in macOS."""


from PySide6.QtCore import QObject,QTimer
from PySide6.QtWidgets import QWidget
from ..constants import Constants
import logging
from ..UIkit import setTheme, Theme , setThemeColor,SystemThemeListener
from ..UIWindow.utils import getSystemAccentColor

class ThemeManager(QObject):
    def __init__(self,global_constants:Constants=None):
        super().__init__()
        logging.info("######################")
        logging.info("###Theme Manager:OK###")
        logging.info("######################")
        setTheme(Theme.AUTO)
        setThemeColor(getSystemAccentColor(), save=False)
        self.constants = global_constants
        self.current_theme = "dark"
        self.last_accent_color = None
        self.running = True
        themeListener= SystemThemeListener(self)
        self.system_theme_thread = None
        self.app_theme_thread = None
        self.accent_color_thread = None
        self.last_color_hex = None

    def check_accent_color(self):
        """check accent color"""
        color = getSystemAccentColor()
        color_hex = color.name()
        if color_hex != self.last_color_hex:
            self.last_color_hex = color_hex
            color_dict = {
                "r": color.red(),
                "g": color.green(),
                "b": color.blue(),
                "a": color.alpha(),
                "hex": color_hex
            }
            self.on_color_change(color_dict)

    def on_color_change(self, color_dict):
        """apply color change"""
        setThemeColor(getSystemAccentColor(), save=False)
        print("Color changed:", color_dict)

    def start(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check_accent_color)
        self.timer.start(100)

    def stop(self):
        pass
    


