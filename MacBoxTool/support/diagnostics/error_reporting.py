"""
error_reporting.py: Safe entry point for crash/error reporting.

`crash_report` is a development-only module: it instantiates `Constants()` and
configures a reporting endpoint at import time, so it may be absent (or fail to
import) in a shipped build. GUI pages must never break because of that.

This wrapper resolves the real implementation lazily on each call and degrades
to a silent no-op when it is unavailable, which is exactly what the per-page
try/except import blocks used to do by hand.
"""

import logging


def send_error_report_async(*args, **kwargs) -> None:
    """
    Forward to `crash_report.send_error_report_async` when it is available.

    Never raises: error reporting must not be able to take down the caller.
    """
    try:
        from .crash_report import send_error_report_async as _implementation
    except Exception as exc:  # module absent, or failed at import time
        logging.debug("Error reporting unavailable, dropping report: %s", exc)
        return
    _implementation(*args, **kwargs)
