from ..include import *

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
    def __init__(self,global_constants:Constants):
        self.constants = global_constants
        super().__init__()
        
    def _setup_window(self):
        self.setWindowTitle("MacBoxTool")
        self.setMinimumSize(*WINDOW_MIN_SIZE)
        
        self._restore_window_geometry()

        font = QFont()
        system = platform.system()
        font_family = self.PLATFORM_FONTS.get(system, "Ubuntu")
        font.setFamily(font_family)
        font.setStyleHint(QFont.StyleHint.SansSerif)
        self.setFont(font)

    def _restore_window_geometry(self):
        saved_geometry = self.settings.get("window_geometry")
        
        if saved_geometry and isinstance(saved_geometry, dict):
            x = saved_geometry.get("x")
            y = saved_geometry.get("y")
            width = saved_geometry.get("width", WINDOW_DEFAULT_SIZE[0])
            height = saved_geometry.get("height", WINDOW_DEFAULT_SIZE[1])
            
            if x is not None and y is not None:
                screen = QApplication.primaryScreen()
                if screen:
                    screen_geometry = screen.availableGeometry()
                    if (screen_geometry.left() <= x <= screen_geometry.right() and
                        screen_geometry.top() <= y <= screen_geometry.bottom()):
                        self.setGeometry(x, y, width, height)
                        return
        
        self._center_window()

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
        self.settings.set("window_geometry", window_geometry)

    def _init_state(self):
        pass