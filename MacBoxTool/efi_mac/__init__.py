"""
efi_mac: Modular EFI builder for unsupported Macs

This module provides a modular architecture for building OpenCore EFI
for unsupported Mac models. The main entry point is BuildOpenCore in
builder.py, which coordinates various specialized modules.

Example:
    from MacBoxTool.efi_mac import BuildOpenCore
    from MacBoxTool.constants import Constants

    constants = Constants()
    builder = BuildOpenCore("MacPro7,1", constants)
    logs = builder.build()
"""

# Core modules
from .builder import BuildOpenCore
from .base import BaseGenerator
from .config import ConfigManager
from .utils import rmtree_handler, find_kext_zip, find_acpi_file

# Submodules
from .kexts import KextManager
from .acpi import ACPIManager
from .drivers import DriverManager
from .smbios import SMBIOSManager

__all__ = [
    # Core
    "BuildOpenCore",
    "BaseGenerator",
    "ConfigManager",
    "rmtree_handler",
    "find_kext_zip",
    "find_acpi_file",
    # Submodules
    "KextManager",
    "ACPIManager",
    "DriverManager",
    "SMBIOSManager",
]
