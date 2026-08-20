# coding:utf-8
import sys
import warnings
from typing import Union

from PySide6.QtCore import Qt, QSize, QRect, QEvent
from PySide6.QtGui import QIcon, QPainter, QColor
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QApplication

from ..common.config import qconfig
from ..common.icon import FluentIconBase
from ..common.router import qrouter
from ..common.style_sheet import FluentStyleSheet, isDarkTheme, setTheme, Theme
from ..common.animation import BackgroundAnimationWidget
from ..components.widgets.frameless_window import FramelessWindow
from ..components.widgets.label import CaptionLabel
from ..components.navigation import (NavigationInterface, NavigationBar, NavigationItemPosition,
                                     NavigationBarPushButton, NavigationTreeWidget)
from .stacked_widget import StackedWidget

from ...UIWindow import TitleBar, TitleBarBase, TitleBarButton
from ...UIWindow.utils import startSystemMove, toggleMaxState


class FluentWidget(BackgroundAnimationWidget, FramelessWindow):
    """ Fluent widget """

    def __init__(self, parent=None):
        self._isMicaEnabled = False
        self._lightBackgroundColor = QColor(240, 244, 249)
        self._darkBackgroundColor = QColor(32, 32, 32)
        super().__init__(parent=parent)

        # enable mica effect on win11
        self.setMicaEffectEnabled(True)

        # Keep the platform's internal frameless-window hook, but remove every
        # title-bar control and give it no geometry.
        self._removeTitleBar()
        if sys.platform == "darwin":
            self.setSystemTitleBarButtonVisible(True)

        qconfig.themeChangedFinished.connect(self._onThemeChangedFinished)

    def _removeTitleBar(self):
        self.titleBar.setFixedHeight(0)
        self.titleBar.hide()

    def setWindowTitle(self, title: str):
        """Deprecated: window titles are no longer displayed by FluentWidget."""
        warnings.warn(
            "FluentWidget.setWindowTitle() is deprecated because the title bar "
            "has been removed",
            DeprecationWarning,
            stacklevel=2,
        )
        super().setWindowTitle(title)

    def setCustomBackgroundColor(self, light, dark):
        """ set custom background color

        Parameters
        ----------
        light, dark: QColor | Qt.GlobalColor | str
            background color in light/dark theme mode
        """
        self._lightBackgroundColor = QColor(light)
        self._darkBackgroundColor = QColor(dark)
        self._updateBackgroundColor()

    def _normalBackgroundColor(self):
        if not self.isMicaEffectEnabled():
            return self._darkBackgroundColor if isDarkTheme() else self._lightBackgroundColor

        return QColor(0, 0, 0, 0)

    def _onThemeChangedFinished(self):
        if self.isMicaEffectEnabled():
            self.windowEffect.setMicaEffect(self.winId(), isDarkTheme())

    def paintEvent(self, e):
        super().paintEvent(e)
        painter = QPainter(self)
        painter.setPen(Qt.NoPen)
        painter.setBrush(self.backgroundColor)
        painter.drawRect(self.rect())

    def showEvent(self, e):
        super().showEvent(e)
        # reapply mica effect after window is fully initialized
        if self.isMicaEffectEnabled():
            self.windowEffect.setMicaEffect(self.winId(), isDarkTheme())

    def setMicaEffectEnabled(self, isEnabled: bool):
        """ set whether the mica effect is enabled, only available on Win11 """
        if sys.platform != 'win32' or sys.getwindowsversion().build < 22000:
            return
        else:
            self._isMicaEnabled = isEnabled

            if isEnabled:
                self.windowEffect.setMicaEffect(self.winId(), isDarkTheme())
            else:
                self.windowEffect.removeBackgroundEffect(self.winId())

            self.setBackgroundColor(self._normalBackgroundColor())

    def isMicaEffectEnabled(self):
        return self._isMicaEnabled

    def systemTitleBarRect(self, size: QSize) -> QRect:
        """ Returns the system title bar rect, only works for macOS

        Parameters
        ----------
        size: QSize
            original system title bar rect
        """
        return QRect(12, 0 if self.isFullScreen() else 8, 54, size.height())

    def setTitleBar(self, titleBar):
        super().setTitleBar(titleBar)

        # hide title bar buttons on macOS
        if sys.platform == "darwin" and self.isSystemButtonVisible() and isinstance(titleBar, TitleBarBase):
            titleBar.minBtn.hide()
            titleBar.maxBtn.hide()
            titleBar.closeBtn.hide()


