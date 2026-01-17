"""
gui_support.py: Give custom looks
"""
from typing import Optional, Tuple, TYPE_CHECKING
from ..constants import Constants
from ..UIkit import *
from ..UIkit import FluentIcon as FIF
from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *
from ..support.colors import COLORS, RADIUS, SPACING


class DefGUI():
    def __init__(self,global_constants:Constants):
        self.constants:Constants=global_constants
    def custom_card(self, card_type: str = "note", icon: Optional[FluentIcon] = None, title: str = "", body: str = "", custom_widget: Optional[QWidget] = None, parent: Optional[QWidget] = None) -> CardWidget:
        card_styles = {
            "note": {
                "bg": COLORS["note_bg"],
                "text": COLORS["note_text"],
                "border": "rgba(21, 101, 192, 0.2)",
                "default_icon": FluentIcon.INFO
            },
            "warning": {
                "bg": COLORS["warning_bg"],
                "text": COLORS["warning_text"],
                "border": "rgba(245, 124, 0, 0.25)",
                "default_icon": FluentIcon.MEGAPHONE
            },
            "success": {
                "bg": COLORS["success_bg"],
                "text": COLORS["success"],
                "border": "rgba(16, 124, 16, 0.2)",
                "default_icon": FluentIcon.COMPLETED
            },
            "error": {
                "bg": "#FFEBEE",
                "text": COLORS["error"],
                "border": "rgba(232, 17, 35, 0.25)",
                "default_icon": FluentIcon.CLOSE
            },
            "info": {
                "bg": COLORS["note_bg"],
                "text": COLORS["info"],
                "border": "rgba(0, 120, 212, 0.2)",
                "default_icon": FluentIcon.INFO
            }
        }
        
        style = card_styles.get(card_type, card_styles["note"])
        
        if icon is None:
            icon = style["default_icon"]
        
        card = CardWidget(parent)
        card.setStyleSheet(f"""
            CardWidget {{
                background-color: {style["bg"]};
                border: 1px solid {style["border"]};
                border-radius: {RADIUS["card"]}px;
            }}
        """)
        
        main_layout = QHBoxLayout(card)
        main_layout.setContentsMargins(SPACING["large"], SPACING["large"], SPACING["large"], SPACING["large"])
        main_layout.setSpacing(SPACING["large"])
        
        icon_label = self.build_icon_label(icon, style["text"], size=40)
        main_layout.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignVCenter)
        
        text_layout = QVBoxLayout()
        text_layout.setSpacing(SPACING["small"])
        
        if title:
            title_label = StrongBodyLabel(title)
            title_label.setStyleSheet("color: {}; font-size: 16px;".format(style["text"]))
            text_layout.addWidget(title_label)
        
        if body:
            body_label = BodyLabel(body)
            body_label.setWordWrap(True)
            body_label.setOpenExternalLinks(True)
            body_label.setStyleSheet("color: #424242; line-height: 1.6;")
            text_layout.addWidget(body_label)
        
        if custom_widget:
            text_layout.addWidget(custom_widget)
        
        main_layout.addLayout(text_layout)
        
        return card
        
