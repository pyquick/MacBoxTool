"""
test_download_object.py: Test DownloadObject and signal overflow fix
Run with: python test_download_object.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

from MacBoxTool.support.network_handler import (
    DownloadObject, DownloadWorker, DownloadStatus
)


def test_large_size_signal():
    """Test that progress_signal handles sizes > 2GB (32-bit int overflow)"""
    print("=" * 50)
    print("Test: Large file size signal (>2GB overflow)")
    print("=" * 50)

    app = QApplication.instance() or QApplication(sys.argv)

    large_size = 12_416_490_165  # ~12.4GB (Big Sur InstallAssistant.pkg)
    dl = DownloadObject("https://example.com/large.pkg", "/tmp", "large.pkg")
    worker = DownloadWorker(dl)

    received = {"downloaded": None, "total": None}

    def on_progress(downloaded, total):
        received["downloaded"] = downloaded
        received["total"] = total

    worker.progress_signal.connect(on_progress)

    # Emit directly to test signal doesn't overflow
    worker.progress_signal.emit(large_size // 2, large_size)

    app.processEvents()

    assert received["total"] == large_size, \
        f"Total size mismatch: expected {large_size}, got {received['total']}"
    assert received["downloaded"] == large_size // 2, \
        f"Downloaded mismatch: expected {large_size // 2}, got {received['downloaded']}"

    print(f"  Emitted total:      {large_size} ({DownloadObject._format_size(large_size)})")
    print(f"  Received total:     {received['total']}")
    print(f"  Emitted downloaded: {large_size // 2}")
    print(f"  Received downloaded:{received['downloaded']}")
    print("[PASS] Large file size signal works without overflow")
    print()


def test_download_object_large_progress():
    """Test DownloadObject progress with large sizes"""
    print("=" * 50)
    print("Test: DownloadObject large size progress")
    print("=" * 50)

    dl = DownloadObject("https://example.com/big.pkg", "/tmp", "big.pkg")

    large_total = 12_416_490_165
    half = large_total // 2

    dl.update_progress(half, large_total)

    assert dl.total_size == large_total, f"total_size wrong: {dl.total_size}"
    assert dl.downloaded_size == half, f"downloaded_size wrong: {dl.downloaded_size}"
    assert dl.get_progress_percentage() in (49, 50), f"progress wrong: {dl.get_progress_percentage()}"
    assert "GB" in dl.get_size_display(), f"size display should show GB: {dl.get_size_display()}"

    print(f"  Size display: {dl.get_size_display()}")
    print(f"  Progress: {dl.get_progress_percentage()}%")
    print("[PASS] Large size progress tracking works")
    print()


def test_download_object_basic():
    """Test basic DownloadObject functionality"""
    print("=" * 50)
    print("Test: DownloadObject basics")
    print("=" * 50)

    dl = DownloadObject("https://example.com/file.zip", "/tmp", "file.zip")
    assert dl.status == DownloadStatus.PENDING
    assert dl.get_progress_percentage() == 0
    assert dl.get_size_display() == "0 B / 0 B"

    dl.update_progress(1024, 2048)
    assert dl.get_progress_percentage() == 50
    assert dl.downloaded_size == 1024

    dl.status = DownloadStatus.DOWNLOADING
    assert dl.is_downloading() is True
    assert dl.is_completed() is False

    dl.status = DownloadStatus.COMPLETED
    assert dl.is_completed() is True

    # Auto filename from URL
    dl2 = DownloadObject("https://example.com/path/InstallAssistant.pkg", "/tmp")
    assert dl2.filename == "InstallAssistant.pkg"

    print("[PASS] DownloadObject basics all passed")
    print()


def main():
    print()
    print("###########################################")
    print("# DownloadObject & Signal Overflow Tests  #")
    print("###########################################")
    print()

    passed = 0
    failed = 0

    for test_fn in [test_download_object_basic, test_download_object_large_progress, test_large_size_signal]:
        try:
            test_fn()
            passed += 1
        except (AssertionError, Exception) as e:
            print(f"[FAIL] {test_fn.__name__}: {e}")
            failed += 1

    print("=" * 50)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 50)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
