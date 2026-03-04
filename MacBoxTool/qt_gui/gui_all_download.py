"""
gui_all_download.py: Download interface with Pivot tabs
"""

from ..include import *
from .gui_support import DefGUI
from .gui_macos_installer import MacOSInstallerList


class DownloadInterface(QWidget):
    """Download interface with Pivot tabs for different download categories"""

    def __init__(self, global_constants: Constants, ui_support: DefGUI = None, global_settings: GlobalSettings = None, parent=None):
        super().__init__(parent)
        self.setObjectName("Download")

        # Add constants
        self.constants = global_constants
        self.ui_support = ui_support
        self.settings = global_settings

        # Initialize UI
        self.init_ui()

    def init_ui(self):
        """Initialize UI layout"""
        # Main layout - vertical (Pivot on top, content below)
        self.mainLayout = QVBoxLayout(self)
        self.mainLayout.setContentsMargins(SPACING["large"], SPACING["large"], SPACING["large"], SPACING["large"])
        self.mainLayout.setSpacing(SPACING["medium"])

        # Create Pivot (horizontal tab bar on top)
        self.pivot = Pivot(self)

        # Create tab content container
        self.stack = QStackedWidget(self)

        # Create tab content
        self.tab_installer = MacOSInstallerList(
            self.constants,
            self.ui_support,
            self.settings,
            self
        )

        # Add tabs
        self._add_tab("installer", "macOS Installer", self.tab_installer)

        # Set default tab
        self.pivot.setCurrentItem("installer")

        # Auto-load installers
        self.fetch_installers()

        # Add to layout (Pivot on top, content below)
        self.mainLayout.addWidget(self.pivot)
        self.mainLayout.addWidget(self.stack, 1)

    def _add_tab(self, key: str, label: str, widget: QWidget):
        """Add a tab to the pivot"""
        self.stack.addWidget(widget)
        self.pivot.addItem(
            routeKey=key,
            text=label,
            onClick=lambda checked, w=widget: self.stack.setCurrentWidget(w)
        )

    def fetch_installers(self):
        """Fetch available installers from Apple catalog"""
        self.tab_installer.load_installers()