"""
support: Shared code for MacBoxTool, organized by category.

Modules are grouped by what they do, not by who uses them:

    system/       Host OS and process primitives (utilities, subprocess_wrapper,
                  install_helper, scan_disk_efi)
    artifacts/    Downloaded and installed package domain (KDK, metallib,
                  installer, integrity verification, validation)
    config/       Persisted settings and build/branch identity
    diagnostics/  Logging, crash reporting and analytics
    net/          Network transport and remote API helpers
    ui/           Qt-facing shared helpers (colors, theme, assets)
    hardware/     SMBIOS generation and the hardware compatibility checker
    mount/        Root volume, EFI partition and APFS snapshot handling
    update/       Self-update check, fetch, install and launch
    workers/      Background QThread workers

This package deliberately imports NOTHING at module level. Several submodules
have heavy import-time side effects (network_handler creates a requests.Session
and imports PySide6; crash_report instantiates Constants; utilities imports
py_sip_xnu and the constants module). Eager imports here would run those during
`constants -> detections.device_probe -> system.utilities -> constants`, which
currently only survives because utilities touches constants inside a function.
Keep every __init__.py in this tree inert.

Always import the submodule you need explicitly:

    from .support.system import utilities
    from .support.artifacts.kdk_sort import parse_build_version
"""

__all__ = []
