"""
plist_metadata.py: Access to the installed-patch metadata plist.

When MacBoxTool patches a root volume it writes
``/System/Library/CoreServices/MacBoxTool.plist`` describing what was installed
(patch version, commit URL, PSP version, per-patch file lists, ...). Everything
that needs to inspect the *currently installed* patches reads this file, which
is why the same "does it exist / load it" dance used to appear in eight places.

Standard library only, so it is safe to import from detection, sys_patch and
GUI code alike.
"""

import logging
import plistlib
from pathlib import Path

MBT_PLIST_PATH = "/System/Library/CoreServices/MacBoxTool.plist"


def mbt_plist_exists(path: str = MBT_PLIST_PATH) -> bool:
    """True when the installed-patch metadata plist is present."""
    return Path(path).exists()


def read_mbt_plist(path: str = MBT_PLIST_PATH) -> dict:
    """
    Return the installed-patch metadata plist, or ``{}`` when it cannot be read.

    An absent file, a corrupt file and a non-dict payload all collapse to the
    same empty result: callers treat "no metadata" as "no patches installed",
    which is the safe reading. Callers that must distinguish absent from
    unreadable should check `mbt_plist_exists()` first.
    """
    try:
        with open(path, "rb") as handle:
            data = plistlib.load(handle)
    except (OSError, plistlib.InvalidFileException, ValueError) as exc:
        logging.debug("Could not read %s: %s", path, exc)
        return {}
    return data if isinstance(data, dict) else {}


def mbt_plist_value(key: str, default=None, path: str = MBT_PLIST_PATH):
    """Convenience lookup for a single key in the metadata plist."""
    return read_mbt_plist(path).get(key, default)
