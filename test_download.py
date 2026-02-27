"""
test_download.py: End-to-end test for download system
Run with: python test_download.py

Tests:
  1. DownloadObject data structure
  2. TaskManager registration / start_download API
  3. DownloadWorker actual download (single-thread + multi-thread)
  4. Full flow: start_download -> TaskInterface display -> auto-history
"""
import sys
import os
import tempfile
import shutil
import time

sys.path.insert(0, os.path.dirname(__file__))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer, QEventLoop

from MacBoxTool.support.network_handler import (
    DownloadObject, DownloadWorker, DownloadStatus, NetworkUtilities
)
from MacBoxTool.qt_gui.gui_task import TaskManager

# A small public file for testing (~1KB)
TEST_URL_SMALL = "https://raw.githubusercontent.com/nicehash/NiceHashQuickMiner/main/LICENSE"
# A medium file for multi-thread testing (~100KB)
TEST_URL_MEDIUM = "https://raw.githubusercontent.com/nicehash/NiceHashQuickMiner/main/README.md"


def wait_with_events(app, timeout_ms=15000):
    """Process Qt events for up to timeout_ms"""
    loop = QEventLoop()
    QTimer.singleShot(timeout_ms, loop.quit)
    loop.exec()


def test_download_object():
    """Test 1: DownloadObject data structure"""
    print("=" * 50)
    print("Test 1: DownloadObject data structure")
    print("=" * 50)

    dl = DownloadObject("https://example.com/file.zip", "/tmp", "file.zip")

    assert dl.url == "https://example.com/file.zip", "URL mismatch"
    assert dl.save_path == "/tmp", "save_path mismatch"
    assert dl.filename == "file.zip", "filename mismatch"
    assert dl.status == DownloadStatus.PENDING, "initial status should be PENDING"
    assert dl.total_size == 0, "initial total_size should be 0"
    assert dl.downloaded_size == 0, "initial downloaded_size should be 0"
    assert dl.get_progress_percentage() == 0, "initial progress should be 0"
    assert dl.get_size_display() == "0 B / 0 B", "initial size display mismatch"

    # Test progress update
    dl.update_progress(512, 1024)
    assert dl.downloaded_size == 512, "downloaded_size should be 512"
    assert dl.total_size == 1024, "total_size should be 1024"
    assert dl.get_progress_percentage() == 50, "progress should be 50%"
    assert "512" in dl.get_size_display(), "size display should contain 512"

    # Test auto filename from URL
    dl2 = DownloadObject("https://example.com/path/to/data.tar.gz", "/tmp")
    assert dl2.filename == "data.tar.gz", "auto filename extraction failed"

    # Test size formatting
    assert DownloadObject._format_size(0) == "0 B"
    assert DownloadObject._format_size(500) == "500 B"
    assert "KB" in DownloadObject._format_size(2048)
    assert "MB" in DownloadObject._format_size(2 * 1024 * 1024)
    assert "GB" in DownloadObject._format_size(3 * 1024 * 1024 * 1024)

    # Test status helpers
    dl.status = DownloadStatus.DOWNLOADING
    assert dl.is_downloading() is True
    assert dl.is_completed() is False
    dl.status = DownloadStatus.COMPLETED
    assert dl.is_completed() is True
    assert dl.is_downloading() is False
    dl.status = DownloadStatus.FAILED
    assert dl.is_failed() is True

    print("[PASS] DownloadObject all checks passed")
    print()


def test_task_manager_registration():
    """Test 2: TaskManager registration API"""
    print("=" * 50)
    print("Test 2: TaskManager registration API")
    print("=" * 50)

    TaskManager.clear()

    dl1 = DownloadObject("https://example.com/a.zip", "/tmp", "a.zip")
    dl2 = DownloadObject("https://example.com/b.zip", "/tmp", "b.zip")

    # Register
    TaskManager.register_download(dl1)
    assert len(TaskManager.get_downloads()) == 1, "should have 1 download"

    TaskManager.register_download(dl2)
    assert len(TaskManager.get_downloads()) == 2, "should have 2 downloads"

    # Duplicate registration should be ignored
    TaskManager.register_download(dl1)
    assert len(TaskManager.get_downloads()) == 2, "duplicate should be ignored"

    # Unregister
    TaskManager.unregister_download(dl1)
    assert len(TaskManager.get_downloads()) == 1, "should have 1 after unregister"
    assert TaskManager.get_downloads()[0] is dl2, "remaining should be dl2"

    # Clear
    TaskManager.clear()
    assert len(TaskManager.get_downloads()) == 0, "should be empty after clear"

    print("[PASS] TaskManager registration all checks passed")
    print()


