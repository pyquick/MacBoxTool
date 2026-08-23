from ..include import *
from .gui_support import DefGUI, AutoUpdateStages

from .gui_introduction import Introduction
from .gui_build import BuildOCPage

from .gui_about import AboutInterface
from .gui_settings import SettingsInterface
from .gui_hardware_support import HardwareSupport
from .gui_task import TaskInterface, TaskManager

from .gui_all_download import DownloadInterface

WINDOW_MIN_SIZE = (1000, 700)
WINDOW_DEFAULT_SIZE = (1200, 800)


def _xcode_version() -> int | None:
    """Return the Xcode major version, or None if not found."""
    import shutil
    if not shutil.which("xcodebuild"):
        return None
    try:
        import subprocess
        r = subprocess.run(
            ["xcodebuild", "-version"], capture_output=True, text=True, timeout=15
        )
        if r.returncode != 0:
            return None
        # "Xcode 26.6" -> 26
        for part in r.stdout.split():
            try:
                return int(float(part))
            except ValueError:
                continue
    except Exception:
        return None
    return None


class Widget(QFrame):

    def __init__(self, text: str, parent=None):
        super().__init__(parent=parent)
        self.label = SubtitleLabel(text, self)
        self.hBoxLayout = AdaptiveFlowLayout(self)
        
        setFont(self.label, 24)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hBoxLayout.addWidget(self.label, 1, Qt.AlignmentFlag.AlignCenter)

        
        self.setObjectName(text.replace(' ', '-'))


