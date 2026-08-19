"""
crash_report.py: Real-time Crash Reporting Handler

Posts unhandled exceptions to the Crash Report Server (http://192.168.1.157:8080).
"""

import io
import logging
import os
import socket
import sys
import tarfile
import threading
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Tuple

import requests

# ── Configuration ──────────────────────────────────────────────
CRASH_SERVER_URL: str = "http://192.168.1.157:8080/api/v1/crash-report"
CRASH_API_KEY:  str = "crs_iq8Ka_xEbbRhpaJDStgH7p1dQfPt5OAopl2s8CkzZUA"
ALLOWED_HOSTNAME: str = "Ghltbms-Mac-Pro.local"
PROJECT_NAME:    str = "MacBoxTool"

# Dedicated endpoint for immutable source snapshots (Crash Analysis)
PROJECT_SOURCES_URL: str = CRASH_SERVER_URL.replace(
    "api/v1/crash-report", "api/v1/project-sources"
)

# Source snapshot settings: the MacBoxTool folder's source code is archived
# as a .tar.gz and uploaded alongside the crash report.
SOURCE_EXTENSIONS: set[str] = {
    ".py", ".pyw", ".spec", ".command", ".sh", ".bat", ".ps1",
    ".md", ".txt", ".rst", ".json", ".plist", ".yml", ".yaml",
    ".toml", ".cfg", ".ini", ".qss", ".ui",
}
EXCLUDED_DIRS: set[str] = {
    "payloads", "build", "dist", "EFI_Build", "__pycache__", "_rc",
}
SOURCE_BUNDLE_MAX_FILE_SIZE: int = 2 * 1024 * 1024  # server limit: 2 MiB per file
SOURCE_BUNDLE_TIMEOUT:      int = 30  # seconds

# ── Constants ──────────────────────────────────────────────────
REQUEST_TIMEOUT: int = 10  # seconds

# ── Internal state ─────────────────────────────────────────────
_original_excepthook: Any = None
_installed:          bool = False
_logger:             Optional[logging.Logger] = None


def _get_logger() -> logging.Logger:
    """Return a cached logger instance."""
    global _logger
    if _logger is None:
        _logger = logging.getLogger(__name__)
    return _logger


def _get_hostname() -> str:
    """Return the current hostname."""
    return socket.gethostname()


def is_reporting_enabled() -> bool:
    """
    Check whether crash reporting should be active.

    Returns True only when the hostname matches ALLOWED_HOSTNAME (case-insensitive).
    """
    try:
        return _get_hostname().upper() == ALLOWED_HOSTNAME.upper()
    except Exception:
        return False


def _format_traceback(exc_type: type, exc_value: BaseException, exc_tb: Any) -> str:
    """Format exception info into a traceback string."""
    lines = traceback.format_exception(exc_type, exc_value, exc_tb)
    return "".join(lines)


def _build_payload(
    exception_type: str,
    exception_message: str,
    stack_trace: str = "",
    log_text: str = "",
    **extra: Any,
) -> dict:
    """Build the JSON payload for the crash-report API."""
    payload: dict = {
        "exception_type": exception_type,
        "exception_message": exception_message,
        "project_name": PROJECT_NAME,
        "runtime": "Python",
        "runtime_version": sys.version,
        "platform": sys.platform,
        "server_name": _get_hostname(),
        "release":"0.0.4",
        "environment":"development",
        "client_timestamp": datetime.now(timezone.utc).isoformat(),
        "error_severity": "crash",
    }

    if stack_trace:
        payload["stack_trace"] = stack_trace

    if log_text:
        payload["log_text"] = log_text

    # Merge extra fields (allow caller to override / add fields)
    payload.update(extra)
    return payload


def _get_source_root() -> Optional[Path]:
    """Return the MacBoxTool source folder (this file's package root)."""
    root = Path(__file__).resolve().parents[1]
    return root if root.is_dir() else None


