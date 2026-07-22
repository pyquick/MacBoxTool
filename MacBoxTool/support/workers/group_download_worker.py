"""QThread worker for grouped macOS installer component downloads."""

import logging
import threading
from pathlib import Path

from PySide6.QtCore import QThread, Signal, Qt

from ..network_handler import DownloadObject, DownloadWorker, DownloadStatus


class GroupDownloadWorker(QThread):
    """Download all installer components concurrently while exposing one task."""

    progress_signal = Signal(object, object)
    finished_signal = Signal(bool, str)
    status_changed_signal = Signal(str)

    def __init__(self, download: DownloadObject, constants=None):
        super().__init__()
        self.download = download
        self.constants = constants
        self._is_cancelled = False
        self._is_paused = False
        self._workers: list[DownloadWorker] = []
        self._results = []
        self._lock = threading.Lock()

    def cancel(self) -> None:
        self._is_cancelled = True
        for worker in self._workers:
            worker.cancel()

    def pause(self) -> None:
        self._is_paused = True
        self.download.status = DownloadStatus.PAUSED
        for worker in self._workers:
            worker.pause()
        self.status_changed_signal.emit(DownloadStatus.PAUSED)

    def resume(self) -> None:
        self._is_paused = False
        self.download.status = DownloadStatus.DOWNLOADING
        for worker in self._workers:
            worker.resume()
        self.status_changed_signal.emit(DownloadStatus.DOWNLOADING)

    def run(self) -> None:
        try:
            self.download.status = DownloadStatus.DOWNLOADING
            self.status_changed_signal.emit(DownloadStatus.DOWNLOADING)
            self.download.component_progress = [
                [0, component.get("Size", 0)] for component in self.download.components
            ]
            self.download.total_size = sum(
                component.get("Size", 0) for component in self.download.components
            )
            self._results = [None] * len(self.download.components)

            for index, component in enumerate(self.download.components):
                url = component["URL"]
                child = DownloadObject(url, self.download.save_path, Path(url).name)
                child.total_size = component.get("Size", 0)
                child.thread_count = max(
                    1,
                    self.download.thread_count // len(self.download.components),
                )
                worker = DownloadWorker(child, self.constants)
                worker.progress_signal.connect(
                    lambda current, total, i=index: self._on_component_progress(
                        i, current, total
                    ),
                    Qt.ConnectionType.DirectConnection,
                )
                worker.finished_signal.connect(
                    lambda success, message, i=index: self._on_component_finished(
                        i, success, message
                    ),
                    Qt.ConnectionType.DirectConnection,
                )
                self._workers.append(worker)

            for worker in self._workers:
                worker.start()
                if self._is_paused:
                    worker.pause()

            for worker in self._workers:
                worker.wait()

            if self._is_cancelled:
                self._finish_cancelled()
                return

            for index, component in enumerate(self.download.components):
                result = self._results[index]
                filename = Path(component["URL"]).name
                if not result or not result[0]:
                    message = result[1] if result else f"Failed to download {filename}"
                    self._finish_failed(message)
                    return

                component_size = Path(result[1]).stat().st_size
                expected_size = component.get("Size", 0)
                if expected_size and component_size != expected_size:
                    self._finish_failed(
                        f"Size mismatch for {filename}: expected {expected_size}, "
                        f"got {component_size}"
                    )
                    return
                self._on_component_progress(index, component_size, component_size)

            self.download.downloaded_size = self.download.total_size
            self.finished_signal.emit(True, self.download.save_path)
        except Exception as error:
            logging.error(f"Grouped download failed: {error}")
            self._finish_failed(str(error))
        finally:
            self._workers.clear()

    def _on_component_progress(self, index: int, current: int, total: int) -> None:
        with self._lock:
            configured_total = self.download.component_progress[index][1]
            component_total = configured_total or total
            self.download.component_progress[index] = [current, component_total]
            downloaded = sum(
                component_downloaded
                for component_downloaded, _ in self.download.component_progress
            )
            combined_total = sum(
                component_total
                for _, component_total in self.download.component_progress
            )
            self.download.update_progress(downloaded, combined_total)
        self.progress_signal.emit(downloaded, combined_total)

    def _on_component_finished(self, index: int, success: bool, message: str) -> None:
        with self._lock:
            self._results[index] = (success, message)
        if not success and not self._is_cancelled:
            for worker_index, worker in enumerate(self._workers):
                if worker_index != index:
                    worker.cancel()

    def _finish_failed(self, message: str) -> None:
        self.download.status = DownloadStatus.FAILED
        self.download.error_message = message
        self.status_changed_signal.emit(DownloadStatus.FAILED)
        self.finished_signal.emit(False, message)

    def _finish_cancelled(self) -> None:
        self.download.status = DownloadStatus.CANCELLED
        self.status_changed_signal.emit(DownloadStatus.CANCELLED)
        self.finished_signal.emit(False, "Download cancelled")
