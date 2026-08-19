# coding:utf-8
import sys
from PySide2.QtCore import Qt, Signal, QEasingCurve
from PySide2.QtWidgets import QFrame, QHBoxLayout, QAbstractScrollArea

from ..components.widgets.stacked_widget import (
    PopUpAniStackedWidget,
    DualSnapshotSlideStackedWidget,
)



class StackedWidget(QFrame):
    """ Stacked widget """

    currentChanged = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.hBoxLayout = QHBoxLayout(self)

        if sys.platform == "win32":
            # DualSnapshotSlideStackedWidget renders both the outgoing and
            # incoming page to pixmap snapshots at animation start, then
            # slides/fades only the lightweight snapshot labels.  No real
            # widgets are moved or re-laid-out, eliminating the layout
            # thrash that causes stutter on Windows with complex pages.
            self.view = DualSnapshotSlideStackedWidget(self)
        else:
            self.view = PopUpAniStackedWidget(self)

        self.hBoxLayout.setContentsMargins(0, 0, 0, 0)
        self.hBoxLayout.addWidget(self.view)

        self.view.currentChanged.connect(self.currentChanged)
        self.setAttribute(Qt.WA_StyledBackground)

    def isAnimationEnabled(self) -> bool:
        if isinstance(self.view, DualSnapshotSlideStackedWidget):
            return True
        return self.view.isAnimationEnabled

    def setAnimationEnabled(self, isEnabled: bool):
        """set whether the pop animation is enabled"""
        if not isinstance(self.view, DualSnapshotSlideStackedWidget):
            self.view.setAnimationEnabled(isEnabled)

    def addWidget(self, widget):
        """ add widget to view """
        self.view.addWidget(widget)

    def removeWidget(self, widget):
        """ remove widget from view """
        self.view.removeWidget(widget)

    def widget(self, index: int):
        return self.view.widget(index)

    def setCurrentWidget(self, widget, popOut=True):
        if isinstance(widget, QAbstractScrollArea):
            widget.verticalScrollBar().setValue(0)

        if isinstance(self.view, DualSnapshotSlideStackedWidget):
            # Windows: dual-snapshot slide — smooth, no real-widget thrash
            self.view.setCurrentWidget(widget, duration=300, isBack=popOut)
        elif not popOut:
            self.view.setCurrentWidget(widget, duration=300)
        else:
            self.view.setCurrentWidget(
                widget, True, False, 300, QEasingCurve.Type.InQuad)

    def setCurrentIndex(self, index, popOut=True):
        self.setCurrentWidget(self.view.widget(index), popOut)

    def currentIndex(self):
        return self.view.currentIndex()

    def currentWidget(self):
        return self.view.currentWidget()

    def indexOf(self, widget):
        return self.view.indexOf(widget)

    def count(self):
        return self.view.count()
