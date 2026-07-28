"""
network_handler.py: Network utilities and download management
"""
import logging
import os
import ssl
import requests
import urllib3
from requests.adapters import HTTPAdapter
from urllib.parse import urlparse
from urllib3.exceptions import InsecureRequestWarning
from urllib3.util.retry import Retry
import threading
import sys
if sys.platform=="darwin":
    import MacBoxTool.support.utilities as utilities
else:
    import MacBoxTool.support.utilities_win as utilities
import os
from PySide6.QtWidgets import *
from PySide6.QtGui import *
from PySide6.QtCore import *
from .. import constants
import json,shutil
from typing import Optional

SESSION = requests.Session()

# Security constants
ALLOWED_URL_SCHEMES = {'https', 'http'}
MAX_REDIRECTS = 10
MAX_MEMORY_USAGE = 1024 * 1024 * 1024 * 1024  # 1TB max memory for multipart downloads
SENSITIVE_PARAMS = {'token', 'key', 'api_key', 'apikey', 'secret', 'password', 'auth', 'access_token'}

MAX_RANGE_RETRIES = 5
RANGE_RETRY_BACKOFF = 1.0


def _certificate_bundle() -> str | bool:
    verify_paths = ssl.get_default_verify_paths()
    for path in (verify_paths.cafile, "/etc/ssl/cert.pem"):
        if path and os.path.isfile(path):
            return path
    return True


TLS_CERTIFICATE_BUNDLE = _certificate_bundle()
TLS_REQUIRED_HOSTS = {
    "swscan.apple.com",
    "swcdn.apple.com",
    "updates.cdn-apple.com",
    "updates-http.cdn-apple.com",
}


def _tls_verification(url: str) -> str | bool:
    if urlparse(url).hostname in TLS_REQUIRED_HOSTS:
        return TLS_CERTIFICATE_BUNDLE
    return False


urllib3.disable_warnings(InsecureRequestWarning)

