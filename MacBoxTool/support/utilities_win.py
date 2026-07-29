"""
utilities_win.py: Utility functions for MacBoxTool for Windows
"""

import os
import math
import shutil
import logging
import binascii
import struct
import hashlib
import zlib
import tempfile
import xml.etree.ElementTree as ET

from pathlib import Path

from .. import constants

def disable_cls():
    global clear
    clear = False

def cls():
    global clear
    if not clear:
        return

    if not check_recovery():
        os.system("cls" if os.name == "nt" else "clear")
    else:
        logging.info("c")

def hexswap(input_hex: str):
    #Example: 0x12345678
    hex_pairs = [input_hex[i : i + 2] for i in range(0, len(input_hex), 2)] 
    hex_rev = hex_pairs[::-1]
    hex_str = "".join(["".join(x) for x in hex_rev])
    return hex_str.upper()

def string_to_hex(input_string):
    if not (len(input_string) % 2) == 0:
        input_string = "0" + input_string
    input_string = hexswap(input_string)
    input_string = binascii.unhexlify(input_string)
    return input_string

def human_fmt(num):
    for unit in ["B", "KB", "MB", "GB", "TB", "PB"]:
        if abs(num) < 1000.0:
            return "%3.1f %s" % (num, unit)
        num /= 1000.0
    return "%.1f %s" % (num, "EB")

def seconds_to_readable_time(seconds) -> str:
    """
    Convert seconds to a readable time format

    Parameters:
        seconds (int | float | str): Seconds to convert

    Returns:
        str: Readable time format
    """
    seconds = int(seconds)
    time = ""

    if 0 <= seconds < 60:
        return "Less than a minute "
    if seconds < 0:
        return "Indeterminate time "

    years, seconds = divmod(seconds, 31536000)
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)

    if years > 0:
        return "Over a year"
    if days > 0:
        if days > 31:
            return "Over a month"
        time += f"{days}d "
    if hours > 0:
        time += f"{hours}h "
    if minutes > 0:
        time += f"{minutes}m "
    #if seconds > 0:
    #    time += f"{seconds}s"
    return time


def header(lines):
    lines = [i for i in lines if i is not None]
    total_length = len(max(lines, key=len)) + 4
    logging.info("#" * total_length)
    for line in lines:
        left_side = math.floor(((total_length - 2 - len(line.strip())) / 2))
        logging.info("#" + " " * left_side + line.strip() + " " * (total_length - len("#" + " " * left_side + line.strip()) - 1) + "#")
    logging.info("#" * total_length)


RECOVERY_STATUS = None


def check_recovery():
    global RECOVERY_STATUS
    if RECOVERY_STATUS is None:
        RECOVERY_STATUS = False
    return RECOVERY_STATUS


def friendly_hex(integer: int):
    return "{:02X}".format(integer)


# ---------------------------------------------------------------------------
# NVRAM — Windows EFI NVRAM access via Firmware Environment Variables
# ---------------------------------------------------------------------------

