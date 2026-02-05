"""
gui_go_in.py: Go to Gui
"""


from ..include import *
class OpenGUI:
    def __init__(self,global_constants:Constants):
        self.constants:Constants = global_constants
        logging.info("Opening GUI...")
    def gui_main_menu(self):
        from .gui_main_menu import Window
        app = QApplication(sys.argv)
        w = Window(self.constants)
        w.show()
        app.exec()