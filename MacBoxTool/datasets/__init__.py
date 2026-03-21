"""
datasets: Hardware data modules for MacBoxTool
"""

from .compatibility_data import (
    CompatStatus,
    CompatResult,
    CompatibilityChecker,
    CPU_COMPAT,
    GPU_FAMILIES,
)

__all__ = [
    "CompatStatus",
    "CompatResult",
    "CompatibilityChecker",
    "CPU_COMPAT",
    "GPU_FAMILIES",
]