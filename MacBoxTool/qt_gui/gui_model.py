"""
gui_model.py: Model File
"""
from ..include import *
from .gui_support import DefGUI
class Model(ScrollArea):
    def __init__(self, global_constants:Constants,ui_support:DefGUI=None,global_settings:GlobalSettings=None,parent=None):
        super().__init__(parent)
        logging.info("######################")
        logging.info("#####gui_model:OK#####")
        logging.info("######################") 

        self.setObjectName("Model")

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

        self.init_ui()

    def init_ui(self):
        self.expandLayout.setContentsMargins(
            SPACING["xxlarge"], SPACING["xlarge"],
            SPACING["xxlarge"], SPACING["xlarge"]
        )
        self.expandLayout.setSpacing(SPACING["large"])
        ...

    def xx_card(self):
        return self.ui_support.custom_card(
            card_type="abc",
            title="xxxx",
            body=(
                "",
                "",
            )
        )
        