class FluentWindowBase(FluentWidget):
    """ Fluent window base class """

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.hBoxLayout = QHBoxLayout(self)
        self.stackedWidget = StackedWidget(self)
        self.navigationInterface = None
        self._interfaceBatchDepth = 0
        self._pendingStackedBackgroundUpdate = False
        self._wasUpdatesEnabled = True
        self._wasStackAnimationEnabled = True
        self._wasIndicatorAnimationEnabled = True

        # initialize layout
        self.hBoxLayout.setSpacing(0)
        self.hBoxLayout.setContentsMargins(0, 0, 0, 0)

        FluentStyleSheet.FLUENT_WINDOW.apply(self.stackedWidget)

    @staticmethod
    def _scrollBarObjects(scrollArea):
        """Return scroll controls that must not start a window drag."""
        if scrollArea is None:
            return ()

        objects = [scrollArea, scrollArea.viewport()]
        delegate = getattr(scrollArea, "scrollDelagate", None)
        if delegate:
            objects.extend((delegate.vScrollBar, delegate.hScrollBar))
        return tuple(objects)

    def eventFilter(self, obj, event):
        navigationInterface = getattr(self, 'navigationInterface', None)
        panel = getattr(navigationInterface, 'panel', None)
        scrollArea = getattr(panel, "scrollArea", None)
        scrollObjects = self._scrollBarObjects(scrollArea)
        if obj in scrollObjects:
            return super().eventFilter(obj, event)

        dragSource = obj in (self, navigationInterface, panel)
        if not dragSource or self.isFullScreen():
            return super().eventFilter(obj, event)

        if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            if obj is panel and scrollArea and scrollArea.geometry().contains(event.position().toPoint()):
                return super().eventFilter(obj, event)
            startSystemMove(self, event.globalPosition().toPoint())
            return True

        if event.type() == QEvent.MouseButtonDblClick and event.button() == Qt.LeftButton:
            if obj is panel and scrollArea and scrollArea.geometry().contains(event.position().toPoint()):
                return super().eventFilter(obj, event)
            toggleMaxState(self)
            return True

        return super().eventFilter(obj, event)

    def _enableWindowDragging(self):
        self.installEventFilter(self)
        self.navigationInterface.installEventFilter(self)
        panel = getattr(self.navigationInterface, 'panel', None)
        if panel:
            panel.installEventFilter(self)
            scrollArea = getattr(panel, "scrollArea", None)
            if scrollArea:
                scrollArea.installEventFilter(self)
                delegate = getattr(scrollArea, "scrollDelagate", None)
                if delegate:
                    delegate.vScrollBar.installEventFilter(self)
                    delegate.hScrollBar.installEventFilter(self)

    def addSubInterface(self, interface: QWidget, icon: Union[FluentIconBase, QIcon, str], text: str,
                        position=NavigationItemPosition.TOP):
        """ add sub interface """
        raise NotImplementedError

    def beginAddSubInterfaceBatch(self):
        """Suspend expensive UI updates while adding multiple sub interfaces."""
        if self._interfaceBatchDepth == 0:
            self._wasUpdatesEnabled = self.updatesEnabled()
            self._wasStackAnimationEnabled = self.stackedWidget.isAnimationEnabled()
            indicatorController = self._indicatorAnimationController()
            self._wasIndicatorAnimationEnabled = bool(
                indicatorController and indicatorController.isIndicatorAnimationEnabled()
            )

            self.setUpdatesEnabled(False)
            self.stackedWidget.setAnimationEnabled(False)
            if indicatorController:
                indicatorController.setIndicatorAnimationEnabled(False)

        self._interfaceBatchDepth += 1

    def endAddSubInterfaceBatch(self):
        """Resume UI updates after adding multiple sub interfaces."""
        if self._interfaceBatchDepth == 0:
            return

        self._interfaceBatchDepth -= 1
        if self._interfaceBatchDepth:
            return

        if self._pendingStackedBackgroundUpdate:
            self._pendingStackedBackgroundUpdate = False
            self._requestStackedBackgroundUpdate()

        indicatorController = self._indicatorAnimationController()
        if indicatorController:
            indicatorController.setIndicatorAnimationEnabled(self._wasIndicatorAnimationEnabled)

        self.stackedWidget.setAnimationEnabled(self._wasStackAnimationEnabled)
        self.setUpdatesEnabled(self._wasUpdatesEnabled)
        self.update()

    def _indicatorAnimationController(self):
        if not self.navigationInterface:
            return None

        panel = getattr(self.navigationInterface, 'panel', None)
        if panel and hasattr(panel, 'setIndicatorAnimationEnabled'):
            return panel

        if hasattr(self.navigationInterface, 'setIndicatorAnimationEnabled'):
            return self.navigationInterface

        return None

    def _requestStackedBackgroundUpdate(self):
        if self._interfaceBatchDepth:
            self._pendingStackedBackgroundUpdate = True
            return

        self._updateStackedBackground()

    def removeInterface(self, interface: QWidget, isDelete=False):
        """ remove sub interface

        Parameters
        ----------
        interface: QWidget
            sub interface to be removed

        isDelete: bool
            whether to delete the sub interface
        """
        raise NotImplementedError

    def switchTo(self, interface: QWidget):
        self.stackedWidget.setCurrentWidget(interface, popOut=False)

    def _onCurrentInterfaceChanged(self, index: int):
        widget = self.stackedWidget.widget(index)
        self.navigationInterface.setCurrentItem(widget.objectName())
        qrouter.push(self.stackedWidget, widget.objectName())

        self._requestStackedBackgroundUpdate()

    def _updateStackedBackground(self):
        isTransparent = self.stackedWidget.currentWidget().property("isStackedTransparent")
        if bool(self.stackedWidget.property("isTransparent")) == isTransparent:
            return

        self.stackedWidget.setProperty("isTransparent", isTransparent)
        self.stackedWidget.setStyle(QApplication.style())

    def systemTitleBarRect(self, size: QSize) -> QRect:
        """ Returns the system title bar rect, only works for macOS

        Parameters
        ----------
        size: QSize
            original system title bar rect
        """
        return super().systemTitleBarRect(size)


