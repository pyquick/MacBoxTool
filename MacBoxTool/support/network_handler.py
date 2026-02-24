"""
network_handler.py: Network utilities and download management
"""
from ..include import *
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import threading
import os
from typing import Optional


class DownloadStatus:
    """Download task status enum"""
    PENDING = "pending"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DownloadObject:
    """Download task data structure"""

    def __init__(self, url: str, save_path: str, filename: str = None):
        self.url = url
        self.save_path = save_path
        self.filename = filename or os.path.basename(url)
        self.total_size = 0
        self.downloaded_size = 0
        self.status = DownloadStatus.PENDING
        self.thread_count = 16
        self.error_message = ""
        self.created_at = QDateTime.currentDateTime()
        self.completed_at = None

    def update_progress(self, downloaded: int, total: int):
        """Update download progress"""
        self.downloaded_size = downloaded
        if total > 0:
            self.total_size = total

    def get_progress_percentage(self) -> int:
        """Get download progress percentage"""
        if self.total_size == 0:
            return 0
        return int((self.downloaded_size / self.total_size) * 100)

    def get_size_display(self) -> str:
        """Get formatted size display"""
        downloaded = self._format_size(self.downloaded_size)
        total = self._format_size(self.total_size)
        return f"{downloaded} / {total}"

    @staticmethod
    def _format_size(size: int) -> str:
        """Format size in bytes to human readable format"""
        if size == 0:
            return "0 B"
        units = ["B", "KB", "MB", "GB", "TB"]
        unit_index = 0
        size_float = float(size)
        while size_float >= 1024 and unit_index < len(units) - 1:
            size_float /= 1024
            unit_index += 1
        if unit_index == 0:
            return f"{int(size_float)} {units[unit_index]}"
        return f"{size_float:.2f} {units[unit_index]}"

    def is_downloading(self) -> bool:
        return self.status == DownloadStatus.DOWNLOADING

    def is_completed(self) -> bool:
        return self.status == DownloadStatus.COMPLETED

    def is_failed(self) -> bool:
        return self.status == DownloadStatus.FAILED


class NetworkUtilities:
    """Network utility methods"""

    _session = None
    _thread_local = threading.local()

    @classmethod
    def _get_session(cls) -> requests.Session:
        """Get or create a requests session with retry strategy"""
        if cls._session is None:
            cls._session = requests.Session()
            retry_strategy = Retry(
                total=3,
                backoff_factor=1,
                status_forcelist=[429, 500, 502, 503, 504],
            )
            adapter = HTTPAdapter(max_retries=retry_strategy)
            cls._session.mount("http://", adapter)
            cls._session.mount("https://", adapter)
        return cls._session

    @classmethod
    def check_network(cls) -> bool:
        """Check network connectivity via HEAD request to GitHub.com"""
        try:
            session = cls._get_session()
            response = session.head("https://github.com", timeout=10)
            return response.status_code == 200
        except Exception as e:
            logging.warning(f"Network check failed: {e}")
            return False

    @classmethod
    def custom_get(cls, url: str, **kwargs) -> requests.Response:
        """Custom GET request wrapper"""
        session = cls._get_session()
        timeout = kwargs.pop('timeout', 30)
        return session.get(url, timeout=timeout, **kwargs)

    @classmethod
    def custom_post(cls, url: str, **kwargs) -> requests.Response:
        """Custom POST request wrapper"""
        session = cls._get_session()
        timeout = kwargs.pop('timeout', 30)
        return session.post(url, timeout=timeout, **kwargs)

    @classmethod
    def get_file_size(cls, url: str) -> int:
        """Get file size from URL without downloading"""
        try:
            session = cls._get_session()
            response = session.head(url, allow_redirects=True, timeout=10)
            return int(response.headers.get('content-length', 0))
        except Exception as e:
            logging.warning(f"Failed to get file size: {e}")
            return 0


