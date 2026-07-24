"""
global_settings.py: Remember your settings
"""
import os
import json
import logging
import threading
import time
import datetime
import sched
import subprocess
import sys

from pathlib import Path
from ..constants import Constants

GITHUB_TOKEN_KEY = "github_token"
KEYCHAIN_SERVICE = "MacBoxTool"
KEYCHAIN_GITHUB_TOKEN_ACCOUNT = "github_token"

# Settings that directly mirror an attribute on Constants.  They are applied as
# soon as GlobalSettings is created so every GUI page receives persisted values
# while it is constructing its controls.
CONSTANTS_SETTING_KEYS = (
    "allow_oc_everywhere",
    "allow_apfs_aligned_patch",
    "allow_native_spoofs",
    "allow_nvme_fixing",
    "allow_ts2_accel",
    "allow_usb_patch",
    "amd_gop_injection",
    "apfs_trim_timeout",
    "applehda_version",
    "audio_type",
    "custom_board_serial_number",
    "custom_serial_number",
    "custom_sip_value",
    "dGPU_switch",
    "disable_amfi",
    "disable_connectdrivers",
    "disable_cs_lv",
    "disable_fw_throttle",
    "disable_mediaanalysisd",
    "disable_tb",
    "disallow_cpufriend",
    "drm_support",
    "enable_wake_on_wlan",
    "firewire_boot",
    "force_nv_web",
    "force_quad_thread",
    "fu_status",
    "imac_model",
    "imac_vendor",
    "kext_debug",
    "metal_build",
    "nvidia_kepler_gop_injection",
    "nvme_boot",
    "nvram_write",
    "oc_timeout",
    "opencore_debug",
    "override_smbios",
    "secure_status",
    "serial_settings",
    "set_vmm_cpuid",
    "show_logs",
    "showpicker",
    "sip_status",
    "software_demux",
    "verbose_debug",
    "vault",
    "xhci_boot",
)


class GlobalSettings:
    def __init__(self, global_constants: Constants):
        super().__init__()
        logging.info("Initializing global settings...")
        self.constants = global_constants
        self.settings_path:Path = Path(os.path.expanduser("~")) / ".macboxtool"
        self.settings_file:Path = self.settings_path / "settings.json"
        self.settings: dict = self.read_settings()
        self.create_file()

        # Ensure first_run flag exists
        if "first_run" not in self.settings:
            self.add_key("first_run", True)

        # Ensure download_path exists (default to Downloads folder)
        if "download_path" not in self.settings:
            default_download_path = str(Path.home() / "Downloads")
            self.add_key("download_path", default_download_path)

        self._migrate_github_token_to_keychain()
        setattr(self.constants, GITHUB_TOKEN_KEY, self.get_secure_key(GITHUB_TOKEN_KEY) or "")
        self.apply_to_constants()

    def apply_to_constants(self) -> None:
        """Apply persisted build settings before any GUI controls are created."""
        for key in CONSTANTS_SETTING_KEYS:
            if key in self.settings:
                setattr(self.constants, key, self.settings[key])

    def is_first_run(self) -> bool:
        """Check if this is the first run of the application."""
        return self.settings.get("first_run", True)

    def mark_first_run_complete(self) -> None:
        """Mark that first run has completed."""
        self.edit_key("first_run", False)

    def create_file(self) -> None:
        if self.settings_path.exists():
            logging.info("Settings Path has already created.")
            print("Settings Path has already created.")
            return
        else:
            os.mkdir(self.settings_path)
        if self.settings_file.exists():
            logging.info("Settings Files has already created")
            print("Settings Files has already created")
            return
        
        Path(self.settings_file).touch()
        return None

    def read_settings(self) -> dict:

        """Reads the settings file and returns the contents as a dictionary."""

        if not self.settings_file.exists():
            self.create_file()
            return {}

        with open(self.settings_file, "r") as f:
            logging.info("Action: Read settings")
            return json.load(f)

    def _log_value(self, key: str, value):
        if "token" in key.lower():
            return "<redacted>" if value else ""
        return value

    def _secure_account(self, key: str) -> str:
        if key == GITHUB_TOKEN_KEY:
            return KEYCHAIN_GITHUB_TOKEN_ACCOUNT
        return key

    def _set_keychain_password(self, key: str, value: str) -> bool:
        if sys.platform != "darwin":
            return False
        account = self._secure_account(key)
        delete_args = ["/usr/bin/security", "delete-generic-password", "-s", KEYCHAIN_SERVICE, "-a", account]
        subprocess.run(delete_args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if not value:
            return True
        add_args = [
            "/usr/bin/security", "add-generic-password",
            "-U", "-s", KEYCHAIN_SERVICE,
            "-a", account,
            "-w", value,
        ]
        result = subprocess.run(add_args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return result.returncode == 0

    def _get_keychain_password(self, key: str) -> str | None:
        if sys.platform != "darwin":
            return None
        account = self._secure_account(key)
        args = ["/usr/bin/security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-a", account, "-w"]
        result = subprocess.run(args, capture_output=True, text=True)
        if result.returncode != 0:
            return None
        return result.stdout.rstrip("\n")

    def set_secure_key(self, key: str, value: str) -> bool:
        success = self._set_keychain_password(key, value)
        if success:
            if key in self.settings:
                self.settings.pop(key, None)
                self.save_settings()
            logging.info(f"Setting {key} -> {self._log_value(key, value)}")
        else:
            logging.error(f"Failed to securely store {key}")
        return success

    def get_secure_key(self, key: str) -> str | None:
        value = self._get_keychain_password(key)
        logging.info(f"Getting {key} -> {self._log_value(key, value)}")
        return value

    def _migrate_github_token_to_keychain(self) -> None:
        token = self.settings.get(GITHUB_TOKEN_KEY)
        if not token:
            self.settings.pop(GITHUB_TOKEN_KEY, None)
            self.save_settings()
            return
        if self.set_secure_key(GITHUB_TOKEN_KEY, token):
            logging.info("Migrated GitHub token to secure storage")

    def find_key(self, key: str) -> str | None:
        """Finds a key in the settings file and returns its value."""
        if key == GITHUB_TOKEN_KEY:
            return self.get_secure_key(key)
        value = self.settings.get(key)
        logging.info(f"Getting {key} -> {self._log_value(key, value)}")
        return value
    
    def check_key(self,key:str)->bool:
        if key == GITHUB_TOKEN_KEY:
            return self.get_secure_key(key) is not None
        return key in self.settings

    def add_key(self, key:str, value):
        """ADD a key to the self.settings."""
        if key == GITHUB_TOKEN_KEY:
            self.set_secure_key(key, value)
            return None
        if self.check_key(key):
            return None
        self.settings[key] = value
        logging.info(f"Adding {key} -> {self._log_value(key, value)}")
        self.save_settings()
        return None

    def edit_key(self,key:str,value):
        if key == GITHUB_TOKEN_KEY:
            self.set_secure_key(key, value)
            return None
        if self.check_key(key):
            self.settings[key] = value
            self.save_settings()
        logging.info(f"Setting {key} -> {self._log_value(key, value)}")
        return None

    def save_settings(self):
        """Saves the settings file."""

        with open(self.settings_file, "w") as f:
            json.dump(self.settings, f, indent=4)
        return None

    def show_settings(self):
        return self.settings
    
    
       

        
