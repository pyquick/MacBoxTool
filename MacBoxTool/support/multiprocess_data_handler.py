"""
multiprocess_data_handler.py: Multi-process data processing for KDK and MetalLib
"""

import logging
import multiprocessing
import requests
from PySide6.QtCore import QThread, QTimer, Signal


def _process_data(api_url: str, data_type: str, queue: multiprocessing.Queue) -> None:
    """
    Process data in a separate process.

    This function runs in a subprocess and must be a top-level function
    to be picklable by multiprocessing.

    Args:
        api_url: URL to fetch data from
        data_type: Type of data ("kdk" or "metallib")
        queue: Multiprocessing queue for IPC
    """
    try:
        # 1. Fetch API data
        response = requests.get(api_url, timeout=10)
        if response.status_code != 200:
            queue.put(("error", f"API request failed: {response.status_code}"))
            return

        raw_data = response.json()

        # 2. Process data based on type
        if data_type == "kdk":
            processed = _process_kdk_data(raw_data)
        elif data_type == "metallib":
            processed = _process_metallib_data(raw_data)
        else:
            processed = {"all": raw_data, "latest": []}

        # 3. Put result in queue
        queue.put(("success", processed))

    except requests.exceptions.Timeout:
        queue.put(("error", "Request timeout - API took too long to respond"))
    except requests.exceptions.ConnectionError:
        queue.put(("error", "Connection error - please check your internet connection"))
    except Exception as e:
        queue.put(("error", str(e)))


def _process_kdk_data(raw_data: list) -> dict:
    """
    Process KDK data in subprocess.

    Args:
        raw_data: Raw JSON data from API

    Returns:
        dict with "all" and "latest" keys
    """
    # 1. Sort by build and version (descending)
    sorted_data = sorted(
        raw_data,
        key=lambda x: (x.get("build", ""), x.get("version", "")),
        reverse=True
    )

    # 2. Extract latest version for each major version (top 4 major versions)
    version_groups = {}
    for kdk in sorted_data:
        version = kdk.get("version", "")
        if not version:
            continue

        # Extract major version number (e.g., "26.3" -> 26)
        major_version = version.split(".")[0]
        if major_version not in version_groups:
            version_groups[major_version] = kdk

    latest_kdks = list(version_groups.values())[:4]

    return {
        "all": sorted_data,
        "latest": latest_kdks
    }


def _parse_build_version(build_string: str) -> tuple:
    """
    Parse Apple build version number (e.g., 24G90, 24G711)
    Returns sortable tuple (major, letter, minor).

    Args:
        build_string: Version string like "24G90", "24G711"

    Returns:
        tuple: (major number, letter, minor number)
               Example: "24G90" -> (24, "G", 90)
                        "24G711" -> (24, "G", 711)
    """
    if not build_string:
        return (0, "", 0)

    # Match format: number + letter + number (e.g., 24G90)
    import re
    match = re.match(r'^(\d+)([A-Za-z]+)?(\d+)?$', build_string)
    if match:
        major = int(match.group(1)) if match.group(1) else 0
        letter = match.group(2) if match.group(2) else ""
        minor = int(match.group(3)) if match.group(3) else 0
        return (major, letter, minor)

    return (0, "", 0)


def _process_metallib_data(raw_data: list) -> dict:
    """
    Process MetalLib data in subprocess.

    Args:
        raw_data: Raw JSON data from API

    Returns:
        dict with "all" and "latest" keys
    """
    # 1. Sort by build version and version (descending)
    sorted_data = sorted(
        raw_data,
        key=lambda x: (_parse_build_version(x.get("build", "")), x.get("version", "")),
        reverse=True
    )

    # 2. Extract latest 4
    latest_metallibs = sorted_data[:4]

    return {
        "all": sorted_data,
        "latest": latest_metallibs
    }


class DataProcessorWorker(QThread):
    """
    Worker thread that manages a subprocess for data processing.

    This QThread creates and manages a subprocess for CPU-intensive
    data processing operations, keeping the main thread responsive.
    """

    data_ready = Signal(dict)  # Emitted when data is ready
    error_occurred = Signal(str)  # Emitted when an error occurs

    def __init__(self, api_url: str, data_type: str, parent=None):
        """
        Initialize the worker.

        Args:
            api_url: URL to fetch data from
            data_type: Type of data ("kdk" or "metallib")
            parent: Parent QObject
        """
        super().__init__(parent)
        self.api_url = api_url
        self.data_type = data_type
        self.process = None
        self.queue = None
        self._timer = None

    def start_processing(self):
        """Start subprocess processing."""
        # Create IPC queue
        self.queue = multiprocessing.Queue()

        # Start subprocess
        self.process = multiprocessing.Process(
            target=_process_data,
            args=(self.api_url, self.data_type, self.queue)
        )
        self.process.start()

        # Start timer to check queue
        self._timer = QTimer()
        self._timer.timeout.connect(self._check_queue)
        self._timer.start(50)  # Check every 50ms

    def _check_queue(self):
        """Check queue for results."""
        try:
            if not self.queue.empty():
                status, data = self.queue.get_nowait()

                if status == "success":
                    logging.info(f"Successfully processed {self.data_type} data in subprocess")
                    self.data_ready.emit(data)
                elif status == "error":
                    logging.error(f"Error processing {self.data_type} data: {data}")
                    self.error_occurred.emit(data)

                # Cleanup resources
                self._cleanup_resources()

        except Exception as e:
            logging.error(f"Error checking queue: {e}")
            self._cleanup_resources()

    def _cleanup_resources(self):
        """Clean up resources after processing completes."""
        if self._timer:
            self._timer.stop()
            self._timer = None

        if self.process and self.process.is_alive():
            self.process.terminate()
            self.process.join(timeout=1)
            if self.process.is_alive():
                logging.warning(f"Process {self.process.pid} did not terminate gracefully, killing")
                self.process.kill()

        self.process = None

        if self.queue:
            self.queue.close()
            self.queue = None

    def stop(self):
        """Stop processing and clean up resources."""
        logging.info(f"Stopping data processor for {self.data_type}")
        self._cleanup_resources()

    def __del__(self):
        """Destructor to ensure cleanup."""
        self.stop()
