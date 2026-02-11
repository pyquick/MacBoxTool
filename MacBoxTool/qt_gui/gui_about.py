"""
gui_about.py: Show about UI
"""

from ..include import *
from .gui_support import DefGUI

class AboutInterface(ScrollArea):

    def __init__(self, global_constants:Constants,ui_support:DefGUI=None,global_settings:GlobalSettings=None,parent=None):
        super().__init__(parent)

        logging.info("######################")
        logging.info("#####gui_about:OK#####")
        logging.info("######################") 

        # SetObject
        self.setObjectName("About")
        # Add constants
        self.constants=global_constants
        self.gui_support=ui_support
        self.settings=global_settings
        #Add QWidgets
        self.scrollWidget = QWidget()
        self.expandLayout = QVBoxLayout(self.scrollWidget)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # Interface
        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)
        self.enableTransparentBackground()

        #self.settings.add_key("MODEL","N/A")

        self.init_ui()

    def init_ui(self):
        ...

    