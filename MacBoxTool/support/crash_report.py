"""
crash_report.py: Real-time Crash Reporting Handler

Posts unhandled exceptions to the Crash Report Server (http://192.168.1.157:8080).

Works in both source and packaged (PyInstaller) builds:
- sys.excepthook catches main-thread crashes, threading.excepthook worker threads
- After a crash, in-flight reports are flushed briefly before the process exits
- Packaged builds attach build identity (version, commit, Info.plist) instead of
  the source snapshot, because source files are not on disk when frozen
"""

import io
import logging
import os
import socket
import sys
import tarfile
import threading
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Tuple
from ..constants import Constants
import requests
cons=Constants()
# ── Configuration ──────────────────────────────────────────────
CRASH_SERVER_URL: str = "http://192.168.1.157:8080/api/v1/crash-report"
CRASH_API_KEY:  str = "crs_iq8Ka_xEbbRhpaJDStgH7p1dQfPt5OAopl2s8CkzZUA"
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

# How long the exception hooks wait for in-flight reports after a crash
# before handing control back (the process usually exits right after).
CRASH_REPORT_FLUSH_TIMEOUT: float = 1.0  # seconds

# ── Internal state ─────────────────────────────────────────────
_original_excepthook:          Any = None
_original_thread_excepthook:   Any = None
_installed:                    bool = False
_logger:                       Optional[logging.Logger] = None
_pending_sends:                set = set()
_pending_sends_lock:           threading.Lock = threading.Lock()


def _get_logger() -> logging.Logger:
    """Return a cached logger instance."""
    global _logger
    if _logger is None:
        _logger = logging.getLogger(__name__)
    return _logger


def _get_hostname() -> str:
    """Return the current hostname."""
    return socket.gethostname()


def _is_frozen() -> bool:
    """True when running from a packaged (PyInstaller) build."""
    return bool(getattr(sys, "frozen", False))


def _get_environment() -> str:
    """'production' for packaged builds, 'development' when running from source."""
    return "production" if _is_frozen() else "development"


def _get_frozen_metadata() -> dict:
    """
    Build-identity fields available in packaged builds.

    Source files are not on disk when frozen (the source snapshot upload is
    skipped instead), so attach what identifies the build: git branch/commit
    from the bundle's commit info, plus Info.plist fields on macOS.
    """
    metadata: dict = {}

    try:
        from ..support.commit_info import ParseCommitInfo
        branch, commit_date, commit_url = ParseCommitInfo(sys.executable).generate_commit_info()
        if branch != "Running from source":
            metadata["git_branch"] = branch
            metadata["git_commit_date"] = commit_date
            metadata["git_commit_url"] = commit_url
    except Exception:
        pass

    if sys.platform == "darwin":
        try:
            import plistlib
            plist_path = Path(sys.executable).resolve().parents[1] / "Info.plist"
            if plist_path.is_file():
                plist_info = plistlib.load(plist_path.open("rb"))
                for key in ("CFBundleVersion", "Build Date"):
                    if key in plist_info:
                        metadata[key.replace(" ", "_").lower()] = str(plist_info[key])
        except Exception:
            pass

    return metadata


def _track_pending_send(thread: threading.Thread) -> None:
    with _pending_sends_lock:
        _pending_sends.add(thread)


def _untrack_pending_send(thread: threading.Thread) -> None:
    with _pending_sends_lock:
        _pending_sends.discard(thread)


def _wait_for_pending_sends(timeout: float) -> None:
    """
    Join in-flight report threads for up to `timeout` seconds.

    Used before the process exits (e.g. from the exception hooks) so a
    fire-and-forget report gets a chance to reach the server.
    """
    deadline = time.monotonic() + timeout
    while True:
        with _pending_sends_lock:
            threads = list(_pending_sends)
        if not threads:
            return
        for thread in threads:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return
            thread.join(timeout=min(remaining, 0.5))
        with _pending_sends_lock:
            if not _pending_sends:
                return


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
        "release":cons.macboxtool_version,
        "environment": _get_environment(),
        "client_timestamp": datetime.now(timezone.utc).isoformat(),
        "error_severity": "crash",
    }

    # Packaged builds have no source tree on disk; attach build identity
    # instead so the server can still tell which build crashed.
    if _is_frozen():
        payload.update(_get_frozen_metadata())

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
    if _is_frozen():
        # Source files are archived inside the executable, not on disk.
        return None

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