class DownloadStatus:
    """Download task status enum"""
    PENDING = "pending"
    DOWNLOADING = "downloading"
    PAUSED = "paused"
    VALIDATING = "validating"
    EXTRACTING = "extracting"
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
        self.completed_at: Optional[QDateTime] = None
        self.last_update_time = QDateTime.currentDateTime()
        self.last_downloaded_size = 0
        self.download_speed = 0
        self.icon_path = None
        self.display_name = self.filename
        self.components = []
        self.component_progress = []
        self.output_path = None
        self.installer_app_name = None
        self.replace_existing_app = False

        # Validation progress tracking
        self.current_validation_chunk = 0
        self.total_validation_chunks = 0
        self.chunklist_url = None  # URL to download chunklist for validation
        self.legacy_installer = False
        self.requires_validation = False
        self.requires_extraction = False

    def update_progress(self, downloaded: int, total: int):
        """Update download progress and calculate speed"""
        current_time = QDateTime.currentDateTime()
        time_diff = self.last_update_time.msecsTo(current_time) / 1000.0

        # Only update speed if enough time has passed (at least 0.1s)
        if time_diff >= 0.1:
            bytes_diff = downloaded - self.last_downloaded_size
            self.download_speed = bytes_diff / time_diff if time_diff > 0 else 0
            self.last_update_time = current_time
            self.last_downloaded_size = downloaded

        self.downloaded_size = downloaded
        if total > 0:
            self.total_size = total

    

    def get_speed_display(self) -> str:
        """Get formatted speed display"""
        return f"{self._format_size(int(self.download_speed))}/s"

    def get_progress_percentage(self) -> int:
        """Get download progress percentage"""
        if self.status == DownloadStatus.VALIDATING and self.total_validation_chunks > 0:
            return int((self.current_validation_chunk / self.total_validation_chunks) * 100)
        if self.components and self.component_progress:
            combined_total = sum(total for _, total in self.component_progress)
            if combined_total == 0:
                return 0
            combined_downloaded = sum(
                downloaded for downloaded, _ in self.component_progress
            )
            return int((combined_downloaded / combined_total) * 100)
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

    def __init__(self, global_constants: constants.Constants = None):
        self.constants = global_constants
        self._session = None
        self.headers=None

    def _apply_github_headers(self, url: str, kwargs: dict) -> dict:
        token = getattr(self.constants, "github_token", "") if self.constants else ""
        if token and "api.github.com" in url:
            headers = dict(kwargs.get("headers") or {})
            headers.setdefault("Accept", "application/vnd.github+json")
            headers.setdefault("X-GitHub-Api-Version", "2022-11-28")
            headers.setdefault("Authorization", f"Bearer {token}")
            kwargs["headers"] = headers
        return kwargs
    
    def _github_headers(self) -> dict:
        self.token = self.constants.github_token
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _get_session(self) -> requests.Session:
        """Get or create a requests session with retry strategy"""
        if self._session is None:
            self._session = requests.Session()
            retry_strategy = Retry(
                total=3,
                backoff_factor=1,
                status_forcelist=[429, 500, 502, 503, 504],
            )
            adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=20, pool_maxsize=20)
            self._session.mount("http://", adapter)
            self._session.mount("https://", adapter)
        return self._session

    def check_network(self) -> bool:
        """Check network connectivity via HEAD request to GitHub.com"""
        try:
            session = self._get_session()
            response = session.head(
                "https://github.com",
                timeout=10,
                verify=_tls_verification("https://github.com"),
            )
            return response.status_code == 200
        except Exception as e:
            logging.warning(f"Network check failed: {e}")
            return False


    def verify_network_connection(self, url: str, timeout: int) -> bool:
        """
        Verifies that the network is available

        Returns:
            bool: True if network is available, False otherwise
        """
        self.headers=self._github_headers()
        try:
            if "nightly.link" in url:
                response=requests.get(url, timeout=timeout, allow_redirects=True, verify=_tls_verification(url), stream=True, headers=self.headers)
            else:
                response = requests.head(url, timeout=timeout, allow_redirects=True, verify=_tls_verification(url), headers=self.headers)
            
            print("Checking network connection...")
            if response.status_code == 200:
                print("Network connection verified")
                return True
            if response.status_code == 404:
                print("Network connection is 404")
                return False
            print(f"Status Co: {response.status_code}")
            return True
        except (
            requests.exceptions.Timeout,
            requests.exceptions.TooManyRedirects,
            requests.exceptions.ConnectionError,
            requests.exceptions.HTTPError,
            requests.exceptions.SSLError
        ) as e:
            print(f"Error:{e}")
            return False

    def get(self, url: str, **kwargs) -> requests.Response:
        """
        Wrapper for requests's get method
        Implement additional error handling

        Parameters:
            url (str): URL to get
            **kwargs: Additional parameters for requests.get

        Returns:
            requests.Response: Response object from requests.get
        """
        
        result: requests.Response = None

        try:
            # Set default max redirects if not specified
            if 'allow_redirects' in kwargs and kwargs['allow_redirects']:
                kwargs['max_redirects'] = kwargs.get('max_redirects', MAX_REDIRECTS)
            kwargs = self._apply_github_headers(url, kwargs)
            kwargs.setdefault('timeout', 30)
            kwargs.setdefault('verify', _tls_verification(url))
            result = self._get_session().get(url, **kwargs)
        except (
            requests.exceptions.Timeout,
            requests.exceptions.TooManyRedirects,
            requests.exceptions.ConnectionError,
            requests.exceptions.HTTPError,
            requests.exceptions.SSLError
        ) as error:
            logging.warning(f"'Error calling requests.get': {error}")
            # Return empty response object
            return requests.Response()

        return result

    def custom_get(self, url: str, **kwargs) -> requests.Response:
        """Custom GET request wrapper"""
        session = self._get_session()
        timeout = kwargs.pop('timeout', 30)
        kwargs = self._apply_github_headers(url, kwargs)
        kwargs.setdefault('verify', False)
        return session.get(url, timeout=timeout, **kwargs)

    def custom_post(self, url: str, **kwargs) -> requests.Response:
        """Custom POST request wrapper"""
        session = self._get_session()
        timeout = kwargs.pop('timeout', 30)
        kwargs = self._apply_github_headers(url, kwargs)
        kwargs.setdefault('verify', False)
        return session.post(url, timeout=timeout, **kwargs)

    def post(self, url: str, **kwargs) -> requests.Response:
        return self.custom_post(url, **kwargs)

    def get_file_size(self, url: str) -> int:
        """Get file size from URL without downloading"""
        try:
            session = self._get_session()
            response = session.head(
                url,
                allow_redirects=True,
                timeout=10,
                verify=_tls_verification(url),
            )
            return int(response.headers.get('content-length', 0))
        except Exception as e:
            logging.warning(f"[NetworkUtilities] Failed to get file size: {e}")
            return 0