class FluentTitleBar(TitleBar):
    """ Fluent title bar"""

    def __init__(self, parent):
        super().__init__(parent)
        self.setFixedHeight(48)
        self.hBoxLayout.removeWidget(self.minBtn)
        self.hBoxLayout.removeWidget(self.maxBtn)
        self.hBoxLayout.removeWidget(self.closeBtn)

        # add window icon
        self.iconLabel = QLabel(self)
        self.iconLabel.setFixedSize(18, 18)
        self.hBoxLayout.setContentsMargins(12, 0, 0, 0)
        self.hBoxLayout.insertWidget(0, self.iconLabel, 0, Qt.AlignLeft | Qt.AlignVCenter)
        self.window().windowIconChanged.connect(self.setIcon)

        # add title label
        self.titleLabel = CaptionLabel(self)
        self.hBoxLayout.insertWidget(1, self.titleLabel, 0, Qt.AlignLeft | Qt.AlignVCenter)
        self.titleLabel.setObjectName('titleLabel')
        self.window().windowTitleChanged.connect(self.setTitle)

        self.vBoxLayout = QVBoxLayout()
        self.buttonLayout = QHBoxLayout()
        self.buttonLayout.setSpacing(0)
        self.buttonLayout.setContentsMargins(0, 0, 0, 0)
        self.buttonLayout.setAlignment(Qt.AlignTop)
        self.buttonLayout.addWidget(self.minBtn)
        self.buttonLayout.addWidget(self.maxBtn)
        self.buttonLayout.addWidget(self.closeBtn)
        self.vBoxLayout.addLayout(self.buttonLayout)
        self.vBoxLayout.addStretch(1)
        self.hBoxLayout.addLayout(self.vBoxLayout, 0)

        FluentStyleSheet.FLUENT_WINDOW.apply(self)

    def canDrag(self, pos):
        if sys.platform == "darwin" and QRect(self.width() - 110, 0, 110, self.height()).contains(pos):
            return False

        return super().canDrag(pos)

    def setTitle(self, title):
        self.titleLabel.setText(title)
        self.titleLabel.adjustSize()

    def setIcon(self, icon):
        self.iconLabel.setPixmap(QIcon(icon).pixmap(18, 18))


