"""Validate legacy installer components and build the installer application."""

import logging
import subprocess
import tempfile
from io import BytesIO
from pathlib import Path

import requests
from PySide6.QtCore import QThread, Signal

from .. import subprocess_wrapper
from ..integrity_verification import ChunklistStatus, ChunklistVerification


class LegacyInstallerSetupWorker(QThread):
    """Build a High Sierra, Mojave, or Catalina installer application."""

    progress_signal = Signal(int, int)
    finished_signal = Signal(bool, str)
    status_changed_signal = Signal(str)

    def __init__(self, download):
        super().__init__()
        self.download = download
        self._is_cancelled = False

    def cancel(self) -> None:
        self._is_cancelled = True

    def run(self) -> None:
        try:
            self.status_changed_signal.emit("validating")
            components = {
                Path(component["URL"]).name: component
                for component in self.download.components
            }
            assistant = components.get("InstallAssistantAuto.pkg")
            payload = components.get("InstallESDDmg.pkg")
            if not assistant or not payload:
                raise RuntimeError("Required legacy installer components are missing")

            assistant_path = Path(self.download.save_path) / "InstallAssistantAuto.pkg"
            payload_path = Path(self.download.save_path) / "InstallESDDmg.pkg"
            self._verify_package_signature(assistant_path)
            if self._is_cancelled:
                self.finished_signal.emit(False, "Setup cancelled")
                return

            integrity_url = payload.get("IntegrityDataURL")
            if integrity_url:
                self._verify_chunklist(payload_path, integrity_url)
            else:
                self._verify_package_signature(payload_path)
            if self._is_cancelled:
                self.finished_signal.emit(False, "Setup cancelled")
                return

            self.status_changed_signal.emit("extracting")
            self._build_application(assistant_path, payload_path)
            self.finished_signal.emit(True, self.download.output_path)
        except Exception as error:
            logging.error(f"Legacy installer setup failed: {error}")
            self.finished_signal.emit(False, str(error))

    def _verify_package_signature(self, package_path: Path) -> None:
        result = subprocess.run(
            ["/usr/sbin/pkgutil", "--check-signature", str(package_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Apple signature validation failed for {package_path.name}: "
                f"{result.stdout.decode(errors='replace').strip()}"
            )

    def _verify_chunklist(self, package_path: Path, integrity_url: str) -> None:
        response = requests.get(integrity_url, timeout=30)
        response.raise_for_status()
        verifier = ChunklistVerification(package_path, BytesIO(response.content))
        if not verifier.parse():
            raise RuntimeError(f"Failed to parse integrity data for {package_path.name}")

        self.progress_signal.emit(0, verifier.total_chunks)

        def report_progress(current: int, total: int) -> None:
            if self._is_cancelled:
                verifier.status = ChunklistStatus.FAILURE
            self.progress_signal.emit(current, total)

        verifier.set_progress_callback(report_progress)
        if not verifier.verify():
            if self._is_cancelled:
                return
            raise RuntimeError(
                f"Hash mismatch on chunk {verifier.current_chunk} of {package_path.name}"
            )

    def _build_application(self, assistant_path: Path, payload_path: Path) -> None:
        with tempfile.TemporaryDirectory(dir=self.download.save_path) as temp_dir:
            temp_path = Path(temp_dir)
            expanded_path = temp_path / "InstallAssistantAuto"
            result = subprocess.run(
                [
                    "/usr/sbin/pkgutil",
                    "--expand-full",
                    str(assistant_path),
                    str(expanded_path),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            if result.returncode != 0:
                raise RuntimeError(
                    "Failed to expand InstallAssistantAuto.pkg: "
                    f"{result.stdout.decode(errors='replace').strip()}"
                )

            payload_root = expanded_path / "Payload"
            applications = [
                path for path in payload_root.iterdir()
                if path.is_dir() and path.suffix == ".app"
            ]
            if len(applications) != 1:
                raise RuntimeError(
                    f"Expected one installer application, found {len(applications)}"
                )

            app_name = applications[0].name
            if self.download.installer_app_name and app_name != self.download.installer_app_name:
                raise RuntimeError(
                    f"Unexpected installer application {app_name}; "
                    f"expected {self.download.installer_app_name}"
                )

            staged_app = temp_path / app_name
            self._run(["/usr/bin/ditto", str(applications[0]), str(staged_app)])
            shared_support = staged_app / "Contents" / "SharedSupport"
            shared_support.mkdir(parents=True, exist_ok=True)
            self._run(
                [
                    "/usr/bin/ditto",
                    str(payload_path),
                    str(shared_support / "InstallESD.dmg"),
                ]
            )

            install_info = shared_support / "InstallInfo.plist"
            createinstallmedia = staged_app / "Contents" / "Resources" / "createinstallmedia"
            startosinstall = staged_app / "Contents" / "Resources" / "startosinstall"
            for required_path in (install_info, createinstallmedia, startosinstall):
                if not required_path.exists():
                    raise RuntimeError(f"Installer is missing {required_path.name}")

            self._verify_code_signature(createinstallmedia)
            self._verify_code_signature(startosinstall)

            destination = Path("/Applications") / app_name
            if destination.exists():
                if not self.download.replace_existing_app:
                    raise FileExistsError(f"{destination} already exists")
                subprocess_wrapper.run_as_root_and_verify(
                    ["/bin/rm", "-rf", str(destination)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                )

            subprocess_wrapper.run_as_root_and_verify(
                ["/usr/bin/ditto", str(staged_app), str(destination)],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            if not destination.exists():
                raise RuntimeError(f"Installer application was not created at {destination}")

            self.download.output_path = str(destination)

    def _verify_code_signature(self, executable: Path) -> None:
        result = subprocess.run(
            ["/usr/bin/codesign", "--verify", "--strict", "--verbose=2", str(executable)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Code signature validation failed for {executable.name}: "
                f"{result.stdout.decode(errors='replace').strip()}"
            )

    @staticmethod
    def _run(command: list[str]) -> None:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if result.returncode != 0:
            raise RuntimeError(
                f"Command failed: {' '.join(command)}\n"
                f"{result.stdout.decode(errors='replace').strip()}"
            )
