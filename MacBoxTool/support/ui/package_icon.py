"""
package_icon.py: Resolve the per-macOS-version "package" icon used by the
KDK and Metallib download lists.

Both pages carried a private copy of this mapping (four copies in total). They
differed in one respect only: the KDK list verified the icon file exists and fell
back to the generic icon, while the Metallib list returned the versioned path
unconditionally. That is preserved via `require_exists`.
"""

from pathlib import Path


def package_icon_path(constants, major_version: int, *, require_exists: bool = True) -> str:
    """
    Path to the package icon for a macOS major version (11-27).

    The display major version is mapped onto the existing/reserved package icon
    set; anything outside the known range falls back to the generic icon.

    Args:
        constants: object exposing `package_icns_path_generic`,
            `package_icns_path_tahoe` and `package_icns_paths`.
        major_version: macOS major version (11 = Big Sur, 15 = Sequoia, ...).
        require_exists: when True, a missing icon file resolves to the generic
            icon; when False the versioned path is returned as-is.
    """
    generic_icon_path = str(Path(constants.package_icns_path_generic).with_suffix(".png"))

    def resolve(icns_path) -> str:
        # The constants hold .icns paths; these lists ship .png renders.
        path = Path(icns_path).with_suffix(".png")
        if require_exists:
            return str(path) if path.exists() else generic_icon_path
        return str(path)

    if major_version == 27:
        return resolve(Path(constants.package_icns_path_tahoe).with_name("Package27.icns"))

    if major_version == 26:
        index = 6
    elif 11 <= major_version <= 15:
        index = major_version - 10
    else:
        return generic_icon_path

    if index < len(constants.package_icns_paths):
        return resolve(constants.package_icns_paths[index])

    return generic_icon_path
