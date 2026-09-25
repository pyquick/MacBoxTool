import subprocess
import plistlib
import logging
import re

def list_disks():
    """
    Scans the system for physical disks that have EFI or FAT partitions.
    Returns a dictionary of supported disks with their partitions.
    """
    all_disks = {}

    try:
        # Use "physical" to only get physical disks
        try:
            diskutil_output = subprocess.run(
                ["/usr/sbin/diskutil", "list", "-plist", "physical"],
                capture_output=True, text=True, check=True
            ).stdout
        except ValueError:
            # Fallback for older macOS
            diskutil_output = subprocess.run(
                ["/usr/sbin/diskutil", "list", "-plist"],
                capture_output=True, text=True, check=True
            ).stdout

        disks = plistlib.loads(diskutil_output.strip().encode())

        for disk in disks.get("AllDisksAndPartitions", []):
            disk_ident = disk.get("DeviceIdentifier")

            # Get detailed disk info
            try:
                info_res = subprocess.run(
                    ["/usr/sbin/diskutil", "info", "-plist", disk_ident],
                    capture_output=True, text=True, check=True
                ).stdout
                disk_info = plistlib.loads(info_res.strip().encode())
            except Exception as e:
                logging.debug(f"Failed to get info for {disk_ident}: {e}")
                # Try to clean up garbaged MediaName
                try:
                    diskutil_output = subprocess.run(
                        ["/usr/sbin/diskutil", "info", "-plist", disk_ident],
                        capture_output=True, text=True
                    ).stdout
                    ungarbafied_output = re.sub(
                        r'(<key>MediaName</key>\s*<string>).*?(</string>)',
                        r'\1Disk</string>',
                        diskutil_output
                    ).encode()
                    disk_info = plistlib.loads(ungarbafied_output)
                except Exception as e2:
                    logging.debug(f"Failed to get info for {disk_ident} after cleanup: {e2}")
                    continue

            disk_name = disk_info.get("MediaName", "Disk")
            disk_node = disk_info.get("DeviceNode", f"/dev/{disk_ident}")
            disk_size = disk_info.get("TotalSize", 0)

            partitions = {}
            try:
                for partition in disk.get("Partitions", []):
                    part_ident = partition.get("DeviceIdentifier")
                    try:
                        part_info_res = subprocess.run(
                            ["/usr/sbin/diskutil", "info", "-plist", part_ident],
                            capture_output=True, text=True, check=True
                        ).stdout
                        part_info = plistlib.loads(part_info_res.strip().encode())
                    except Exception as e:
                        logging.debug(f"Failed to get partition info for {part_ident}: {e}")
                        continue

                    fs_type = part_info.get("FilesystemType", part_info.get("Content", ""))
                    content = part_info.get("Content", "")
                    partitions[part_ident] = {
                        "fs": fs_type,
                        "type": content,
                        "name": part_info.get("VolumeName", ""),
                        "size": part_info.get("TotalSize", 0),
                    }
            except KeyError:
                # Skip disks without partitions (e.g., CDs)
                continue

            all_disks[disk_ident] = {
                "identifier": disk_node,
                "name": disk_name,
                "size": disk_size,
                "partitions": partitions
            }

    except Exception as e:
        logging.error(f"Failed to scan for disks: {e}")

    # Filter: only keep disks that have EFI or FAT (msdos) partitions
    supported_disks = {}
    for disk in all_disks:
        has_efi_or_fat = any(
            all_disks[disk]["partitions"][partition]["fs"] in ("msdos", "EFI")
            or all_disks[disk]["partitions"][partition]["type"] == "EFI"
            for partition in all_disks[disk]["partitions"]
        )
        if not has_efi_or_fat:
            continue

        # Filter out disk image, read-only, virtual
        disk_name_lower = all_disks[disk]["name"].lower()
        ignore = ["disk image", "read-only", "virtual"]
        if any(s in disk_name_lower for s in ignore):
            continue

        supported_disks[disk] = {
            "disk": disk,
            "name": all_disks[disk]["name"],
            "size": all_disks[disk]["size"],
            "partitions": all_disks[disk]["partitions"]
        }

    return supported_disks


def list_partitions(disk_identifier):
    """
    Get partitions for a specific disk.
    Returns a dictionary of partitions with their details.
    """
    all_disks = list_disks()
    if disk_identifier in all_disks:
        return all_disks[disk_identifier]["partitions"]
    return {}


def get_efi_partition_for_disk(disk_identifier):
    """
    Gets the EFI partition for a specific disk.
    Returns a dictionary with 'identifier', 'size', 'disk_name', or None if not found.
    """
    partitions = list_partitions(disk_identifier)
    if not partitions:
        return None

    for part_ident, part_data in partitions.items():
        if part_data.get("fs") == "EFI":
            # Get disk name
            disk_name = "Unknown Disk"
            try:
                info_res = subprocess.run(
                    ["/usr/sbin/diskutil", "info", "-plist", disk_identifier],
                    capture_output=True, text=True, check=True
                )
                info_data = plistlib.loads(info_res.stdout.encode('utf-8'))
                disk_name = info_data.get('MediaName', "Unknown Disk")
            except Exception as e:
                logging.debug(f"Failed to get name for {disk_identifier}: {e}")

            return {
                'identifier': part_ident,
                'size': part_data.get('size', 0),
                'disk_name': disk_name,
                'name': f"{disk_name} - EFI ({part_ident})"
            }

    return None


def get_all_disks():
    """
    Returns a list of all supported disks (for backward compatibility).
    """
    disks = list_disks()
    result = []
    for disk_ident, disk_data in disks.items():
        result.append({
            'identifier': disk_ident,
            'name': f"{disk_data['name']} ({disk_ident})"
        })
    return result


def get_efi_partitions():
    """
    Scans the system for disks containing EFI partitions.
    Returns a list of dictionaries with 'identifier', 'name', and 'disk_name'.
    """
    efi_partitions = []
    supported_disks = list_disks()

    for disk_ident, disk_data in supported_disks.items():
        for part_ident, part_data in disk_data["partitions"].items():
            if part_data.get("fs") == "EFI":
                efi_partitions.append({
                    'identifier': part_ident,
                    'size': part_data.get('size', 0),
                    'disk_name': disk_data['name'],
                    'name': f"{disk_data['name']} - {part_ident}"
                })

    return efi_partitions


if __name__ == "__main__":
    print("Supported disks:")
    for disk in list_disks():
        print(f"  {disk}")
    print("\nEFI partitions:")
    for efi in get_efi_partitions():
        print(f"  {efi}")