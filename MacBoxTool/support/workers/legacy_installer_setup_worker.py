"""Validate legacy installer components and build the installer application."""

import logging
import os
import subprocess
import tempfile
import uuid
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse

import requests
from PySide2.QtCore import QThread, Signal

from .. import subprocess_wrapper
from ..integrity_verification import ChunklistStatus, ChunklistVerification
from ..network_handler import TLS_CERTIFICATE_BUNDLE, TLS_REQUIRED_HOSTS


class SetupCancelledError(RuntimeError):
    """Raised when legacy installer setup is cancelled."""


class LegacyInstallerSetupWorker(QThread):
    """Build a High Sierra, Mojave, or Catalina installer application."""

    APPLICATIONS_DIRECTORY = Path("/Applications")
    TRUSTED_APPLE_HOSTS = TLS_REQUIRED_HOSTS
    REQUIRED_COMPONENTS = (
        "InstallAssistantAuto.pkg",
        "InstallESDDmg.pkg",
        "BaseSystem.dmg",
        "BaseSystem.chunklist",
        "AppleDiagnostics.dmg",
        "AppleDiagnostics.chunklist",
    )
    IMAGE_CHUNKLISTS = {
        "BaseSystem.dmg": "BaseSystem.chunklist",
        "AppleDiagnostics.dmg": "AppleDiagnostics.chunklist",
    }

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
            self._raise_if_cancelled()
            self.status_changed_signal.emit("validating")
            components = {
                self._component_name(component["URL"]): component
                for component in self.download.components
            }
            missing_components = [
                name for name in self.REQUIRED_COMPONENTS
                if name not in components
            ]
            if missing_components:
                raise RuntimeError(
                    "Required legacy installer components are missing: "
                    f"{', '.join(missing_components)}"
                )

            for component in components.values():
                self._validate_apple_url(component["URL"])
                integrity_url = component.get("IntegrityDataURL")
                if integrity_url:
                    self._validate_apple_url(integrity_url)

            component_paths = {
                name: Path(self.download.save_path) / name
                for name in self.REQUIRED_COMPONENTS
            }
            missing_downloads = [
                name for name, path in component_paths.items()
                if not path.is_file()
            ]
            if missing_downloads:
                raise RuntimeError(
                    "Downloaded legacy installer components are missing: "
                    f"{', '.join(missing_downloads)}"
                )

            assistant_path = component_paths["InstallAssistantAuto.pkg"]
            payload_path = component_paths["InstallESDDmg.pkg"]
            self._verify_package_signature(assistant_path)
            if self._is_cancelled:
                self.finished_signal.emit(False, "Setup cancelled")
                return

            integrity_url = components["InstallESDDmg.pkg"].get("IntegrityDataURL")
            if integrity_url:
                self._verify_remote_chunklist(payload_path, integrity_url)
            else:
                self._verify_package_signature(payload_path)
            if self._is_cancelled:
                self.finished_signal.emit(False, "Setup cancelled")
                return

            for image_name, chunklist_name in self.IMAGE_CHUNKLISTS.items():
                image_path = component_paths[image_name]
                integrity_url = components[image_name].get("IntegrityDataURL")
                if integrity_url:
                    self._verify_remote_chunklist(image_path, integrity_url)
                self._verify_local_chunklist(
                    image_path,
                    component_paths[chunklist_name],
                )
                self._verify_disk_image(image_path)
                if self._is_cancelled:
                    self.finished_signal.emit(False, "Setup cancelled")
                    return

            self.status_changed_signal.emit("extracting")
            self._build_application(component_paths)
            self._raise_if_cancelled()
            self.finished_signal.emit(True, self.download.output_path)
        except SetupCancelledError:
            self.finished_signal.emit(False, "Setup cancelled")
        except Exception as error:
            logging.error(f"Legacy installer setup failed: {error}")
            self.finished_signal.emit(False, str(error))

    @staticmethod
    def _component_name(url: str) -> str:
        return Path(urlparse(url).path).name

    @classmethod
    def _validate_apple_url(cls, url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname not in cls.TRUSTED_APPLE_HOSTS:
            raise RuntimeError(f"Untrusted Apple download URL: {url}")

    def _raise_if_cancelled(self) -> None:
        if self._is_cancelled:
            raise SetupCancelledError()

    def _verify_package_signature(self, package_path: Path) -> None:
        self._raise_if_cancelled()
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

    def _verify_remote_chunklist(self, package_path: Path, integrity_url: str) -> None:
        self._raise_if_cancelled()
        self._validate_apple_url(integrity_url)
        response = requests.get(
            integrity_url,
            timeout=30,
            verify=TLS_CERTIFICATE_BUNDLE,
        )
        response.raise_for_status()
        self._verify_chunklist(package_path, BytesIO(response.content))

    def _verify_local_chunklist(
        self, image_path: Path, chunklist_path: Path
    ) -> None:
        self._raise_if_cancelled()
        self._verify_chunklist(image_path, BytesIO(chunklist_path.read_bytes()))

    def _verify_chunklist(self, file_path: Path, chunklist: BytesIO) -> None:
        verifier = ChunklistVerification(file_path, chunklist)
        if not verifier.parse():
            raise RuntimeError(f"Failed to parse integrity data for {file_path.name}")

        self.progress_signal.emit(0, verifier.total_chunks)

        def report_progress(current: int, total: int) -> None:
            if self._is_cancelled:
                verifier.status = ChunklistStatus.FAILURE
            self.progress_signal.emit(current, total)

        verifier.set_progress_callback(report_progress)
        if not verifier.verify():
            if self._is_cancelled:
                raise SetupCancelledError()
            raise RuntimeError(
                f"Hash mismatch on chunk {verifier.current_chunk} of {file_path.name}"
            )

    def _verify_disk_image(self, image_path: Path) -> None:
        self._raise_if_cancelled()
        result = subprocess.run(
            ["/usr/bin/hdiutil", "imageinfo", str(image_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Invalid disk image {image_path.name}: "
                f"{result.stdout.decode(errors='replace').strip()}"
            )

    def _build_application(self, component_paths: dict[str, Path]) -> None:
        self._raise_if_cancelled()
        assistant_path = component_paths["InstallAssistantAuto.pkg"]
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
            self._raise_if_cancelled()

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
            expected_app_name = self.download.installer_app_name
            accepted_app_names = {expected_app_name}
            if expected_app_name == "Install macOS High Sierra.app":
                accepted_app_names.add("Install macOS High Sierra Beta.app")

            if expected_app_name and app_name not in accepted_app_names:
                raise RuntimeError(
                    f"Unexpected installer application {app_name}; "
                    f"expected {expected_app_name}"
                )

            staged_app = temp_path / app_name
            self._run(["/usr/bin/ditto", str(applications[0]), str(staged_app)])
            self._raise_if_cancelled()
            shared_support = staged_app / "Contents" / "SharedSupport"
            shared_support.mkdir(parents=True, exist_ok=True)
            for name in (
                "InstallESDDmg.pkg",
                "BaseSystem.dmg",
                "BaseSystem.chunklist",
                "AppleDiagnostics.dmg",
                "AppleDiagnostics.chunklist",
            ):
                destination_name = (
                    "InstallESD.dmg" if name == "InstallESDDmg.pkg" else name
                )
                self._run([
                    "/usr/bin/ditto",
                    str(component_paths[name]),
                    str(shared_support / destination_name),
                ])
                self._raise_if_cancelled()

            required_shared_support = (
                "InstallInfo.plist",
                "InstallESD.dmg",
                "BaseSystem.dmg",
                "BaseSystem.chunklist",
                "AppleDiagnostics.dmg",
                "AppleDiagnostics.chunklist",
            )
            missing_shared_support = [
                name for name in required_shared_support
                if not (shared_support / name).is_file()
            ]
            if missing_shared_support:
                raise RuntimeError(
                    "Installer SharedSupport is incomplete: "
                    f"{', '.join(missing_shared_support)}"
                )

            self._verify_package_signature(shared_support / "InstallESD.dmg")
            for image_name, chunklist_name in self.IMAGE_CHUNKLISTS.items():
                self._verify_local_chunklist(
                    shared_support / image_name,
                    shared_support / chunklist_name,
                )
                self._verify_disk_image(shared_support / image_name)

            install_info = shared_support / "InstallInfo.plist"
            createinstallmedia = staged_app / "Contents" / "Resources" / "createinstallmedia"
            startosinstall = staged_app / "Contents" / "Resources" / "startosinstall"
            for required_path in (install_info, createinstallmedia, startosinstall):
                if not required_path.exists():
                    raise RuntimeError(f"Installer is missing {required_path.name}")

            self._verify_code_signature(createinstallmedia)
            self._verify_code_signature(startosinstall)
            self._raise_if_cancelled()

            self._install_application(
                staged_app,
                app_name,
                expected_app_name,
            )

    @staticmethod
    def _validate_app_name(app_name: str) -> None:
        if (
            not app_name
            or Path(app_name).name != app_name
            or not app_name.endswith(".app")
        ):
            raise RuntimeError(f"Invalid installer application name: {app_name!r}")

    @staticmethod
    def _path_exists(path: Path) -> bool:
        return os.path.lexists(path)

    def _run_as_root(self, command: list[str]) -> None:
        subprocess_wrapper.run_as_root_and_verify(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

    def _remove_transaction_directory(self, transaction_directory: Path) -> None:
        if not self._path_exists(transaction_directory):
            return
        self._run_as_root(["/bin/rm", "-rf", str(transaction_directory)])

    def _install_application(
        self,
        staged_app: Path,
        app_name: str,
        expected_app_name: str | None,
    ) -> None:
        self._validate_app_name(app_name)
        if expected_app_name:
            self._validate_app_name(expected_app_name)

        applications_directory = self.APPLICATIONS_DIRECTORY
        destination = applications_directory / app_name
        expected_destination = (
            applications_directory / expected_app_name
            if expected_app_name else destination
        )
        targets = list(dict.fromkeys((destination, expected_destination)))

        for target in targets:
            if not self._path_exists(target):
                continue
            if not self.download.replace_existing_app:
                raise FileExistsError(f"{target} already exists")
            if target.is_symlink() or not target.is_dir():
                raise RuntimeError(
                    f"Refusing to replace non-application path: {target}"
                )

        self._raise_if_cancelled()
        transaction_directory = (
            applications_directory
            / f".MacBoxTool-legacy-installer-{uuid.uuid4().hex}"
        )
        incoming = transaction_directory / app_name
        backups: list[tuple[Path, Path]] = []
        activated = False

        try:
            self._run_as_root(["/bin/mkdir", str(transaction_directory)])
            self._run_as_root([
                "/usr/bin/ditto",
                str(staged_app),
                str(incoming),
            ])
            if not incoming.is_dir():
                raise RuntimeError(
                    f"Installer staging failed at {incoming}"
                )

            self._verify_installer_application(incoming)
            self._raise_if_cancelled()

            for target in targets:
                if not self._path_exists(target):
                    continue
                if target.is_symlink() or not target.is_dir():
                    raise RuntimeError(
                        f"Refusing to replace non-application path: {target}"
                    )

            for index, target in enumerate(targets):
                if not self._path_exists(target):
                    continue
                backup = transaction_directory / f"backup-{index}.app"
                self._run_as_root(["/bin/mv", str(target), str(backup)])
                backups.append((target, backup))

            self._run_as_root(["/bin/mv", str(incoming), str(destination)])
            activated = True
        except Exception as install_error:
            restore_errors = []
            for target, backup in reversed(backups):
                if not self._path_exists(backup):
                    continue
                if self._path_exists(target):
                    restore_errors.append(
                        f"Cannot restore {target}: destination is occupied"
                    )
                    continue
                try:
                    self._run_as_root(["/bin/mv", str(backup), str(target)])
                except Exception as restore_error:
                    restore_errors.append(f"{target}: {restore_error}")

            if restore_errors:
                raise RuntimeError(
                    f"Installer replacement failed: {install_error}. "
                    f"Backups retained at {transaction_directory}. "
                    f"Restore failures: {'; '.join(restore_errors)}"
                ) from install_error
            raise
        finally:
            backups_retained = any(
                self._path_exists(backup) for _, backup in backups
            )
            if activated or not backups_retained:
                try:
                    self._remove_transaction_directory(transaction_directory)
                except Exception as cleanup_error:
                    logging.warning(
                        "Legacy installer transaction cleanup failed at %s: %s",
                        transaction_directory,
                        cleanup_error,
                    )

        if not destination.is_dir():
            raise RuntimeError(f"Installer application was not created at {destination}")

        self.download.installer_app_name = app_name
        self.download.output_path = str(destination)

    def _verify_installer_application(self, app_path: Path) -> None:
        shared_support = app_path / "Contents" / "SharedSupport"
        required_shared_support = (
            "InstallInfo.plist",
            "InstallESD.dmg",
            "BaseSystem.dmg",
            "BaseSystem.chunklist",
            "AppleDiagnostics.dmg",
            "AppleDiagnostics.chunklist",
        )
        missing_shared_support = [
            name for name in required_shared_support
            if not (shared_support / name).is_file()
        ]
        if missing_shared_support:
            raise RuntimeError(
                "Installer SharedSupport is incomplete: "
                f"{', '.join(missing_shared_support)}"
            )

        createinstallmedia = app_path / "Contents" / "Resources" / "createinstallmedia"
        startosinstall = app_path / "Contents" / "Resources" / "startosinstall"
        self._verify_package_signature(shared_support / "InstallESD.dmg")
        self._verify_code_signature(createinstallmedia)
        self._verify_code_signature(startosinstall)

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
