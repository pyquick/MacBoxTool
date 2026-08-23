"""
gui_all_download.py: Download interface with Pivot tabs
"""

from ..include import *
from .gui_support import DefGUI
from .gui_macos_installer import MacOSInstallerList
from .gui_kdk import KDKList
from .gui_metallib import MetallibList


class DownloadInterface(QWidget):
    """Download interface with Pivot tabs for different download categories"""

    def __init__(self, global_constants: Constants, ui_support: DefGUI = None, global_settings: GlobalSettings = None, parent=None):
        super().__init__(parent)
        self.setObjectName("Download")

        # Add constants
        self.constants = global_constants
        self.ui_support = ui_support
        self.settings = global_settings
        self._installers_loaded = False

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

        self.tab_kdk = None
        self.tab_metallib = None

        # Add tabs
        self._add_tab("installer", "macOS Installer", self.tab_installer)
        self._add_tab("kdk", "Kernel Debug Kit", None)
        self._add_tab("metallib", "Metallib", None)

        # Set default tab
        self.pivot.setCurrentItem("installer")

        # Add to layout (Pivot on top, content below)
        self.mainLayout.addWidget(self.pivot)
        self.mainLayout.addWidget(self.stack, 1)

    def _add_tab(self, key: str, label: str, widget: QWidget):
        """Add a tab to the pivot"""
        if widget:
            self.stack.addWidget(widget)
        self.pivot.addItem(
            routeKey=key,
            text=label,
            onClick=lambda checked, k=key: self._on_tab_clicked(k)
        )

    def _on_tab_clicked(self, key: str):
        """Handle tab click with lazy loading"""
        if key == "installer":
            self.fetch_installers()
        elif key == "kdk" and self.tab_kdk is None:
            self.tab_kdk = KDKList(self.constants, self.ui_support, self.settings, self)
            self.stack.addWidget(self.tab_kdk)
        elif key == "metallib" and self.tab_metallib is None:
            self.tab_metallib = MetallibList(self.constants, self.ui_support, self.settings, self)
            self.stack.addWidget(self.tab_metallib)

        widget = {"installer": self.tab_installer, "kdk": self.tab_kdk, "metallib": self.tab_metallib}.get(key)
        if widget:
            self.stack.setCurrentWidget(widget)

    def fetch_installers(self):
        """Fetch available installers from Apple catalog once on first use."""
        if self._installers_loaded:
            return
        self._installers_loaded = True
        self.tab_installer.load_installers()

    def refresh(self):
        """Load the default installer tab when the Downloads page is first shown."""
        self.fetch_installers()

    def cleanup_workers(self, deadline=None):
        """Stop workers owned by lazily-created download tabs."""
        for tab in (self.tab_installer, self.tab_kdk, self.tab_metallib):
            cleanup = getattr(tab, "cleanup_workers", None)
            if callable(cleanup):
                cleanup(deadline)

    def closeEvent(self, event):
        self.cleanup_workers()
        super().closeEvent(event)
