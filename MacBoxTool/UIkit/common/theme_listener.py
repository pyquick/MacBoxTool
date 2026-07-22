# coding:utf-8
from PySide6.QtCore import QThread, Signal, Slot

from .config import Theme, qconfig
from .style_sheet import updateStyleSheet
import darkdetect
import sys


class SystemThemeListener(QThread):
    """ System theme listener """

    systemThemeChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.systemThemeChanged.connect(self._applyThemeChange)

    def run(self):
        if sys.platform == "win32":
            darkdetect.listener(self._onThemeChanged)
            return

        while not self.isInterruptionRequested():
            t = darkdetect.theme().lower()
            theme = Theme.DARK if t == "dark" else Theme.LIGHT
            if theme != qconfig.theme:
                self._onThemeChanged(t)
                self.msleep(2000)   # anti shake
            else:
                self.msleep(1000)

    @Slot()
    def _applyThemeChange(self):
        qconfig.themeChanged.emit(Theme.AUTO)
        updateStyleSheet()
        qconfig.themeChangedFinished.emit()

    def _onThemeChanged(self, theme: str):
        theme = Theme.DARK if theme.lower() == "dark" else Theme.LIGHT

        if qconfig.themeMode.value != Theme.AUTO or theme == qconfig.theme:
            return

        qconfig.theme = Theme.AUTO
        self.systemThemeChanged.emit()
