"""Graphical Windows installer for the compiled MacBoxTool application."""

from __future__ import annotations

import argparse
import ctypes
import os
import shutil
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QMessageBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from MacBoxTool.UIkit import (
    BodyLabel,
    CardWidget,
    CheckBox,
    FluentWidget,
    LineEdit,
    PrimaryPushButton,
    ProgressBar,
    PushButton,
    StrongBodyLabel,
    SubtitleLabel,
    TitleLabel,
)


APP_NAME = "MacBoxTool"


def bundled_root() -> Path:
    """Return the root extracted by PyInstaller or the source checkout."""
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))


def default_install_dir() -> Path:
    program_files = os.environ.get("ProgramFiles", r"C:\\Program Files")
    return Path(program_files) / APP_NAME


def start_menu_dir() -> Path:
    return (
        Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs"
        / APP_NAME
    )


def is_elevated() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


def installation_requires_elevation(target: Path) -> bool:
    """Return whether writing the selected location requires elevation."""
    if is_elevated():
        return False

    probe = target
    while not probe.exists() and probe.parent != probe:
        probe = probe.parent

    test_file = probe / f".{APP_NAME}.write-test"
    try:
        with test_file.open("x", encoding="utf-8"):
            pass
        test_file.unlink()
        return False
    except OSError:
        return True


def relaunch_as_admin(install_dir: Path) -> None:
    """Relaunch setup elevated and resume immediately at installation."""
    arguments = subprocess.list2cmdline(
        ["--install-dir", str(install_dir), "--start-install"]
    )
    if getattr(sys, "frozen", False):
        executable = str(Path(sys.executable).resolve())
        parameters = arguments
    else:
        executable = sys.executable
        parameters = f'"{Path(__file__).resolve()}" {arguments}'

    result = ctypes.windll.shell32.ShellExecuteW(None, "runas", executable, parameters, None, 1)
    if result <= 32:
        raise OSError("Administrator privileges are required to install MacBoxTool.")


def copy_tree(source: Path, destination: Path) -> None:
    """Copy source atomically enough to avoid stale files from earlier installs."""
    if not source.is_dir():
        raise FileNotFoundError(f"Setup payload is missing: {source}")

    temporary = destination.with_name(f".{destination.name}.installing")
    if temporary.exists():
        shutil.rmtree(temporary)
    shutil.copytree(source, temporary)

    backup = destination.with_name(f".{destination.name}.previous")
    if backup.exists():
        shutil.rmtree(backup)
    if destination.exists():
        destination.replace(backup)

    try:
        temporary.replace(destination)
    except Exception:
        if backup.exists() and not destination.exists():
            backup.replace(destination)
        raise
    finally:
        if temporary.exists():
            shutil.rmtree(temporary, ignore_errors=True)
        if backup.exists():
            shutil.rmtree(backup, ignore_errors=True)


def create_shortcut(target: Path, icon: Path) -> Path:
    """Create the current-user Start Menu shortcut without a shell command."""
    try:
        from win32com.client import Dispatch
    except ImportError as error:
        raise RuntimeError("pywin32 is not bundled; cannot create the Start Menu shortcut.") from error

    folder = start_menu_dir()
    folder.mkdir(parents=True, exist_ok=True)
    shortcut_path = folder / f"{APP_NAME}.lnk"
    shell = Dispatch("WScript.Shell")
    shortcut = shell.CreateShortCut(str(shortcut_path))
    shortcut.Targetpath = str(target)
    shortcut.WorkingDirectory = str(target.parent)
    shortcut.IconLocation = f"{icon},0"
    shortcut.Description = "MacBoxTool"
    shortcut.Save()
    return shortcut_path


class InstallerWorker(QThread):
    progress_changed = Signal(int, str)
    succeeded = Signal(str)
    failed = Signal(str)

    def __init__(self, install_dir: Path):
        super().__init__()
        self.install_dir = install_dir

    def run(self) -> None:
        try:
            source = bundled_root() / "MacBoxTool"
            target = self.install_dir
            executable = target / "MacBoxTool.exe"
            icon = target / "_internal" / "payloads" / "Icon" / "AppIcons" / "AppIcon.ico"

            self.progress_changed.emit(10, "正在准备安装目录…")
            target.parent.mkdir(parents=True, exist_ok=True)
            self.progress_changed.emit(30, "正在复制 MacBoxTool…")
            copy_tree(source, target)

            if not executable.is_file():
                raise FileNotFoundError(f"安装包不完整，找不到 {executable.name}")
            if not icon.is_file():
                raise FileNotFoundError("安装包不完整，找不到应用图标")

            self.progress_changed.emit(80, "正在创建开始菜单快捷方式…")
            create_shortcut(executable, icon)

            self.progress_changed.emit(100, "安装完成")
            self.succeeded.emit(str(executable))
        except Exception as error:  # UI reports the exact error to the user.
            self.failed.emit(str(error))


class SetupPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(42, 32, 42, 32)
        self.layout.setSpacing(16)

    def add_heading(self, title: str, subtitle: str) -> None:
        title_label = TitleLabel(title, self)
        subtitle_label = BodyLabel(subtitle, self)
        subtitle_label.setWordWrap(True)
        self.layout.addWidget(title_label)
        self.layout.addWidget(subtitle_label)


class WelcomePage(SetupPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.add_heading("安装 MacBoxTool", "Windows 版安装程序将安装已编译的 MacBoxTool，无需下载或挂载任何 DMG 镜像。")
        card = CardWidget(self)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 20, 24, 20)
        card_layout.addWidget(SubtitleLabel("准备就绪", card))
        detail = BodyLabel("点击“下一步”选择安装位置。安装完成后将在开始菜单创建 MacBoxTool 快捷方式。", card)
        detail.setWordWrap(True)
        card_layout.addWidget(detail)
        self.layout.addWidget(card)
        self.layout.addStretch(1)


class LocationPage(SetupPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.add_heading("选择安装位置", "选择需要管理员权限的位置时，安装程序会在安装前自动请求提升权限。")

        self.path_edit = LineEdit(self)
        self.path_edit.setText(str(default_install_dir()))
        self.path_edit.setClearButtonEnabled(False)
        self.path_edit.setMinimumWidth(420)
        self.browse_button = PushButton("浏览…", self)
        self.browse_button.clicked.connect(self.browse)

        row = QHBoxLayout()
        row.addWidget(self.path_edit, 1)
        row.addWidget(self.browse_button)
        self.layout.addLayout(row)

        self.overwrite = CheckBox("如目标文件夹已存在，替换其中的 MacBoxTool 文件", self)
        self.overwrite.setChecked(True)
        self.layout.addWidget(self.overwrite)
        self.layout.addStretch(1)

    def browse(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "选择安装目录", self.path_edit.text())
        if selected:
            self.path_edit.setText(str(Path(selected) / APP_NAME))

    def installation_dir(self) -> Path:
        return Path(self.path_edit.text().strip()).expanduser()


class InstallPage(SetupPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.add_heading("正在安装", "请不要关闭安装程序。")
        self.status = StrongBodyLabel("等待开始…", self)
        self.progress = ProgressBar(self, useAni=False)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.layout.addWidget(self.status)
        self.layout.addWidget(self.progress)
        self.layout.addStretch(1)

    def update_progress(self, value: int, message: str) -> None:
        self.progress.setValue(value)
        self.status.setText(message)


class FinishPage(SetupPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.add_heading("MacBoxTool 已安装", "可从开始菜单启动 MacBoxTool。")
        self.launch = CheckBox("现在启动 MacBoxTool", self)
        self.launch.setChecked(True)
        self.layout.addWidget(self.launch)
        self.layout.addStretch(1)


class SetupWindow(FluentWidget):
    """A Fluent-styled, wizard-like installer without a navigation sidebar."""

    def __init__(self):
        super().__init__()
        self.requested_install_dir = self._requested_install_dir()
        self.start_install_requested = self._start_install_requested()
        self.worker: InstallerWorker | None = None
        self.installed_executable: Path | None = None
        self.setWindowTitle("MacBoxTool 安装程序")
        self.setMinimumSize(680, 460)
        self.resize(760, 520)
        self.setMicaEffectEnabled(True)

        root = QWidget(self)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, self.titleBar.height(), 0, 0)
        root_layout.setSpacing(0)

        self.pages = QStackedWidget(root)
        self.welcome_page = WelcomePage(self.pages)
        self.location_page = LocationPage(self.pages)
        if self.requested_install_dir:
            self.location_page.path_edit.setText(str(self.requested_install_dir))
        self.install_page = InstallPage(self.pages)
        self.finish_page = FinishPage(self.pages)
        for page in (self.welcome_page, self.location_page, self.install_page, self.finish_page):
            self.pages.addWidget(page)
        root_layout.addWidget(self.pages, 1)

        footer = QWidget(root)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(42, 16, 42, 24)
        footer_layout.setSpacing(10)
        self.back_button = PushButton("上一步", footer)
        self.next_button = PrimaryPushButton("下一步", footer)
        self.cancel_button = PushButton("取消", footer)
        footer_layout.addWidget(self.back_button)
        footer_layout.addStretch(1)
        footer_layout.addWidget(self.cancel_button)
        footer_layout.addWidget(self.next_button)
        root_layout.addWidget(footer)

        self.setLayout(QVBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().addWidget(root)

        self.back_button.clicked.connect(self.go_back)
        self.next_button.clicked.connect(self.go_next)
        self.cancel_button.clicked.connect(self.close)
        self.update_buttons()
        if self.start_install_requested:
            # The elevated instance must never render the welcome page before it
            # starts copying the already-selected installation target.
            self.start_installation()

    @staticmethod
    def _elevated_install_request() -> Path | None:
        """Parse the exact request passed to an elevated setup instance."""
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument("--install-dir")
        parser.add_argument("--start-install", action="store_true")
        args, _ = parser.parse_known_args()
        if not args.start_install or not args.install_dir:
            return None
        return Path(args.install_dir).expanduser()

    @staticmethod
    def _requested_install_dir() -> Path | None:
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument("--install-dir")
        args, _ = parser.parse_known_args()
        return Path(args.install_dir).expanduser() if args.install_dir else None

    @classmethod
    def _start_install_requested(cls) -> bool:
        return cls._elevated_install_request() is not None

    def update_buttons(self) -> None:
        index = self.pages.currentIndex()
        self.back_button.setVisible(index == 1)
        self.cancel_button.setVisible(index < 2)
        self.next_button.setVisible(index != 2)
        self.next_button.setText("安装" if index == 1 else "完成" if index == 3 else "下一步")

    def go_back(self) -> None:
        self.pages.setCurrentIndex(0)
        self.update_buttons()

    def go_next(self) -> None:
        index = self.pages.currentIndex()
        if index == 0:
            self.pages.setCurrentIndex(1)
            self.update_buttons()
        elif index == 1:
            self.start_installation()
        elif index == 3:
            self.finish()

    def start_installation(self) -> None:
        target = self.location_page.installation_dir()
        if not target.name:
            QMessageBox.warning(self, "无效位置", "请选择有效的安装路径。")
            return
        if target.exists() and not self.location_page.overwrite.isChecked():
            QMessageBox.warning(self, "目标已存在", "目标文件夹已存在，请允许替换或选择其他位置。")
            return

        if installation_requires_elevation(target):
            try:
                relaunch_as_admin(target)
            except OSError as error:
                QMessageBox.critical(self, "需要管理员权限", str(error))
                return
            QApplication.quit()
            return

        self.pages.setCurrentIndex(2)
        self.update_buttons()
        self.worker = InstallerWorker(target)
        self.worker.progress_changed.connect(self.install_page.update_progress)
        self.worker.succeeded.connect(self.installation_succeeded)
        self.worker.failed.connect(self.installation_failed)
        self.worker.start()

    def installation_succeeded(self, executable: str) -> None:
        self.installed_executable = Path(executable)
        self.pages.setCurrentIndex(3)
        self.update_buttons()

    def installation_failed(self, message: str) -> None:
        QMessageBox.critical(self, "安装失败", message)
        self.pages.setCurrentIndex(1)
        self.update_buttons()

    def finish(self) -> None:
        if self.finish_page.launch.isChecked() and self.installed_executable:
            subprocess.Popen([str(self.installed_executable)], cwd=str(self.installed_executable.parent))
        self.close()

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            QMessageBox.information(self, "正在安装", "安装正在进行，请等待完成。")
            event.ignore()
            return
        event.accept()


def main() -> None:
    if sys.platform != "win32":
        raise SystemExit("MacBoxTool Setup can only run on Windows.")
    application = QApplication(sys.argv)
    application.setApplicationName("MacBoxTool Setup")
    application.setOrganizationName("Pyquick")
    application.setWindowIcon(QIcon(str(bundled_root() / "AppIcon.ico")))
    window = SetupWindow()
    window.show()
    raise SystemExit(application.exec())


if __name__ == "__main__":
    main()
