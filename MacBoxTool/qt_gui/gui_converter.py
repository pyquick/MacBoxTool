"""
gui_converter.py: GUI for converting macOS 26 .icon files to Assets.car and AppIcon.icns

Design uses:
- gui_update.py pattern: SettingCardGroup + PushSettingCard for import/export
- gui_hardware_support.py pattern: _row / _separator for icon info display
"""

from ..include import *
from .gui_support import DefGUI
from ..support.icon_to_assets import convert_icon_file_streaming as _convert_streaming

from PySide6.QtCore import QThread, Signal


# ---------------------------------------------------------------------------
# Background worker
# ---------------------------------------------------------------------------

class _ConvertWorker(QThread):
    log_line = Signal(str)
    finished = Signal(bool, str, str, str)

    def __init__(self, icon_path: str, parent=None):
        super().__init__(parent)
        self.icon_path = icon_path

    def run(self):
        try:
            car, icns = _convert_streaming(self.icon_path, on_log=lambda line: (
                print(line),
                self.log_line.emit(line),
            ))
            self.finished.emit(True, str(car), str(icns), "")
        except Exception as e:
            self.finished.emit(False, "", "", str(e))


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

class IconConverterInterface(ScrollArea):

    def __init__(
        self,
        global_constants: Constants,
        ui_support: DefGUI = None,
        global_settings: GlobalSettings = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("IconConverter")
        self.constants = global_constants
        self.gui_support = ui_support
        self.settings = global_settings

        self.scrollWidget = QWidget()
        self.expandLayout = QVBoxLayout(self.scrollWidget)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)
        self.enableTransparentBackground()

        self._selected_icon = ""
        self._out_car = ""
        self._out_icns = ""
        self._export_car = ""
        self._export_icns = ""
        self._worker: _ConvertWorker | None = None

        self._build_ui()

    # ==================================================================
    # Shared building blocks
    # ==================================================================

    def _row(self, icon: FluentIcon, title: str, subtitle="", color=None) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING["medium"])

        if self.gui_support:
            iw = self.gui_support.build_icon_label(icon, color or COLORS["primary"], size=22)
        else:
            iw = QLabel()
            iw.setPixmap(icon.icon(color=color or COLORS["primary"]).pixmap(22, 22))
            iw.setAlignment(Qt.AlignmentFlag.AlignCenter)
        iw.setFixedWidth(30)
        layout.addWidget(iw, 0, Qt.AlignmentFlag.AlignTop)

        t = QVBoxLayout()
        t.setContentsMargins(0, 0, 0, 0)
        t.setSpacing(2)
        tl = BodyLabel(title)
        if color:
            tl.setTextColor(color, color)
            f = tl.font()
            f.setWeight(QFont.Weight.DemiBold)
            tl.setFont(f)
        t.addWidget(tl)
        if subtitle:
            s = CaptionLabel(subtitle)
            s.setWordWrap(True)
            t.addWidget(s)
        layout.addLayout(t, 1)
        return row

    def _hw_card(self, heading_text: str) -> tuple[CardWidget, QVBoxLayout]:
        c = CardWidget()
        c.setBorderRadius(RADIUS["card"])
        l = QVBoxLayout(c)
        l.setContentsMargins(SPACING["large"], SPACING["large"], SPACING["large"], SPACING["large"])
        l.setSpacing(SPACING["medium"])

        h = StrongBodyLabel(heading_text)
        f = h.font()
        f.setPixelSize(16)
        f.setWeight(QFont.Weight.DemiBold)
        h.setFont(f)
        l.addWidget(h)
        return c, l

    @staticmethod
    def _replace_content(layout: QVBoxLayout, content_start: int):
        while layout.count() > content_start:
            item = layout.takeAt(content_start)
            w = item.widget()
            if w:
                w.deleteLater()
            elif item.layout():
                IconConverterInterface._clear_layout(item.layout())

    # ==================================================================
    # Helpers
    # ==================================================================

    @staticmethod
    def _dir_size(p: Path) -> int:
        total = 0
        for f in p.rglob("*"):
            if f.is_file():
                total += f.stat().st_size
        return total

    @staticmethod
    def _fmt_size(size: int) -> str:
        if size <= 0:
            return "Unknown"
        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024:
                return f"{size:.1f} {unit}" if unit != "B" else f"{size} B"
            size /= 1024
        return f"{size:.1f} TB"

    @staticmethod
    def _clear_layout(layout):
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
            elif item.layout():
                IconConverterInterface._clear_layout(item.layout())

    # ==================================================================
    # Build UI
    # ==================================================================

    def _build_ui(self):
        self.expandLayout.setContentsMargins(
            SPACING["xxlarge"], SPACING["xlarge"],
            SPACING["xxlarge"], SPACING["xlarge"],
        )
        self.expandLayout.setSpacing(SPACING["large"])
        
        converter_text=SubtitleLabel("Icon Converter")
        converter_text.setStyleSheet("font-size: 24px; font-weight: bold;")
        self.expandLayout.addWidget(converter_text)

        self._build_import_group()
        self._build_export_group()
        self._build_info_card()
        self._build_action_card()
        self._build_build_card()
        self._build_result_card()

        self.expandLayout.addStretch()

    # ── Import group (SettingCardGroup + PushSettingCard) ──

    def _build_import_group(self):
        self.import_group = SettingCardGroup("Import", self.scrollWidget)

        self.import_card = PushSettingCard(
            text="Browse",
            icon=FluentIcon.PHOTO,
            title="Import .icon File",
            content="No file selected",
            parent=self.import_group,
        )
        self.import_card.clicked.connect(self._browse_icon)

        self.import_group.addSettingCard(self.import_card)
        self.expandLayout.addWidget(self.import_group)

    # ── Export group ──

    def _build_export_group(self):
        self.export_group = SettingCardGroup("Export", self.scrollWidget)

        self.export_car_card = PushSettingCard(
            text="Choose",
            icon=FluentIcon.SAVE,
            title="Assets.car",
            content="Not set — will prompt after conversion",
            parent=self.export_group,
        )
        self.export_car_card.clicked.connect(self._choose_export_car)

        self.export_icns_card = PushSettingCard(
            text="Choose",
            icon=FluentIcon.SAVE,
            title="AppIcon.icns",
            content="Not set — will prompt after conversion",
            parent=self.export_group,
        )
        self.export_icns_card.clicked.connect(self._choose_export_icns)

        self.export_group.addSettingCard(self.export_car_card)
        self.export_group.addSettingCard(self.export_icns_card)
        self.expandLayout.addWidget(self.export_group)

    # ── Info card (HW support style) ──

    def _build_info_card(self):
        self.info_card, self.info_layout = self._hw_card("Icon Information")
        self.info_card.hide()
        self.expandLayout.addWidget(self.info_card)

    def _refresh_info(self, path: str):
        p = Path(path)
        is_bundle = p.is_dir()
        name = p.name

        if is_bundle:
            type_text = "macOS 26 Icon Bundle"
            assets_dir = p / "Assets"
            count = len(list(assets_dir.glob("*"))) if assets_dir.is_dir() else 0
            detail = f"{count} asset(s)"
        else:
            type_text = "File"
            detail = name

        size = self._fmt_size(self._dir_size(p) if is_bundle else p.stat().st_size)

        self._replace_content(self.info_layout, 1)
        self.info_layout.addWidget(self._row(FluentIcon.TAG, name, "File name"))
        self.info_layout.addWidget(self._row(FluentIcon.DEVELOPER_TOOLS, type_text, detail))
        self.info_layout.addWidget(self._row(FluentIcon.CODE, size, "Total size"))

    # ── Action card ──

    def _build_action_card(self):
        self.action_card, self.action_layout = self._hw_card("Convert")

        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(SPACING["medium"])

        self.convert_btn = PushButton(FluentIcon.DEVELOPER_TOOLS, "Convert to Assets.car & AppIcon.icns")
        self.convert_btn.setFixedHeight(40)
        setCustomStyleSheet(
            self.convert_btn,
            "PushButton { border-radius: 20px; }",
            "PushButton { border-radius: 20px; }",
        )
        self.convert_btn.clicked.connect(self._start_conversion)
        self.convert_btn.setEnabled(False)
        l.addWidget(self.convert_btn)

        self.action_layout.addWidget(w)
        self.expandLayout.addWidget(self.action_card)

    # ── Build card ──

    def _build_build_card(self):
        self.build_card, self.build_layout = self._hw_card("Building")

        bar_w = QWidget()
        bl = QVBoxLayout(bar_w)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(SPACING["medium"])
        self.build_bar = IndeterminateProgressBar(start=False)
        bl.addWidget(self.build_bar)

        self.build_layout.addWidget(bar_w)

        log_w = QWidget()
        ll = QVBoxLayout(log_w)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(SPACING["medium"])

        self.build_log = TextEdit()
        self.build_log.setReadOnly(True)
        self.build_log.setMinimumHeight(200)
        ll.addWidget(self.build_log)

        self.build_layout.addWidget(log_w)

        self.build_card.hide()
        self.expandLayout.addWidget(self.build_card)

    # ── Result card ──

    def _build_result_card(self):
        self.result_card, self.result_layout = self._hw_card("Conversion Complete")
        self.result_card.hide()
        self.expandLayout.addWidget(self.result_card)

    def _refresh_result(self, car_path: str, icns_path: str):
        self._replace_content(self.result_layout, 1)

        car_size = self._fmt_size(Path(car_path).stat().st_size)
        icns_size = self._fmt_size(Path(icns_path).stat().st_size)

        # Assets.car
        car_row = self._row(FluentIcon.ACCEPT, "Assets.car", car_size, COLORS["success"])
        self._add_row_button(car_row, "Save", self._save_car)
        self.result_layout.addWidget(car_row)

        # AppIcon.icns
        icns_row = self._row(FluentIcon.ACCEPT, "AppIcon.icns", icns_size, COLORS["success"])
        self._add_row_button(icns_row, "Save", self._save_icns)
        self.result_layout.addWidget(icns_row)

        # Actions
        aw = QWidget()
        al = QHBoxLayout(aw)
        al.setContentsMargins(0, 0, 0, 0)
        al.setSpacing(SPACING["medium"])
        sb = PrimaryPushButton("Save Both")
        sb.clicked.connect(self._save_both)
        al.addWidget(sb)
        ca = PushButton("Convert Another")
        ca.clicked.connect(self._reset)
        al.addWidget(ca)
        self.result_layout.addWidget(aw)

    @staticmethod
    def _add_row_button(row: QWidget, label: str, slot):
        btn = PushButton(label)
        btn.setFixedWidth(80)
        btn.clicked.connect(slot)
        row.layout().addWidget(btn)

    # ==================================================================
    # Slots
    # ==================================================================

    def _browse_icon(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select .icon File", "",
            "Icon Files (*.icon);;All Files (*)",
        )
        if path:
            self._selected_icon = path
            self.import_card.setContent(path)
            self._refresh_info(path)
            self.info_card.show()
            self.convert_btn.setEnabled(True)

    def _choose_export_car(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Assets.car", "Assets.car",
            "Asset Catalog (*.car);;All Files (*)",
        )
        if path:
            self._export_car = path
            self.export_car_card.setContent(path)

    def _choose_export_icns(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save AppIcon.icns", "AppIcon.icns",
            "ICNS Files (*.icns);;All Files (*)",
        )
        if path:
            self._export_icns = path
            self.export_icns_card.setContent(path)

    def _start_conversion(self):
        if not self._selected_icon:
            return

        self.convert_btn.setEnabled(False)
        self.result_card.hide()
        self.build_log.clear()
        self._append_log("=== Starting conversion ===\n")
        self.build_card.show()
        self.build_bar.start()

        self._worker = _ConvertWorker(self._selected_icon, self)
        self._worker.log_line.connect(self._append_log)
        self._worker.finished.connect(self._on_conversion_done)
        self._worker.start()

    def _append_log(self, line: str):
        self.build_log.append(line)

    def _on_conversion_done(self, success, car_path, icns_path, error_msg):
        self.convert_btn.setEnabled(True)
        self.build_bar.stop()
        self.build_card.hide()
        self._append_log(f"\n=== {'SUCCESS' if success else 'FAILED'} ===\n")

        if not success:
            InfoBar.error(
                "Conversion Failed", error_msg,
                duration=5000, position=InfoBarPosition.BOTTOM_RIGHT,
                parent=self,
            )
            return

        # Copy to pre-selected export paths
        if self._export_car:
            shutil.copy2(car_path, self._export_car)
        if self._export_icns:
            shutil.copy2(icns_path, self._export_icns)

        self._out_car = car_path
        self._out_icns = icns_path

        self._refresh_result(car_path, icns_path)
        self.result_card.show()

        InfoBar.success(
            "Conversion Complete",
            "Assets.car and AppIcon.icns are ready.",
            duration=3000, position=InfoBarPosition.BOTTOM_RIGHT,
            parent=self,
        )

    def _reset(self):
        self._out_car = ""
        self._out_icns = ""
        self._export_car = ""
        self._export_icns = ""
        self.export_car_card.setContent("Not set — will prompt after conversion")
        self.export_icns_card.setContent("Not set — will prompt after conversion")
        self.result_card.hide()
        self.build_card.hide()
        self._selected_icon = ""
        self.import_card.setContent("No file selected")
        self.info_card.hide()
        self.convert_btn.setEnabled(False)

    def _save_car(self):
        if not self._out_car:
            return
        dest, _ = QFileDialog.getSaveFileName(
            self, "Save Assets.car", "Assets.car",
            "Asset Catalog (*.car);;All Files (*)",
        )
        if dest:
            shutil.copy2(self._out_car, dest)
            InfoBar.success("Saved", "Assets.car saved",
                            duration=3000, position=InfoBarPosition.BOTTOM_RIGHT, parent=self)

    def _save_icns(self):
        if not self._out_icns:
            return
        dest, _ = QFileDialog.getSaveFileName(
            self, "Save AppIcon.icns", "AppIcon.icns",
            "ICNS Files (*.icns);;All Files (*)",
        )
        if dest:
            shutil.copy2(self._out_icns, dest)
            InfoBar.success("Saved", "AppIcon.icns saved",
                            duration=3000, position=InfoBarPosition.BOTTOM_RIGHT, parent=self)

    def _save_both(self):
        dest_dir = QFileDialog.getExistingDirectory(self, "Save Both Files To...")
        if dest_dir:
            shutil.copy2(self._out_car, dest_dir)
            shutil.copy2(self._out_icns, dest_dir)
            InfoBar.success("Saved",
                            f"Assets.car and AppIcon.icns saved to {dest_dir}",
                            duration=3000, position=InfoBarPosition.BOTTOM_RIGHT, parent=self)

    def closeEvent(self, event):
        if self._worker and self._worker.isRunning():
            self._worker.wait(5000)
        super().closeEvent(event)
