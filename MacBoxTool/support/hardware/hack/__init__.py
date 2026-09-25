"""Hardware compatibility checker package."""

from .checker import (
    CompatStatus,
    ComponentResult,
    CompatibilityReport,
    NativeMacOSRange,
    check_board,
    check_cpu,
    check_gpu,
    check_gpus,
    check_hardware,
    check_storage,
    check_wifi,
    evaluate,
    native_cpu_macos_range,
    native_gpu_macos_range,
    native_wifi_macos_range,
)

__all__ = [
    "CompatStatus", "ComponentResult", "CompatibilityReport", "NativeMacOSRange",
    "check_board", "check_cpu", "check_gpu", "check_gpus", "check_hardware",
    "check_storage", "check_wifi", "evaluate", "native_cpu_macos_range",
    "native_gpu_macos_range", "native_wifi_macos_range",
]