def _build_source_bundle() -> Optional[Tuple[bytes, int, int]]:
    """
    Create a gzipped tar archive (.tar.gz) of the MacBoxTool folder's
    source files. Member paths are relative (no absolute or '..' paths).

    Only collects text-based source files; skips generated resources,
    build outputs and the payloads directory.

    Returns
    -------
    Optional[Tuple[bytes, int, int]]
        (tar.gz bytes, file count, uncompressed size in bytes) or None.
    """
    root = _get_source_root()
    if root is None:
        return None

    buffer = io.BytesIO()
    file_count = 0
    total_size = 0

    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for dirpath, dirnames, filenames in os.walk(root):
            rel_dir = Path(dirpath).relative_to(root)
            dirnames[:] = [
                d for d in dirnames
                if d not in EXCLUDED_DIRS and not d.startswith(".")
            ]
            for filename in filenames:
                if filename.startswith("."):
                    continue
                file_path = Path(dirpath) / filename
                if file_path.suffix.lower() not in SOURCE_EXTENSIONS:
                    continue
                try:
                    size = file_path.stat().st_size
                except OSError:
                    continue
                if size > SOURCE_BUNDLE_MAX_FILE_SIZE:
                    continue
                try:
                    archive.add(file_path, arcname=str(rel_dir / filename))
                except OSError:
                    continue
                file_count += 1
                total_size += size

    if file_count == 0:
        return None

    return buffer.getvalue(), file_count, total_size


def _send_source_bundle(release: Optional[str]) -> bool:
    """
    Upload the MacBoxTool source snapshot to the project-sources endpoint.

    Multipart fields per API spec: 'project_name' (required), 'release'
    (optional, max 200 chars) and 'archive' (.tar.gz). A successful upload
    creates an immutable source snapshot for Crash Analysis. Attempted on
    every crash, regardless of whether the crash report itself was accepted.
    """
    bundle = _build_source_bundle()
    if bundle is None:
        return False

    archive_bytes, file_count, total_size = bundle

    data = {"project_name": PROJECT_NAME}
    if release:
        data["release"] = str(release)[:200]

    files = {
        "archive": ("MacBoxTool.tar.gz", archive_bytes, "application/gzip"),
    }

    headers = {"X-API-Key": CRASH_API_KEY}

    try:
        resp = requests.post(
            PROJECT_SOURCES_URL,
            data=data,
            files=files,
            headers=headers,
            timeout=SOURCE_BUNDLE_TIMEOUT,
        )
        if resp.status_code == 201:
            snapshot_id = "?"
            try:
                snapshot_id = resp.json().get("snapshot_id", "?")
            except Exception:
                pass
            _get_logger().info(
                "Source snapshot uploaded (snapshot_id=%s): %d files, %d bytes",
                snapshot_id,
                file_count,
                total_size,
            )
            return True
        _get_logger().warning(
            "Source snapshot upload failed: HTTP %d — %s",
            resp.status_code,
            resp.text[:200],
        )
        return False
    except requests.exceptions.RequestException:
        _get_logger().warning("Source snapshot upload failed", exc_info=True)
        return False