class Window(FluentWindow):
    
    PLATFORM_FONTS = {
        "Windows": "Segoe UI",
        "Darwin": ".AppleSystemUIFont",
        "Linux": "Ubuntu"
    }
    def __init__(self,global_constants:Constants,global_settings:GlobalSettings,parent=None):
        super().__init__(parent=parent)
        self.constants = global_constants
        self.settings=global_settings
        system = platform.system()
        font_family = self.PLATFORM_FONTS.get(system, "Ubuntu")
        qconfig.set(qconfig.fontFamilies, [font_family], save=False)


        logging.info("init gui")

        self.themeListener= SystemThemeListener(self)
        self.themeListener.start()
        self.theme_manager=ThemeManager(self.constants)
        self.theme_manager.start()
        self.gui_support=DefGUI(self.constants)
        self._init_state()
        self._setup_window()
        setTheme(Theme.AUTO, lazy=True)
        self._init_ui()

   

    def _setup_window(self):
        self.setMinimumSize(*WINDOW_MIN_SIZE)
        
        #self._restore_window_geometry()

        font = QFont()
        font_family = qconfig.get(qconfig.fontFamilies)[0]
        logging.info(f"Using font: {font_family}")
        font.setFamily(font_family)
        font.setStyleHint(QFont.StyleHint.SansSerif)
        self.setFont(font)

    
    
    def _center_window(self):
        screen = QApplication.primaryScreen()
        if screen:
            screen_geometry = screen.availableGeometry()
            window_width = WINDOW_DEFAULT_SIZE[0]
            window_height = WINDOW_DEFAULT_SIZE[1]
            
            x = screen_geometry.left() + (screen_geometry.width() - window_width) // 2
            y = screen_geometry.top() + (screen_geometry.height() - window_height) // 2
            
            self.setGeometry(x, y, window_width, window_height)
        else:
            self.resize(*WINDOW_DEFAULT_SIZE)

    def _save_window_geometry(self):
        geometry = self.geometry()
        window_geometry = {
            "x": geometry.x(),
            "y": geometry.y(),
            "width": geometry.width(),
            "height": geometry.height()
        }
        
        

    def _init_state(self):
        self._shutdown_in_progress = False
        self._shutdown_cleanup_done = False

    def _stop_child_workers(self, deadline=None):
        for page in (
            getattr(self, "introduction", None),
            getattr(self, "build", None),
            getattr(self, "task_page", None),
            getattr(self, "sys_patch_page", None),
            getattr(self, "download_page", None),
            getattr(self, "updater", None),
            getattr(self, "icon_converter", None),
        ):
            cleanup = getattr(page, "cleanup_workers", None)
            if callable(cleanup):
                cleanup(deadline)

        TaskManager.shutdown_all(deadline)

    def _perform_shutdown_cleanup(self):
        if self._shutdown_cleanup_done:
            return

        self._shutdown_cleanup_done = True
        utilities.enable_sleep_after_running()
        logging.info("Clean-up")
        # Shared deadline bounds the whole shutdown sequence to ~2s: the worker
        # grace phase and the theme listener stop both count against it.
        deadline = time.monotonic() + 0.1
        self._stop_child_workers(deadline)

        utilities.enable_sleep_after_running()
        self.theme_manager.stop()
        self.themeListener.requestInterruption()
        remaining_ms = int((deadline - time.monotonic()) * 1000.0)
        if remaining_ms <= 0 or not self.themeListener.wait(remaining_ms):
            self.themeListener.terminate()
            self.themeListener.wait(100)
        self.themeListener.deleteLater()

        app = QApplication.instance()
        
        if app:
            app.quit()

    def closeEvent(self, event):
        if self._shutdown_in_progress:
            event.accept()
            return

        self._shutdown_in_progress = True
        self._save_window_geometry()

        # Hide window immediately, then run cleanup synchronously.
        # QTimer.singleShot(0) is unreliable when Command+Q triggers
        # an application-level quit (threads get destroyed before the
        # timer fires). Sync cleanup ensures threads are stopped first.
        event.accept()
        self.hide()
        QApplication.processEvents()
        self._perform_shutdown_cleanup()

    def update_status(self, message, status_type="INFO"):
        if status_type == "success":
            InfoBar.success(
                title="Success",
                content=message,
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM_RIGHT,
                duration=3000,
                parent=self
            )
        elif status_type == "ERROR":
            InfoBar.error(
                title="ERROR",
                content=message,
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM_RIGHT,
                duration=5000,
                parent=self
            )
        elif status_type == "WARNING":
            InfoBar.warning(
                title="WARNING",
                content=message,
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM_RIGHT,
                duration=4000,
                parent=self
            )
        else:
            InfoBar.info(
                title="INFO",
                content=message,
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM_RIGHT,
                duration=3000,
                parent=self
            )
    def _init_ui(self):
        self.setResizeEnabled(True)
        self.setMinimumWidth(1200)
        self.beginAddSubInterfaceBatch()
        try:
            self.introduction=Introduction(self.constants,self.gui_support,self)
            self.introduction.set_navigation_callback(self._on_intro_navigate)

            self.addSubInterface(
                self.introduction,
                FluentIcon.HOME,
                "Home",
                NavigationItemPosition.SCROLL
            )

            self.build=BuildOCPage(self.constants,self.gui_support,self.settings,self)
            self.addSubInterface(
                self.build,
                FluentIcon.DEVELOPER_TOOLS,
                "Build For Macs",
                NavigationItemPosition.SCROLL
            )

            self.task_page=TaskInterface(self.constants,self.gui_support,self.settings,self)
            self.addSubInterface(
                self.task_page,
                FluentIcon.DOWNLOAD,
                "Download Tasks",
                NavigationItemPosition.SCROLL
            )
            if sys.platform=="darwin":
                from .gui_sys_patch import SysPatch
                self.sys_patch_page=SysPatch(self.constants,self.gui_support,self.settings,self)
                self.addSubInterface(
                    self.sys_patch_page,
                    FluentIcon.PASTE,
                    "Root Patching",
                    NavigationItemPosition.SCROLL
                )

            self.download_page=DownloadInterface(self.constants,self.gui_support,self.settings,self)
            self.addSubInterface(
                self.download_page,
                FluentIcon.SYNC,
                "Downloads",
                NavigationItemPosition.SCROLL
            )

            self.hardware_support = HardwareSupport(self.constants, self.gui_support, self)
            self.addSubInterface(
                self.hardware_support,
                FluentIcon.CERTIFICATE,
                "Hardware Support",
                NavigationItemPosition.SCROLL
            )

            _xcode_ver = _xcode_version()
            if _xcode_ver is not None and _xcode_ver >= 26:
                from .gui_converter import IconConverterInterface
                self.icon_converter=IconConverterInterface(self.constants,self.gui_support,self.settings,self)
                self.addSubInterface(
                    self.icon_converter,
                    FluentIcon.PHOTO,
                    "Icon Converter",
                    NavigationItemPosition.SCROLL
                )

            self.settings_page=SettingsInterface(self.constants,self.gui_support,self.settings,self)
            self.settings_nav_item = self.addSubInterface(
                self.settings_page,
                FluentIcon.SETTING,
                "Settings",
                NavigationItemPosition.BOTTOM
            )
            self.settings_nav_item.clicked.connect(lambda *_: self._rotate_settings_icon())
            if sys.platform=="darwin":
                from .gui_update import Updater
                self.updater=Updater(self.constants,self.gui_support,self.settings,self)
                self.addSubInterface(
                    self.updater,
                    FluentIcon.DOWNLOAD,
                    "Updater",
                    NavigationItemPosition.BOTTOM
                )

            self.about=AboutInterface(self.constants,self.gui_support,self.settings,self)
            channel_color = self.about.channel_color
            self.about_nav_item = self.addSubInterface(
                self.about,
                FluentIcon.INFO.colored(channel_color, channel_color),
                "About",
                NavigationItemPosition.BOTTOM
            )
            self.about_nav_item.setTextColor(channel_color, channel_color)
            self.about_nav_item.setIndicatorColor(channel_color, channel_color)
        finally:
            self.endAddSubInterfaceBatch()

        self.stackedWidget.currentChanged.connect(self._on_page_changed)
        QTimer.singleShot(0, self._apply_startup_navigation)
        QTimer.singleShot(0, self._preload_pages)

    def _rotate_settings_icon(self):
        item = getattr(self, "settings_nav_item", None)
        icon_widget = getattr(item, "itemWidget", item)
        rotate = getattr(icon_widget, "rotateIcon", None)
        if callable(rotate):
            rotate()

    def _apply_startup_navigation(self):
        if getattr(self.constants, "start_update_installed", False):
            self.constants.has_checked_updates = True
            reply = QMessageBox.question(
                self,
                "Update successful!",
                f"MacBoxTool has been updated to version {self.constants.macboxtool_version}.\n\nWould you like to update OpenCore and your root volume patches?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.constants.update_stage = AutoUpdateStages.CHECKING
                self.stackedWidget.setCurrentWidget(self.build)
                QTimer.singleShot(500, self.build._on_build)
            return
        if getattr(self.constants, "start_build_install", False):
            self.stackedWidget.setCurrentWidget(self.build)
            return
        if getattr(self.constants, "start_updater", False):
            self.stackedWidget.setCurrentWidget(self.updater)
            return
        if getattr(self.constants, "start_sys_patch", False):
            self.stackedWidget.setCurrentWidget(self.sys_patch_page)
            # SysPatch handles auto-patch via its own pending_auto_patch mechanism
            return

    def _on_intro_navigate(self, target: str):
        """Handle navigation from introduction page."""
        if target == Introduction.NAV_BUILD:
            self.stackedWidget.setCurrentWidget(self.build)
        elif target == Introduction.NAV_SETTINGS:
            self.stackedWidget.setCurrentWidget(self.settings_page)
        elif target == Introduction.NAV_ABOUT:
            self.stackedWidget.setCurrentWidget(self.about)
        elif target == Introduction.NAV_DOWNLOADS:
            self.stackedWidget.setCurrentWidget(self.download_page)
        elif target == Introduction.NAV_PATCH:
            sys_patch_page = getattr(self, "sys_patch_page", None)
            if sys_patch_page is not None:
                self.stackedWidget.setCurrentWidget(sys_patch_page)

    def navigate_to_sys_patch(self):
        """Navigate to SysPatch page. Called by BuildOCPage after install in update flow."""
        sys_patch_page = getattr(self, "sys_patch_page", None)
        if sys_patch_page is not None:
            self.stackedWidget.setCurrentWidget(sys_patch_page)

    def _on_page_changed(self, index):
        widget = self.stackedWidget.widget(index)
        if hasattr(widget, 'refresh'):
            widget.refresh()

    def _preload_pages(self):
        """Silently preload heavy pages after init gui, before user navigation."""
        for attr in ("hardware_support", "settings_page"):
            page = getattr(self, attr, None)
            if page is None:
                continue
            try:
                page.refresh()
            except Exception as e:
                logging.warning(f"Failed to preload {attr}: {e}")