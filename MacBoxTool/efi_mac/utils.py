"""
utils.py: Utility functions for EFI building
"""


import logging
import os
import shutil
import stat
import time
from pathlib import Path

logger = logging.getLogger(__name__)


def rmtree_handler(func, path, exc_info):
    """
    Error handler for shutil.rmtree with Windows file lock support.

    On Windows PermissionError:
    1. Try to clear read-only bit
    2. Wait briefly and retry (up to 3 times)
    3. If still fails, log warning but continue (don't fail build)
    """
    # Ignore FileNotFoundError (file already deleted)
    if exc_info[0] == FileNotFoundError:
        return

    # Windows file lock or non-empty dir - try to recover
    if exc_info[0] in (PermissionError, OSError):
        # Try clearing read-only bit
        try:
            os.chmod(path, stat.S_IWRITE)
            func(path)
            return
        except Exception:
            pass

        # Retry after brief delay (files may be temporarily locked)
        for i in range(3):
            time.sleep(0.1)
            try:
                func(path)
                return
            except Exception:
                continue

        # Log but don't fail - user can manually delete if needed
        logger.warning(f"Could not remove {path} (may be locked by another process)")
        return

    raise


def find_kext_zip(payload_kexts_path: Path, kext_name: str) -> Path | None:
    """
    Search for a kext zip in payload subdirectories.

    Args:
        payload_kexts_path: Path to the Kexts payload directory
        kext_name: Name of the kext (with or without .kext suffix)

    Returns:
        Path to the kext zip file, or None if not found
    """
    name = kext_name.replace(".kext", "").lower()

    release = None
    debug = None

    # Case-insensitive search across all zip files
    for p in payload_kexts_path.rglob("*.zip"):
        if p.name.lower().startswith(name):
            if "debug" not in p.name.lower():
                release = p
            else:
                debug = p

    return release or debug


def find_acpi_file(payload_acpi_path: Path, acpi_name: str) -> Path | None:
    """
    Search for an ACPI file in payload directory.

    Args:
        payload_acpi_path: Path to the ACPI payload directory
        acpi_name: Name of the ACPI file (with or without .aml suffix)

    Returns:
        Path to the ACPI file, or None if not found
    """
    name = acpi_name.replace(".aml", "")
    aml_path = payload_acpi_path / f"{name}.aml"
    if aml_path.exists():
        return aml_path
    return None
