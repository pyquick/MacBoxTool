"""
global_settings.py: Remember your settings
"""
import os
import json
import logging
import threading
import time
import datetime

from pathlib import Path
from ..constants import Constants

class GlobalSettings:
    def __init__(self, global_constants: Constants):
        logging.info("Initializing global settings...")
        self.constants = global_constants
        self.settings_path:Path = Path(os.path.expanduser("~")) / ".macboxtool"
        self.settings_file:Path = self.settings_path / "settings.json"
        self.settings: dict = self.read_settings()
        threading.Thread(name=self.hook,daemon=True).start()

    def create_file(self) -> None:
        if not self.settings_path.exists():
            logging.info("Settings Path has already created.")
            return
        if self.settings_file.exists():
            logging.info("Settings Files has already created")
            return
        Path(self.settings_file).touch()

    def read_settings(self) -> dict:

        """Reads the settings file and returns the contents as a dictionary."""

        if not self.settings_file.exists():
            self.create_file()
            return {}

        with open(self.settings_file, "r") as f:
            logging.info("Read Settings")
            return json.load(f)

    def find_key(self, key: str) -> str:
        """Finds a key in the settings file and returns its value."""

        return self.settings.get(key)
    
    def add_key(self, key:str, value):
        """ADD a key to the self.settings."""
        self.settings[key] = value
        self.save_settings()

    def save_settings(self):
        """Saves the settings file."""

        with open(self.settings_file, "w") as f:
            json.dump(self.settings, f, indent=4)
    
    def hook(self):
        """
        auto-save settings
        """
        hook = threading.Thread(target=self.save_settings,daemon=True)
        while True:
            hook.start()
            hook.join()
            time.sleep(0.6)
            logging.info(f"Settings Saved:{datetime.timezone()}")

    def show_settings(self):
        return self.settings

        