class FluentWindow(FluentWindowBase):
    """ Fluent window """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.navigationInterface = NavigationInterface(self, showReturnButton=True)
        self._enableWindowDragging()
        self.widgetLayout = QHBoxLayout()

        # initialize layout
        self.hBoxLayout.addWidget(self.navigationInterface)
        self.hBoxLayout.addLayout(self.widgetLayout)
        self.hBoxLayout.setStretchFactor(self.widgetLayout, 1)

        self.widgetLayout.addWidget(self.stackedWidget)
        self.widgetLayout.setContentsMargins(0, 0, 0, 0)

    def addSubInterface(self, interface: QWidget, icon: Union[FluentIconBase, QIcon, str], text: str,
                        position=NavigationItemPosition.TOP, parent=None, isTransparent=False) -> NavigationTreeWidget:
        """ add sub interface, the object name of `interface` should be set already
        before calling this method

        Parameters
        ----------
        interface: QWidget
            the subinterface to be added

        icon: FluentIconBase | QIcon | str
            the icon of navigation item

        text: str
            the text of navigation item

        position: NavigationItemPosition
            the position of navigation item

        parent: QWidget | str
            * QWidget: the parent of navigation item
            * str: the parent route key of navigation item

        isTransparent: bool
            whether to use transparent background
        """
        if not interface.objectName():
            raise ValueError("The object name of `interface` can't be empty string.")

        parentRouteKey = parent
        if parent and isinstance(parent, QWidget):
            parentRouteKey = parent.objectName()
            if not parentRouteKey:
                raise ValueError("The object name of `parent` can't be empty string.")

        interface.setProperty("isStackedTransparent", isTransparent)
        self.stackedWidget.addWidget(interface)

        # add navigation item
        routeKey = interface.objectName()
        item = self.navigationInterface.addItem(
            routeKey=routeKey,
            icon=icon,
            text=text,
            onClick=lambda: self.switchTo(interface),
            position=position,
            tooltip=text,
            parentRouteKey=parentRouteKey
        )

        # initialize selected item
        if self.stackedWidget.count() == 1:
            self.stackedWidget.currentChanged.connect(self._onCurrentInterfaceChanged)
            self.navigationInterface.setCurrentItem(routeKey)
            qrouter.setDefaultRouteKey(self.stackedWidget, routeKey)

        if self.stackedWidget.currentWidget() is interface:
            self._requestStackedBackgroundUpdate()

        return item

    def removeInterface(self, interface, isDelete=False):
        self.navigationInterface.removeWidget(interface.objectName())
        self.stackedWidget.removeWidget(interface)
        interface.hide()

        if isDelete:
            interface.deleteLater()

    def resizeEvent(self, e):
        super().resizeEvent(e)


class MSFluentTitleBar(FluentTitleBar):

    def __init__(self, parent):
        super().__init__(parent)
        self.hBoxLayout.insertSpacing(0, 20)
        self.hBoxLayout.insertSpacing(2, 2)


