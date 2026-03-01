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

    def mount(self) -> str | None:
        """
        Mount the partition.

        Returns the mount point path, or None on failure.
        """
        mount_res = subprocess_wrapper.run_as_root(
            ["/usr/sbin/diskutil", "mount", self.identifier],
            capture_output=True, text=True,
        )
        if mount_res.returncode != 0:
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

        info_data = plistlib.loads(info_res.stdout.encode("utf-8"))
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

        result = subprocess_wrapper.run_as_root(
            ["/usr/sbin/diskutil", "unmount", self.identifier],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        if result.returncode != 0:
            if not ignore_errors:
                logging.error(f"Failed to unmount {self.identifier}")
                subprocess_wrapper.log(result)
            return False

        self.mount_point = None
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