def get_nvram(variable: str, uuid: str = None, *, decode: bool = False):
    """
    Read EFI NVRAM variable on Windows.

    On Windows, EFI variables are exposed as "Firmware Environment Variables".
    The GUID is passed as the namespace in the format: "{GUID}-VariableName".

    Common OpenCore GUIDs:
    - 4D1FDA02-38C7-4A6A-9CC6-4BCCA8B30102 (MBT custom variables)
    - 94B73556-2197-4702-82A8-3E1337DAFBFB (Apple Secure Boot)
    - 7C436110-AB2A-4BBB-A880-FE41995C9F82 (OpenCore & Apple boot-args csr-active-config run-efi-upd)

    Parameters:
        variable: NVRAM variable name (e.g., "MBT-Version")
        uuid: EFI GUID in 8-4-4-4-12 format without hyphens or with standard format
        decode: If True, decode bytes to string

    Returns:
        bytes or str or None: Variable value, or None if not found
    """
    try:
        import ctypes
        from ctypes import wintypes

        # Format UUID for Windows API
        if uuid is None:
            guid = "{00000000-0000-0000-0000-000000000000}"
        else:
            # Convert to standard GUID format if needed
            # Input formats: "4D1FDA02-38C7-4A6A-9CC6-4BCCA8B30102" or "4D1FDA0238C74A6A9CC64BCCA8B30102"
            uuid_clean = uuid.replace("-", "")
            if len(uuid_clean) == 32:
                guid = "{" + uuid_clean[0:8] + "-" + uuid_clean[8:12] + "-" + uuid_clean[12:16] + "-" + uuid_clean[16:20] + "-" + uuid_clean[20:32] + "}"
            else:
                guid = "{" + uuid + "}"

        # Construct the full namespace: {GUID}-VariableName
        # Windows expects: {GUID}\VariableName
        namespace = guid + "-" + variable

        # Kernel32.dll functions
        kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

        # GetFirmwareEnvironmentVariableW(LPWSTR lpName, LPWSTR lpGuid, PVOID pBuffer, DWORD nSize)
        # Actually on Windows, the GUID and name are combined differently
        # The function signature varies by Windows version

        # For UEFI firmware, use: GetFirmwareEnvironmentVariableW
        # lpName = variable name
        # lpGuid = GUID in {xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx} format

        # Try with variable as name and GUID as guid
        GetFirmwareEnvironmentVariableW = kernel32.GetFirmwareEnvironmentVariableW
        GetFirmwareEnvironmentVariableW.restype = wintypes.DWORD
        GetFirmwareEnvironmentVariableW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.c_void_p, wintypes.DWORD]

        # First call to get required buffer size
        size = GetFirmwareEnvironmentVariableW(variable, guid, None, 0)
        if size == 0:
            # Try alternative format with combined namespace
            size = GetFirmwareEnvironmentVariableW(namespace, None, None, 0)
            if size == 0:
                error = ctypes.get_last_error()
                if error == 203:  # ERROR_ENVVAR_NOT_FOUND
                    return None
                # May need admin privileges, try reading from registry as fallback
                return _get_nvram_from_registry(variable, uuid, decode)

        # Allocate buffer and read value
        buffer = ctypes.create_string_buffer(size)
        size = GetFirmwareEnvironmentVariableW(variable, guid, buffer, size)
        if size == 0:
            return None

        value = buffer.raw[:size]

        if decode:
            if isinstance(value, bytes):
                try:
                    value = value.strip(b"\x00").decode("utf-8")
                except UnicodeDecodeError:
                    value = None
            elif isinstance(value, str):
                value = value.strip("\x00")

        return value

    except Exception:
        return None


def _get_nvram_from_registry(variable: str, uuid: str = None, *, decode: bool = False):
    r"""
    Fallback: Try to read NVRAM values from registry if firmware access fails.
    Some boot loaders store variables in HKLM\System\CurrentControlSet\Control\FirmwareEnvironmentVariables
    """
    try:
        import winreg

        if uuid is None:
            return None

        # Format UUID for registry path
        uuid_clean = uuid.replace("-", "")
        if len(uuid_clean) == 32:
            guid = "{" + uuid_clean[0:8] + "-" + uuid_clean[8:12] + "-" + uuid_clean[12:16] + "-" + uuid_clean[16:20] + "-" + uuid_clean[20:32] + "}"
        else:
            return None

        # Registry path for firmware variables
        reg_path = f"SYSTEM\\CurrentControlSet\\Control\\FirmwareEnvironmentVariables\\{guid}"

        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path)
            value, _ = winreg.QueryValueEx(key, variable)
            winreg.CloseKey(key)

            if decode and isinstance(value, bytes):
                try:
                    value = value.strip(b"\x00").decode("utf-8")
                except UnicodeDecodeError:
                    value = None

            return value

        except (FileNotFoundError, OSError):
            return None

    except Exception:
        return None


def get_rom(variable: str, *, decode: bool = False):
    """
    Read ROM/BIOS information on Windows.

    On macOS, this reads from IORegistry'sIODeviceTree:/rom.
    On Windows, we use WMI to read BIOS information.

    Parameters:
        variable: Property name to read (e.g., "BIOSVersion", "ReleaseDate")
        decode: If True, decode bytes to string

    Returns:
        bytes or str or None: ROM/BIOS property value
    """
    try:
        import wmi
        bios = wmi.WMI().Win32_BIOS()[0]

        # Map common ROM variable names to WMI properties
        property_map = {
            "Version": bios.BIOSVersion,
            "ReleaseDate": bios.ReleaseDate,
            "SerialNumber": bios.SerialNumber,
            "SMBIOSBIOSVersion": bios.SMBIOSBIOSVersion,
        }

        value = property_map.get(variable)

        if value is None:
            # Try direct attribute access
            value = getattr(bios, variable, None)

        if value and decode:
            if isinstance(value, bytes):
                try:
                    value = value.strip(b"\x00").decode("utf-8")
                except UnicodeDecodeError:
                    value = None
            elif isinstance(value, str):
                value = value.strip("\x00")
        elif value and isinstance(value, str) and not decode:
            value = value.encode("utf-8")

        return value

    except Exception:
        return None


def get_firmware_vendor(*, decode: bool = False):
    try:
        import wmi
        bios = wmi.WMI().Win32_BIOS()[0]
        vendor = bios.Manufacturer or None
        if vendor and decode:
            return vendor
        if vendor:
            return vendor.encode("utf-8")
        return None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Disk functions — macOS-only, stubs on Windows
# ---------------------------------------------------------------------------

