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
        
        self.expandLayout.setContentsMargins(
            SPACING["xxlarge"], SPACING["xlarge"],
            SPACING["xxlarge"], SPACING["xlarge"]
        )
        self.expandLayout.setSpacing(SPACING["large"])

        self.expandLayout.addWidget(self.show_about_label())
        self.expandLayout.addWidget(self.show_your_model())
        self.expandLayout.addWidget(self.show_your_board_id())
        self.expandLayout.addSpacing(26)

        self.expandLayout.addWidget(self.gro())
        self.expandLayout.addWidget(self.gengrate_settings_card())
        self.expandLayout.addWidget(self.show_pspkg_card())
        self.expandLayout.addWidget(self.show_launcher_card())

        self.expandLayout.addStretch()

    def gengrate_settings_card(self):
        version_card=SettingCard(
            FIF.APPLICATION,
            "MacBoxTool",
            f"Version {self.constants.mactoolbox_version}",
            self
        )
        return version_card
    
    def show_about_label(self):
        self.label="About MacBoxTool"
        title_label = SubtitleLabel(self.label)
        title_label.setStyleSheet("font-size: 24px; font-weight: bold;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return title_label
    
    def show_your_model(self):
        self.model= self.constants.computer.real_model
        model_label = BodyLabel("Model:"+" "+self.model)
        model_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return model_label
    
    def gro(self):
        self.model= self.constants.computer.real_model
        model_label = BodyLabel("Basic Information")
        model_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        return model_label

    def show_your_board_id(self):
        self.board_id= self.constants.computer.real_board_id
        board_label = BodyLabel("Board id:"+" "+self.board_id)
        board_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return board_label
    
    def show_pspkg_card(self):
        version_card=SettingCard(
            FIF.ZIP_FOLDER,
            "PatcherSupportPkg Version",
            f"Version {self.constants.patcher_support_pkg_version}",
            self
        )
        return version_card

    def show_launcher_card(self):
        path_card=SettingCard(
            FIF.PASTE,
            "Luancher Path",
            f"{self.constants.launcher_binary}",
            self
        )
        return path_card

    
    
    
    
    

    