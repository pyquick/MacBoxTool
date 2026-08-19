# coding:utf-8
import weakref

from PySide2.QtCore import QEvent, QObject
from PySide2.QtWidgets import QWidget

from .config import Theme, qconfig
from .style_sheet import StyleSheetBase, addStyleSheet, getStyleSheet, styleSheetManager


def maximumBorderRadius(widget: QWidget) -> int:
    """Return the largest radius valid for the current widget size."""
    return max(0, min(widget.width(), widget.height()) // 2)


class DynamicBorderRadiusStyleSheet(StyleSheetBase):
    """Generate border radius rules from a widget's current dimensions."""

    def __init__(self, widget: QWidget, selectors: tuple[str, ...]):
        self._widget = weakref.ref(widget)
        self._selectors = selectors

    def path(self, theme=Theme.AUTO):
        return ""

    def content(self, theme=Theme.AUTO):
        widget = self._widget()
        if widget is None:
            return ""
        radius = maximumBorderRadius(widget)
        return f"{', '.join(self._selectors)} {{ border-radius: {radius}px; }}"


class DynamicBorderRadiusWatcher(QObject):
    """Refresh managed QSS only when a control's radius changes."""

    def __init__(self, widget: QWidget, selectors: tuple[str, ...]):
        super().__init__(widget)
        self._widget = widget
        self._radius = -1
        self._source = DynamicBorderRadiusStyleSheet(widget, selectors)
        widget.installEventFilter(self)
        addStyleSheet(widget, self._source)
        self._refresh()

    def eventFilter(self, watched, event):
        if event.type() in (QEvent.Resize, QEvent.Show):
            self._refresh()
        return super().eventFilter(watched, event)

    def _refresh(self):
        radius = maximumBorderRadius(self._widget)
        if radius == self._radius:
            return
        self._radius = radius
        if self._widget in styleSheetManager.widgets:
            self._widget.setStyleSheet(getStyleSheet(styleSheetManager.source(self._widget), qconfig.theme))
            styleSheetManager.setAppliedQss(self._widget, self._widget.styleSheet())


def installDynamicBorderRadius(widget: QWidget, *selectors: str) -> None:
    """Install dimension-aware radius styling on a control."""
    if getattr(widget, "_dynamicBorderRadiusWatcher", None):
        return
    widget._dynamicBorderRadiusWatcher = DynamicBorderRadiusWatcher(widget, tuple(selectors))