def send_crash_report(
    exception_type: str,
    exception_message: str,
    stack_trace: str = "",
    log_text: str = "",
    **extra: Any,
) -> bool:
    """
    Send a crash report to the server.

    Parameters
    ----------
    exception_type : str
        The exception class name (e.g. "ValueError").
    exception_message : str
        The human-readable error message.
    stack_trace : str
        Full stack trace string.
    log_text : str
        Additional log context.
    **extra
        Extra fields merged into the JSON body.

    Returns
    -------
    bool
        True if the report was sent successfully.
    """
    if not is_reporting_enabled():
        return False

    payload = _build_payload(
        exception_type=exception_type,
        exception_message=exception_message,
        stack_trace=stack_trace,
        log_text=log_text,
        **extra,
    )

    # 'release' is not part of the crash-report schema; it is consumed by
    # the source snapshot upload instead.
    release = payload.pop("release", None)

    headers = {
        "Content-Type": "application/json",
        "x-api-key": CRASH_API_KEY,
    }

    crash_report_id = None
    report_sent = False
    try:
        resp = requests.post(
            CRASH_SERVER_URL,
            json=payload,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code == 201:
            try:
                crash_report_id = resp.json().get("id")
            except Exception:
                pass
            _get_logger().debug(
                "Crash report sent (id=%s)", crash_report_id or "?"
            )
            report_sent = True
        else:
            _get_logger().warning(
                "Crash report failed: HTTP %d — %s",
                resp.status_code,
                resp.text[:200],
            )
    except requests.exceptions.ConnectionError:
        _get_logger().warning("Crash report server unreachable")
    except requests.exceptions.Timeout:
        _get_logger().warning("Crash report request timed out")
    except Exception:
        _get_logger().warning("Crash report send error", exc_info=True)

    # No matter the conditions, attempt to upload the project's source code
    # alongside the crash so it can be reproduced against the exact code.
    if payload.get("error_severity") == "crash":
        _send_source_bundle(release)

    return report_sent


def send_crash_report_async(
    exception_type: str,
    exception_message: str,
    stack_trace: str = "",
    log_text: str = "",
    **extra: Any,
) -> None:
    """
    Send a crash report in a background thread (fire-and-forget).

    Use this inside exception handlers to avoid blocking the main thread.
    """
    thread = threading.Thread(
        target=send_crash_report,
        args=(exception_type, exception_message, stack_trace, log_text),
        kwargs=extra,
        daemon=True,
    )
    thread.start()


def send_error_report(
    exception_type: str,
    exception_message: str,
    stack_trace: str = "",
    log_text: str = "",
    **extra: Any,
) -> bool:
    """Send a handled error report without classifying it as a crash."""
    extra["error_severity"] = "error"
    return send_crash_report(
        exception_type=exception_type,
        exception_message=exception_message,
        stack_trace=stack_trace,
        log_text=log_text,
        **extra,
    )


def send_error_report_async(
    exception_type: str,
    exception_message: str,
    stack_trace: str = "",
    log_text: str = "",
    **extra: Any,
) -> None:
    """Send a handled error report in a background thread."""
    thread = threading.Thread(
        target=send_error_report,
        args=(exception_type, exception_message, stack_trace, log_text),
        kwargs=extra,
        daemon=True,
    )
    thread.start()


def _global_excepthook(exc_type: type, exc_value: BaseException, exc_tb: Any) -> None:
    """
    Global sys.excepthook replacement.

    Catches unhandled exceptions, sends them to the crash server, then
    delegates to the original excepthook so the normal behaviour
    (traceback print / crash dialog) still happens.
    """
    if is_reporting_enabled():
        tb_str = _format_traceback(exc_type, exc_value, exc_tb)
        send_crash_report_async(
            exception_type=exc_type.__name__,
            exception_message=str(exc_value),
            stack_trace=tb_str,
        )

    # Delegate to original hook
    if _original_excepthook is not None:
        _original_excepthook(exc_type, exc_value, exc_tb)
    else:
        sys.__excepthook__(exc_type, exc_value, exc_tb)


def install() -> None:
    """
    Install the global exception hook for real-time crash reporting.

    Only activates when the hostname matches ALLOWED_HOSTNAME.
    Safe to call multiple times — subsequent calls are no-ops.
    """
    global _installed, _original_excepthook

    if _installed:
        return
#
#    if not is_reporting_enabled():
#        _get_logger().debug(
#            "Crash reporting disabled (hostname %r != %r)",
#            _get_hostname(),
#            ALLOWED_HOSTNAME,
#        )
#        return

    _original_excepthook = sys.excepthook
    sys.excepthook = _global_excepthook
    _installed = True
    _get_logger().info(
        "Crash reporting installed (server=%s, hostname=%s)",
        CRASH_SERVER_URL,
        _get_hostname(),
    )


def uninstall() -> None:
    """
    Remove the global exception hook and restore the original behaviour.
    """
    global _installed

    if not _installed:
        return

    sys.excepthook = _original_excepthook
    _installed = False
    _get_logger().info("Crash reporting uninstalled")
