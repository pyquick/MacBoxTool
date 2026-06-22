"""toggle_theme.py: A script to toggle between light and dark theme in macOS."""


from PySide6.QtCore import QObject, QTimer, Signal
from ..constants import Constants
import logging
import sys
from ..UIkit import setThemeColor
from ..UIWindow.utils import getSystemAccentColor


class _MacAccentColorObserver(QObject):
    """Bridge macOS accent color notifications to Qt signals."""

    accentColorChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._centers = []
        self._observer = None

    def start(self) -> bool:
        if sys.platform != "darwin":
            return False

        try:
            import Cocoa
            import objc
        except Exception as e:
            logging.debug(f"Unable to import macOS notification APIs: {e}")
            return False

        signal = self.accentColorChanged

        class _Observer(Cocoa.NSObject):
            def init(self):
                self = objc.super(_Observer, self).init()
                return self

            def accentColorChanged_(self, _notification):
                signal.emit()

        try:
            self._observer = _Observer.alloc().init()
            centers_and_names = [
                (
                    Cocoa.NSNotificationCenter.defaultCenter(),
                    [
                        Cocoa.NSSystemColorsDidChangeNotification,
                        "AppleColorPreferencesChangedNotification",
                        "AppleAquaColorVariantChanged",
                        "AppleInterfaceThemeChangedNotification",
                    ],
                ),
                (
                    Cocoa.NSDistributedNotificationCenter.defaultCenter(),
                    [
                        "AppleColorPreferencesChangedNotification",
                        "AppleAquaColorVariantChanged",
                        "AppleInterfaceThemeChangedNotification",
                    ],
                ),
            ]

            for center, names in centers_and_names:
                for name in names:
                    center.addObserver_selector_name_object_(
                        self._observer,
                        "accentColorChanged:",
                        name,
                        None,
                    )
                self._centers.append(center)

            return True
        except Exception as e:
            logging.debug(f"Unable to listen for accent color notifications: {e}")
            self.stop()
            return False

    def stop(self):
        if self._observer:
            for center in self._centers:
                try:
                    center.removeObserver_(self._observer)
                except Exception as e:
                    logging.debug(f"Unable to remove accent color observer: {e}")

        self._centers = []
        self._observer = None


class ThemeManager(QObject):
    def __init__(self,global_constants:Constants=None):
        super().__init__()

        logging.info("init Theme Manager")

        self.constants = global_constants
        self.current_theme = "dark"
        self.last_accent_color = None
        self.running = True
        self.system_theme_thread = None
        self.app_theme_thread = None
        self.accent_color_thread = None
        self.last_color_hex = None
        self.timer = None
        self.accent_observer = None
        self._apply_accent_color()

    def _read_accent_color(self):
        color = getSystemAccentColor()
        return color, color.name()

    def _apply_accent_color(self, color=None, color_hex=None):
        if color is None or color_hex is None:
            color, color_hex = self._read_accent_color()

        self.last_color_hex = color_hex
        setThemeColor(color, save=False)
        return color

    def check_accent_color(self):
        """check accent color"""
        color, color_hex = self._read_accent_color()
        if color_hex != self.last_color_hex:
            color_dict = {
                "r": color.red(),
                "g": color.green(),
                "b": color.blue(),
                "a": color.alpha(),
                "hex": color_hex
            }
            self.on_color_change(color_dict, color, color_hex)

    def on_color_change(self, color_dict=None, color=None, color_hex=None):
        """apply color change"""
        self._apply_accent_color(color, color_hex)
        if color_dict:
            logging.info(f"Accent color changed: {color_dict}")

    def start(self):
        self.accent_observer = _MacAccentColorObserver(self)
        self.accent_observer.accentColorChanged.connect(self.check_accent_color)
        observer_started = self.accent_observer.start()

        # macOS does not reliably post the same notification on every release,
        # so keep a light safety check to guarantee live accent-color updates.
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check_accent_color)
        self.timer.start(250 if sys.platform == "darwin" else 2000)

        if not observer_started:
            logging.debug("Accent color notification observer unavailable; using timer fallback")

    def stop(self):
        self.running = False

        if self.timer:
            self.timer.stop()
            try:
                self.timer.timeout.disconnect(self.check_accent_color)
            except (TypeError, RuntimeError):
                pass
            self.timer.deleteLater()
            self.timer = None

        if self.accent_observer:
            self.accent_observer.stop()
            try:
                self.accent_observer.accentColorChanged.disconnect(self.check_accent_color)
            except (TypeError, RuntimeError):
                pass
            self.accent_observer.deleteLater()
            self.accent_observer = None
