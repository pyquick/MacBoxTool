"""
gui_introduction.py: Give introduction on GUI
"""
from ..include import *
from ..constants import Constants
from .gui_support import DefGUI


class Introduction(ScrollArea):

    # Navigation target constants
    NAV_BUILD = "build"
    NAV_SETTINGS = "settings"
    NAV_ABOUT = "about"

    def __init__(self,global_constants:Constants,ui_support:DefGUI=None,global_settings:GlobalSettings=None,parent=None):
        super().__init__(parent=parent)
        self.setObjectName("Introduction")

        logging.info("#############################")
        logging.info("#####gui_introduction:OK#####")
        logging.info("#############################")

        self.global_constants = global_constants
        self.navigation_callback = None  # For page navigation

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

    def set_navigation_callback(self, callback):
        """Set callback for page navigation."""
        self.navigation_callback = callback

    def navigate_to(self, target: str):
        """Navigate to target page."""
        if self.navigation_callback:
            self.navigation_callback(target)

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

        self.expandLayout.addWidget(self._create_guide_card())

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
            title="MacBoxTool: - Now Supports macOS Tahoe 26!",
            body=(
                "The long awaited version 3.0.1 of MacBoxTool is here, bringing <b>initial support for macOS Tahoe 26</b> to the community!<br><br>"
                "<b>Please Note:</b><br>"
                "- Only MacBoxTool 3.0.2 from the <a href=\"https://github.com/pyquick/MacBoxTool/releases/download/3.0.2/MacBoxTool.pkg\" style=\"color: #0078D4; text-decoration: none;\">pyquick/MacBoxTool</a> repository provides support for macOS Tahoe 26 with early patches.<br>"
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

    def _create_guide_card(self):
        """Create a guide card with navigation buttons to different pages."""
        card = CardWidget()

        layout = QVBoxLayout(card)
        layout.setContentsMargins(SPACING["large"], SPACING["large"], SPACING["large"], SPACING["large"])
        layout.setSpacing(SPACING["medium"])

        # Title
        title = StrongBodyLabel("Quick Start Guide")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        # Description
        desc = BodyLabel("Get started by following these steps:")
        desc.setStyleSheet("font-size: 14px; color: #888;")
        layout.addWidget(desc)

        # Guide items with buttons
        layout.addWidget(self._create_guide_item(
            icon=FluentIcon.DEVELOPER_TOOLS,
            title="1. Build OpenCore EFI",
            description="Generate OpenCore EFI for your Mac or Hackintosh. Select your target model and click Build.",
            button_text="Go to Build",
            navigate_target=self.NAV_BUILD
        ))

        layout.addWidget(self._create_guide_item(
            icon=FluentIcon.SETTING,
            title="2. Configure Settings",
            description="Adjust build settings like SMBIOS spoofing level, GPU options, and more.",
            button_text="Go to Settings",
            navigate_target=self.NAV_SETTINGS
        ))

        layout.addWidget(self._create_guide_item(
            icon=FluentIcon.INFO,
            title="3. Learn More",
            description="Read about this tool, check for updates, and view credits.",
            button_text="Go to About",
            navigate_target=self.NAV_ABOUT
        ))

        return card

    def _create_guide_item(self, icon, title, description, button_text, navigate_target):
        """Create a single guide item with navigation button."""
        item_widget = QWidget()
        item_layout = QHBoxLayout(item_widget)
        item_layout.setContentsMargins(0, SPACING["small"], 0, SPACING["small"])
        item_layout.setSpacing(SPACING["medium"])

        # Icon
        icon_label = self.ui_support.build_icon_label(icon, COLORS["primary"], size=32)
        item_layout.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignVCenter)

        # Text content
        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)

        title_label = BodyLabel(title)
        title_label.setStyleSheet("font-weight: bold; font-size: 14px;")

        desc_label = BodyLabel(description)
        desc_label.setStyleSheet("font-size: 12px; color: #888;")
        desc_label.setWordWrap(True)

        text_layout.addWidget(title_label)
        text_layout.addWidget(desc_label)
        item_layout.addLayout(text_layout, 1)

        # Navigate button
        nav_btn = PrimaryPushButton(button_text)
        nav_btn.setFixedHeight(32)
        nav_btn.clicked.connect(lambda: self.navigate_to(navigate_target))

        item_layout.addWidget(nav_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        return item_widget

    def refresh(self):
        ...