def _send_in_background(
    target: Any,
    args: Tuple[Any, ...],
    kwargs: dict,
) -> threading.Thread:
    """
    Run a report sender in a daemon thread and track it as in-flight so the
    exception hooks can flush it before the process exits.
    """
    def _wrapped() -> None:
        try:
            target(*args, **kwargs)
        finally:
            _untrack_pending_send(thread)

    thread = threading.Thread(target=_wrapped, daemon=True)
    _track_pending_send(thread)
    thread.start()
    return thread


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
    _send_in_background(
        send_crash_report,
        (exception_type, exception_message, stack_trace, log_text),
        extra,
    )


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
    _send_in_background(
        send_error_report,
        (exception_type, exception_message, stack_trace, log_text),
        extra,
    )


def _global_excepthook(exc_type: type, exc_value: BaseException, exc_tb: Any) -> None:
    """
    Global sys.excepthook replacement (main-thread crashes).

    Catches unhandled exceptions, sends them to the crash server, then
    delegates to the original excepthook so the normal behaviour
    (traceback print / crash dialog) still happens.

    The process usually exits right after the original hook runs, so the
    in-flight report is flushed first (bounded by CRASH_REPORT_FLUSH_TIMEOUT).
    """
    tb_str = _format_traceback(exc_type, exc_value, exc_tb)
    send_crash_report_async(
        exception_type=exc_type.__name__,
        exception_message=str(exc_value),
        stack_trace=tb_str,
    )
    _wait_for_pending_sends(CRASH_REPORT_FLUSH_TIMEOUT)

    # Delegate to original hook
    if _original_excepthook is not None:
        _original_excepthook(exc_type, exc_value, exc_tb)
    else:
        sys.__excepthook__(exc_type, exc_value, exc_tb)


def _global_thread_excepthook(args: threading.ExceptHookArgs) -> None:
    """
    Global threading.excepthook replacement (worker-thread crashes).

    sys.excepthook is never called for unhandled exceptions in worker
    threads; without this hook they would only print to stderr and be lost.
    """
    tb_str = "".join(
        traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)
    )
    extra: dict = {}
    if args.thread is not None:
        extra["thread_name"] = args.thread.name
        extra["thread_ident"] = args.thread.ident
    send_crash_report_async(
        exception_type=args.exc_type.__name__,
        exception_message=str(args.exc_value),
        stack_trace=tb_str,
        **extra,
    )

    # Delegate to original hook
    if _original_thread_excepthook is not None:
        _original_thread_excepthook(args)
    else:
        threading.__excepthook__(args)


def install() -> None:
    """
    Install the global exception hooks for real-time crash reporting.

    Covers unhandled exceptions in the main thread (sys.excepthook) and in
    worker threads (threading.excepthook). Active in source and packaged
    builds alike. Safe to call multiple times — subsequent calls are no-ops.
    """
    global _installed, _original_excepthook, _original_thread_excepthook

    if _installed:
        return

    _original_excepthook = sys.excepthook
    sys.excepthook = _global_excepthook

    _original_thread_excepthook = threading.excepthook
    threading.excepthook = _global_thread_excepthook

    _installed = True
    _get_logger().info(
        "Crash reporting installed (server=%s, hostname=%s, frozen=%s)",
        CRASH_SERVER_URL,
        _get_hostname(),
        _is_frozen(),
    )


def uninstall() -> None:
    """
    Remove the global exception hooks and restore the original behaviour.
    """
    global _installed, _original_thread_excepthook

    if not _installed:
        return

    sys.excepthook = _original_excepthook
    threading.excepthook = _original_thread_excepthook
    _installed = False
    _get_logger().info("Crash reporting uninstalled")
