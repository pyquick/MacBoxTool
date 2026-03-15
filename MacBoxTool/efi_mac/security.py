"""Security validation utilities for EFI building."""

import re
from pathlib import Path


class SecurityValidator:
    """Minimal security validation for EFI building."""

    @staticmethod
    def safe_path(base: Path, user_path: str) -> Path:
        """Validate path is within base directory."""
        resolved = (base / user_path).resolve()
        if not str(resolved).startswith(str(base.resolve())):
            raise ValueError(f"Path traversal detected: {user_path}")
        return resolved

    @staticmethod
    def safe_extract(zip_file, dest: Path):
        """Extract zip safely, preventing Zip Slip."""
        for member in zip_file.namelist():
            member_path = (dest / member).resolve()
            if not str(member_path).startswith(str(dest.resolve())):
                raise ValueError(f"Zip Slip detected: {member}")
        zip_file.extractall(dest)

    @staticmethod
    def validate_model(model: str) -> bool:
        """Validate SMBIOS model format."""
        return bool(re.match(r'^[A-Za-z]+\d+,\d+$', model))

    @staticmethod
    def validate_hex(value: str) -> bool:
        """Validate hex string format."""
        try:
            int(value.lstrip("0x"), 16)
            return True
        except ValueError:
            return False
