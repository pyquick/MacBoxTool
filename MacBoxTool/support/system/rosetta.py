"""
rosetta.py: Apple Silicon and Rosetta 2 runtime detection.

Standard library only, and deliberately free of project imports: this module is
reached from `detections.device_probe`, which is imported by `constants`, so it
must be safe to import while the package graph is still initialising.

Two related but distinct questions are answered here:

- `is_apple_silicon()`  -- is this an Apple Silicon machine (native or Rosetta)?
- `is_rosetta_translated()` -- is this process actually running under Rosetta 2?

The distinction matters: on Apple Silicon the platform exposes `target-type`
where Intel exposes `board-id`, and that is decided by whether the sysctl key
exists at all, not by its value.
"""

import platform
import subprocess
import sys


def _read_proc_translated():
    """
    Return the raw `sysctl.proc_translated` value, or None when unavailable.

    None means the key does not exist, which is the case on Intel Macs (and on
    any non-macOS host). "0" and "1" both mean the key exists, i.e. Apple
    Silicon; only "1" means Rosetta translation is active.
    """
    if sys.platform != "darwin":
        return None
    try:
        result = subprocess.run(
            ["/usr/sbin/sysctl", "-n", "sysctl.proc_translated"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.decode(errors="replace").strip()


def is_apple_silicon() -> bool:
    """
    True when running on an Apple Silicon Mac, natively or under Rosetta 2.

    The machine() check catches native arm64; under Rosetta Python reports
    x86_64, so the sysctl probe is needed to catch the translated case.
    """
    if platform.machine().lower().startswith("arm64"):
        return True
    return _read_proc_translated() is not None


def is_rosetta_translated() -> bool:
    """True when this process is running under Rosetta 2 translation."""
    return _read_proc_translated() == "1"