def get_disk_path():
    return None

def check_if_root_is_apfs_snapshot():
    return False

def check_seal():
    return False

def check_filesystem_type():
    return "ntfs"

def find_apfs_physical_volume(device):
    return []

def find_disk_off_uuid(uuid):
    return None

def grab_mount_point_from_disk(disk):
    return None

def monitor_disk_output(disk):
    return "0"

def get_preboot_uuid() -> str:
    return ""


# ---------------------------------------------------------------------------
# SIP / Security — macOS-only concepts, stubs on Windows
# ---------------------------------------------------------------------------

def csr_decode(os_sip):
    return False

def check_filevault_skip():
    return False

def check_secure_boot_model():
    return None

def check_ap_security_policy():
    return 0

def check_secure_boot_level():
    return False


def patching_status(os_sip, os):
    return False, False, False, False


clear = True

def check_command_line_tools():
    return False

def check_boot_mode():
    return None

def fetch_staged_update(variant: str = "Update") -> tuple:
    return (None, None)


# ---------------------------------------------------------------------------
# Sleep management — Windows equivalent using ctypes
# ---------------------------------------------------------------------------

sleep_process = None

def disable_sleep_while_running():
    global sleep_process
    logging.info("Disabling Idle Sleep")
    if sleep_process is None:
        import ctypes
        # ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001 | 0x00000002)
        sleep_process = True

def enable_sleep_after_running():
    global sleep_process
    if sleep_process:
        logging.info("Re-enabling Idle Sleep")
        import ctypes
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
        sleep_process = None


# ---------------------------------------------------------------------------
# Kext / driver checks — macOS-only, stubs on Windows
# ---------------------------------------------------------------------------

def check_kext_loaded(bundle_id: str) -> str:
    return ""

def check_mbt_boot():
    return False

def check_monterey_wifi():
    return False


# ---------------------------------------------------------------------------
# Cross-platform functions
# ---------------------------------------------------------------------------

def check_metal_support(device_probe, computer):
    if computer.gpus:
        for gpu in computer.gpus:
            if gpu.arch in [
                device_probe.NVIDIA.Archs.Tesla,
                device_probe.NVIDIA.Archs.Fermi,
                device_probe.NVIDIA.Archs.Maxwell,
                device_probe.NVIDIA.Archs.Pascal,
                device_probe.AMD.Archs.TeraScale_1,
                device_probe.AMD.Archs.TeraScale_2,
                device_probe.Intel.Archs.Iron_Lake,
                device_probe.Intel.Archs.Sandy_Bridge,
            ]:
                return False
    return True


def clean_device_path(device_path: str):
    if device_path:
        if not any(partition in device_path for partition in ["GPT", "MBR"]):
            return None
        device_path_array = device_path.split("/")
        if len(device_path_array) >= 2:
            device_path_stripped = device_path_array[-2]
            device_path_root_array = device_path_stripped.split(",")
            if len(device_path_root_array) > 2:
                return device_path_root_array[2]
    return None


def get_free_space(disk=None):
    if disk is None:
        disk = "C:\\"
    total, used, free = shutil.disk_usage(disk)
    return free


def block_os_updaters():
    pass


# ---------------------------------------------------------------------------
# macOS pkg extraction — Windows implementation
# ---------------------------------------------------------------------------

def get_downloads_dir() -> str:
    """Return the user's Downloads directory on Windows.

    Uses shell32 to resolve the real Downloads folder rather than
    hard‑coding ``C:\\Users\\...`` so it works on systems where the
    Downloads folder was relocated (OneDrive redirect, etc.).
    """
    import ctypes
    from ctypes import wintypes

    buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
    ctypes.windll.shell32.SHGetFolderPathW(
        None,  # CSIDL_DOWNLOADS
        0x002A,  # FOLDERID_Downloads / CSIDL_DOWNLOADS
        None,
        0,
        buf,
    )
    return buf.value