class DownloadWorker(QThread):
    """Multi-threaded download worker (16 threads)"""
    progress_signal = Signal(int, int)  # downloaded, total
    finished_signal = Signal(bool, str)  # success, message
    status_changed_signal = Signal(str)  # DownloadStatus

    def __init__(self, download_object: DownloadObject):
        super().__init__()
        self.download = download_object
        self._is_cancelled = False
        self._lock = threading.Lock()

    def run(self):
        """Execute multi-threaded download with 16 threads"""
        try:
            self.status_changed_signal.emit(DownloadStatus.DOWNLOADING)
            self.download.status = DownloadStatus.DOWNLOADING

            # Get file size
            total_size = NetworkUtilities.get_file_size(self.download.url)
            if total_size == 0:
                # Fallback: download normally if HEAD request fails
                self._download_single_thread(total_size)
                return

            self.download.total_size = total_size

            # Create temp directory for parts
            temp_dir = os.path.join(self.download.save_path, ".temp")
            os.makedirs(temp_dir, exist_ok=True)

            # Calculate chunk size for 16 threads
            chunk_size = total_size // 16
            threads = []
            parts = []

            # Start 16 threads to download different parts
            for i in range(16):
                start = i * chunk_size
                end = total_size if i == 15 else (i + 1) * chunk_size
                part_file = os.path.join(temp_dir, f"part_{i}")

                if self._is_cancelled:
                    self._cleanup_temp(temp_dir)
                    self.status_changed_signal.emit(DownloadStatus.CANCELLED)
                    self.download.status = DownloadStatus.CANCELLED
                    self.finished_signal.emit(False, "Download cancelled")
                    return

                thread = threading.Thread(
                    target=self._download_range,
                    args=(self.download.url, start, end - 1, part_file, i)
                )
                threads.append(thread)
                parts.append(part_file)
                thread.start()

            # Wait for all threads to complete
            for thread in threads:
                thread.join()

            if self._is_cancelled:
                self._cleanup_temp(temp_dir)
                self.status_changed_signal.emit(DownloadStatus.CANCELLED)
                self.download.status = DownloadStatus.CANCELLED
                self.finished_signal.emit(False, "Download cancelled")
                return

            # Combine parts
            final_path = os.path.join(self.download.save_path, self.download.filename)
            self._combine_parts(parts, final_path)

            # Cleanup temp directory
            self._cleanup_temp(temp_dir)

            self.download.status = DownloadStatus.COMPLETED
            self.status_changed_signal.emit(DownloadStatus.COMPLETED)
            self.finished_signal.emit(True, final_path)

        except Exception as e:
            logging.error(f"Download failed: {e}")
            self.download.status = DownloadStatus.FAILED
            self.download.error_message = str(e)
            self.status_changed_signal.emit(DownloadStatus.FAILED)
            self.finished_signal.emit(False, str(e))

    def _download_range(self, url: str, start: int, end: int, part_file: str, thread_id: int):
        """Download a specific range of bytes"""
        try:
            headers = {'Range': f'bytes={start}-{end}'}
            response = NetworkUtilities.custom_get(url, headers=headers, stream=True)

            with open(part_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if self._is_cancelled:
                        return
                    f.write(chunk)

            # Update progress
            with self._lock:
                self.download.downloaded_size += (end - start + 1)
                self.progress_signal.emit(self.download.downloaded_size, self.download.total_size)

        except Exception as e:
            logging.error(f"Thread {thread_id} download failed: {e}")

    def _download_single_thread(self, total_size: int):
        """Fallback single-thread download"""
        try:
            final_path = os.path.join(self.download.save_path, self.download.filename)
            response = NetworkUtilities.custom_get(self.download.url, stream=True)

            with open(final_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if self._is_cancelled:
                        self.download.status = DownloadStatus.CANCELLED
                        self.status_changed_signal.emit(DownloadStatus.CANCELLED)
                        self.finished_signal.emit(False, "Download cancelled")
                        return
                    f.write(chunk)
                    self.download.downloaded_size += len(chunk)
                    self.progress_signal.emit(self.download.downloaded_size, total_size)

            self.download.status = DownloadStatus.COMPLETED
            self.status_changed_signal.emit(DownloadStatus.COMPLETED)
            self.finished_signal.emit(True, final_path)

        except Exception as e:
            self.download.status = DownloadStatus.FAILED
            self.download.error_message = str(e)
            self.status_changed_signal.emit(DownloadStatus.FAILED)
            self.finished_signal.emit(False, str(e))

    def _combine_parts(self, parts: list, final_path: str):
        """Combine downloaded parts into final file"""
        with open(final_path, 'wb') as outfile:
            for part in parts:
                with open(part, 'rb') as infile:
                    outfile.write(infile.read())

    def _cleanup_temp(self, temp_dir: str):
        """Clean up temporary files"""
        try:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
        except Exception as e:
            logging.warning(f"Failed to cleanup temp directory: {e}")

    def cancel(self):
        """Cancel the download"""
        self._is_cancelled = True


class DownloadHistory:
    """Download history manager"""

    def __init__(self):
        self.history: list[DownloadObject] = []
        self._load_history()

    def add(self, download: DownloadObject):
        """Add download to history"""
        self.history.append(download)
        self._save_history()

    def remove(self, download: DownloadObject):
        """Remove download from history"""
        if download in self.history:
            self.history.remove(download)
            self._save_history()

    def clear(self):
        """Clear all history"""
        self.history.clear()
        self._save_history()

    def _get_history_path(self) -> str:
        """Get history file path"""
        app_data = QStandardPaths.standardLocations(QStandardPaths.StandardLocation.AppDataLocation)[0]
        return os.path.join(app_data, "download_history.json")

    def _save_history(self):
        """Save history to file"""
        try:
            history_path = self._get_history_path()
            os.makedirs(os.path.dirname(history_path), exist_ok=True)

            data = []
            for d in self.history:
                data.append({
                    "url": d.url,
                    "filename": d.filename,
                    "save_path": d.save_path,
                    "total_size": d.total_size,
                    "downloaded_size": d.downloaded_size,
                    "status": d.status,
                    "completed_at": d.completed_at.toSecsSinceEpoch() if d.completed_at else None
                })

            with open(history_path, 'w') as f:
                json.dump(data, f)

        except Exception as e:
            logging.error(f"Failed to save download history: {e}")

    def _load_history(self):
        """Load history from file"""
        try:
            history_path = self._get_history_path()
            if not os.path.exists(history_path):
                return

            with open(history_path, 'r') as f:
                data = json.load(f)

            for item in data:
                download = DownloadObject(item["url"], item["save_path"], item["filename"])
                download.total_size = item.get("total_size", 0)
                download.downloaded_size = item.get("downloaded_size", 0)
                download.status = item.get("status", DownloadStatus.COMPLETED)
                if item.get("completed_at"):
                    download.completed_at = QDateTime.fromSecsSinceEpoch(item["completed_at"])
                self.history.append(download)

        except Exception as e:
            logging.error(f"Failed to load download history: {e}")