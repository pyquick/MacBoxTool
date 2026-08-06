"""
crash_report.py: Real-time Crash Reporting Handler

Posts unhandled exceptions to the Crash Report Server (http://127.0.0.1:8080).
Only reports when the hostname matches "JN26".
"""

import logging
import socket
import sys
import threading
import traceback
from datetime import datetime, timezone
from typing import Any, Optional

import requests

# ── Configuration ──────────────────────────────────────────────
CRASH_SERVER_URL: str = "http://127.0.0.1:8080/api/v1/crash-report"
CRASH_API_KEY:  str = "crs_lvrPC3XE4yUCXPrdIt_44EAVQXnkqXcbSgWLDYktG1g"
ALLOWED_HOSTNAME: str = "GhltbmA2141.local"
PROJECT_NAME:    str = "MacBoxTool"

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

    headers = {
        "Content-Type": "application/json",
        "x-api-key": CRASH_API_KEY,
    }

    try:
        resp = requests.post(
            CRASH_SERVER_URL,
            json=payload,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code == 201:
            _get_logger().debug(
                "Crash report sent (id=%s)", resp.json().get("id", "?")
            )
            return True
        else:
            _get_logger().warning(
                "Crash report failed: HTTP %d — %s",
                resp.status_code,
                resp.text[:200],
            )
            return False
    except requests.exceptions.ConnectionError:
        _get_logger().warning("Crash report server unreachable")
        return False
    except requests.exceptions.Timeout:
        _get_logger().warning("Crash report request timed out")
        return False
    except Exception:
        _get_logger().warning("Crash report send error", exc_info=True)
        return False


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

    if not is_reporting_enabled():
        _get_logger().debug(
            "Crash reporting disabled (hostname %r != %r)",
            _get_hostname(),
            ALLOWED_HOSTNAME,
        )
        return

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
