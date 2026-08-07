"""Hardware compatibility scoring for Hackintosh and Apple hardware."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import platform as host_platform
import re
from typing import Any, Iterable


class CompatStatus(str, Enum):
    """Compatibility states shared by the scorer and GUI."""

    PERFECT = "perfect"
    CONDITIONAL = "conditional"
    INCOMPATIBLE = "incompatible"
    UNKNOWN = "unknown"


@dataclass
class ComponentResult:
    """Compatibility result for one displayed hardware category."""

    category: str
    name: str
    score: int = 0
    status: CompatStatus = CompatStatus.UNKNOWN
    details: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    grade_cap: str | None = None


@dataclass(frozen=True)
class NativeMacOSRange:
    """Native macOS support range without third-party or system patches."""

    minimum: str | None = None
    maximum: str | None = None
    reason: str | None = None

    @property
    def label(self) -> str:
        """Format the native support range for display."""
        if self.reason:
            return self.reason
        if not self.minimum or not self.maximum:
            return "Unknown"
        return f"macOS {self.minimum} – macOS {self.maximum}"


@dataclass
class CompatibilityReport:
    """Aggregated compatibility result."""

    score: int
    grade: str
    status: CompatStatus
    components: list[ComponentResult]
    platform: str
    os_name: str = "Unknown"
    grade_caps: list[str] = field(default_factory=list)


_GRADE_ORDER = ("S", "A", "B", "C", "D")
_GRADE_CAP_ORDER = {grade: index for index, grade in enumerate(_GRADE_ORDER)}
_HACKINTOSH_MAX_SCORE = 140
_PROBLEMATIC_SAMSUNG_NVME = {
    0xA808: "Samsung PM981",
    0xA80A: "Samsung PM9A1",
}
_CPU_NATIVE_MINIMUMS = {
    "yonah": "10.4", "conroe": "10.4", "penryn": "10.5",
    "nehalem": "10.5", "westmere": "10.6", "sandy_bridge": "10.7",
    "sandy_bridge_e": "10.7", "ivy_bridge": "10.8", "ivy_bridge_e": "10.9",
    "haswell": "10.9", "haswell_e": "10.10", "broadwell": "10.10",
    "broadwell_e": "10.11", "skylake": "10.11", "skylake_x": "10.13",
    "kaby_lake": "10.12", "kaby_lake_or_coffee_lake": "10.12",
    "coffee_lake": "10.13", "whiskey_lake": "10.14", "comet_lake": "10.15",
    "ice_lake": "10.15", "rocket_lake": "11.3", "tiger_lake": "11.0",
    "alder_lake": "12", "raptor_lake": "13", "meteor_lake": "14",
    "arrow_lake": "15", "lunar_lake": "15",
}
_APPLE_SILICON_MINIMUMS = {
    "1": "11",
    "2": "12.4",
    "3": "14.1",
    "4": "15.1",
    "5": "26",
}
_GPU_NATIVE_RANGES = {
    "r500": ("10.4", "10.7"),
    "gma 950": ("10.4", "10.7"),
    "gma x3100": ("10.5", "10.7"),
    "iron lake": ("10.6", "10.13"),
    "sandy bridge": ("10.7", "10.13"),
    "ivy bridge": ("10.8", "11"),
    "haswell": ("10.9", "12"),
    "broadwell": ("10.10", "12"),
    "skylake": ("10.11", "12"),
    "kaby lake": ("10.12", "26"),
    "coffee lake": ("10.13", "26"),
    "comet lake": ("10.15", "26"),
    "ice lake": ("10.15", "26"),
    "terascale 1": ("10.4", "10.13"),
    "terascale 2": ("10.7", "10.13"),
    "legacy gcn v1": ("10.10", "12"),
    "legacy gcn v2": ("10.11", "12"),
    "legacy gcn v3": ("10.12", "12"),
    "polaris": ("10.12", "26"),
    "vega": ("10.13", "26"),
    "navi": ("10.15", "26"),
    "curie": ("10.4", "10.7"),
    "tesla": ("10.4", "10.13"),
    "fermi": ("10.6", "10.13"),
    "kepler": ("10.8", "11"),
}
_APPLE_WIFI_MINIMUMS = {
    0x43DC: "10.12",
    0x4464: "10.14",
    0x4488: "10.14",
}
_APPLE_SILICON_WIFI_MINIMUMS = {
    0x4425: "11",
    0x4433: "12",
}
_RDNA2_DEVICE_IDS = {
    0x73A2,
    0x73A3,
    0x73AB,
    0x73BF,
    0x73E0,
    0x73E3,
    0x73FF,
}


def _text(value: Any) -> str:
    """Convert probe values and enum values to text."""
    return "" if value is None else str(getattr(value, "value", value))


def _name(device: Any) -> str:
    """Get the best available device name."""
    return (_text(getattr(device, "name", "")) or _text(getattr(device, "model", "")) or "Unknown").strip()


def _hardware_id(value: Any) -> int | None:
    """Normalize integer and hexadecimal hardware identifiers."""
    if value in (None, ""):
        return None
    if isinstance(value, int):
        return value
    try:
        text = str(value).strip()
        return int(text, 16 if text.lower().startswith("0x") or any(character in "abcdefABCDEF" for character in text) else 10)
    except (TypeError, ValueError):
        return None


def _contains(device: Any, *values: str) -> bool:
    """Find text in common hardware identification fields."""
    text = " ".join(
        _text(getattr(device, field, ""))
        for field in ("name", "model", "chipset", "arch", "architecture", "device_id")
    ).lower()
    return any(value.lower() in text for value in values)


def _is_windows(platform_name: str) -> bool:
    """Return whether the current report targets Windows."""
    return platform_name.lower() in {"windows", "win32"}


def _cpu_generation(cpu: Any) -> int | None:
    """Infer an Intel Core generation from probe information."""
    architecture = _text(getattr(cpu, "architecture", "")).lower().replace(" ", "_")
    if architecture in {"yonah", "conroe", "penryn"}:
        return 0
    generations = {
        1: ("nehalem", "westmere"), 2: ("sandy_bridge",), 3: ("ivy_bridge",),
        4: ("haswell", "haswell_e"), 5: ("broadwell", "broadwell_e"),
        6: ("skylake", "skylake_x"), 7: ("kaby_lake",), 8: ("coffee_lake",),
        9: ("whiskey_lake",), 10: ("comet_lake", "ice_lake"),
        11: ("rocket_lake", "tiger_lake"), 12: ("alder_lake",),
        13: ("raptor_lake",), 14: ("meteor_lake",), 15: ("arrow_lake", "lunar_lake"),
    }
    for generation, names in generations.items():
        if any(name in architecture for name in names):
            return generation
    match = re.search(r"(?:i[3579]|core)\s*[- ]?(\d{4,5})", _text(getattr(cpu, "name", "")).lower())
    if match:
        number = match.group(1)
        return int(number[:2]) if len(number) == 5 else int(number[:1])
    return None


def _apple_cpu_score(cpu: Any) -> tuple[int, str] | None:
    """Return the Apple Silicon score and model label."""
    value = " ".join((_text(getattr(cpu, "name", "")), _text(getattr(cpu, "architecture", "")))).lower()
    if not ("apple" in value or re.search(r"\bm[1-5]\b", value) or "arm64" in value):
        return None
    match = re.search(r"\bm([1-5])\b", value)
    if not match:
        return 0, "Apple Silicon"
    suffix = next(((label, score) for label, score in (("ultra", 36), ("max", 19), ("pro", 10)) if label in value), ("", 0))
    score = {"1": 35, "2": 40, "3": 48, "4": 52, "5": 64}[match.group(1)] + suffix[1]
    return score, f"M{match.group(1)}{(' ' + suffix[0].title()) if suffix[0] else ''}"


def native_cpu_macos_range(cpu: Any) -> NativeMacOSRange:
    """Return the fully native macOS range for a CPU."""
    if not cpu:
        return NativeMacOSRange()
    apple = _apple_cpu_score(cpu)
    if apple:
        match = re.search(r"\bm([1-5])(?:\s|\b)", _text(getattr(cpu, "name", "")).lower())
        if not match:
            return NativeMacOSRange()
        return NativeMacOSRange(_APPLE_SILICON_MINIMUMS[match.group(1)], "27+")

    vendor = _text(getattr(cpu, "vendor_id", "") or getattr(cpu, "vendor", "")).lower()
    if "amd" in vendor or "1022" in vendor or _contains(cpu, "ryzen", "threadripper", "epyc", "athlon"):
        return NativeMacOSRange(reason="Not natively supported")

    architecture = _text(getattr(cpu, "architecture", "")).lower().replace(" ", "_")
    minimum = _CPU_NATIVE_MINIMUMS.get(architecture)
    generation = _cpu_generation(cpu)
    if not minimum or generation is None:
        return NativeMacOSRange()
    return NativeMacOSRange(minimum, "12" if generation <= 3 else "26")


def native_gpu_macos_range(gpu: Any) -> NativeMacOSRange:
    """Return the macOS range containing native drivers for one GPU."""
    if not gpu:
        return NativeMacOSRange()
    vendor = _gpu_vendor(gpu)
    arch = _gpu_arch(gpu).replace("_", " ").strip()
    if vendor == "nvidia" and arch in {"maxwell", "pascal", "turing", "ampere", "ada"}:
        return NativeMacOSRange(reason="Not natively supported")
    if vendor == "intel" and any(value in arch for value in ("arc", "xe", "alder", "raptor", "meteor", "arrow")):
        return NativeMacOSRange(reason="Not natively supported")
    if vendor == "amd" and ("spoof" in arch or arch == "rdna3"):
        return NativeMacOSRange(reason="Not natively supported")
    if vendor == "amd" and arch == "navi" and _hardware_id(getattr(gpu, "device_id", None)) in _RDNA2_DEVICE_IDS:
        return NativeMacOSRange("11.4", "26")
    native_range = _GPU_NATIVE_RANGES.get(arch)
    if not native_range:
        return NativeMacOSRange()
    return NativeMacOSRange(*native_range)


def native_wifi_macos_range(wifi: Any, computer: Any = None) -> NativeMacOSRange:
    """Return the fully native macOS range for one Wi-Fi card."""
    if not wifi:
        return NativeMacOSRange()
    vendor_id = _hardware_id(getattr(wifi, "vendor_id", None))
    device_id = _hardware_id(getattr(wifi, "device_id", None))
    value = " ".join(
        _text(getattr(wifi, field, ""))
        for field in ("name", "model", "chipset")
    ).lower()
    if vendor_id == 0x8086 or "intel" in value:
        return NativeMacOSRange(reason="Compatible with itlwm/AirportItlwm (hardware support)")
    if "thirdparty" in value or "airportbrcmfixup" in value:
        return NativeMacOSRange(reason="Not natively supported")
    if any(token in value for token in ("airportbrcm4331", "airportbrcm43224", "atheros40")):
        return NativeMacOSRange("10.6", "11")
    if any(token in value for token in ("airportbrcm4360", "airportbrcmnic")):
        return NativeMacOSRange("10.8", "13")
    if vendor_id == 0x14E4 and device_id in _APPLE_SILICON_WIFI_MINIMUMS:
        if _is_hackintosh(computer):
            return NativeMacOSRange(reason="Not natively supported")
        return NativeMacOSRange(_APPLE_SILICON_WIFI_MINIMUMS[device_id], "27+")
    if vendor_id == 0x14E4 and device_id in _APPLE_WIFI_MINIMUMS:
        if _is_hackintosh(computer):
            return NativeMacOSRange(reason="Not natively supported")
        return NativeMacOSRange(_APPLE_WIFI_MINIMUMS[device_id], "26")
    if vendor_id not in (0x14E4, 0x168C):
        return NativeMacOSRange(reason="Not natively supported")
    return NativeMacOSRange()


def check_cpu(cpu: Any, platform_name: str = "Darwin") -> ComponentResult:
    """Evaluate CPU support and its score contribution."""
    if not cpu:
        return ComponentResult("CPU", "Unknown", status=CompatStatus.UNKNOWN, notes=["CPU data is unavailable"])
    name = _name(cpu)
    apple = _apple_cpu_score(cpu)
    if apple:
        score, label = apple
        return ComponentResult("CPU", name, score, CompatStatus.PERFECT, [f"Apple Silicon {label}"])

    vendor = _text(getattr(cpu, "vendor_id", "") or getattr(cpu, "vendor", "")).lower()
    if "amd" in vendor or "1022" in vendor or _contains(cpu, "ryzen", "threadripper", "epyc", "athlon"):
        supported = any(token in _text(getattr(cpu, "architecture", "")).lower() for token in ("zen", "bulldozer", "piledriver", "steamroller", "excavator")) or _contains(cpu, "ryzen", "threadripper")
        return ComponentResult("CPU", name, 10 if supported else 0, CompatStatus.CONDITIONAL if supported else CompatStatus.INCOMPATIBLE, ["AMD CPU support requires a kernel patch" if supported else "Unsupported AMD CPU"], grade_cap="B" if supported else "C")

    generation = _cpu_generation(cpu)
    if generation is None:
        return ComponentResult("CPU", name, status=CompatStatus.UNKNOWN, notes=["Intel generation could not be determined"])
    if generation <= 3:
        return ComponentResult("CPU", name, 15, CompatStatus.CONDITIONAL, ["Supported with limitations"], ["AVX2 and macOS 13 or newer need additional work"])
    if generation <= 6:
        return ComponentResult("CPU", name, 25, CompatStatus.CONDITIONAL, ["Strong compatibility"], ["Integrated graphics is unsupported on macOS 13 or newer"])
    if generation <= 10:
        return ComponentResult("CPU", name, 30, CompatStatus.PERFECT, ["Excellent Hackintosh CPU"])
    if generation == 11:
        return ComponentResult("CPU", name, 24, CompatStatus.CONDITIONAL, ["Strong compatibility"], ["Integrated graphics cannot be driven"])
    return ComponentResult("CPU", name, 27, CompatStatus.CONDITIONAL, ["Strong compatibility"], ["Hybrid cores need OpenCore configuration; integrated graphics cannot be driven"])


def _gpu_arch(gpu: Any) -> str:
    """Get a normalized GPU architecture string."""
    return _text(getattr(gpu, "arch", "") or getattr(gpu, "family", "")).lower()


def _gpu_vendor(gpu: Any) -> str:
    """Identify the GPU vendor from probe data and PCI identifiers."""
    vendor = _text(getattr(gpu, "vendor", "")).lower()
    if vendor:
        return vendor
    vendor_id = _hardware_id(getattr(gpu, "vendor_id", None))
    if vendor_id in {0x1002, 0x1022}:
        return "amd"
    if vendor_id == 0x10DE:
        return "nvidia"
    if vendor_id == 0x8086:
        return "intel"
    if _contains(gpu, "nvidia", "geforce", "gtx", "rtx"):
        return "nvidia"
    if _contains(gpu, "amd", "radeon", "rx"):
        return "amd"
    if _contains(gpu, "intel", "uhd", "iris", "hd graphics"):
        return "intel"
    return "unknown"


def _gpu_capability(gpu: Any, capability: str) -> bool:
    """Use explicit capability flags or conservative architecture inference."""
    if capability.startswith("metal") and getattr(gpu, "disable_metal", False):
        return False
    explicit = getattr(gpu, capability, None)
    if explicit is not None:
        return bool(explicit)
    arch = _gpu_arch(gpu)
    if capability == "qe_ci":
        return not any(token in arch for token in ("unknown", "arc", "xe", "turing", "ampere", "ada"))
    if capability == "metal":
        metal2 = getattr(gpu, "metal2", None)
        if metal2 is not None:
            return bool(metal2)
        return any(token in arch for token in ("ivy", "haswell", "broadwell", "skylake", "kaby", "coffee", "comet", "ice", "polaris", "vega", "navi", "rdna"))
    if capability == "metal3":
        return any(token in arch for token in ("navi", "rdna2", "rdn2"))
    return False


def _gpu_result(gpu: Any, platform_name: str) -> ComponentResult:
    """Evaluate one GPU for aggregation by check_gpus."""
    name = _name(gpu)
    vendor = _gpu_vendor(gpu)
    arch = _gpu_arch(gpu)
    if _is_windows(platform_name):
        return ComponentResult("GPU", name, status=CompatStatus.PERFECT if vendor != "unknown" else CompatStatus.UNKNOWN, details=["Windows driver compatibility detected"])
    if vendor == "nvidia":
        if "kepler" in arch:
            return ComponentResult("GPU", name, 2, CompatStatus.CONDITIONAL, ["NVIDIA Kepler has limited support"], grade_cap="B")
        return ComponentResult("GPU", name, -2, CompatStatus.INCOMPATIBLE, ["No supported macOS driver"], grade_cap="C")
    if vendor == "intel":
        if any(token in arch for token in ("arc", "xe", "alder", "raptor", "meteor", "arrow")):
            return ComponentResult("GPU", name, -2, CompatStatus.INCOMPATIBLE, ["Integrated graphics cannot be driven"], grade_cap="C")
        if _contains(gpu, "uhd 630", "uhd graphics 630"):
            return ComponentResult("GPU", name, 5, CompatStatus.PERFECT, ["Supported Intel graphics"])
        if _contains(gpu, "hd 4000", "hd graphics 4000", "hd 5000", "hd 6000", "hd 630", "iris"):
            return ComponentResult("GPU", name, 2, CompatStatus.CONDITIONAL, ["Supported Intel graphics"])
        return ComponentResult("GPU", name, -2, CompatStatus.INCOMPATIBLE, ["Unsupported Intel graphics"], grade_cap="C")
    if vendor == "amd":
        if re.search(r"\brx\s*(5[6-9]\d|6\d{3})\b", name.lower()) and "6950" not in name.lower():
            return ComponentResult("GPU", name, 15, CompatStatus.PERFECT, ["Native AMD graphics support"])
        return ComponentResult("GPU", name, 5, CompatStatus.CONDITIONAL, ["AMD graphics needs compatibility confirmation"])
    return ComponentResult("GPU", name, status=CompatStatus.UNKNOWN, notes=["GPU vendor could not be determined"])


def check_gpus(gpus: Iterable[Any] | None, computer: Any = None, platform_name: str = "Darwin") -> ComponentResult:
    """Evaluate all GPUs as one card and count graphics capabilities once."""
    devices = list(gpus or [])
    if not devices:
        return ComponentResult("GPU", "Not detected", status=CompatStatus.UNKNOWN, notes=["GPU data is unavailable"])
    results = [_gpu_result(gpu, platform_name) for gpu in devices]
    names = ", ".join(result.name for result in results)
    if _is_windows(platform_name):
        status = CompatStatus.UNKNOWN if any(result.status == CompatStatus.UNKNOWN for result in results) else CompatStatus.PERFECT
        return ComponentResult("GPU", names, status=status, details=["Windows graphics support is detected"])

    score = sum(result.score for result in results)
    qe_ci = any(_gpu_capability(gpu, "qe_ci") for gpu in devices)
    metal3 = any(_gpu_capability(gpu, "metal3") for gpu in devices)
    metal4 = any(_gpu_capability(gpu, "metal4") for gpu in devices)
    metal = metal3 or metal4 or any(_gpu_capability(gpu, "metal") for gpu in devices)
    if qe_ci:
        score += 15
    if metal:
        score += 20
    score += 40 if metal4 else 25 if metal3 else 0

    vendors = {_gpu_vendor(gpu) for gpu in devices}
    model = _text(getattr(computer, "reported_model", "") or getattr(computer, "real_model", ""))
    has_intel = any(_gpu_vendor(gpu) == "intel" and result.status != CompatStatus.INCOMPATIBLE for gpu, result in zip(devices, results))
    has_amd = any(_gpu_vendor(gpu) == "amd" and result.status != CompatStatus.INCOMPATIBLE for gpu, result in zip(devices, results))
    if has_intel and has_amd and model.startswith(("iMac", "MacBookPro")):
        score += 5

    caps = [result.grade_cap for result in results if result.grade_cap]
    details = ["Full graphics acceleration" if qe_ci and metal else "Graphics acceleration has limitations"]
    notes = [note for result in results for note in result.notes]
    if metal4:
        details.append("Metal 4 support")
    elif metal3:
        details.append("Metal 3 support")
    elif metal:
        details.append("Metal 2 support")
    if has_intel and has_amd and model.startswith(("iMac", "MacBookPro")):
        details.append("Supported Intel and AMD graphics combination")
    status = CompatStatus.INCOMPATIBLE if any(result.status == CompatStatus.INCOMPATIBLE for result in results) else CompatStatus.PERFECT if metal else CompatStatus.CONDITIONAL
    return ComponentResult("GPU", names, score, status, details, notes, max(caps, key=_GRADE_CAP_ORDER.get) if caps else None)


def check_gpu(gpu: Any, platform_name: str = "Darwin") -> ComponentResult:
    """Backward-compatible single-GPU entry point."""
    result = check_gpus([gpu] if gpu else [], platform_name=platform_name)
    return result


def _is_hackintosh(computer: Any) -> bool:
    """Return whether firmware identifies a non-Apple host."""
    firmware = _text(getattr(computer, "firmware_vendor", "")).lower() if computer else ""
    return bool(firmware and firmware != "apple")


def check_wifi(wifi: Any, platform_name: str = "Darwin", computer: Any = None) -> ComponentResult:
    """Evaluate Wi-Fi compatibility."""
    if not wifi:
        return ComponentResult("Wi-Fi", "Not detected", status=CompatStatus.UNKNOWN, notes=["Wi-Fi card was not detected"])
    name = _name(wifi)
    value = " ".join(_text(getattr(wifi, field, "")) for field in ("name", "model", "chipset", "device_id")).lower()
    if any(token in value for token in ("4364", "4377", "2018", "applebcmwlanbusinterfacepcie")):
        if _is_hackintosh(computer):
            return ComponentResult("Wi-Fi", name, status=CompatStatus.INCOMPATIBLE, details=["Apple-exclusive Wi-Fi is not compatible with Hackintosh"])
        return ComponentResult("Wi-Fi", name, 20, CompatStatus.PERFECT, ["Apple-native Wi-Fi"] if not _is_windows(platform_name) else ["Native Windows Wi-Fi"])
    if any(token in value for token in ("94360", "943602", "94352", "airportbrcm4360")):
        return ComponentResult("Wi-Fi", name, 15, CompatStatus.PERFECT, ["Native Wi-Fi support"])
    if "intel" in value or "0x8086" in value:
        return ComponentResult("Wi-Fi", name, 5, CompatStatus.CONDITIONAL, ["Intel Wi-Fi support"], ["Requires itlwm/AirportItlwm kext for hardware support"])
    if "dw560" in value:
        return ComponentResult("Wi-Fi", name, 5, CompatStatus.CONDITIONAL, ["Dell DW560 support"])
    return ComponentResult("Wi-Fi", name, status=CompatStatus.UNKNOWN, notes=["Wi-Fi chipset needs confirmation"])


def check_board(computer: Any) -> ComponentResult:
    """Evaluate motherboard settings and Apple security chips."""
    if not computer:
        return ComponentResult("Motherboard", "Unknown", status=CompatStatus.UNKNOWN)
    model = _text(getattr(computer, "reported_model", "") or getattr(computer, "real_model", ""))
    value = " ".join((model, _text(getattr(computer, "reported_board_id", "")), _text(getattr(computer, "chipset", "")))).lower()
    score, details, notes = 0, [], []
    if getattr(computer, "cfg_lock", None) is True or getattr(computer, "cfg_lock_locked", None) is True:
        score -= 5
        details.append("CFG Lock must be disabled")
    else:
        details.append("CFG Lock is not reported as enabled")
    security_chips = list(getattr(computer, "security_chip_details", []) or [])
    if getattr(computer, "t2_chip", False):
        score += 15
        details.append("Apple T2 security chip")
    if getattr(computer, "t1_chip", False):
        score += 5
        details.append("Apple T1 security chip")
    for chip in security_chips:
        chip_type = _text(chip.get("type", "Apple security chip"))
        vendor_id = _hardware_id(chip.get("vendor_id"))
        device_id = _hardware_id(chip.get("device_id"))
        source = _text(chip.get("source", ""))
        identity = ":".join(f"{hardware_id:04X}" for hardware_id in (vendor_id, device_id) if hardware_id is not None)
        details.append(" | ".join(value for value in (chip_type, identity, source) if value))
    if any(token in value for token in ("z390", "z490", "z590", "z690", "z790")) and "z370" not in value:
        notes.append("Native NVRAM may be unavailable; apply the PMC patch")
    status = CompatStatus.CONDITIONAL if score < 15 or notes else CompatStatus.PERFECT
    return ComponentResult("Motherboard", model or "Unknown", score, status, details, notes)


def check_storage(storages: Iterable[Any] | None) -> ComponentResult:
    """Evaluate all storage devices as one category."""
    devices = list(storages or [])
    if not devices:
        return ComponentResult("Storage", "Not detected", status=CompatStatus.UNKNOWN, notes=["Storage device was not detected"])
    score, details, notes, cap = 0, [], [], None
    for storage in devices:
        vendor_id = _hardware_id(getattr(storage, "vendor_id", None))
        device_id = _hardware_id(getattr(storage, "device_id", None))
        if vendor_id == 0x106B:
            score += 20
            details.append(f"{_name(storage)}: Apple storage controller")
        elif vendor_id == 0x15B7:
            score += 10
            details.append(f"{_name(storage)}: recommended Western Digital controller")
        elif vendor_id == 0x144D and device_id in _PROBLEMATIC_SAMSUNG_NVME:
            score -= 2
            cap = "B"
            details.append(f"{_name(storage)}: known-problem {_PROBLEMATIC_SAMSUNG_NVME[device_id]} controller")
            notes.append("This NVMe controller limits the overall grade to B")
        else:
            score += 5
            details.append(f"{_name(storage)}: compatible storage controller")
    status = CompatStatus.INCOMPATIBLE if score < 0 else CompatStatus.CONDITIONAL if notes else CompatStatus.PERFECT
    return ComponentResult("Storage", ", ".join(_name(device) for device in devices), score, status, details, notes, cap)


def _needs_system_patches(computer: Any, cpu_result: ComponentResult, gpu_result: ComponentResult) -> bool | None:
    """Determine whether detected hardware needs macOS root patches."""
    if not computer:
        return None
    if cpu_result.status == CompatStatus.UNKNOWN or gpu_result.status == CompatStatus.UNKNOWN:
        return None
    return cpu_result.status == CompatStatus.CONDITIONAL and _cpu_generation(getattr(computer, "cpu", None)) in range(1, 7) or gpu_result.status == CompatStatus.INCOMPATIBLE


def _cached_system_patch_result(constants: Any, computer: Any) -> ComponentResult | None:
    """Build a system patch result from a current Sys Patch cache."""
    getter = getattr(constants, "get_sys_patch_cache", None)
    cache = getter() if callable(getter) else None
    if not cache:
        return None

    properties = cache.get("properties", {})
    patch_names = [
        str(name) for name, enabled in properties.items()
        if enabled is True and not str(name).startswith(("Settings", "Validation"))
    ]
    blocked = bool(properties.get("Validation: Patching not possible", False))
    dirty = bool(properties.get("Validation: Root volume dirty", False))
    patched = bool(_text(getattr(computer, "mbt_sys_version", ""))) if computer else False
    no_new_patches = cache.get("no_new_patches") is True

    if not patch_names:
        return ComponentResult("System Patch", "macOS", 5, CompatStatus.PERFECT, ["No patches required"])
    if blocked:
        reasons = [
            str(name).removeprefix("Validation: ")
            for name, enabled in properties.items()
            if enabled is True and str(name).startswith("Validation: ")
            and str(name) not in {
                "Validation: Patching not possible",
                "Validation: Unpatching not possible",
            }
        ]
        return ComponentResult(
            "System Patch", "macOS", status=CompatStatus.INCOMPATIBLE,
            details=["Root patches required"], notes=reasons or ["Root patching is not possible"],
        )
    if patched and no_new_patches:
        return ComponentResult(
            "System Patch", _text(getattr(computer, "mbt_sys_version", "macOS")), 5,
            CompatStatus.PERFECT, ["All required root patches are installed"],
        )

    details = ["Root patches required", *patch_names]
    notes = ["Root volume must be restored before repatching"] if dirty else []
    if patched:
        notes.append("Installed root patches require an update")
    return ComponentResult("System Patch", "macOS", status=CompatStatus.CONDITIONAL, details=details, notes=notes)


def _system_results(constants: Any, computer: Any, cpu_result: ComponentResult, gpu_result: ComponentResult) -> list[ComponentResult]:
    """Evaluate patch requirements and the current macOS version."""
    patch = _cached_system_patch_result(constants, computer)
    patched = bool(_text(getattr(computer, "mbt_sys_version", ""))) if computer else False
    needs_patches = _needs_system_patches(computer, cpu_result, gpu_result)
    if patch is None:
        if not patched and needs_patches is False:
            patch = ComponentResult("System Patch", "macOS", 5, CompatStatus.PERFECT, ["No patches required"])
        elif needs_patches is None:
            patch = ComponentResult("System Patch", "macOS", status=CompatStatus.UNKNOWN, notes=["Patch requirement needs confirmation"])
        else:
            patch = ComponentResult("System Patch", "macOS", status=CompatStatus.CONDITIONAL, details=["Patches required"])

    kernel = int(getattr(constants, "detected_os", 0) or 0)
    cpu_is_apple = _apple_cpu_score(getattr(computer, "cpu", None)) is not None
    if kernel >= 26 and cpu_is_apple:
        score, status, detail = 10, CompatStatus.PERFECT, "macOS 27 or newer on Apple Silicon"
    elif kernel >= 26:
        score, status, detail = 0, CompatStatus.CONDITIONAL, "macOS 27 or newer needs confirmation on Hackintosh"
    elif kernel >= 25:
        score, status, detail = 5, CompatStatus.PERFECT, "macOS 26 compatibility target"
    elif kernel >= 22:
        score, status, detail = 1, CompatStatus.PERFECT, "macOS 13 or newer"
    else:
        score, status, detail = 0, CompatStatus.CONDITIONAL, "macOS version is older than macOS 13"
    os_result = ComponentResult("macOS", _text(getattr(constants, "detected_os_version", "")) or "Unknown", score, status, [detail])
    return [patch, os_result]


def _grade(score: int, caps: Iterable[str]) -> str:
    """Apply the fixed Hackintosh score thresholds and hardware caps."""
    grade = "S" if score >= _HACKINTOSH_MAX_SCORE - 5 else "A" if score >= _HACKINTOSH_MAX_SCORE - 17 else "B" if score >= 90 else "C" if score >= 40 else "D"
    for cap in caps:
        if _GRADE_CAP_ORDER.get(cap, 4) > _GRADE_CAP_ORDER[grade]:
            grade = cap
    return grade


def check_hardware(computer: Any, constants: Any = None, platform_name: str | None = None) -> CompatibilityReport:
    """Evaluate detected hardware without probing or mutating the system."""
    platform_name = platform_name or host_platform.system()
    cpu_result = check_cpu(getattr(computer, "cpu", None), platform_name)
    gpu_result = check_gpus(getattr(computer, "gpus", []), computer, platform_name)
    components = [cpu_result, gpu_result, check_wifi(getattr(computer, "wifi", None), platform_name, computer), check_board(computer), check_storage(getattr(computer, "storage", []))]
    components.extend(_system_results(constants, computer, cpu_result, gpu_result))
    caps = [result.grade_cap for result in components if result.grade_cap]
    score = max(0, sum(result.score for result in components))
    status = CompatStatus.INCOMPATIBLE if any(result.status == CompatStatus.INCOMPATIBLE for result in components) else CompatStatus.CONDITIONAL if any(result.status in (CompatStatus.CONDITIONAL, CompatStatus.UNKNOWN) for result in components) else CompatStatus.PERFECT
    os_name = _text(getattr(constants, "detected_os_version", "")) if constants else "Unknown"
    return CompatibilityReport(score, _grade(score, caps), status, components, platform_name, os_name, caps)


evaluate = check_hardware

__all__ = [
    "CompatStatus", "ComponentResult", "CompatibilityReport", "NativeMacOSRange",
    "native_cpu_macos_range", "native_gpu_macos_range", "native_wifi_macos_range",
    "check_cpu", "check_gpu", "check_gpus", "check_wifi", "check_board",
    "check_storage", "check_hardware", "evaluate",
]
