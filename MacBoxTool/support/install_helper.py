"""
install_helper.py: Privileged Helper Tool Installer for MacBoxTool

Installs com.pyquick.macboxtool.privileged-helper to /Library/PrivilegedHelperTools/
Requests administrator authorization when the caller is not already root.

Usage:
    from MacBoxTool.support.install_helper import install_privileged_helper, check_helper_installed
    install_privileged_helper()  # Prompts for administrator authorization if needed
    check_helper_installed()     # Check if already installed
"""

import ctypes
import logging
import os
import stat
import subprocess
import sys
from typing import Optional, Tuple

# Only works on macOS
if sys.platform != "darwin":
    raise ImportError("Privileged Helper Tool is only supported on macOS")

# Constants
HELPER_NAME = "com.pyquick.macboxtool.privileged-helper"
HELPER_DEST_PATH = f"/Library/PrivilegedHelperTools/{HELPER_NAME}"
HELPER_BASE_PATH = "/Library/PrivilegedHelperTools"
HELPER_SOURCE_PATHS = [
    # From PKG installer payload
    "/Applications/MacBoxTool.app/Contents/Library/LaunchServices/com.pyquick.macboxtool.privileged-helper",
    # From source code (CI build)
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "ci", "privileged_helper_tool", HELPER_NAME),
    # From payload directory
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "payloads", "Tools", HELPER_NAME),
]

# Authorization Services constants
_SECURITY_FRAMEWORK = "/System/Library/Frameworks/Security.framework/Security"
_AUTHORIZATION_RIGHT_EXECUTE = b"system.privilege.admin"
_AUTHORIZATION_FLAG_DEFAULTS = 0
_AUTHORIZATION_FLAG_INTERACTION_ALLOWED = 1 << 0
_AUTHORIZATION_FLAG_EXTEND_RIGHTS = 1 << 1
_AUTHORIZATION_FLAG_DESTROY_RIGHTS = 1 << 3
_AUTHORIZATION_SUCCESS = 0
_AUTHORIZATION_CANCELED = -60006


class _AuthorizationItem(ctypes.Structure):
    _fields_ = [
        ("name", ctypes.c_char_p),
        ("value_length", ctypes.c_size_t),
        ("value", ctypes.c_void_p),
        ("flags", ctypes.c_uint32),
    ]


class _AuthorizationRights(ctypes.Structure):
    _fields_ = [
        ("count", ctypes.c_uint32),
        ("items", ctypes.POINTER(_AuthorizationItem)),
    ]


def _load_authorization_services():
    """Load the native macOS Authorization Services API."""
    security = ctypes.CDLL(_SECURITY_FRAMEWORK)
    security.AuthorizationCreate.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    security.AuthorizationCreate.restype = ctypes.c_int32
    security.AuthorizationCopyRights.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(_AuthorizationRights),
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_void_p,
    ]
    security.AuthorizationCopyRights.restype = ctypes.c_int32
    security.AuthorizationExecuteWithPrivileges.argtypes = [
        ctypes.c_void_p,
        ctypes.c_char_p,
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_char_p),
        ctypes.c_void_p,
    ]
    security.AuthorizationExecuteWithPrivileges.restype = ctypes.c_int32
    security.AuthorizationFree.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    security.AuthorizationFree.restype = ctypes.c_int32
    return security


def _authorization_error(status: int) -> str:
    if status == _AUTHORIZATION_CANCELED:
        return "Installation was cancelled."
    return f"Authorization Services failed with status {status}."


def _execute_authorized(security, authorization, executable: bytes, arguments) -> int:
    """Execute one native tool as root and wait for it to finish."""
    arguments = list(arguments) + [None]
    argument_array = (ctypes.c_char_p * len(arguments))(*arguments)
    communications_pipe = ctypes.c_void_p()
    status = security.AuthorizationExecuteWithPrivileges(
        authorization,
        executable,
        _AUTHORIZATION_FLAG_DEFAULTS,
        argument_array,
        ctypes.byref(communications_pipe),
    )
    if status != _AUTHORIZATION_SUCCESS or not communications_pipe.value:
        return status

    # AuthorizationExecuteWithPrivileges returns after launching the tool. Reading
    # its communications pipe to EOF waits for completion before the next step.
    libc = ctypes.CDLL(None)
    libc.fread.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_size_t, ctypes.c_void_p]
    libc.fread.restype = ctypes.c_size_t
    libc.fclose.argtypes = [ctypes.c_void_p]
    buffer = ctypes.create_string_buffer(4096)
    while libc.fread(buffer, 1, len(buffer), communications_pipe):
        pass
    libc.fclose(communications_pipe)
    return status


def _install_with_authorization(source_path: str) -> Tuple[bool, str]:
    """Install the helper through the native Authorization Services API."""
    security = _load_authorization_services()
    authorization = ctypes.c_void_p()
    status = security.AuthorizationCreate(
        None,
        None,
        _AUTHORIZATION_FLAG_DEFAULTS,
        ctypes.byref(authorization),
    )
    if status != _AUTHORIZATION_SUCCESS:
        return False, _authorization_error(status)

    try:
        item = _AuthorizationItem(_AUTHORIZATION_RIGHT_EXECUTE, 0, None, 0)
        rights = _AuthorizationRights(1, ctypes.pointer(item))
        flags = _AUTHORIZATION_FLAG_INTERACTION_ALLOWED | _AUTHORIZATION_FLAG_EXTEND_RIGHTS
        status = security.AuthorizationCopyRights(
            authorization,
            ctypes.byref(rights),
            None,
            flags,
            None,
        )
        if status != _AUTHORIZATION_SUCCESS:
            return False, _authorization_error(status)

        status = _execute_authorized(
            security,
            authorization,
            b"/bin/cp",
            (b"-R", os.fsencode(source_path), os.fsencode(HELPER_DEST_PATH)),
        )
        if status != _AUTHORIZATION_SUCCESS:
            return False, _authorization_error(status)

        status = _execute_authorized(
            security,
            authorization,
            b"/bin/chmod",
            (b"4755", os.fsencode(HELPER_DEST_PATH)),
        )
        if status != _AUTHORIZATION_SUCCESS:
            return False, _authorization_error(status)
    finally:
        security.AuthorizationFree(authorization, _AUTHORIZATION_FLAG_DESTROY_RIGHTS)

    if not check_helper_installed():
        return False, f"Helper was not installed at {HELPER_DEST_PATH}"

    helper_stat = os.stat(HELPER_DEST_PATH)
    if helper_stat.st_uid != 0 or not helper_stat.st_mode & stat.S_ISUID:
        return False, "Helper was installed without the required root ownership or SUID permission"

    return True, f"Successfully installed helper to {HELPER_DEST_PATH}"


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

    # Find source path before requesting administrator authorization.
    if source_path is None:
        source_path = get_helper_source_path()

    if source_path is None or not os.path.exists(source_path):
        return False, f"Helper binary not found. Searched in: {HELPER_SOURCE_PATHS}"

    if not is_root():
        try:
            return _install_with_authorization(source_path)
        except Exception as e:
            error_msg = f"Failed to authorize helper installation: {e}"
            if verbose:
                logging.error(error_msg)
            return False, error_msg

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
        if not os.path.exists(HELPER_BASE_PATH):
            os.makedirs(HELPER_BASE_PATH, exist_ok=True)
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