def extract_pkg(pkg_path: str | Path, output_dir: str | Path) -> bool:
    """Extract an Apple ``.pkg`` (XAR) on Windows.

    Prefers 7‑Zip when available, otherwise falls back to a pure‑Python
    XAR extractor.  Returns ``True`` on success.
    """
    pkg_path = Path(pkg_path)
    output_dir = Path(output_dir)

    if not pkg_path.exists():
        logging.error(f"pkg not found: {pkg_path}")
        return False

    # -- 7-Zip fast path -------------------------------------------------
    seven_zip = _find_seven_zip()
    if seven_zip:
        import subprocess

        output_dir.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            [seven_zip, "x", str(pkg_path), f"-o{output_dir}", "-y"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return True
        logging.warning(f"7-Zip extraction failed, falling back to pure Python: {result.stderr}")

    # -- Pure Python XAR fallback ----------------------------------------
    return _extract_xar_pure(pkg_path, output_dir)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _find_seven_zip() -> str | None:
    """Locate the 7‑Zip executable on the system."""
    import subprocess
    import sys

    known = [
        Path(os.environ.get("ProgramFiles", "C:\\Program Files")) / "7-Zip" / "7z.exe",
        Path(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")) / "7-Zip" / "7z.exe",
    ]
    for candidate in known:
        if candidate.exists():
            return str(candidate)

    # Try PATH
    try:
        subprocess.run(["7z", "--help"], capture_output=True)
        return "7z"
    except FileNotFoundError:
        pass

    return None


# XAR header format (big-endian)
_XAR_HEADER = struct.Struct(">IHHQQI")
# magic (4) + size (2) + version (2) + toc_compressed_size (8)
# + toc_uncompressed_size (8) + checksum_algo (4) = 28 bytes


def _extract_xar_pure(pkg_path: Path, output_dir: Path) -> bool:
    """Pure‑Python extraction of a XAR archive (no external tools)."""
    try:
        with open(pkg_path, "rb") as f:
            header_bytes = f.read(_XAR_HEADER.size)
            if len(header_bytes) < _XAR_HEADER.size:
                return False

            magic, hdr_size, version, toc_comp_size, toc_uncomp_size, checksum_algo = (
                _XAR_HEADER.unpack(header_bytes)
            )
            magic_str = header_bytes[:4]
            if magic_str != b"xar!":
                logging.error(f"Not a XAR file: {magic_str!r}")
                return False

            # Read the compressed TOC
            f.seek(hdr_size)
            toc_bytes = f.read(toc_comp_size)
            if len(toc_bytes) < toc_comp_size:
                return False

            toc_xml = zlib.decompress(toc_bytes)
            if len(toc_xml) != toc_uncomp_size:
                logging.warning("TOC size mismatch, continuing anyway")

            toc_root = ET.fromstring(toc_xml)

            # XAR TOC namespace varies by toolchain:
            #     http://code.google.com/p/xar/toc  (standard)
            #     no namespace at all              (some Apple pkgs)
            #     http://www.w3.org/2005/Atom       (misidentified)
            # Strip namespaces entirely so we match against bare tag names.
            for el in toc_root.iter():
                if "}" in (el.tag or ""):
                    el.tag = el.tag.split("}", 1)[1]

            # Build output paths — keep directory structure
            for file_el in toc_root.iter("file"):
                name_el = file_el.find("name")
                if name_el is None:
                    continue
                rel_path = name_el.text
                dest = output_dir / rel_path.lstrip("/")

                file_type = file_el.find("type")
                if file_type is not None and file_type.text == "directory":
                    dest.mkdir(parents=True, exist_ok=True)
                    continue

                dest.parent.mkdir(parents=True, exist_ok=True)

                # Collect chunk data offsets (each <data> child has
                # <offset> and <size>)
                data_el = file_el.find("data")
                offset_tag = data_el.find("offset") if data_el is not None else None
                size_tag = data_el.find("size") if data_el is not None else None
                if offset_tag is None or size_tag is None:
                    continue

                file_start = int(offset_tag.text)
                file_size = int(size_tag.text)

                # Handle archived/extracted — skip archived content
                encoding = data_el.find("encoding")
                encoding_style = encoding.get("style") if encoding is not None else None

                with open(dest, "wb") as out:
                    if encoding_style == "application/x-gzip":
                        # Decompress with gzip (the data in the XAR is
                        # stored gzip‑compressed per <encoding>)
                        import gzip

                        f.seek(file_start)
                        raw = f.read(file_size)
                        out.write(gzip.decompress(raw))
                    elif encoding_style == "application/octet-stream":
                        f.seek(file_start)
                        out.write(f.read(file_size))
                    else:
                        # Uncompressed — read from archive position
                        # (XAR stores the content directly)
                        f.seek(file_start)
                        out.write(f.read(file_size))

        logging.info(f"Pure Python XAR extraction complete: {output_dir}")
        return True

    except Exception as e:
        logging.error(f"XAR extraction failed: {e}")
        return False


# ---------------------------------------------------------------------------
# Command line arguments for testing
# ---------------------------------------------------------------------------

_test_args_model: str = None


def get_test_args() -> dict:
    """
    Get command line arguments for testing.

    Returns:
        dict: Dictionary with 'model' key if --model was passed
    """
    import sys
    global _test_args_model

    if _test_args_model is not None:
        return {"model": _test_args_model}

    for i, arg in enumerate(sys.argv):
        if arg == "--model" and i + 1 < len(sys.argv):
            _test_args_model = sys.argv[i + 1]
            return {"model": _test_args_model}
    return {}


def clear_test_args():
    """Clear test arguments after use."""
    global _test_args_model
    _test_args_model = None