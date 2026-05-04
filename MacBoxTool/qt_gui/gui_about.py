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

        #Gen
        self.expandLayout.addWidget(self.show_about_label())
        self.expandLayout.addWidget(self.show_your_model())
        self.expandLayout.addWidget(self.show_your_custom_model())
        self.expandLayout.addWidget(self.show_your_board_id())
        self.expandLayout.addSpacing(26)
        # App Information
        self.expandLayout.addWidget(self.app_information())
        

        self.expandLayout.addSpacing(13)
        self.expandLayout.addWidget(self.show_commit_information())
        self.expandLayout.addStretch()

  
    def show_about_label(self):
        self.label="About MacBoxTool"
        title_label = SubtitleLabel(self.label)
        title_label.setStyleSheet("font-size: 24px; font-weight: bold;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return title_label

    def show_custom_label(self):
        self.label="Custom Label"
        title_label = SubtitleLabel(self.label)
        title_label.setStyleSheet("font-size: 24px; font-weight: bold;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return title_label
    
    def show_your_model(self):
        self.model= self.constants.computer.real_model
        model_label = BodyLabel("Model:"+" "+self.model)
        model_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return model_label
    
    def show_your_custom_model(self):
        self.model= str(self.constants.custom_model)
        model_label = BodyLabel("Custom Model:"+" "+self.model)
        model_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return model_label

    def show_your_board_id(self):
        self.board_id= self.constants.computer.real_board_id
        board_label = BodyLabel("Board id:"+" "+self.board_id)
        board_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return board_label
    
    
    def app_information(self):
        widgets=QWidget()
        expandLayout = QVBoxLayout(widgets)
        self.model= self.constants.computer.real_model
        model_label = BodyLabel("Application Information")
        model_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        version_card=SettingCard(
            FIF.APPLICATION,
            "MacBoxTool",
            f"Version {self.constants.macboxtool_version}",
            self
        )
        pversion_card=SettingCard(
            FIF.ZIP_FOLDER,
            "PatcherSupportPkg Version",
            f"Version {self.constants.patcher_support_pkg_version}",
            self
        )
        path_card=SettingCard(
            FIF.PASTE,
            "Luancher Path",
            f"{self.constants.launcher_binary}",
            self
        )
        mount_card= SettingCard(
            FIF.PASTE,
            "Payload Mount",
            f"{self.constants.payload_path}"
        )
        expandLayout.addWidget(version_card)
        expandLayout.addWidget(pversion_card)
        expandLayout.addWidget(path_card)
        expandLayout.addWidget(mount_card)
        return widgets
    
    
    def show_commit_information(self):
        widgets=QWidget()
        expandLayout = QVBoxLayout(widgets)
        commit_label = BodyLabel("Commit Information")
        branch_card=SettingCard(
            FIF.BRUSH,
            "Branch",
            f"{self.constants.commit_info[0]}",
        )
        date_card=SettingCard(
            FIF.DATE_TIME,
            "Date",
            f"{self.constants.commit_info[1]}",
        )
        url_card=SettingCard(
            FIF.WIFI,
            "URL",
            f"{self.constants.commit_info[2]}",
        )
        expandLayout.addWidget(commit_label)
        expandLayout.addWidget(branch_card)
        expandLayout.addWidget(date_card)
        expandLayout.addWidget(url_card)
        return widgets




    
    
    
    
    

    