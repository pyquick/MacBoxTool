"""
gui_go_in.py: Go to Gui
"""


from ..include import *
from . import (
    gui_about,
    gui_all_download,
    gui_build,
    gui_download,
    gui_introduction,
    gui_ipsw_download,
    gui_kdk,
    gui_macos_installer,
    gui_main_menu,
    gui_metallib,
    gui_model,
    gui_settings,
    gui_sys_patch,
    gui_task,
    gui_update
)
class SupportedEntryPoints:
    """
    GUI entry.
    """
    INTRODUCTION = gui_introduction.Introduction
    OS_CACHE = ... # gui_os_update.py
    BUILD_OC= gui_build.BuildOCPage._on_build
    INSTALL_OC_UI = gui_build.BuildOCPage
    SYS_PATCH = gui_sys_patch.SysPatch.start_root_patching


class OpenGUI:
    def __init__(self,global_constants:Constants,global_settings:GlobalSettings):
        self.constants:Constants = global_constants
        self.settings=global_settings
        logging.info("Init GuiBase")

    def gui_main_menu(self):
        import sys as _sys
        from .. import app_entry as _app_entry
        from .gui_main_menu import Window

        app = QApplication(_sys.argv)
        w = Window(self.constants,self.settings)

        # Save references globally for signal handler access
        _app_entry._qt_app = app
        _app_entry._qt_window = w

        w.show()
        app.exec_()


class EntryPoint:
    """Launch GUI with specific entry point. Qt-compatible replacement for OCLP-R wx.EntryPoint."""

    def __init__(self, global_constants: Constants):
        self.constants: Constants = global_constants
        self.constants.gui_mode = True

    def start(self, entry=None):
        if entry is None:
            entry = SupportedEntryPoints.INTRODUCTION

        # Map entry to Window navigation flags
        if entry == SupportedEntryPoints.SYS_PATCH:
            self.constants.start_sys_patch = True
            self.constants.start_sys_patch_now = True
        elif entry == SupportedEntryPoints.INSTALL_OC_UI:
            self.constants.start_build_install = True
        elif entry == SupportedEntryPoints.OS_CACHE:
            logging.warning("OS_CACHE entry point is not yet implemented, falling back to main menu")
            entry = SupportedEntryPoints.INTRODUCTION

        from ..support.global_settings import GlobalSettings
        settings = GlobalSettings(self.constants)
        gui = OpenGUI(self.constants, settings)
        gui.gui_main_menu()
    