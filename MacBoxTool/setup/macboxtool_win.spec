# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller specification for the Windows MacBoxTool application."""

from pathlib import Path

from PyInstaller.building.api import COLLECT, EXE, PYZ
from PyInstaller.building.build_main import Analysis

ROOT = Path(SPECPATH).parent.parent
ENTRY_POINT = ROOT / "MacBoxTool" / "setup" / "app_entry_win.py"
ICON = ROOT / "payloads" / "Icon" / "AppIcons" / "AppIcon.ico"

if not ICON.exists():
    raise FileNotFoundError(f"Windows icon was not generated: {ICON}")

# Dependencies installed in a developer environment must not silently become part
# of the release.  These libraries are neither imported by MacBoxTool nor
# required by the Windows application bundle.
EXCLUDED_MODULES = [
    "tkinter",
    "matplotlib",
    "pytest",
    "unittest",
    "torch",
    "torchaudio",
    "tensorflow",
    "onnxruntime",
    "transformers",
    "pandas",
    "numba",
    "llvmlite",
    "sklearn",
    "librosa",
    "soundfile",
    "openpyxl",
    "fsspec",
    "rich",
    "uvicorn",
    "IPython",
    "jupyter",
    "notebook",
]

# Windows packages the local payload directory in the application's internal
# data directory. It does not package or mount payloads.dmg or
# Universal-Binaries.dmg.
a = Analysis(
    [str(ENTRY_POINT)],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[(str(ROOT / "payloads"), "payloads")],
    hiddenimports=[
        "MacBoxTool.qt_gui.gui_main_menu",
        "MacBoxTool.qt_gui.gui_macos_installer",
        "MacBoxTool.qt_gui.gui_settings",
        "MacBoxTool.qt_gui.gui_introduction",
        "win32com.client",
        "pythoncom",
        "wmi",
        "darkdetect",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDED_MODULES,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MacBoxTool",
    icon=str(ICON),
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="MacBoxTool",
)
