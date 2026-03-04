"""
mount_volume.py: Handling macOS volume mounting and unmounting
"""

import logging
import plistlib
import subprocess

from pathlib import Path

from .apfs_snapshot import APFSSnapshot

from ...datasets import os_data
from ..           import subprocess_wrapper


class RootVolumeMount:
    """Mount / unmount the macOS root volume (Catalina+ read-only root, Big Sur+ APFS snapshots)."""

    def __init__(self, xnu_major: int) -> None:
        self.xnu_major = xnu_major
        self.root_volume_identifier = self._fetch_root_volume_identifier()
        self.mount_path = None

    def _fetch_root_volume_identifier(self) -> str:
        """
        Resolve path to disk identifier.

        ex. / -> disk1s1
        """
        try:
            content = plistlib.loads(
                subprocess.run(
                    ["/usr/sbin/diskutil", "info", "-plist", "/"],
                    capture_output=True,
                ).stdout
            )
        except plistlib.InvalidFileException:
            raise RuntimeError("Failed to parse diskutil output.")

        disk = content["DeviceIdentifier"]

        if content.get("APFSSnapshot") is True:
            # Remove snapshot suffix (last 2 characters)
            # ex. disk1s1s1 -> disk1s1
            disk = disk[:-2]

        return disk

    def _mount_root_volume(self) -> str | None:
        """
        Mount the root volume.

        Returns the path to the root volume.
        """
        # Root volume same as data volume
        if self.xnu_major < os_data.os_data.catalina.value:
            return "/"

        # Catalina implemented a read-only root volume
        if self.xnu_major == os_data.os_data.catalina.value:
            result = subprocess_wrapper.run_as_root(
                ["/sbin/mount", "-uw", "/"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            )
            if result.returncode != 0:
                logging.error("Failed to mount root volume")
                subprocess_wrapper.log(result)
                return None
            return "/"

        # Big Sur and newer implemented APFS snapshots for the root volume
        if self.xnu_major >= os_data.os_data.big_sur.value:
            if Path("/System/Volumes/Update/mnt1/System/Library/CoreServices/SystemVersion.plist").exists():
                return "/System/Volumes/Update/mnt1"

            result_unmount = subprocess_wrapper.run_as_root(
                ["/usr/sbin/diskutil", "unmount", f"/dev/{self.root_volume_identifier}"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            )
            if result_unmount.returncode != 0:
                logging.info(f"{self.root_volume_identifier} has already been unmounted.")

            result = subprocess_wrapper.run_as_root(
                ["/sbin/mount", "-o", "nobrowse", "-t", "apfs",
                 f"/dev/{self.root_volume_identifier}", "/System/Volumes/Update/mnt1"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            )
            if result.returncode != 0:
                logging.error("Failed to mount root volume")
                subprocess_wrapper.log(result)
                return None
            return "/System/Volumes/Update/mnt1"

        return None

    def _unmount_root_volume(self, ignore_errors: bool = True) -> bool:
        """
        Unmount the root volume.
        """
        if self.xnu_major < os_data.os_data.catalina.value:
            return True

        args = ["/sbin/umount"]

        if self.xnu_major == os_data.os_data.catalina.value:
            args += ["-uw", self.mount_path]

        if self.xnu_major >= os_data.os_data.big_sur.value:
            args += [self.mount_path]

        result = subprocess_wrapper.run_as_root(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if result.returncode != 0:
            if not ignore_errors:
                logging.error("Failed to unmount root volume")
                subprocess_wrapper.log(result)
            return False

        return True

    def mount(self) -> str | None:
        """
        Mount the root volume.

        Returns the path to the root volume, or None on failure.
        """
        result = self._mount_root_volume()
        if result is None:
            logging.error("Failed to mount root volume")
            return None
        if not Path(result).exists():
            logging.error(f"Attempted to mount root volume, but failed: {result}")
            return None

        self.mount_path = result
        return result

    def unmount(self, ignore_errors: bool = True) -> bool:
        """
        Unmount the root volume.

        Returns True if successful, False otherwise.
        """
        return self._unmount_root_volume(ignore_errors=ignore_errors)

    def create_snapshot(self) -> bool:
        """
        Create APFS snapshot of the root volume.
        """
        if self.mount_path is None:
            return False
        return APFSSnapshot(self.xnu_major, self.mount_path).create_snapshot()

    def revert_snapshot(self) -> bool:
        """
        Revert APFS snapshot of the root volume.
        """
        if self.mount_path is None:
            return False
        return APFSSnapshot(self.xnu_major, self.mount_path).revert_snapshot()


class EFIPartitionMount:
    """Mount / unmount an EFI (or any) partition by its disk identifier."""

    def __init__(self, identifier: str) -> None:
        self.identifier = identifier
        self.mount_point = None

    def _try_mount(self, as_root: bool = False) -> subprocess.CompletedProcess:
        """
        Try to mount the partition.
        """
        if as_root:
            return subprocess_wrapper.run_as_root(
                ["/usr/sbin/diskutil", "mount", self.identifier],
                capture_output=True, text=True,
            )
        else:
            return subprocess.run(
                ["/usr/sbin/diskutil", "mount", self.identifier],
                capture_output=True, text=True,
            )

    def mount(self) -> str | None:
        """
        Mount the partition.

        Returns the mount point path, or None on failure.
        """
        # Try non-root first (EFI partitions often mount without root)
        mount_res = self._try_mount(as_root=False)

        # If non-root succeeded, continue
        if mount_res.returncode == 0:
            pass  # Proceed to get mount point
        else:
            # Non-root failed, check if it's a permission issue
            # Error message patterns for permission denied
            permission_errors = [
                "permission denied",
                "not permitted",
                "Operation not permitted",
            ]
            is_permission_error = any(
                err.lower() in mount_res.stderr.lower()
                for err in permission_errors
            )

            if is_permission_error:
                # Try with root
                mount_res = self._try_mount(as_root=True)
                if mount_res.returncode != 0:
                    # Check for helper tool errors first
                    if mount_res.returncode >= 160:
                        logging.error(f"Privileged helper error (code {mount_res.returncode}): helper tool not properly installed or signed")
                        return None

                    logging.error(f"Failed to mount {self.identifier} (as root): {mount_res.stderr}")
                    return None
            else:
                # Check for specific known errors
                stderr_lower = mount_res.stderr.lower()
                if "failed to mount" in stderr_lower and "readonly" in stderr_lower:
                    logging.error(f"Failed to mount {self.identifier}: volume appears damaged or unformatted. Try reformatting the partition first.")
                    return None

                # Other error, log and return None
                logging.error(f"Failed to mount {self.identifier}: {mount_res.stderr}")
                return None

        # Query mount point via diskutil info
        info_res = subprocess.run(
            ["/usr/sbin/diskutil", "info", "-plist", self.identifier],
            capture_output=True, text=True,
        )
        if info_res.returncode != 0:
            logging.error(f"diskutil info failed for {self.identifier}")
            return None

        try:
            info_data = plistlib.loads(info_res.stdout.encode("utf-8"))
        except Exception as e:
            logging.error(f"Failed to parse diskutil info: {e}")
            return None

        mount_point = info_data.get("MountPoint")

        if not mount_point:
            logging.error(f"Could not find mount point for {self.identifier}")
            return None

        self.mount_point = mount_point
        return mount_point

    def unmount(self, ignore_errors: bool = True) -> bool:
        """
        Unmount the partition.

        Returns True if successful, False otherwise.
        """
        if self.mount_point is None:
            return True

        # Try non-root first
        result = subprocess.run(
            ["/usr/sbin/diskutil", "unmount", self.identifier],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            # Try with root if permission error
            permission_errors = [
                "permission denied",
                "not permitted",
                "Operation not permitted",
            ]
            is_permission_error = any(
                err.lower() in result.stderr.lower()
                for err in permission_errors
            )

            if is_permission_error:
                result = subprocess_wrapper.run_as_root(
                    ["/usr/sbin/diskutil", "unmount", self.identifier],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                )
                if result.returncode != 0:
                    if not ignore_errors:
                        logging.error(f"Failed to unmount {self.identifier}")
                        subprocess_wrapper.log(result)
                    return False
            else:
                if not ignore_errors:
                    logging.error(f"Failed to unmount {self.identifier}: {result.stderr}")
                return False

        self.mount_point = None
        return True

    def format_efi(self, volume_name: str = "EFI") -> bool:
        """
        Format/erase the EFI partition as FAT32.

        This is useful when the EFI partition is corrupted or unformatted.

        Returns True if successful, False otherwise.
        """
        result = subprocess_wrapper.run_as_root(
            ["/usr/sbin/diskutil", "eraseVolume", "FAT32", volume_name, self.identifier],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            logging.error(f"Failed to format {self.identifier}: {result.stderr}")
            return False
        return True

    def get_disk_info(self) -> dict | None:
        """
        Return the full diskutil info plist for the parent disk.

        Useful for determining disk type (SSD, USB, internal, SD card, etc.).
        """
        parent_disk = self.identifier.rstrip("0123456789")
        if parent_disk.endswith("s"):
            parent_disk = parent_disk[:-1]

        try:
            info_res = subprocess.run(
                ["/usr/sbin/diskutil", "info", "-plist", parent_disk],
                capture_output=True, text=True, check=True,
            )
            return plistlib.loads(info_res.stdout.encode("utf-8"))
        except Exception:
            return None
