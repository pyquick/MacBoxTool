"""
cards.py: Plain card widgets shared by GUI pages.

Distinct from `UIkit.components.widgets.card_widget.CardWidget`: that one is an
animated widget with a 16px default radius and its own background logic. This is
the static, 5px-radius variant used by the package download lists. The two must
stay separate — folding this into CardWidget would change how those pages render.

Widget code here is intentionally verbatim from its previous home in
`qt_gui/gui_kdk.py` / `qt_gui/gui_metallib.py` so that pixels are unchanged.
"""

from PySide6.QtCore import Qt, Signal, Property
from PySide6.QtGui import QPainter, QColor, QPainterPath
from PySide6.QtWidgets import QFrame

from ...UIkit.common.style_sheet import isDarkTheme


class NoAnimCardWidget(QFrame):
    """Simple card widget without hover animation"""

    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._borderRadius = 5

    def mouseReleaseEvent(self, e):
        super().mouseReleaseEvent(e)
        self.clicked.emit()

    def getBorderRadius(self):
        return self._borderRadius

    def setBorderRadius(self, radius: int):
        self._borderRadius = radius
        self.update()

    def paintEvent(self, e):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        r = self.borderRadius
        d = 2 * r

        isDark = isDarkTheme()

        # draw top border
        path = QPainterPath()
        path.arcMoveTo(1, h - d - 1, d, d, 240)
        path.arcTo(1, h - d - 1, d, d, 225, -60)
        path.lineTo(1, r)
        path.arcTo(1, 1, d, d, -180, -90)
        path.lineTo(w - r, 1)
        path.arcTo(w - d - 1, 1, d, d, 90, -90)
        path.lineTo(w - 1, h - r)
        path.arcTo(w - d - 1, h - d - 1, d, d, 0, -60)

        topBorderColor = QColor(0, 0, 0, 20)
        if isDark:
            topBorderColor = QColor(255, 255, 255, 13)
        else:
            topBorderColor = QColor(0, 0, 0, 15)

        painter.strokePath(path, topBorderColor)

        # draw bottom border
        path = QPainterPath()
        path.arcMoveTo(1, h - d - 1, d, d, 240)
        path.arcTo(1, h - d - 1, d, d, 240, 30)
        path.lineTo(w - r - 1, h - 1)
        path.arcTo(w - d - 1, h - d - 1, d, d, 270, 30)

        painter.strokePath(path, topBorderColor)

        # draw background
        painter.setPen(Qt.NoPen)
        bgColor = QColor(255, 255, 255, 13 if isDark else 170)
        painter.setBrush(bgColor)
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), r, r)

    borderRadius = Property(int, getBorderRadius, setBorderRadius)
