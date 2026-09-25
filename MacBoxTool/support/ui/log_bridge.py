"""
log_bridge.py: Route Python logging into a Qt signal for live log panes.

Only `logging` is imported here — the signal objects are duck-typed, so this
module carries no Qt or project dependency. It replaces two near-identical
handler classes that had grown up separately in the build and sys-patch pages:
the sys-patch one was a strict subset (thread filter + format + emit) of the
build one, which additionally maps log lines onto build stages and progress.
"""

import logging


class QtLogHandler(logging.Handler):
    """
    Forward formatted log records to a Qt signal.

    Args:
        log_signal: emitted with each formatted message (``str``).
        progress_signal: optional; emitted with a percentage when a stage in
            `stage_map` is recognised.
        thread_id: when set, records from other threads are dropped. Pass the
            worker thread's ident so a page only shows its own output.
        stage_map: optional sequence of ``(pattern, percent, stage_name)``. The
            first pattern found in a message selects the stage; each new stage
            is announced on `log_signal` as ``"[STEP] <stage_name>"``, and the
            percent is emitted on `progress_signal` when it advances.
    """

    def __init__(self, log_signal, progress_signal=None, thread_id=None, stage_map=None):
        super().__init__()
        self._log_signal = log_signal
        self._progress_signal = progress_signal
        self._thread_id = thread_id
        self._stage_map = tuple(stage_map or ())
        self._last_progress = 0
        self._last_stage = None

    def _emit_stage_progress(self, message: str) -> None:
        for pattern, percent, stage_name in self._stage_map:
            if pattern not in message:
                continue
            if stage_name != self._last_stage:
                self._last_stage = stage_name
                self._log_signal.emit(f"[STEP] {stage_name}")
            if self._progress_signal and percent > self._last_progress:
                self._last_progress = percent
                self._progress_signal.emit(percent)
            return

    def emit(self, record: logging.LogRecord) -> None:
        if self._thread_id is not None and record.thread != self._thread_id:
            return
        message = self.format(record)
        if self._stage_map:
            self._emit_stage_progress(message)
        self._log_signal.emit(message)
