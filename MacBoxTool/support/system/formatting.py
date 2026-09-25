"""
formatting.py: Human-readable formatting helpers shared across the UI.

This module is intentionally dependency-free (standard library only) so it can
be imported from anywhere, including modules that must not pull in Qt or the
platform-specific `utilities` shims.
"""

# Most call sites display bytes as a whole number and switch to two decimals
# once a larger unit is reached.
DEFAULT_UNITS = ("B", "KB", "MB", "GB", "TB")


def format_size(
    size: int,
    *,
    precision: int = 2,
    unknown: str = "0 B",
    units: tuple = DEFAULT_UNITS,
    integer_bytes: bool = True,
    base: int = 1024,
) -> str:
    """
    Format a byte count for display, e.g. ``1536`` -> ``"1.50 KB"``.

    Parameters mirror the variations that used to be duplicated per call site:

    - ``precision``: decimal places once a unit larger than bytes is reached.
    - ``unknown``: returned for zero/negative input. Pass ``None`` to format the
      value instead of substituting a placeholder at all.
    - ``units``: unit ladder; the last entry is never divided past, so pass an
      extra unit if larger values should keep scaling.
    - ``integer_bytes``: render the bytes unit as a whole number. The disk image
      picker wants one decimal even for bytes, so it passes ``False``.
    - ``base``: 1024 for binary units. Note this is NOT the same as
      ``utilities.human_fmt``, which is deliberately decimal (base 1000).
    """
    if unknown is not None and size <= 0:
        return unknown

    value = float(size)
    index = 0
    while value >= base and index < len(units) - 1:
        value /= base
        index += 1

    if index == 0 and integer_bytes:
        return f"{int(value)} {units[index]}"
    return f"{value:.{precision}f} {units[index]}"


def format_speed(bytes_per_second: float, **kwargs) -> str:
    """Format a transfer rate, e.g. ``"1.50 MB/s"``."""
    return f"{format_size(bytes_per_second, **kwargs)}/s"
