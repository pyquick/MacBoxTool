# coding:utf-8
"""
CheckableComboBox: Multi-select dropdown with checkboxes.

Provides a dropdown where users can select multiple items via checkboxes.
Uses UIkit's Fluent design patterns.
"""
from typing import List, Iterable

from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QWidget, QListWidget, QListWidgetItem

from .menu import RoundMenu, MenuAnimationType
from .button import PushButton
from ...common.font import setFont
from ...common.style_sheet import FluentStyleSheet


class CheckableComboBox(QWidget):
    """
    Multi-select combo box with checkable items.

    Usage:
        combo = CheckableComboBox()
        combo.addItem("macOS 12 Monterey", "12")
        combo.addItem("macOS 13 Ventura", "13")
        combo.setCheckedItems(["12", "13"])  # Select by userData
        combo.checkedItemsChanged.connect(lambda items: print(items))
    """

    checkedItemsChanged = Signal(list)  # Emits list of checked userData values

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items = []  # List of (text, userData, checked)
        self._button = PushButton()
        self._menu = RoundMenu()
        self._list_widget = QListWidget()
        self._ignore_signals = False

        self._init_ui()

    def _init_ui(self):
        """Initialize the UI components."""
        from PySide6.QtWidgets import QVBoxLayout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._button)

        # Configure the button
        self._button.setText("Select versions...")
        self._button.setFixedHeight(32)
        setFont(self._button)
        FluentStyleSheet.COMBO_BOX.apply(self._button)

        # Configure the menu
        self._menu.setObjectName("checkableComboMenu")
        self._list_widget.setObjectName("checkableListWidget")
        self._list_widget.setMinimumWidth(200)
        self._list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # Set menu content to list widget
        self._menu.layout().addWidget(self._list_widget)

        # Connect signals
        self._button.clicked.connect(self._show_menu)
        self._list_widget.itemChanged.connect(self._on_item_changed)

    def _show_menu(self):
        """Show the dropdown menu at button position."""
        pos = self._button.mapToGlobal(QPoint(0, self._button.height()))
        self._menu.exec(pos)

    def _on_item_changed(self, item: QListWidgetItem):
        """Handle checkbox state change."""
        if self._ignore_signals:
            return

        index = self._list_widget.row(item)
        if 0 <= index < len(self._items):
            self._items[index] = (self._items[index][0], self._items[index][1], item.checkState() == Qt.CheckState.Checked)
            self._update_button_text()
            self.checkedItemsChanged.emit(self.checkedItems())

    def addItem(self, text: str, userData=None):
        """Add an item with checkbox."""
        self._items.append((text, userData, False))

        # Create list widget item with checkbox
        item = QListWidgetItem(text)
        item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(Qt.CheckState.Unchecked)
        item.setData(Qt.ItemDataRole.UserRole, userData)
        self._list_widget.addItem(item)

    def addItems(self, items: Iterable[tuple]):
        """Add multiple items. Each item is a (text, userData) tuple."""
        for text, userData in items:
            self.addItem(text, userData)

    def setCheckedItems(self, userDataList: List):
        """Set checked items by their userData values."""
        self._ignore_signals = True
        try:
            for i in range(self._list_widget.count()):
                item = self._list_widget.item(i)
                data = item.data(Qt.ItemDataRole.UserRole)
                if data in userDataList:
                    item.setCheckState(Qt.CheckState.Checked)
                else:
                    item.setCheckState(Qt.CheckState.Unchecked)

            # Update internal state
            for i, (text, data, _) in enumerate(self._items):
                self._items[i] = (text, data, data in userDataList)

            self._update_button_text()
        finally:
            self._ignore_signals = False

    def checkedItems(self) -> list:
        """Return list of userData values for checked items."""
        return [data for _, data, checked in self._items if checked]

    def _update_button_text(self):
        """Update button text based on checked items."""
        checked = self.checkedItems()
        if not checked:
            self._button.setText("Select versions...")
        elif len(checked) == 1:
            # Find the display text for this item
            for text, data, _ in self._items:
                if data == checked[0]:
                    self._button.setText(text)
                    break
        else:
            self._button.setText(f"{len(checked)} versions selected")

    def setVisible(self, visible: bool):
        """Override setVisible to propagate to button."""
        self._button.setVisible(visible)

    def setEnabled(self, enabled: bool):
        """Set enabled state."""
        self._button.setEnabled(enabled)

    def setPlaceholderText(self, text: str):
        """Set placeholder text when nothing is selected."""
        if not self.checkedItems():
            self._button.setText(text)

    def setMinimumWidth(self, width: int):
        """Set minimum width."""
        self._button.setMinimumWidth(width)

    def setFixedHeight(self, height: int):
        """Set fixed height."""
        self._button.setFixedHeight(height)