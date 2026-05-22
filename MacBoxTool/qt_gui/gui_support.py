"""
gui_support.py: Give custom looks
"""


from ..include import *


class ThemeAwareCard(CardWidget):
    def __init__(self, get_style_fn, parent=None):
        super().__init__(parent)
        self._get_style = get_style_fn
        self._apply_style()
        qconfig.themeChanged.connect(self._apply_style)

    def _apply_style(self):
        style = self._get_style()
        self.setStyleSheet(f"""
            CardWidget {{
                background-color: {style["bg"]};
                border: 1px solid {style["border"]};
                border-radius: {RADIUS["card"]}px;
            }}
        """)

class ProgressStatusHelper:
    def __init__(self, status_icon_label, progress_label, progress_bar, progress_container):
        

        logging.info("init gui_support")

        
        self.status_icon_label = status_icon_label
        self.progress_label = progress_label
        self.progress_bar = progress_bar
        self.progress_container = progress_container
        

    
    
    def update(self, status, message, progress=None):
        icon_size = 28
        icon_map = {
            "loading": (FluentIcon.SYNC, COLORS["primary"]),
            "success": (FluentIcon.COMPLETED, COLORS["success"]),
            "error": (FluentIcon.CLOSE, COLORS["error"]),
            "warning": (FluentIcon.INFO, COLORS["warning"]),
        }
        
        if status in icon_map:
            icon, color = icon_map[status]
            pixmap = icon.icon(color=color).pixmap(icon_size, icon_size)
            self.status_icon_label.setPixmap(pixmap)
        
        self.progress_label.setText(message)
        if status == "success":
            self.progress_label.setStyleSheet("color: {}; font-size: 15px; font-weight: 600;".format(COLORS["success"]))
        elif status == "error":
            self.progress_label.setStyleSheet("color: {}; font-size: 15px; font-weight: 600;".format(COLORS["error"]))
        elif status == "warning":
            self.progress_label.setStyleSheet("color: {}; font-size: 15px; font-weight: 600;".format(COLORS["warning"]))
        else:
            self.progress_label.setStyleSheet("color: {}; font-size: 15px; font-weight: 600;".format(COLORS["primary"]))
        
        if progress is not None:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(progress)
        else:
            self.progress_bar.setRange(0, 0)
        
        self.progress_container.setVisible(True)

