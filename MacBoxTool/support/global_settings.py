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

from pathlib import Path
from ..constants import Constants

class GlobalSettings:
    def __init__(self, global_constants: Constants):
        super().__init__()
        logging.info("Initializing global settings...")
        self.constants = global_constants
        self.settings_path:Path = Path(os.path.expanduser("~")) / ".macboxtool"
        self.settings_file:Path = self.settings_path / "settings.json"
        self.settings: dict = self.read_settings()
        self.create_file()

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

    def find_key(self, key: str) -> str | None:
        """Finds a key in the settings file and returns its value."""
        value = self.settings.get(key)
        logging.info(f"Getting {key} -> {value}")
        return value
    
    def check_key(self,key:str)->bool:
        return key in self.settings

    def add_key(self, key:str, value):
        """ADD a key to the self.settings."""
        if self.check_key(key):
            return None
        self.settings[key] = value
        logging.info(f"Adding {key} -> {value}")
        self.save_settings()
        return None

    def edit_key(self,key:str,value):
        if self.check_key(key):
            self.settings[key] = value
            self.save_settings()
        logging.info(f"Setting {key} -> {value}")
        return None

    def save_settings(self):
        """Saves the settings file."""

        with open(self.settings_file, "w") as f:
            json.dump(self.settings, f, indent=4)
        return None

    def show_settings(self):
        return self.settings
    
    
       

        
