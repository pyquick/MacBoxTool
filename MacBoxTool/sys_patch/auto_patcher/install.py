"""
install.py: Install the auto patcher launch services
"""

import hashlib
import logging
import plistlib
import subprocess

from pathlib import Path

from ... import constants

from ...volume import generate_copy_arguments

from ...support import (
    utilities,
    subprocess_wrapper,
)


class InstallAutomaticPatchingServices:
    """
    Install the auto patcher launch services
    """

    def __init__(self, global_constants: constants.Constants):
        self.constants: constants.Constants = global_constants


    def install_auto_patcher_launch_agent(self, kdk_caching_needed: bool = False):
        """
        Install patcher launch services

        See start_auto_patch() comments for more info
        """

        if self.constants.launcher_script is not None:
            logging.info("- Skipping Auto Patcher Launch Agent, not supported when running from source")
            return

        services = {
            self.constants.auto_patch_launch_agent_path:        "/Library/LaunchAgents/com.pyquick.macboxtool.auto-patch.plist",
            self.constants.update_launch_daemon_path:           "/Library/LaunchDaemons/com.pyquick.macboxtool.macos-update.plist",
            **({ self.constants.rsr_monitor_launch_daemon_path: "/Library/LaunchDaemons/com.pyquick.macboxtool.rsr-monitor.plist" } if self._create_rsr_monitor_daemon() else {}),
            **({ self.constants.kdk_launch_daemon_path:         "/Library/LaunchDaemons/com.pyquick.macboxtool.os-caching.plist" } if kdk_caching_needed is True else {} ),
        }

        for service in services:
            name = Path(service).name
            logging.info("- Installing {name}".format(name=name))
            if Path(services[service]).exists():
                if hashlib.sha256(open(service, "rb").read()).hexdigest() == hashlib.sha256(open(services[service], "rb").read()).hexdigest():
                    logging.info("  - {name} checksums match, skipping".format(name=name))
                    continue
                logging.info("  - Existing service found, removing")
                subprocess_wrapper.run_as_root_and_verify(["/bin/rm", services[service]], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            # Create parent directories
            if not Path(services[service]).parent.exists():
                logging.info("  - Creating {path} directory".format(path=Path(services[service]).parent))
                subprocess_wrapper.run_as_root_and_verify(["/bin/mkdir", "-p", Path(services[service]).parent], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            subprocess_wrapper.run_as_root_and_verify(generate_copy_arguments(service, services[service]), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

            # Set the permissions on the service
            subprocess_wrapper.run_as_root_and_verify(["/bin/chmod", "644", services[service]], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            subprocess_wrapper.run_as_root_and_verify(["/usr/sbin/chown", "root:wheel", services[service]], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


    def _create_rsr_monitor_daemon(self) -> bool:
        # Get kext list in /Library/Extensions that have the 'GPUCompanionBundles' property
        # This is used to determine if we need to run the RSRMonitor
        logging.info("- Checking if RSRMonitor is needed")

        cryptex_path = f"/System/Volumes/Preboot/{utilities.get_preboot_uuid()}/cryptex1/current/OS.dmg"
        if not Path(cryptex_path).exists():
            logging.info("- No OS.dmg, skipping RSRMonitor")
            return False

        kexts = []
        for kext in Path("/Library/Extensions").glob("*.kext"):
            try:
                if not Path(f"{kext}/Contents/Info.plist").exists():
                    continue
            except Exception as e:
                logging.info("  - Failed to check if {name} is a directory: {error}".format(name=kext.name, error=e))
                continue
            try:
                kext_plist = plistlib.load(open(f"{kext}/Contents/Info.plist", "rb"))
            except Exception as e:
                logging.info("  - Failed to load plist for {name}: {error}".format(name=kext.name, error=e))
                continue
            if "GPUCompanionBundles" not in kext_plist:
                continue
            logging.info("  - Found kext with GPUCompanionBundles: {name}".format(name=kext.name))
            kexts.append(kext.name)

        # If we have no kexts, we don't need to run the RSRMonitor
        if not kexts:
            logging.info("- No kexts found with GPUCompanionBundles, skipping RSRMonitor")
            return False

        # Load the RSRMonitor plist
        rsr_monitor_plist = plistlib.load(open(self.constants.rsr_monitor_launch_daemon_path, "rb"))

        arguments = ["/bin/rm", "-Rfv"]
        arguments += [f"/Library/Extensions/{kext}" for kext in kexts]

        # Add the arguments to the RSRMonitor plist
        rsr_monitor_plist["ProgramArguments"] = arguments

        # Next add monitoring for '/System/Volumes/Preboot/{UUID}/cryptex1/OS.dmg'
        logging.info("  - Adding monitor: {path}".format(path=cryptex_path))
        rsr_monitor_plist["WatchPaths"] = [
            cryptex_path,
        ]

        # Write the RSRMonitor plist
        plistlib.dump(rsr_monitor_plist, Path(self.constants.rsr_monitor_launch_daemon_path).open("wb"))

        return True
