"""KDK version, build, beta, and release-date ordering helpers."""

from datetime import datetime
import re


_INVALID_VERSION = (-1,)
_INVALID_BUILD = (-1, -1, -1)


def parse_version(version) -> tuple:
    """Return a normalized numeric version tuple suitable for comparison."""
    match = re.fullmatch(r"\s*(\d+(?:\.\d+)*)\s*", str(version or ""))
    if not match:
        return _INVALID_VERSION
    parts = [int(part) for part in match.group(1).split(".")]
    while len(parts) > 1 and parts[-1] == 0:
        parts.pop()
    return tuple(parts)


def build_letter_to_minor(letter: str) -> int:
    """Convert an Apple build letter to its order, excluding the unused I."""
    index = ord(letter.upper()) - ord("A")
    return index - 1 if letter.upper() > "I" else index


def parse_build_version(build) -> tuple:
    """Return build major, letter, and numeric build components."""
    match = re.fullmatch(r"\s*(\d+)([A-Za-z])(\d*)([A-Za-z]*)\s*", str(build or ""))
    if not match:
        return _INVALID_BUILD
    return (
        int(match.group(1)),
        build_letter_to_minor(match.group(2)),
        int(match.group(3) or 0),
    )


def _date_sort_value(date) -> str:
    """Normalize ISO dates while keeping unknown dates below known dates."""
    value = str(date or "").strip()
    if not value:
        return ""
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    return parsed.isoformat()


def _build_version(build) -> tuple:
    """Infer the macOS version represented by an Apple build."""
    parsed = parse_build_version(build)
    if parsed == _INVALID_BUILD:
        return _INVALID_VERSION
    kernel_major, build_minor, _ = parsed
    if kernel_major >= 20:
        os_major = kernel_major + 1 if kernel_major >= 25 else kernel_major - 9
    else:
        os_major = 10
    return (os_major, build_minor)


def effective_kdk_version(item: dict) -> tuple:
    """Use the manifest patch version unless build major/minor contradict it."""
    build_version = _build_version(item.get("build", ""))
    manifest_version = parse_version(item.get("version", ""))
    if build_version == _INVALID_VERSION:
        return manifest_version
    if manifest_version != _INVALID_VERSION and manifest_version[:2] == build_version:
        return manifest_version
    return build_version


def package_sort_key(item: dict) -> tuple:
    """Build the shared package order: version, build, beta, then date."""
    build = str(item.get("build", "") or "")
    build_match = re.fullmatch(r"\s*(\d+)([A-Za-z])(\d*)([A-Za-z]*)\s*", build)
    build_key = parse_build_version(build)
    suffix = build_match.group(4).lower() if build_match else ""
    beta_key = 0 if suffix else 1
    return (
        parse_version(item.get("version", "")),
        beta_key,
        build_key,
        suffix,
        _date_sort_value(item.get("date", "")),
    )


def kdk_sort_key(item: dict) -> tuple:
    """Build the KDK order using the build-derived effective version."""
    build = str(item.get("build", "") or "")
    build_match = re.fullmatch(r"\s*(\d+)([A-Za-z])(\d*)([A-Za-z]*)\s*", build)
    build_key = parse_build_version(build)
    suffix = build_match.group(4).lower() if build_match else ""
    beta_key = 0 if suffix else 1
    return (
        effective_kdk_version(item),
        beta_key,
        build_key,
        suffix,
        _date_sort_value(item.get("date", "")),
    )


def sort_packages(items: list) -> list:
    """Return package records in the shared descending order."""
    return sorted(items, key=package_sort_key, reverse=True)


def sort_kdks(items: list) -> list:
    """Return KDK records in the shared descending order."""
    return sorted(items, key=kdk_sort_key, reverse=True)


def kdk_version_group(item: dict):
    """Group KDK records by their effective macOS major version."""
    version = effective_kdk_version(item)
    return version[0] if version != _INVALID_VERSION else ""


def latest_kdks(items: list, limit: int = 4) -> list:
    """Keep the first canonical record for each macOS major version."""
    latest = []
    seen = set()
    for item in sort_kdks(items):
        group = kdk_version_group(item)
        if group in seen:
            continue
        seen.add(group)
        latest.append(item)
        if len(latest) >= limit:
            break
    return latest
