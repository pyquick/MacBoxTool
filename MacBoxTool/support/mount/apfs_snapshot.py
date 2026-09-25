"""
apfs_snapshot.py: Handling APFS snapshots
"""

import logging
import subprocess

from ...datasets import os_data
from ..system import subprocess_wrapper
from ..system.rosetta import is_apple_silicon


class APFSSnapshot:

    def __init__(self, xnu_major: int, mount_path: str):
        self.xnu_major = xnu_major
        self.mount_path = mount_path

    def create_snapshot(self) -> bool:
        """
        Create APFS snapshot of the root volume.
        """
        if self.xnu_major < os_data.os_data.big_sur.value:
            return True

        args = ["/usr/sbin/bless"]
        if is_apple_silicon():
            args += ["--mount", self.mount_path, "--create-snapshot"]
        else:
            args += [
                "--folder",
                f"{self.mount_path}/System/Library/CoreServices",
                "--bootefi",
                "--create-snapshot",
            ]

        result = subprocess_wrapper.run_as_root(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if result.returncode != 0:
            logging.error("Failed to create APFS snapshot")
            subprocess_wrapper.log(result)
            if "Can't use last-sealed-snapshot or create-snapshot on non system volume" in result.stdout.decode():
                logging.info(
                    "- This is an APFS bug with Monterey and newer! "
                    "Perform a clean installation to ensure your APFS volume is built correctly"
                )
            return False

        return True

    def revert_snapshot(self) -> bool:
        """
        Revert APFS snapshot of the root volume.
        """
        if self.xnu_major < os_data.os_data.big_sur.value:
            return True

        result = subprocess_wrapper.run_as_root(
            ["/usr/sbin/bless", "--mount", self.mount_path, "--bootefi", "--last-sealed-snapshot"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        if result.returncode != 0:
            logging.error("Failed to revert APFS snapshot")
            subprocess_wrapper.log(result)
            return False

        return True
