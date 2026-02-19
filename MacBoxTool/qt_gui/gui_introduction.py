"""
gui_introduction.py: Give introduction on GUI
"""
from ..include import *
from ..constants import Constants
from .gui_support import DefGUI

class Introduction(ScrollArea):
    def __init__(self,global_constants:Constants,ui_support:DefGUI=None,global_settings:GlobalSettings=None,parent=None):
        super().__init__(parent=parent)
        self.setObjectName("Introduction")

        logging.info("#############################")
        logging.info("#####gui_introduction:OK#####")
        logging.info("#############################") 

        self.global_constants = global_constants
        
        self.scrollWidget = QWidget()
        self.expandLayout = QVBoxLayout(self.scrollWidget)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)
        self.enableTransparentBackground()
        self.scrollWidget.setStyleSheet("QWidget { background: transparent; }")
        self.ui_support=ui_support
        
        self._init_ui()

        qconfig.themeChanged.connect(self.update_theme)
        setTheme(Theme.AUTO)

    def update_theme(self):
        setTheme(Theme.AUTO)
        self.update()
        
       
    def closeEvent(self, event):
        self.themeListener.terminate()
        self.themeListener.deleteLater()
        super().closeEvent(event)

    def _init_ui(self):
        self.expandLayout.setContentsMargins(SPACING["xxlarge"], SPACING["xlarge"], SPACING["xxlarge"], SPACING["xlarge"])
        self.expandLayout.setSpacing(SPACING["large"])

        self.expandLayout.addWidget(self._create_title_label())
        
        self.expandLayout.addWidget(self._create_hero_section())
        
        self.expandLayout.addWidget(self._create_note_card())
        
        self.expandLayout.addWidget(self._create_warning_card())
        
        #self.expandLayout.addWidget(self._create_guide_card())

        self.expandLayout.addStretch()
    def _create_hero_section(self):
        hero_card = CardWidget()
        
        hero_layout = QHBoxLayout(hero_card)
        hero_layout.setContentsMargins(SPACING["large"], SPACING["large"], SPACING["large"], SPACING["large"])
        hero_layout.setSpacing(SPACING["large"])

        hero_text = QVBoxLayout()
        hero_text.setSpacing(SPACING["medium"])

        hero_title = QLabel("Introduction")
        hero_title.setStyleSheet("font-size: 18px; color: {};".format(COLORS["primary"]))
        hero_text.addWidget(hero_title)

        hero_body = BodyLabel(
            "A specialized tool that can generate your OpenCore EFI.<br>"
            "Designed to reduce manual effort while ensuring accuracy in your Hackintosh journey.<br>"
            "It both support old Macs."
        )
        hero_body.setWordWrap(True)
        hero_body.setStyleSheet("line-height: 1.6; font-size: 14px;")
        hero_text.addWidget(hero_body)

        hero_layout.addLayout(hero_text, 2)

        robot_icon = self.ui_support.build_icon_label(FluentIcon.ROBOT, COLORS["primary"], size=64)
        hero_layout.addWidget(robot_icon, 1, Qt.AlignmentFlag.AlignVCenter)

        return hero_card
    def _create_title_label(self):
        title_label = SubtitleLabel("Welcome to MacBoxTool")
        title_label.setStyleSheet("font-size: 24px; font-weight: bold;")
        return title_label
    def _create_note_card(self):
        return self.ui_support.custom_card(
            card_type="note",
            title="OCLP-R: - Now Supports macOS Tahoe 26!",
            body=(
                "The long awaited version 3.0.1 of OCLP-R is here, bringing <b>initial support for macOS Tahoe 26</b> to the community!<br><br>"
                "<b>Please Note:</b><br>"
                "- Only OCLP-R 3.0.2 from the <a href=\"https://github.com/hackdoc/OCLP-R/releases/download/3.0.2/OCLP-R.pkg\" style=\"color: #0078D4; text-decoration: none;\">hackdoc/OCLP-R</a> repository provides support for macOS Tahoe 26 with early patches.<br>"
                "- Official Dortania releases or older patches <b>will NOT work</b> with macOS Tahoe 26."
            )
        )
    def _create_warning_card(self):
        return self.ui_support.custom_card(
            card_type="warning",
            title="This tool both support old Macs and Hackintoshes.",
            body=(
                "Even though this device supports older Macs and Hackintosh, "
                "its use is not recommended due to its current instability. "
                "Before using Hackintosh, please be sure to read Dortania's guide."
            )
        )
    def refresh(self):
        ...
