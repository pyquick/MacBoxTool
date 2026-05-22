"""
gui_go_in.py: Go to Gui
"""


from ..include import *

class OpenGUI:
    def __init__(self,global_constants:Constants,global_settings:GlobalSettings):
        self.constants:Constants = global_constants
        self.settings=global_settings
        logging.info("Init GuiBase")

    def gui_main_menu(self):
        import sys as _sys
        from .. import app_entry as _app_entry
        from .gui_main_menu import Window

        app = QApplication(_sys.argv)
        w = Window(self.constants,self.settings)

        # Save references globally for signal handler access
        _app_entry._qt_app = app
        _app_entry._qt_window = w

        w.show()
        app.exec()