class FluentWidgetTitleBar(FluentTitleBar):

    def __init__(self, parent):
        super().__init__(parent)

        if sys.platform == "darwin":
            self.iconLabel.hide()
            self.titleLabel.hide()
            self.setFixedHeight(28)
        else:
            self.hBoxLayout.setContentsMargins(16, 0, 0, 0)
            self.setFixedHeight(self.buttonLayout.sizeHint().height())

        for button in self.findChildren(TitleBarButton):
            FluentStyleSheet.FLUENT_WINDOW.apply(button)



class MSFluentWindow(FluentWindowBase):
    """ Fluent window in Microsoft Store style """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.navigationInterface = NavigationBar(self)
        self._enableWindowDragging()

        # initialize layout
        self.hBoxLayout.setContentsMargins(0, 0, 0, 0)
        self.hBoxLayout.addWidget(self.navigationInterface)
        self.hBoxLayout.addWidget(self.stackedWidget, 1)

    def addSubInterface(self, interface: QWidget, icon: Union[FluentIconBase, QIcon, str], text: str,
                        selectedIcon=None, position=NavigationItemPosition.TOP, isTransparent=False) -> NavigationBarPushButton:
        """ add sub interface, the object name of `interface` should be set already
        before calling this method

        Parameters
        ----------
        interface: QWidget
            the subinterface to be added

        icon: FluentIconBase | QIcon | str
            the icon of navigation item

        text: str
            the text of navigation item

        selectedIcon: str | QIcon | FluentIconBase
            the icon of navigation item in selected state

        position: NavigationItemPosition
            the position of navigation item
        """
        if not interface.objectName():
            raise ValueError("The object name of `interface` can't be empty string.")

        interface.setProperty("isStackedTransparent", isTransparent)
        self.stackedWidget.addWidget(interface)

        # add navigation item
        routeKey = interface.objectName()
        item = self.navigationInterface.addItem(
            routeKey=routeKey,
            icon=icon,
            text=text,
            onClick=lambda: self.switchTo(interface),
            selectedIcon=selectedIcon,
            position=position
        )

        if self.stackedWidget.count() == 1:
            self.stackedWidget.currentChanged.connect(self._onCurrentInterfaceChanged)
            self.navigationInterface.setCurrentItem(routeKey)
            qrouter.setDefaultRouteKey(self.stackedWidget, routeKey)

        if self.stackedWidget.currentWidget() is interface:
            self._requestStackedBackgroundUpdate()

        return item

    def removeInterface(self, interface, isDelete=False):
        self.navigationInterface.removeWidget(interface.objectName())
        self.stackedWidget.removeWidget(interface)
        interface.hide()

        if isDelete:
            interface.deleteLater()


class SplitTitleBar(TitleBar):

    def __init__(self, parent):
        super().__init__(parent)
        # add window icon
        self.iconLabel = QLabel(self)
        self.iconLabel.setFixedSize(18, 18)
        self.hBoxLayout.insertSpacing(0, 12)
        self.hBoxLayout.insertWidget(1, self.iconLabel, 0, Qt.AlignLeft | Qt.AlignBottom)
        self.window().windowIconChanged.connect(self.setIcon)

        # add title label
        self.titleLabel = QLabel(self)
        self.hBoxLayout.insertWidget(2, self.titleLabel, 0, Qt.AlignLeft | Qt.AlignBottom)
        self.titleLabel.setObjectName('titleLabel')
        self.window().windowTitleChanged.connect(self.setTitle)

        FluentStyleSheet.FLUENT_WINDOW.apply(self)

    def setTitle(self, title):
        self.titleLabel.setText(title)
        self.titleLabel.adjustSize()

    def setIcon(self, icon):
        self.iconLabel.setPixmap(QIcon(icon).pixmap(18, 18))


class SplitFluentWindow(FluentWindow):
    """ Fluent window with split style """

    def __init__(self, parent=None):
        super().__init__(parent)


class FluentBackgroundTheme:
    """ Fluent background theme """
    DEFAULT = (QColor(243, 243, 243), QColor(32, 32, 32))   # light, dark
    DEFAULT_BLUE = (QColor(240, 244, 249), QColor(25, 33, 42))
