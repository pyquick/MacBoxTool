"""
install_helper.py: Privileged Helper Tool Installer for MacBoxTool

Installs com.pyquick.macboxtool.privileged-helper to /Library/PrivilegedHelperTools/
Requires sudo/root privileges.

Usage:
    from MacBoxTool.support.install_helper import install_privileged_helper, check_helper_installed
    install_privileged_helper()  # Requires root
    check_helper_installed()     # Check if already installed
"""

import os
import stat
import subprocess
import logging
import sys
from typing import Optional, Tuple

# Only works on macOS
if sys.platform != "darwin":
    raise ImportError("Privileged Helper Tool is only supported on macOS")

# Constants
HELPER_NAME = "com.pyquick.macboxtool.privileged-helper"
HELPER_DEST_PATH = f"/Library/PrivilegedHelperTools/{HELPER_NAME}"
HELPER_SOURCE_PATHS = [
    # From PKG installer payload
    "/Applications/MacBoxTool.app/Contents/Library/LaunchServices/com.pyquick.macboxtool.privileged-helper",
    # From source code (CI build)
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "ci", "privileged_helper_tool", HELPER_NAME),
    # From payload directory
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "payloads", "Tools", HELPER_NAME),
]


def get_helper_source_path() -> Optional[str]:
    """Find the helper binary from known source locations."""
    for source_path in HELPER_SOURCE_PATHS:
        if os.path.exists(source_path):
            logging.info(f"Found helper at: {source_path}")
            return source_path

    # Try to find in current directory
    current_dir = os.path.dirname(os.path.abspath(__file__))
    for root, dirs, files in os.walk(current_dir):
        if HELPER_NAME in files:
            found_path = os.path.join(root, HELPER_NAME)
            logging.info(f"Found helper at: {found_path}")
            return found_path

    return None


def check_helper_installed() -> bool:
    """Check if the privileged helper is already installed."""
    return os.path.exists(HELPER_DEST_PATH)


def check_helper_version() -> Optional[str]:
    """Get the version of installed helper."""
    if not check_helper_installed():
        return None

    try:
        # Use ls to get file info
        result = subprocess.run(
            ["ls", "-l", HELPER_DEST_PATH],
            capture_output=True,
            text=True
        )
        return result.stdout.strip()
    except Exception as e:
        logging.warning(f"Failed to get helper version: {e}")
        return None


def is_root() -> bool:
    """Check if running as root."""
    return os.geteuid() == 0


def install_privileged_helper(source_path: Optional[str] = None, verbose: bool = True) -> Tuple[bool, str]:
    """
    Install the privileged helper tool.

    Args:
        source_path: Optional path to helper binary. If None, will search in default locations.
        verbose: Whether to print progress messages.

    Returns:
        Tuple of (success: bool, message: str)
    """
    if sys.platform != "darwin":
        return False, "Privileged Helper Tool is only supported on macOS"

    # Check if already installed
    if check_helper_installed():
        return True, f"Helper is already installed at {HELPER_DEST_PATH}"

    # Check if running as root
    if not is_root():
        return False, "Installation requires root privileges. Please run with sudo."

    # Find source path
    if source_path is None:
        source_path = get_helper_source_path()

    if source_path is None or not os.path.exists(source_path):
        return False, f"Helper binary not found. Searched in: {HELPER_SOURCE_PATHS}"

    if verbose:
        logging.info(f"Installing helper from: {source_path}")
        logging.info(f"Destination: {HELPER_DEST_PATH}")

    try:
        # Remove existing file if any
        if os.path.exists(HELPER_DEST_PATH):
            if os.path.isdir(HELPER_DEST_PATH):
                subprocess.run(["rm", "-rf", HELPER_DEST_PATH], check=True)
            else:
                os.remove(HELPER_DEST_PATH)

        # Copy helper to destination
        subprocess.run(["cp", "-R", source_path, HELPER_DEST_PATH], check=True)

        # Set SUID bit (required for privileged helper)
        os.chmod(HELPER_DEST_PATH, os.stat(HELPER_DEST_PATH).st_mode | stat.S_ISUID | stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)

        if verbose:
            logging.info("Helper installed successfully!")
            logging.info(f"SUID bit set on {HELPER_DEST_PATH}")

        return True, f"Successfully installed helper to {HELPER_DEST_PATH}"

    except subprocess.CalledProcessError as e:
        error_msg = f"Failed to copy helper: {e}"
        if verbose:
            logging.error(error_msg)
        return False, error_msg
    except Exception as e:
        error_msg = f"Failed to install helper: {e}"
        if verbose:
            logging.error(error_msg)
        return False, error_msg


def uninstall_privileged_helper(verbose: bool = True) -> Tuple[bool, str]:
    """
    Uninstall the privileged helper tool.

    Args:
        verbose: Whether to print progress messages.

    Returns:
        Tuple of (success: bool, message: str)
    """
    if sys.platform != "darwin":
        return False, "Privileged Helper Tool is only supported on macOS"

    if not is_root():
        return False, "Uninstallation requires root privileges. Please run with sudo."

    if not check_helper_installed():
        return True, "Helper is not installed"

    try:
        if os.path.isdir(HELPER_DEST_PATH):
            subprocess.run(["rm", "-rf", HELPER_DEST_PATH], check=True)
        else:
            os.remove(HELPER_DEST_PATH)

        if verbose:
            logging.info("Helper uninstalled successfully!")

        return True, "Successfully uninstalled helper"

    except Exception as e:
        error_msg = f"Failed to uninstall helper: {e}"
        if verbose:
            logging.error(error_msg)
        return False, error_msg


def main():
    """CLI entry point for helper installation."""
    import argparse

    parser = argparse.ArgumentParser(description="MacBoxTool Privileged Helper Installer")
    parser.add_argument("--uninstall", action="store_true", help="Uninstall the helper instead of installing")
    parser.add_argument("--check", action="store_true", help="Check if helper is installed")
    parser.add_argument("--source", type=str, help="Path to helper binary source")

    args = parser.parse_args()

    if args.check:
        if check_helper_installed():
            print(f"Helper is installed at {HELPER_DEST_PATH}")
            sys.exit(0)
        else:
            print(f"Helper is NOT installed")
            sys.exit(1)

    if args.uninstall:
        success, msg = uninstall_privileged_helper()
    else:
        success, msg = install_privileged_helper(args.source)

    print(msg)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()