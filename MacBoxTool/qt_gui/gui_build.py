from ..include import *
from ..constants import Constants
from .gui_support import DefGUI

class BuildOCPage(ScrollArea):

    def __init__(self,  global_constants:Constants,parent=None,ui_support:DefGUI=None):
        super().__init__()
        self.setObjectName("Build_For_Mac")
        self.constants=global_constants
        self.gui_support=ui_support