class DefGUI():
    def __init__(self,global_constants:Constants):
        self.constants:Constants=global_constants
        if qconfig.theme == Theme.DARK:
            self.card_styles = self.card_styles_dark()
        else:
            self.card_styles = self.card_styles_light()
        qconfig.themeChanged.connect(self.update_theme)

    def build_icon_label(self, icon: FluentIcon, color: str, size: int = 32) -> QLabel:
        label = QLabel()
        label.setPixmap(icon.icon(color=color).pixmap(size, size))
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setFixedSize(size + 12, size + 12)
        return label
    
    

    
    def create_info_widget(self, text: str, color: Optional[str] = None) -> QWidget:
        if not text:
            return QWidget()
        
        label = BodyLabel(text)
        label.setWordWrap(True)
        if color:
            label.setStyleSheet("color: {};".format(color))
        return label
    
    def colored_icon(self, icon: FluentIcon, color_hex: str) -> FluentIcon:
        if not icon or not color_hex:
            return icon
        
        tint = QColor(color_hex)
        return icon.colored(tint, tint)

    def get_compatibility_icon(self, compat_tuple: Optional[Tuple[Optional[str], Optional[str]]]) -> FluentIcon:
        if not compat_tuple or compat_tuple == (None, None):
            return self.colored_icon(FluentIcon.CLOSE, COLORS["error"])
        return self.colored_icon(FluentIcon.ACCEPT, COLORS["success"])
    
    def update_theme(self):
        if qconfig.theme == Theme.DARK:
            self.card_styles = self.card_styles_dark()
        else:
            self.card_styles = self.card_styles_light()

    
    def card_styles_light(self):
        return  {
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

    def card_styles_dark(self):
        return {
            "note": {
                "bg": "rgba(33, 90, 160, 0.18)",
                "text": "#82B4F0",
                "border": "rgba(66, 133, 244, 0.35)",
                "default_icon": FluentIcon.INFO
            },
            "warning": {
                "bg": "rgba(160, 90, 0, 0.18)",
                "text": "#FFB74D",
                "border": "rgba(255, 152, 0, 0.35)",
                "default_icon": FluentIcon.MEGAPHONE
            },
            "success": {
                "bg": "rgba(16, 100, 16, 0.18)",
                "text": "#6DBF6D",
                "border": "rgba(16, 124, 16, 0.35)",
                "default_icon": FluentIcon.COMPLETED
            },
            "error": {
                "bg": "rgba(180, 20, 30, 0.18)",
                "text": "#F28B82",
                "border": "rgba(232, 17, 35, 0.35)",
                "default_icon": FluentIcon.CLOSE
            },
            "info": {
                "bg": "rgba(0, 90, 158, 0.18)",
                "text": "#4CC2FF",
                "border": "rgba(0, 120, 212, 0.35)",
                "default_icon": FluentIcon.INFO
            }
        }
    
    def custom_card(self, card_type: str = "note", icon: Optional[FluentIcon] = None, title: str = "", body: str = "", custom_widget: Optional[QWidget] = None, parent: Optional[QWidget] = None) -> CardWidget:
        resolved_icon = icon
        get_style = lambda: self.card_styles.get(card_type, self.card_styles["note"])

        if resolved_icon is None:
            resolved_icon = get_style()["default_icon"]

        card = ThemeAwareCard(get_style, parent)

        main_layout = QHBoxLayout(card)
        main_layout.setContentsMargins(SPACING["large"], SPACING["large"], SPACING["large"], SPACING["large"])
        main_layout.setSpacing(SPACING["large"])

        icon_label = self.build_icon_label(resolved_icon, get_style()["text"], size=40)
        def _refresh_icon():
            icon_label.setPixmap(resolved_icon.icon(color=get_style()["text"]).pixmap(40, 40))
        _refresh_icon()
        qconfig.themeChanged.connect(_refresh_icon)
        main_layout.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignVCenter)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(SPACING["small"])

        if title:
            title_label = StrongBodyLabel(title)
            QTimer.singleShot(40,lambda: title_label.setStyleSheet("color: {}; font-size: 16px;".format(get_style()["text"])))
            title_label.setStyleSheet("color: {}; font-size: 16px;".format(get_style()["text"]))

            # Create proper callback function for theme changes
            def update_title_with_delay():
                QTimer.singleShot(40, lambda: title_label.setStyleSheet("color: {}; font-size: 16px;".format(get_style()["text"])))

            qconfig.themeChanged.connect(update_title_with_delay)
            title_label.setStyleSheet("color: {}; font-size: 16px;".format(get_style()["text"]))
            text_layout.addWidget(title_label)

        if body:
            body_label = BodyLabel(body)
            body_label.setWordWrap(True)
            body_label.setOpenExternalLinks(True)
            QTimer.singleShot(40,lambda: body_label.setStyleSheet("line-height: 1.6;"))
            body_label.setStyleSheet("line-height: 1.6;")
            text_layout.addWidget(body_label)

        if custom_widget:
            text_layout.addWidget(custom_widget)

        main_layout.addLayout(text_layout)
        return card
    
    def add_group_with_indent(self, card: "GroupHeaderCardWidget", icon: FluentIcon, title: str, content: str, widget: Optional[QWidget] = None, indent_level: int = 0) -> "CardGroupWidget":
        if widget is None:
            widget = QWidget()
        
        group = card.addGroup(icon, title, content, widget)
        
        if indent_level > 0:
            base_margin = 24
            indent = 20 * indent_level
            group.hBoxLayout.setContentsMargins(base_margin + indent, 10, 24, 10)
        
        return group

    def create_step_indicator(self, step_number: int, total_steps: int = 4, color: str = "#0078D4") -> BodyLabel:
        label = BodyLabel("STEP {} OF {}".format(step_number, total_steps))
        label.setStyleSheet("color: {}; font-weight: bold;".format(color))
        return label

    def create_vertical_spacer(self, spacing: int = SPACING["medium"]) -> QWidget:
        spacer = QWidget()
        spacer.setFixedHeight(spacing)
        return spacer
        

def wait_for_thread(thread: threading.Thread, sleep_interval=None):
    """
    Waits for a thread to finish while processing UI events at regular intervals
    to prevent UI freezing and excessive CPU usage.

    Args:
        thread: The thread to wait for
        sleep_interval: Optional sleep interval in seconds, defaults to Constants.thread_sleep_interval
    """
    # Use the passed sleep_interval, or get from global_constants
    interval = sleep_interval if sleep_interval is not None else Constants().thread_sleep_interval

    while thread.is_alive():
        QApplication.processEvents()  # Process Qt events instead of wx.Yield()
        thread.join(timeout=interval)