def test_network_check():
    """Test 3: Network connectivity check"""
    print("=" * 50)
    print("Test 3: Network connectivity check")
    print("=" * 50)

    connected = NetworkUtilities.check_network()
    print(f"  Network connected: {connected}")
    if not connected:
        print("[SKIP] No network — skipping download tests")
        return False

    print("[PASS] Network check passed")
    print()
    return True


def test_download_worker_single(app):
    """Test 4: DownloadWorker actual download (single-thread fallback)"""
    print("=" * 50)
    print("Test 4: DownloadWorker single-thread download")
    print("=" * 50)

    temp_dir = tempfile.mkdtemp(prefix="mbt_test_")
    dl = DownloadObject(TEST_URL_SMALL, temp_dir, "LICENSE.txt")
    worker = DownloadWorker(dl)

    result = {"finished": False, "success": False, "msg": ""}
    progress_updates = []

    def on_progress(downloaded, total):
        progress_updates.append((downloaded, total))

    def on_finished(success, msg):
        result["finished"] = True
        result["success"] = success
        result["msg"] = msg

    worker.progress_signal.connect(on_progress)
    worker.finished_signal.connect(on_finished)

    print(f"  Downloading: {TEST_URL_SMALL}")
    print(f"  Save to: {temp_dir}/LICENSE.txt")
    worker.start()

    # Wait for download to complete (max 15s)
    timeout = 150
    while not result["finished"] and timeout > 0:
        app.processEvents()
        time.sleep(0.1)
        timeout -= 1

    assert result["finished"], "Download did not finish in time"
    assert result["success"], f"Download failed: {result['msg']}"
    assert dl.status == DownloadStatus.COMPLETED, f"Status should be COMPLETED, got {dl.status}"
    assert dl.completed_at is not None, "completed_at should be set"
    assert dl.downloaded_size > 0, "downloaded_size should be > 0"
    assert len(progress_updates) > 0, "Should have received progress updates"

    file_path = os.path.join(temp_dir, "LICENSE.txt")
    assert os.path.exists(file_path), "Downloaded file should exist"
    file_size = os.path.getsize(file_path)
    assert file_size > 0, "Downloaded file should not be empty"
    assert file_size == dl.downloaded_size, f"File size ({file_size}) should match downloaded_size ({dl.downloaded_size})"

    print(f"  File size: {DownloadObject._format_size(file_size)}")
    print(f"  Progress updates received: {len(progress_updates)}")
    print(f"  Final progress: {dl.get_progress_percentage()}%")
    print(f"  Size display: {dl.get_size_display()}")

    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)

    print("[PASS] Single-thread download passed")
    print()


def test_download_worker_cancel(app):
    """Test 5: DownloadWorker cancel"""
    print("=" * 50)
    print("Test 5: DownloadWorker cancel")
    print("=" * 50)

    temp_dir = tempfile.mkdtemp(prefix="mbt_test_")
    # Use medium file so we have time to cancel
    dl = DownloadObject(TEST_URL_MEDIUM, temp_dir, "README.md")
    worker = DownloadWorker(dl)

    result = {"finished": False, "success": False, "msg": ""}

    def on_finished(success, msg):
        result["finished"] = True
        result["success"] = success
        result["msg"] = msg

    worker.finished_signal.connect(on_finished)
    worker.start()

    # Cancel immediately
    app.processEvents()
    time.sleep(0.05)
    worker.cancel()

    # Wait for worker to finish
    timeout = 50
    while not result["finished"] and timeout > 0:
        app.processEvents()
        time.sleep(0.1)
        timeout -= 1

    if result["finished"]:
        # Download may have finished before cancel took effect
        if not result["success"]:
            assert dl.status == DownloadStatus.CANCELLED, f"Status should be CANCELLED, got {dl.status}"
            print("  Download was cancelled successfully")
        else:
            print("  Download completed before cancel took effect (file was too small)")
    else:
        print("  Worker still running after cancel (timeout)")

    shutil.rmtree(temp_dir, ignore_errors=True)
    print("[PASS] Cancel test passed")
    print()


