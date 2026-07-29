from ..include import *
from .gui_support import DefGUI

from .gui_introduction import Introduction
from .gui_build import BuildOCPage

from .gui_about import AboutInterface
from .gui_settings import SettingsInterface
from .gui_task import TaskInterface, TaskManager
from .gui_all_download import DownloadInterface
from ..support import on_nightly

WINDOW_MIN_SIZE = (1000, 700)
WINDOW_DEFAULT_SIZE = (1200, 800)
class Widget(QFrame):

    def __init__(self, text: str, parent=None):
        super().__init__(parent=parent)
        self.label = SubtitleLabel(text, self)
        self.hBoxLayout = AdaptiveFlowLayout(self)
        
        setFont(self.label, 24)
        self.label.setAlignment(Qt.AlignCenter)
        self.hBoxLayout.addWidget(self.label, 1, Qt.AlignCenter)

        
        self.setObjectName(text.replace(' ', '-'))


class Window(FluentWindow):
    
    PLATFORM_FONTS = {
        "Windows": "Segoe UI",
        "Darwin": "SF Pro Display",
        "Linux": "Ubuntu"
    }
    def __init__(self,global_constants:Constants,global_settings:GlobalSettings,parent=None):
        super().__init__(parent=parent)
        self.constants = global_constants
        self.settings=global_settings
        

        logging.info("init gui")

        self.themeListener= SystemThemeListener(self)
        self.themeListener.start()
        self.theme_manager=ThemeManager(self.constants)
        self.theme_manager.start()
        self.gui_support=DefGUI(self.constants)
        self._init_state()
        self._setup_window()
        setTheme(Theme.AUTO)
        self._init_ui()
        
        
        qconfig.themeChanged.connect(self.update_theme)

    def update_theme(self):
        self.update()

   

    def _setup_window(self):
        nightly_suffix = " (Nightly)" if on_nightly.CheckNightly(self.constants).check() else ""
        self.setWindowTitle(f"MacBoxTool ({self.constants.macboxtool_version}){nightly_suffix}")
        self.setMinimumSize(*WINDOW_MIN_SIZE)
        
        #self._restore_window_geometry()

        font = QFont()
        system = platform.system()
        font_family = self.PLATFORM_FONTS.get(system, "Ubuntu")
        logging.info(f"Using font: {font_family}")
        font.setFamily(font_family)
        font.setStyleHint(QFont.SansSerif)
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

    def _stop_child_workers(self):
        for page in (
            getattr(self, "introduction", None),
            getattr(self, "build", None),
            getattr(self, "task_page", None),
            getattr(self, "sys_patch_page", None),
            getattr(self, "download_page", None),
            getattr(self, "updater", None),
        ):
            cleanup = getattr(page, "cleanup_workers", None)
            if callable(cleanup):
                try:
                    cleanup()
                except Exception:
                    logging.exception(f"Failed to clean up {page.__class__.__name__} workers")

        TaskManager.shutdown_all()

    def _perform_shutdown_cleanup(self):
        if self._shutdown_cleanup_done:
            return

        self._shutdown_cleanup_done = True
        utilities.enable_sleep_after_running()
        logging.info("Clean-up")
        self._stop_child_workers()
        
        utilities.enable_sleep_after_running()
        self.theme_manager.stop()
        self.themeListener.requestInterruption()
        if not self.themeListener.wait(3000):
            logging.warning("SystemThemeListener did not stop in 3000ms; terminating")
            self.themeListener.terminate()
            self.themeListener.wait()
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

        # Hide the window before potentially blocking while workers finish.
        event.accept()
        self.hide()
        QApplication.processEvents()
        self._perform_shutdown_cleanup()

    def update_status(self, message, status_type="INFO"):
        if status_type == "success":
            InfoBar.success(
                title="Success",
                content=message,
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM_RIGHT,
                duration=3000,
                parent=self
            )
        elif status_type == "ERROR":
            InfoBar.error(
                title="ERROR",
                content=message,
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM_RIGHT,
                duration=5000,
                parent=self
            )
        elif status_type == "WARNING":
            InfoBar.warning(
                title="WARNING",
                content=message,
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM_RIGHT,
                duration=4000,
                parent=self
            )
        else:
            InfoBar.info(
                title="INFO",
                content=message,
                orient=Qt.Horizontal,
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

            if sys.platform == "darwin":
                from .gui_sys_patch import SysPatch
                self.sys_patch_page = SysPatch(self.constants, self.gui_support, self.settings, self)
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

            self.settings_page=SettingsInterface(self.constants,self.gui_support,self.settings,self)
            self.settings_nav_item = self.addSubInterface(
                self.settings_page,
                FluentIcon.SETTING,
                "Settings",
                NavigationItemPosition.BOTTOM
            )
            self.settings_nav_item.clicked.connect(lambda *_: self._rotate_settings_icon())

            if sys.platform == "darwin":
                from .gui_update import Updater
                self.updater = Updater(self.constants, self.gui_support, self.settings, self)
                self.addSubInterface(
                    self.updater,
                    FluentIcon.DOWNLOAD,
                    "Updater",
                    NavigationItemPosition.BOTTOM
                )

            self.about=AboutInterface(self.constants,self.gui_support,self.settings,self)
            self.addSubInterface(
                self.about,
                FluentIcon.INFO,
                "About",
                NavigationItemPosition.BOTTOM
            )
        finally:
            self.endAddSubInterfaceBatch()

        self.stackedWidget.currentChanged.connect(self._on_page_changed)
        QTimer.singleShot(0, self._apply_startup_navigation)

    def _rotate_settings_icon(self):
        item = getattr(self, "settings_nav_item", None)
        icon_widget = getattr(item, "itemWidget", item)
        rotate = getattr(icon_widget, "rotateIcon", None)
        if callable(rotate):
            rotate()

    def _apply_startup_navigation(self):
        if getattr(self.constants, "start_build_install", False):
            self.stackedWidget.setCurrentWidget(self.build)
            return
        if getattr(self.constants, "start_updater", False):
            updater = getattr(self, "updater", None)
            if updater is not None:
                self.stackedWidget.setCurrentWidget(updater)
            return
        if getattr(self.constants, "start_sys_patch", False):
            sys_patch_page = getattr(self, "sys_patch_page", None)
            if sys_patch_page is not None:
                self.stackedWidget.setCurrentWidget(sys_patch_page)
                if getattr(self.constants, "start_sys_patch_now", False):
                    QTimer.singleShot(0, sys_patch_page.start_root_patching)
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

    def _on_page_changed(self, index):
        widget = self.stackedWidget.widget(index)
        if hasattr(widget, 'refresh'):
            widget.refresh()