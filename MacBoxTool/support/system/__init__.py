"""
system: Host OS and process primitives.

Deliberately imports nothing, so that importing this package never triggers
utilities.py (py_sip_xnu / constants) or install_helper.py (macOS-only).

Import submodules explicitly, e.g. `from ..system import utilities`.
"""

__all__ = []