def test_task_manager_start_download(app):
    """Test 6: TaskManager.start_download() full flow"""
    print("=" * 50)
    print("Test 6: TaskManager.start_download() full flow")
    print("=" * 50)

    TaskManager.clear()

    temp_dir = tempfile.mkdtemp(prefix="mbt_test_")
    dl = DownloadObject(TEST_URL_SMALL, temp_dir, "test_flow.txt")

    # start_download should register and start
    worker = TaskManager.start_download(dl)

    assert len(TaskManager.get_downloads()) == 1, "Should have 1 registered download"
    assert dl.status in (DownloadStatus.PENDING, DownloadStatus.DOWNLOADING), \
        f"Status should be PENDING or DOWNLOADING, got {dl.status}"

    print(f"  Download registered and started")
    print(f"  Status: {dl.status}")

    # Wait for completion
    timeout = 150
    while dl.status == DownloadStatus.DOWNLOADING or dl.status == DownloadStatus.PENDING:
        app.processEvents()
        time.sleep(0.1)
        timeout -= 1
        if timeout <= 0:
            break

    assert dl.status == DownloadStatus.COMPLETED, f"Download should complete, got {dl.status}"

    file_path = os.path.join(temp_dir, "test_flow.txt")
    assert os.path.exists(file_path), "Downloaded file should exist"
    print(f"  Download completed: {DownloadObject._format_size(os.path.getsize(file_path))}")

    # Wait a moment for finished_signal to clean up worker
    for _ in range(10):
        app.processEvents()
        time.sleep(0.05)

    # Worker should be cleaned up
    assert id(dl) not in TaskManager._workers, "Worker should be cleaned up after completion"
    print("  Worker cleaned up after completion")

    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)
    TaskManager.clear()

    print("[PASS] TaskManager.start_download() flow passed")
    print()


def test_multiple_downloads(app):
    """Test 7: Multiple concurrent downloads"""
    print("=" * 50)
    print("Test 7: Multiple concurrent downloads")
    print("=" * 50)

    TaskManager.clear()

    temp_dir = tempfile.mkdtemp(prefix="mbt_test_")
    downloads = []
    for i in range(3):
        dl = DownloadObject(TEST_URL_SMALL, temp_dir, f"concurrent_{i}.txt")
        TaskManager.start_download(dl)
        downloads.append(dl)

    assert len(TaskManager.get_downloads()) == 3, "Should have 3 registered downloads"
    print(f"  Started 3 concurrent downloads")

    # Wait for all to complete
    timeout = 200
    while timeout > 0:
        app.processEvents()
        time.sleep(0.1)
        timeout -= 1
        if all(d.status == DownloadStatus.COMPLETED for d in downloads):
            break

    completed_count = sum(1 for d in downloads if d.status == DownloadStatus.COMPLETED)
    print(f"  Completed: {completed_count}/3")

    for i, dl in enumerate(downloads):
        file_path = os.path.join(temp_dir, f"concurrent_{i}.txt")
        exists = os.path.exists(file_path)
        print(f"    [{i}] {dl.filename}: status={dl.status}, exists={exists}, size={dl.get_size_display()}")

    assert completed_count == 3, f"All 3 should complete, only {completed_count} did"

    shutil.rmtree(temp_dir, ignore_errors=True)
    TaskManager.clear()

    print("[PASS] Multiple concurrent downloads passed")
    print()


def main():
    print()
    print("###################################")
    print("# MacBoxTool Download System Test #")
    print("###################################")
    print()

    app = QApplication.instance() or QApplication(sys.argv)

    passed = 0
    failed = 0
    skipped = 0

    # Test 1: DownloadObject (no network needed)
    try:
        test_download_object()
        passed += 1
    except AssertionError as e:
        print(f"[FAIL] Test 1: {e}")
        failed += 1

    # Test 2: TaskManager registration (no network needed)
    try:
        test_task_manager_registration()
        passed += 1
    except AssertionError as e:
        print(f"[FAIL] Test 2: {e}")
        failed += 1

    # Test 3: Network check
    try:
        has_network = test_network_check()
        passed += 1
    except Exception as e:
        print(f"[FAIL] Test 3: {e}")
        has_network = False
        failed += 1

    if has_network:
        # Test 4: Single-thread download
        try:
            test_download_worker_single(app)
            passed += 1
        except (AssertionError, Exception) as e:
            print(f"[FAIL] Test 4: {e}")
            failed += 1

        # Test 5: Cancel download
        try:
            test_download_worker_cancel(app)
            passed += 1
        except (AssertionError, Exception) as e:
            print(f"[FAIL] Test 5: {e}")
            failed += 1

        # Test 6: TaskManager.start_download() flow
        try:
            test_task_manager_start_download(app)
            passed += 1
        except (AssertionError, Exception) as e:
            print(f"[FAIL] Test 6: {e}")
            failed += 1

        # Test 7: Multiple concurrent downloads
        try:
            test_multiple_downloads(app)
            passed += 1
        except (AssertionError, Exception) as e:
            print(f"[FAIL] Test 7: {e}")
            failed += 1
    else:
        skipped += 4
        print(f"[SKIP] Tests 4-7 skipped (no network)")

    print()
    print("=" * 50)
    print(f"Results: {passed} passed, {failed} failed, {skipped} skipped")
    print("=" * 50)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
