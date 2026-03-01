"""
mount: Library for mounting and unmounting volumes.

Includes:
  - RootVolumeMount: Mount/unmount the macOS root volume (supports Catalina+, APFS snapshots)
  - APFSSnapshot: Create/revert APFS snapshots on Big Sur+
  - EFIPartitionMount: Mount an EFI partition and query its mount point

Usage:

>>> from MacBoxTool.support.mount import RootVolumeMount
>>> RootVolumeMount(xnu_major).mount()
'/System/Volumes/Update/mnt1'
>>> RootVolumeMount(xnu_major).unmount()

>>> from MacBoxTool.support.mount import EFIPartitionMount
>>> efi = EFIPartitionMount("disk0s1")
>>> efi.mount()
'/Volumes/EFI'
>>> efi.unmount()
"""

from .mount_volume   import RootVolumeMount, EFIPartitionMount
from .apfs_snapshot  import APFSSnapshot
