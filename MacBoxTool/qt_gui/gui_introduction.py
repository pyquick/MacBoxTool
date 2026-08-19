"""
gui_introduction.py: Give introduction on GUI
"""
from ..include import *
from ..constants import Constants
from .gui_support import DefGUI
from PySide2.QtCore import QThread, Signal, QTimer
from ..support.on_nightly import CheckNightly

# Import install_helper only on macOS
import sys
if sys.platform == "darwin":
    try:
        from ..support.install_helper import check_helper_installed, install_privileged_helper
    except ImportError:
        check_helper_installed = None
        install_privileged_helper = None
else:
    check_helper_installed = None
    install_privileged_helper = None


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


class OCLPVersionWorker(QThread):
    """Fetch the latest OCLP-R version without blocking the GUI thread."""

    version_found = Signal(object)

    def __init__(self, global_constants: Constants):
        super().__init__()
        self.constants = global_constants

    def run(self):
        version_value = Introduction.find_oclp_version_for(self.constants)
        if version_value is not None and not self.isInterruptionRequested():
            self.version_found.emit(version_value)


_active_oclp_version_workers = set()


class Introduction(ScrollArea):

    # Navigation target constants
    NAV_BUILD = "build"
    NAV_SETTINGS = "settings"
    NAV_ABOUT = "about"
    NAV_DOWNLOADS="Downloads"
    NAV_PATCH = "patch"

    def __init__(self,global_constants:Constants,ui_support:DefGUI=None,parent=None):
        super().__init__(parent=parent)
        self.setObjectName("Introduction")

        logging.info("init introduction")


        self.constants = global_constants
        self.navigation_callback = None  # For page navigation
        self._oclp_version_worker = None
        self._is_closing = False

        self.scrollWidget = QWidget()
        self.expandLayout = QVBoxLayout(self.scrollWidget)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)
        self.enableTransparentBackground()
        self.scrollWidget.setStyleSheet("QWidget { background: transparent; }")
        self.ui_support=ui_support

        self._init_ui()

    def _github_headers(self) -> dict:
        self.token = self.constants.github_token
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def set_navigation_callback(self, callback):
        """Set callback for page navigation."""
        self.navigation_callback = callback

    def navigate_to(self, target: str):
        """Navigate to target page."""
        if self.navigation_callback:
            self.navigation_callback(target)

    def _init_ui(self):
        self.expandLayout.setContentsMargins(SPACING["xxlarge"], SPACING["xlarge"], SPACING["xxlarge"], SPACING["xlarge"])
        self.expandLayout.setSpacing(SPACING["large"])

        self.expandLayout.addWidget(self._create_title_label())

        self.expandLayout.addWidget(self._create_hero_section())

        self.expandLayout.addWidget(self._create_note_card())
        QTimer.singleShot(0, self._fetch_oclp_version)

        self.expandLayout.addWidget(self._create_warning_card())

        if CheckNightly(self.constants).check():
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
        """Stop workers owned by this page before it is destroyed."""
        self._is_closing = True
        version_worker = self._oclp_version_worker
        if version_worker and version_worker.isRunning():
            version_worker.requestInterruption()
            if not version_worker.wait(2000):
                logging.info("OCLPVersionWorker is still finishing during shutdown")

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

            if dialog.exec_():
                # User clicked OK
                self._on_install_helper_clicked()
            else:
                # User clicked Cancel - don't mark first run complete, will ask again next time
                pass

    def _on_install_helper_clicked(self):
        """Handle install helper button click."""
        if not install_privileged_helper:
            self._on_install_helper_finished(
                False,
                "Helper installation not available on this platform",
            )
            return

        # Show installing indicator
        InfoBar.info(
            title="Installing",
            content="Installing Privileged Helper...",
            orient=Qt.Horizontal,
            isClosable=False,
            position=InfoBarPosition.BOTTOM_RIGHT,
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
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM_RIGHT,
                duration=3000,
                parent=self
            )

            # Refresh to update the button
            self.update()
        else:
            InfoBar.error(
                title="Installation Failed",
                content=msg,
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM_RIGHT,
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
        hero_layout.addWidget(robot_icon, 1, Qt.AlignVCenter)

        return hero_card

    def _create_title_label(self):
        title_label = SubtitleLabel("Welcome to MacBoxTool")
        title_label.setStyleSheet("font-size: 24px; font-weight: bold;")
        return title_label

    @staticmethod
    def find_oclp_version_for(global_constants: Constants):
        REPO_LATEST_RELEASE_URL: str = "https://api.github.com/repos/hackdoc/OCLP-R/releases/latest"
        network_utilities = NetworkUtilities(global_constants)
        if not network_utilities.verify_network_connection(REPO_LATEST_RELEASE_URL, 1):
            return None

        response = network_utilities.get(REPO_LATEST_RELEASE_URL, timeout=10)
        if not response or response.status_code != 200 or not response.content:
            logging.warning(f"[Introduction] Failed to fetch OCLP-R release: status={getattr(response, 'status_code', None)}")
            return None

        try:
            data_set = response.json()
        except Exception as e:
            logging.warning(f"[Introduction] Invalid OCLP-R release response: {e}")
            return None

        if "tag_name" not in data_set:
            return None
        try:
            latest_remote_version = version.parse(data_set["tag_name"])
            return latest_remote_version
        except version.InvalidVersion:
            return None

    def find_oclp_version(self):
        return self.find_oclp_version_for(self.constants)

    @staticmethod
    def _oclp_note_body(oclp_version):
        return (
            f"The long awaited version {oclp_version} of OCLP-R is here, bringing <b>initial support for macOS Tahoe 26</b> to the community!<br><br>"
            "<b>Please Note:</b><br>"
            f"- Only OCLP-R {oclp_version} from the <a href=\"https://github.com/hackdoc/OCLP-R/releases/download/{oclp_version}/OCLP-R.pkg\" style=\"color: #0078D4; text-decoration: none;\">pyquick/OCLP-R</a> repository provides support for macOS Tahoe 26 with early patches.<br>"
            "- Official Dortania releases or older patches <b>will NOT work</b> with macOS Tahoe 26."
        )

    def _create_note_card(self):
        self.oclp_version = "3.1.6"
        card = self.ui_support.custom_card(
            card_type="note",
            title="OCLP-R: - Now Supports macOS Tahoe 26!",
            body=self._oclp_note_body(self.oclp_version),
        )
        body_labels = [
            label for label in card.findChildren(BodyLabel)
            if not isinstance(label, StrongBodyLabel)
        ]
        self._oclp_note_body_label = body_labels[0] if body_labels else None
        return card

    def _fetch_oclp_version(self):
        if self._is_closing or self._oclp_version_worker is not None:
            return

        worker = OCLPVersionWorker(self.constants)
        self._oclp_version_worker = worker
        _active_oclp_version_workers.add(worker)
        worker.version_found.connect(self._update_oclp_note_card)
        worker.finished.connect(self._on_oclp_version_worker_finished)
        worker.finished.connect(lambda: _active_oclp_version_workers.discard(worker))
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _update_oclp_note_card(self, oclp_version):
        if self._is_closing or self._oclp_note_body_label is None:
            return
        self.oclp_version = oclp_version
        self._oclp_note_body_label.setText(self._oclp_note_body(oclp_version))

    def _on_oclp_version_worker_finished(self):
        if self.sender() is self._oclp_version_worker:
            self._oclp_version_worker = None

    def _create_nightly_warning_card(self):
        
        return self.ui_support.custom_card(
            card_type="warning",
            title="For Nightly Users",
            body=CheckNightly(self.constants).warning()
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
        desc = BodyLabel(
            "Follow these steps to create and use an OpenCore EFI. "
            "Back up your data and current EFI before making changes."
        )
        desc.setStyleSheet("font-size: 14px; color: #888;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        layout.addWidget(self._create_guide_item(
            icon=FluentIcon.SETTING,
            title="1. Configure your target model",
            description=(
                "Open Settings and choose the Mac model you want to build for. "
                "Review the available boot, graphics, security, and SMBIOS options "
                "before building."
            ),
            button_text="Go to Settings",
            navigate_target=self.NAV_SETTINGS
        ))

        layout.addWidget(self._create_guide_item(
            icon=FluentIcon.DOWNLOAD,
            title="2. Download required resources",
            description=(
                "Use Downloads to get a macOS installer, Kernel Debug Kit (KDK), "
                "or Metallib support packages when they are needed for your system."
            ),
            button_text="Go to Downloads",
            navigate_target=self.NAV_DOWNLOADS
        ))

        layout.addWidget(self._create_guide_item(
            icon=FluentIcon.DEVELOPER_TOOLS,
            title="3. Build the OpenCore EFI",
            description=(
                "Open Build For Macs and click Build OpenCore EFI. "
                "The build uses the target model and settings selected above."
            ),
            button_text="Go to Build",
            navigate_target=self.NAV_BUILD
        ))

        layout.addWidget(self._create_guide_item(
            icon=FluentIcon.SAVE,
            title="4. Install and test the EFI",
            description=(
                "After the build succeeds, use Open folder in Finder to inspect or copy "
                "the EFI, or use Install to disk to install it directly. Keep a backup "
                "of the working EFI and restart to test the new configuration."
            ),
            button_text="Go to Build",
            navigate_target=self.NAV_BUILD
        ))
        if sys.platform=="darwin":
            layout.addWidget(self._create_guide_item(
                icon=FluentIcon.PASTE,
                title="5. Apply Root Patches when needed",
                description=(
                    "On supported older Macs, use Root Patching after OpenCore is working. "
                    "The patcher can prepare required KDK and Metallib packages; restart "
                    "when prompted to apply the changes."
                ),
                button_text="Go to Root Patching",
                navigate_target=self.NAV_PATCH
            ))

        return card

    def _create_guide_item(self, icon, title, description, button_text=None, navigate_target=None):
        """Create a single guide item with an optional navigation button."""
        item_widget = QWidget()
        item_layout = QHBoxLayout(item_widget)
        item_layout.setContentsMargins(0, SPACING["small"], 0, SPACING["small"])
        item_layout.setSpacing(SPACING["medium"])

        # Icon
        icon_label = self.ui_support.build_icon_label(icon, COLORS["primary"], size=32)
        item_layout.addWidget(icon_label, 0, Qt.AlignVCenter)

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

        if button_text and navigate_target:
            nav_btn = PrimaryPushButton(button_text)
            nav_btn.setFixedHeight(32)
            nav_btn.clicked.connect(lambda: self.navigate_to(navigate_target))
            item_layout.addWidget(nav_btn, 0, Qt.AlignVCenter)

        return item_widget

    def refresh(self):
        ...