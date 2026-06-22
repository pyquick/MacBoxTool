"""
gui_introduction.py: Give introduction on GUI
"""
from ..include import *
from ..constants import Constants
from .gui_support import DefGUI
from PySide6.QtCore import QThread, Signal, QTimer
from ..support.on_nightly import CheckNightly

# Import install_helper only on macOS
import sys
if sys.platform == "darwin":
    try:
        from ..support.install_helper import check_helper_installed, install_privileged_helper, is_root
    except ImportError:
        check_helper_installed = None
        install_privileged_helper = None
        is_root = None
else:
    check_helper_installed = None
    install_privileged_helper = None
    is_root = None


class HelperInstallWorker(QThread):
    """Worker thread for installing privileged helper."""
    finished_signal = Signal(bool, str)  # success, message

    def __init__(self, parent=None):
        super().__init__(parent)

    def run(self):
        """Run the installation in background thread."""
        if install_privileged_helper:
            success, msg = install_privileged_helper(verbose=False)
            self.finished_signal.emit(success, msg)
        else:
            self.finished_signal.emit(False, "Helper installation not available on this platform")
        is_root = None

    check_helper_installed = None
    install_privileged_helper = None
    is_root = None




class Introduction(ScrollArea):

    # Navigation target constants
    NAV_BUILD = "build"
    NAV_SETTINGS = "settings"
    NAV_ABOUT = "about"
    NAV_DOWNLOADS="Downloads"

    def __init__(self,global_constants:Constants,ui_support:DefGUI=None,parent=None):
        super().__init__(parent=parent)
        self.setObjectName("Introduction")

        logging.info("init introduction")


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

        setTheme(Theme.AUTO)

        qconfig.themeChanged.connect(self.update_theme)

        self._init_ui()


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


    def _init_ui(self):
        self.expandLayout.setContentsMargins(SPACING["xxlarge"], SPACING["xlarge"], SPACING["xxlarge"], SPACING["xlarge"])
        self.expandLayout.setSpacing(SPACING["large"])

        self.expandLayout.addWidget(self._create_title_label())

        self.expandLayout.addWidget(self._create_hero_section())

        self.expandLayout.addWidget(self._create_note_card())

        self.expandLayout.addWidget(self._create_warning_card())

        if CheckNightly(self.global_constants).check():
            self.expandLayout.addWidget(self._create_nightly_warning_card())

        self.expandLayout.addWidget(self._create_guide_card())

        self.expandLayout.addStretch()

        # Defer helper check to after UI is shown (macOS only)
        if sys.platform == "darwin":
            QTimer.singleShot(100, self._check_and_show_helper_prompt)

    def _create_helper_install_button(self):
        """Create a small button for helper installation."""
        card = CardWidget()

        layout = QHBoxLayout(card)
        layout.setContentsMargins(SPACING["large"], SPACING["small"], SPACING["large"], SPACING["small"])
        layout.setSpacing(SPACING["medium"])

        # Check if already installed
        helper_installed = False
        if check_helper_installed:
            helper_installed = check_helper_installed()

        if helper_installed:
            icon = self.ui_support.build_icon_label(FluentIcon.ACCEPT, COLORS["success"], size=20)
            status = StrongBodyLabel("Privileged Helper is installed")
            status.setStyleSheet(f"color: {COLORS['success']}; font-size: 12px;")
            layout.addWidget(icon)
            layout.addWidget(status)
        else:
            icon = self.ui_support.build_icon_label(FluentIcon.INFO, COLORS["warning"], size=20)
            status = StrongBodyLabel("Privileged Helper is NOT installed - Some features may be limited")
            status.setStyleSheet(f"color: {COLORS['warning']}; font-size: 12px;")
            layout.addWidget(icon)
            layout.addWidget(status)

            install_btn = PrimaryPushButton("Install Helper")
            install_btn.clicked.connect(self._on_install_helper_clicked)
            layout.addWidget(install_btn)

        layout.addStretch()
        return card

    def _check_and_show_helper_prompt(self):
        """Check helper status and show installation prompt if needed (deferred after UI init)."""
        if not check_helper_installed:
            return

        if not check_helper_installed():
            self._show_helper_install_dialog()
            # Insert the button after warning card (index 4)
            button = self._create_helper_install_button()
            self.expandLayout.insertWidget(4, button)

    def cleanup_workers(self):
        """Stop helper installation worker before this page is destroyed."""
        worker = getattr(self, "_install_worker", None)
        if worker and worker.isRunning():
            worker.requestInterruption()
            if not worker.wait(5000):
                logging.warning("HelperInstallWorker did not stop in 5000ms; terminating")
                worker.terminate()
                worker.wait(1000)
        if worker:
            worker.deleteLater()
            self._install_worker = None

    def closeEvent(self, event):
        self.cleanup_workers()
        super().closeEvent(event)

    def _show_helper_install_dialog(self):
        """Show a dialog asking to install the helper if not already installed."""
        if not check_helper_installed:
            return

        # Check if helper is installed
        if not check_helper_installed():
            # Show dialog - if helper file doesn't exist, always prompt
            dialog = MessageBox(
                "Privileged Helper Required",
                "MacBoxTool requires a privileged helper tool to perform certain operations.\n\n"
                "The helper will be installed to /Library/PrivilegedHelperTools/ with root privileges.\n\n"
                "Would you like to install it now?",
                self
            )

            if dialog.exec():
                # User clicked OK
                self._on_install_helper_clicked()
            else:
                # User clicked Cancel - don't mark first run complete, will ask again next time
                pass

    def _on_install_helper_clicked(self):
        """Handle install helper button click - relaunch as root if needed."""
        if not install_privileged_helper or (is_root and not is_root()):
            # Need to get root privileges
            self._relaunch_as_root()
            return

        # Show installing indicator
        InfoBar.info(
            title="Installing",
            content="Installing Privileged Helper...",
            orient=Qt.Orientation.Horizontal,
            isClosable=False,
            position=InfoBarPosition.TOP_RIGHT,
            duration=0,  # Don't auto-close
            parent=self
        )

        # Run installation in background thread
        self._install_worker = HelperInstallWorker(self)
        self._install_worker.finished_signal.connect(self._on_install_helper_finished)
        self._install_worker.start()

    def _on_install_helper_finished(self, success: bool, msg: str):
        """Handle helper installation completion."""
        if success:
            # Show success message
            InfoBar.success(
                title="Success",
                content="Privileged Helper installed successfully!",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=3000,
                parent=self
            )

            # Refresh to update the button
            self.update()
        else:
            InfoBar.error(
                title="Installation Failed",
                content=msg,
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=5000,
                parent=self
            )

    def _relaunch_as_root(self):
        """Relaunch the application with sudo using AppleScript."""
        import subprocess

        # Get the current script path
        script_path = sys.executable
        app_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        main_script = os.path.join(app_path, "MacBoxTool", "app_entry.py")

        # Build the AppleScript command
        script = f'''
        do shell script "echo 'Installing Privileged Helper...' && cd '{app_path}' && {script_path} -m MacBoxTool.support.install_helper" with administrator privileges
        '''

        try:
            # Run AppleScript to get admin privileges and install
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode == 0:
                # Success - show message
                InfoBar.success(
                    title="Installed",
                    content="Privileged Helper installed successfully!",
                    orient=Qt.Orientation.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP_RIGHT,
                    duration=3000,
                    parent=self
                )

                # Refresh UI
                self.update()
            else:
                # User cancelled or error
                error_msg = result.stderr or "Installation was cancelled or failed."
                InfoBar.warning(
                    title="Installation",
                    content=error_msg,
                    orient=Qt.Orientation.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP_RIGHT,
                    duration=5000,
                    parent=self
                )

        except subprocess.TimeoutExpired:
            InfoBar.error(
                title="Timeout",
                content="Installation timed out.",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=5000,
                parent=self
            )
        except Exception as e:
            InfoBar.error(
                title="Error",
                content=f"Failed to install: {str(e)}",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=5000,
                parent=self
            )

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
            "A specialized tool that can work like OCLP.<br>"
            "Now it only support old Macs."
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

    def find_oclp_version(self):
        REPO_LATEST_RELEASE_URL: str = "https://api.github.com/repos/hackdoc/OCLP-R/releases/latest"
        if not NetworkUtilities().verify_network_connection(REPO_LATEST_RELEASE_URL,1):
            return None
        response = NetworkUtilities().get(REPO_LATEST_RELEASE_URL)
        data_set = response.json()
        if "tag_name" not in data_set:
            return None
        try:
            latest_remote_version = version.parse(data_set["tag_name"])
            return latest_remote_version
        except version.InvalidVersion:
            return None
    def _create_note_card(self):
        self.oclp_version=self.find_oclp_version() or "3.1.4"
        return self.ui_support.custom_card(
            card_type="note",
            title="OCLP-R: - Now Supports macOS Tahoe 26!",
            body=(
                f"The long awaited version {self.oclp_version} of OCLP-R is here, bringing <b>initial support for macOS Tahoe 26</b> to the community!<br><br>"
                "<b>Please Note:</b><br>"
                f"- Only OCLP-R {self.oclp_version} from the <a href=\"https://github.com/pyquick/MacBoxTool/releases/download/{self.oclp_version}/OCLP-R.pkg\" style=\"color: #0078D4; text-decoration: none;\">pyquick/OCLP-R</a> repository provides support for macOS Tahoe 26 with early patches.<br>"
                "- Official Dortania releases or older patches <b>will NOT work</b> with macOS Tahoe 26."
            )
        )
    def _create_nightly_warning_card(self):
        
        return self.ui_support.custom_card(
            card_type="warning",
            title="For Nightly Users",
            body=CheckNightly(self.global_constants).warning()
        )

    def _create_warning_card(self):
        return self.ui_support.custom_card(
            card_type="warning",
            title="This tool now only support old Macs. Hackintosh will be supported on MacBoxTool 0.2.0",
            body=(
                "Its use is not recommended due to its current instability. "
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
            icon=FluentIcon.DOWNLOAD,
            title="2. Downloads",
            description="Download macOS, KDKs, metallibs",
            button_text="Go to Download",
            navigate_target=self.NAV_DOWNLOADS
        ))

        layout.addWidget(self._create_guide_item(
            icon=FluentIcon.SETTING,
            title="3. Configure Settings",
            description="Adjust build settings like SMBIOS spoofing level, GPU options, and more.",
            button_text="Go to Settings",
            navigate_target=self.NAV_SETTINGS
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