# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller specification for the one-file Windows MacBoxTool setup."""

from pathlib import Path

from PyInstaller.building.api import EXE, PYZ
from PyInstaller.building.build_main import Analysis

ROOT = Path(SPECPATH).parent.parent
SETUP_DIR = ROOT / "MacBoxTool" / "setup"
ICON = ROOT / "payloads" / "Icon" / "AppIcons" / "AppIcon.ico"
APP_DIST = ROOT / "dist" / "windows" / "app" / "MacBoxTool"

if not ICON.exists():
    raise FileNotFoundError(f"Windows icon was not generated: {ICON}")
if not APP_DIST.is_dir() or not (APP_DIST / "MacBoxTool.exe").is_file():
    raise FileNotFoundError(
        "Build MacBoxTool.exe before building setup: "
        f"missing {APP_DIST / 'MacBoxTool.exe'}"
    )

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

# The compiled non-onefile MacBoxTool directory is embedded as a data tree in
# this one-file setup executable.  It is extracted only while setup runs, then
# copied to the chosen installation location.
a = Analysis(
    [str(SETUP_DIR / "setup_wizard.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(APP_DIST), "MacBoxTool"),
        (str(ICON), "."),
    ],
    hiddenimports=["win32com.client", "pythoncom", "darkdetect"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDED_MODULES,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

# No COLLECT object: this produces exactly one setup executable.  UPX remains
# disabled for both the executable and all bundled application files.
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="MacBoxTool_Setup",
    icon=str(ICON),
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
)
