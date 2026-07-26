# -*- mode: python ; coding: utf-8 -*-

import os
import sys
import time
import subprocess

from pathlib import Path

from PyInstaller.building.api import PYZ, EXE, COLLECT
from PyInstaller.building.osx import BUNDLE
from PyInstaller.building.build_main import Analysis

sys.path.append(os.path.abspath(os.getcwd()))

from MacBoxTool import constants

block_cipher = None

datas = [
   ('payloads/Icon/AppIcons/Assets.car', '.'),
   ('payloads.dmg', '.'),
   ('Universal-Binaries.dmg', '.'),
]

if Path("PyquickInternalResources.dmg").exists():
   datas.append(('PyquickInternalResources.dmg', '.'))

a = Analysis(['MaxBoxTool_GUI.command'],
             pathex=[],
             binaries=[],
             datas=datas,
             hiddenimports=[],
             hookspath=[],
             hooksconfig={},
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)

pyz = PYZ(a.pure,
          a.zipped_data,
          cipher=block_cipher)

exe = EXE(pyz,
          a.scripts,
          [],
          exclude_binaries=True,
          name='MacBoxTool',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          console=False,
          disable_windowed_traceback=False,
          target_arch=None,
          codesign_identity=None,
          entitlements_file=None)

coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               upx_exclude=[],
               name='MacBoxTool')

app = BUNDLE(coll,
             name='MacBoxTool.app',
             icon="payloads/Icon/AppIcons/AppIcon.icns",
             bundle_identifier="com.pyquick.macboxtool",
             info_plist={
                "CFBundleName": "MacBoxTool",
                "CFBundleVersion": constants.Constants().macboxtool_version,
                "CFBundleShortVersionString": constants.Constants().macboxtool_version,
                "NSHumanReadableCopyright": constants.Constants().copyright,
                "LSMinimumSystemVersion": "10.15.0",
                "NSRequiresAquaSystemAppearance": False,
                "NSHighResolutionCapable": True,
                "Build Date": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                "BuildMachineOSBuild": subprocess.run(["/usr/bin/sw_vers", "-buildVersion"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout.decode().strip(),
                "NSPrincipalClass": "NSApplication",
                "CFBundleIconName": "macboxtool",
             })