class DownloadWorker(QThread):
    """Multi-threaded download worker"""
    progress_signal = Signal(object, object)  # downloaded, total (object to avoid 32-bit int overflow)
    finished_signal = Signal(bool, str)  # success, message
    status_changed_signal = Signal(str)  # DownloadStatus

    def __init__(self, download_object: DownloadObject, global_constants: constants.Constants = None):
        super().__init__()
        self.download = download_object
        self.constants = global_constants
        self.network_utilities = NetworkUtilities(self.constants)
        self._is_cancelled = False
        self._is_paused = False
        self._lock = threading.Lock()
        self._download_errors = []
        self._range_failed = threading.Event()

    def run(self):
        """Execute multi-threaded download"""
        try:
            # Unified logging: Download start
            logging.info(f"[DownloadWorker] Starting: {self.download.filename}")

            utilities.disable_sleep_while_running()
            self.status_changed_signal.emit(DownloadStatus.DOWNLOADING)
            self.download.status = DownloadStatus.DOWNLOADING

            # Check if file already exists and delete it
            final_path = os.path.join(self.download.save_path, self.download.filename)
            if os.path.isdir(final_path):
                raise IsADirectoryError(f"Download destination is a directory: {final_path}")
            if os.path.exists(final_path):
                logging.info(f"[DownloadWorker] Removing existing file: {final_path}")
                try:
                    os.remove(final_path)
                    logging.info(f"[DownloadWorker] Removed: {final_path}")
                except Exception as e:
                    logging.warning(f"[DownloadWorker] Failed to remove {final_path}: {e}")
                    raise

            # Get file size
            total_size = self.network_utilities.get_file_size(self.download.url)
            if total_size == 0:
                # Fallback: download normally if HEAD request fails
                self._download_single_thread(total_size)
                return

            self.download.total_size = total_size

            thread_count = max(1, self.download.thread_count)

            # Fall back to single-thread for small files
            if total_size < thread_count * 8192:
                self._download_single_thread(total_size)
                return

            # Create temp directory for parts (unique per download to avoid race conditions)
            safe_name = self.download.filename.replace(os.sep, "_")
            temp_dir = os.path.join(self.download.save_path, f".temp_{safe_name}")
            os.makedirs(temp_dir, exist_ok=True)

            # Split the file across the configured worker threads
            chunk_size = total_size // thread_count
            threads = []
            parts = []

            for i in range(thread_count):
                start = i * chunk_size
                end = total_size if i == thread_count - 1 else (i + 1) * chunk_size
                part_file = os.path.join(temp_dir, f"part_{i}")

                if self._is_cancelled:
                    self._cleanup_temp(temp_dir)
                    self.status_changed_signal.emit(DownloadStatus.CANCELLED)
                    self.download.status = DownloadStatus.CANCELLED
                    self.finished_signal.emit(False, "Download cancelled")
                    utilities.enable_sleep_after_running()
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

            if self._download_errors:
                self._cleanup_temp(temp_dir)
                raise RuntimeError(self._download_errors[0])

            if self._is_cancelled:
                self._cleanup_temp(temp_dir)
                self.status_changed_signal.emit(DownloadStatus.CANCELLED)
                self.download.status = DownloadStatus.CANCELLED
                self.finished_signal.emit(False, "Download cancelled")
                utilities.enable_sleep_after_running()
                return

            # Combine parts
            final_path = os.path.join(self.download.save_path, self.download.filename)
            self._combine_parts(parts, final_path)

            # Correct total_size from actual file size
            actual_size = os.path.getsize(final_path)
            self.download.total_size = actual_size
            self.download.downloaded_size = actual_size

            # Cleanup temp directory
            self._cleanup_temp(temp_dir)
            utilities.enable_sleep_after_running()

            self.download.status = DownloadStatus.COMPLETED
            self.download.completed_at = QDateTime.currentDateTime()
            self.status_changed_signal.emit(DownloadStatus.COMPLETED)
            self.finished_signal.emit(True, final_path)

        except Exception as e:
            logging.error(f"Download failed: {e}")
            self.download.status = DownloadStatus.FAILED
            self.download.error_message = str(e)
            self.status_changed_signal.emit(DownloadStatus.FAILED)
            self.finished_signal.emit(False, str(e))
            utilities.enable_sleep_after_running()

    def _download_range(self, url: str, start: int, end: int, part_file: str, thread_id: int):
        """Download a byte range and resume it after transient stream failures."""
        expected_size = end - start + 1
        bytes_written = 0

        with open(part_file, 'wb') as output:
            for attempt in range(MAX_RANGE_RETRIES + 1):
                response = None
                try:
                    range_start = start + bytes_written
                    headers = {
                        'Range': f'bytes={range_start}-{end}',
                        'Accept-Encoding': 'identity',
                    }
                    response = self.network_utilities.custom_get(
                        url,
                        headers=headers,
                        stream=True,
                        timeout=(30, 120),
                    )
                    response.raise_for_status()

                    expected_range = f"bytes {range_start}-{end}/"
                    content_range = response.headers.get('Content-Range', '')
                    if response.status_code != 206 or not content_range.startswith(expected_range):
                        raise RuntimeError(
                            f"Server returned an invalid range for part {thread_id}: "
                            f"HTTP {response.status_code}, Content-Range={content_range!r}"
                        )

                    for chunk in response.iter_content(chunk_size=64 * 1024):
                        if self._is_cancelled or self._range_failed.is_set():
                            return
                        while self._is_paused:
                            if self._is_cancelled:
                                return
                            threading.Event().wait(0.1)
                        if not chunk:
                            continue
                        output.write(chunk)
                        bytes_written += len(chunk)
                        with self._lock:
                            self.download.update_progress(
                                self.download.downloaded_size + len(chunk),
                                self.download.total_size,
                            )
                            self.progress_signal.emit(
                                self.download.downloaded_size,
                                self.download.total_size,
                            )

                    if bytes_written == expected_size:
                        return
                    raise requests.exceptions.ChunkedEncodingError(
                        f"Incomplete response: expected {expected_size}, got {bytes_written}"
                    )
                except (
                    requests.exceptions.ConnectionError,
                    requests.exceptions.ChunkedEncodingError,
                    requests.exceptions.ReadTimeout,
                    requests.exceptions.Timeout,
                ) as error:
                    if attempt >= MAX_RANGE_RETRIES:
                        self._record_range_error(thread_id, error)
                        return
                    logging.warning(
                        f"[DownloadWorker] Part {thread_id} interrupted after "
                        f"{bytes_written}/{expected_size} bytes; resuming "
                        f"(attempt {attempt + 2}/{MAX_RANGE_RETRIES + 1}): {error}"
                    )
                    threading.Event().wait(RANGE_RETRY_BACKOFF * (attempt + 1))
                except Exception as error:
                    self._record_range_error(thread_id, error)
                    return
                finally:
                    if response is not None:
                        response.close()

    def _record_range_error(self, thread_id: int, error: Exception) -> None:
        error_message = f"Download part {thread_id} failed: {error}"
        logging.error(f"[DownloadWorker] {error_message}")
        self._range_failed.set()
        with self._lock:
            self._download_errors.append(error_message)

    def _download_single_thread(self, total_size: int):
        """Fallback single-thread download with stream retry support."""
        final_path = os.path.join(self.download.save_path, self.download.filename)
        self.download.total_size = total_size

        for attempt in range(MAX_RANGE_RETRIES + 1):
            response = None
            try:
                downloaded = os.path.getsize(final_path) if os.path.exists(final_path) else 0
                headers = {'Accept-Encoding': 'identity'}
                if downloaded:
                    headers['Range'] = f'bytes={downloaded}-'
                response = self.network_utilities.custom_get(
                    self.download.url,
                    headers=headers,
                    stream=True,
                    timeout=(30, 120),
                )
                response.raise_for_status()

                if downloaded:
                    content_range = response.headers.get('Content-Range', '')
                    if response.status_code != 206 or not content_range.startswith(
                        f'bytes {downloaded}-'
                    ):
                        raise RuntimeError(
                            f"Server did not honor resume request: {content_range!r}"
                        )
                elif total_size == 0:
                    total_size = int(response.headers.get('content-length', 0))
                    self.download.total_size = total_size

                with open(final_path, 'ab' if downloaded else 'wb') as output:
                    for chunk in response.iter_content(chunk_size=64 * 1024):
                        if self._is_cancelled:
                            self.download.status = DownloadStatus.CANCELLED
                            self.status_changed_signal.emit(DownloadStatus.CANCELLED)
                            self.finished_signal.emit(False, "Download cancelled")
                            utilities.enable_sleep_after_running()
                            return
                        while self._is_paused:
                            if self._is_cancelled:
                                self.download.status = DownloadStatus.CANCELLED
                                self.status_changed_signal.emit(DownloadStatus.CANCELLED)
                                self.finished_signal.emit(False, "Download cancelled")
                                utilities.enable_sleep_after_running()
                                return
                            threading.Event().wait(0.1)
                        if not chunk:
                            continue
                        output.write(chunk)
                        downloaded += len(chunk)
                        self.download.update_progress(downloaded, total_size)
                        self.progress_signal.emit(downloaded, total_size)

                if total_size and downloaded != total_size:
                    raise requests.exceptions.ChunkedEncodingError(
                        f"Incomplete response: expected {total_size}, got {downloaded}"
                    )

                self.download.total_size = downloaded
                self.download.downloaded_size = downloaded
                self.download.status = DownloadStatus.COMPLETED
                self.download.completed_at = QDateTime.currentDateTime()
                self.status_changed_signal.emit(DownloadStatus.COMPLETED)
                self.finished_signal.emit(True, final_path)
                utilities.enable_sleep_after_running()
                return
            except (
                requests.exceptions.ConnectionError,
                requests.exceptions.ChunkedEncodingError,
                requests.exceptions.ReadTimeout,
                requests.exceptions.Timeout,
            ) as error:
                if attempt >= MAX_RANGE_RETRIES:
                    self.download.status = DownloadStatus.FAILED
                    self.download.error_message = str(error)
                    self.status_changed_signal.emit(DownloadStatus.FAILED)
                    self.finished_signal.emit(False, str(error))
                    utilities.enable_sleep_after_running()
                    return
                logging.warning(
                    f"[DownloadWorker] Stream interrupted; resuming "
                    f"(attempt {attempt + 2}/{MAX_RANGE_RETRIES + 1}): {error}"
                )
                threading.Event().wait(RANGE_RETRY_BACKOFF * (attempt + 1))
            except Exception as error:
                self.download.status = DownloadStatus.FAILED
                self.download.error_message = str(error)
                self.status_changed_signal.emit(DownloadStatus.FAILED)
                self.finished_signal.emit(False, str(error))
                utilities.enable_sleep_after_running()
                return
            finally:
                if response is not None:
                    response.close()

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
            logging.warning(f"[DownloadWorker] Cleanup failed: {e}")

    def cancel(self):
        """Cancel the download"""
        self._is_cancelled = True

    def pause(self):
        """Pause the download"""
        self._is_paused = True
        self.download.status = DownloadStatus.PAUSED
        self.status_changed_signal.emit(DownloadStatus.PAUSED)

    def resume(self):
        """Resume the download"""
        self._is_paused = False
        self.download.status = DownloadStatus.DOWNLOADING
        self.status_changed_signal.emit(DownloadStatus.DOWNLOADING)


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
                    "completed_at": d.completed_at.toSecsSinceEpoch() if d.completed_at else None,
                    "icon_path": d.icon_path,
                    "display_name": d.display_name,
                    "components": d.components,
                    "output_path": d.output_path,
                    "installer_app_name": d.installer_app_name,
                    "chunklist_url": d.chunklist_url,
                    "legacy_installer": d.legacy_installer,
                    "requires_validation": d.requires_validation,
                    "requires_extraction": d.requires_extraction,
                })

            with open(history_path, 'w') as f:
                json.dump(data, f)

        except Exception as e:
            logging.error(f"[DownloadHistory] Failed to save: {e}")

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
                download.icon_path = item.get("icon_path")
                download.display_name = item.get("display_name", download.filename)
                download.components = item.get("components", [])
                download.output_path = item.get("output_path")
                download.installer_app_name = item.get("installer_app_name")
                download.chunklist_url = item.get("chunklist_url")
                download.legacy_installer = item.get(
                    "legacy_installer",
                    os.path.basename(download.url) == "InstallAssistantAuto.pkg",
                )
                download.requires_validation = item.get(
                    "requires_validation",
                    download.filename in {"InstallAssistant.pkg", "InstallESDDmg.pkg"}
                    and not (
                        download.filename == "InstallAssistant.pkg"
                        and download.legacy_installer
                    ),
                )
                download.requires_extraction = item.get(
                    "requires_extraction",
                    download.requires_validation,
                )
                if item.get("completed_at"):
                    download.completed_at = QDateTime.fromSecsSinceEpoch(item["completed_at"])
                self.history.append(download)

        except Exception as e:
            logging.error(f"[DownloadHistory] Failed to load: {e}")