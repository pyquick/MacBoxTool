from ..include import *
from .gui_support import DefGUI

from .gui_introduction import Introduction
from .gui_build import BuildOCPage
from .gui_about import AboutInterface

WINDOW_MIN_SIZE = (1000, 700)
WINDOW_DEFAULT_SIZE = (1200, 800)
class Widget(QFrame):

    def __init__(self, text: str, parent=None):
        super().__init__(parent=parent)
        self.label = SubtitleLabel(text, self)
        self.hBoxLayout = QHBoxLayout(self)
        
        setFont(self.label, 24)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hBoxLayout.addWidget(self.label, 1, Qt.AlignmentFlag.AlignCenter)

        
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
        self.gui_support=DefGUI(self.constants)
        logging.info("######################")
        logging.info("###gui_main_menu:OK###")
        logging.info("######################")
        setTheme(Theme.AUTO)
        self.themeListener= SystemThemeListener(self)
        self.themeListener.start()
        self._init_state()
        self._setup_window()
        self._init_ui()
       

   

    def _setup_window(self):
        self.setWindowTitle("MacBoxTool")
        self.setMinimumSize(*WINDOW_MIN_SIZE)
        
        #self._restore_window_geometry()

        font = QFont()
        system = platform.system()
        font_family = self.PLATFORM_FONTS.get(system, "Ubuntu")
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
        pass

    def closeEvent(self, event):
        self._save_window_geometry()
        self.themeListener.terminate()
        self.themeListener.deleteLater()
        super().closeEvent(event)

    def update_status(self, message, status_type="INFO"):
        if status_type == "success":
            InfoBar.success(
                title="Success",
                content=message,
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=3000,
                parent=self
            )
        elif status_type == "ERROR":
            InfoBar.error(
                title="ERROR",
                content=message,
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=5000,
                parent=self
            )
        elif status_type == "WARNING":
            InfoBar.warning(
                title="WARNING",
                content=message,
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=4000,
                parent=self
            )
        else:
            InfoBar.info(
                title="INFO",
                content=message,
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=3000,
                parent=self
            )
    def _init_ui(self):
        self.introduction=Introduction(self.constants,self.gui_support,self.settings,self)
        self.addSubInterface(
            self.introduction,
            FluentIcon.HOME,
            "Home",
            NavigationItemPosition.TOP
        )

        self.build=BuildOCPage(self.constants,self.gui_support,self.settings,self)
        self.addSubInterface(
            self.build,
            FluentIcon.DEVELOPER_TOOLS,
            "Build For Macs",
            NavigationItemPosition.SCROLL
        )

        self.about=AboutInterface(self.constants,self.gui_support,self.settings,self)
        self.addSubInterface(
            self.about,
            FluentIcon.INFO,
            "About",
            NavigationItemPosition.BOTTOM
        )
    
    def refresh(self):
        pass