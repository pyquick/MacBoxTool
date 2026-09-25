"""
build_version.py: Shared Apple build-string and macOS version helpers.

These were duplicated verbatim between the KDK and Metallib download pages
(`qt_gui/gui_kdk.py` and `qt_gui/gui_metallib.py`).

Note what is deliberately NOT here: each page keeps its own
`build_to_display_version`. Those two implementations genuinely differ (the
Metallib page has extra handling for upstream beta version strings and a
special case for the 24G builds), so unifying them would change displayed
versions. Only the provably identical helpers live here.
"""

import re

from ...datasets.os_data import os_data


def build_to_kernel(build_string) -> int | None:
    """Kernel major version from an Apple build string, e.g. "24A335" -> 24."""
    match = re.match(r'^(\d+)[A-Za-z]', str(build_string or ""))
    if match:
        return int(match.group(1))
    return None


def version_major_minor(version) -> tuple | None:
    """Leading "major.minor" of a version string, e.g. "15.6.1" -> (15, 6)."""
    match = re.match(r'^(\d+)\.(\d+)', str(version or ""))
    if not match:
        return None
    return (int(match.group(1)), int(match.group(2)))


def build_to_marketing_name(item: dict) -> str:
    """
    Marketing name ("Sequoia") for a package, via its build string.

    Falls back to interpreting the package's reported version when the build
    string is unusable, and to an empty string when neither can be resolved.
    """
    kernel_major = build_to_kernel(item.get("build", ""))
    if kernel_major is None:
        try:
            kernel_major = os_data.os_conversion.os_to_kernel(str(item.get("version", "0")))
        except (ValueError, IndexError):
            return ""
    return os_data.os_conversion.convert_kernel_to_marketing_name(kernel_major)
