"""
HardwareInfo Data Model

Unified hardware data model with JSON serialization for compatibility checking,
export/import, and wizard mode.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional
import json


@dataclass
class CpuInfo:
    name: str = ""
    vendor: str = ""  # "intel" / "amd" / "apple"
    vendor_id: str = ""
    device_id: Optional[int] = None
    architecture: str = ""
    generation: str = ""  # "alder_lake", "zen3", etc.
    core_count: int = 0
    thread_count: int = 0
    flags: list[str] = field(default_factory=list)


@dataclass
class GpuInfo:
    name: str = ""
    vendor: str = ""  # "amd" / "nvidia" / "intel"
    family: str = ""  # "navi_23", "kepler", etc.
    device_id: str = ""
    is_igpu: bool = False


@dataclass
class NetworkInfo:
    name: str = ""
    type: str = ""  # "ethernet" / "wifi" / "bluetooth"
    vendor: str = ""
    chipset: str = ""


@dataclass
class StorageInfo:
    name: str = ""
    type: str = ""  # "nvme" / "sata"
    model: str = ""


@dataclass
class MotherboardInfo:
    vendor: str = ""
    model: str = ""
    chipset: str = ""


@dataclass
class MemoryInfo:
    total_gb: int = 0


@dataclass
class HardwareInfo:
    version: str = "1.0"
    exported_at: str = ""
    platform: str = ""
    cpu: CpuInfo = field(default_factory=CpuInfo)
    gpu: list[GpuInfo] = field(default_factory=list)
    network: list[NetworkInfo] = field(default_factory=list)
    storage: list[StorageInfo] = field(default_factory=list)
    motherboard: MotherboardInfo = field(default_factory=MotherboardInfo)
    memory: MemoryInfo = field(default_factory=MemoryInfo)
    acpi_paths: dict = field(default_factory=dict)
    io_paths: dict = field(default_factory=dict)

    @staticmethod
    def from_device_probe(constants) -> "HardwareInfo":
        """
        Create HardwareInfo from constants.computer (device_probe.Computer).
        Extracts CPU, GPU, network, storage, and motherboard info.
        """
        info = HardwareInfo()
        info.platform = constants.computer.build_model if constants.computer else "unknown"
        info.exported_at = datetime.now().isoformat()

        if not constants.computer:
            return info

        computer = constants.computer

        # CPU info
        if computer.cpu:
            info.cpu.name = computer.cpu.name
            info.cpu.flags = computer.cpu.flags.copy()
            info.cpu.vendor_id = getattr(computer.cpu, "vendor_id", None) or ""
            info.cpu.device_id = getattr(computer.cpu, "device_id", None)
            info.cpu.architecture = getattr(computer.cpu, "architecture", None) or ""
            if info.cpu.architecture:
                info.cpu.generation = info.cpu.architecture

            vendor_id_lower = info.cpu.vendor_id.lower()
            cpu_name_lower = computer.cpu.name.lower() if computer.cpu.name else ""
            if "intel" in vendor_id_lower or "intel" in cpu_name_lower or "core" in cpu_name_lower:
                info.cpu.vendor = "intel"
            elif "amd" in vendor_id_lower or "amd" in cpu_name_lower or "ryzen" in cpu_name_lower or "athlon" in cpu_name_lower:
                info.cpu.vendor = "amd"
            elif "apple" in vendor_id_lower or "apple" in cpu_name_lower:
                info.cpu.vendor = "apple"

        # GPU info
        for gpu in computer.gpus:
            gpu_info = GpuInfo()
            gpu_info.name = gpu.name if gpu.name else ""
            gpu_info.device_id = gpu.device_id if gpu.device_id else ""
            gpu_info.is_igpu = gpu == computer.igpu

            # Detect vendor from device class or name
            if hasattr(gpu, 'class_code'):
                class_code = gpu.class_code
                if class_code == 0x030000:
                    gpu_info.vendor = "amd"  # VGA compatible controller
                elif class_code == 0x030200:
                    gpu_info.vendor = "nvidia"  # Display controller
                elif class_code == 0x038000:
                    gpu_info.vendor = "intel"  # Unclassified device

            # Detect vendor from name if not set
            if not gpu_info.vendor and gpu.name:
                name_lower = gpu.name.lower()
                if "nvidia" in name_lower or "geforce" in name_lower or "quadro" in name_lower:
                    gpu_info.vendor = "nvidia"
                elif "intel" in name_lower or "uhd" in name_lower or "iris" in name_lower:
                    gpu_info.vendor = "intel"
                elif "amd" in name_lower or "radeon" in name_lower or " RX " in name_lower:
                    gpu_info.vendor = "amd"

            info.gpu.append(gpu_info)

        # Network info - Ethernet
        for eth in computer.ethernet:
            net_info = NetworkInfo()
            net_info.name = eth.name if eth.name else ""
            net_info.type = "ethernet"
            net_info.chipset = eth.device_id if eth.device_id else ""
            if hasattr(eth, 'vendor_id'):
                # Map vendor ID to vendor name
                net_info.vendor = eth.vendor
            info.network.append(net_info)

        # Network info - WiFi
        if computer.wifi:
            wifi_info = NetworkInfo()
            wifi_info.name = computer.wifi.name if computer.wifi.name else ""
            wifi_info.type = "wifi"
            if hasattr(computer.wifi, 'chipset'):
                wifi_info.chipset = computer.wifi.chipset
            info.network.append(wifi_info)

        # Storage info
        for stor in computer.storage:
            stor_info = StorageInfo()
            stor_info.name = stor.name if stor.name else ""
            stor_info.model = stor.name if stor.name else ""  # Model is often in name
            # Detect type from class code
            if hasattr(stor, 'class_code'):
                # 0x010400 = RAID controller, 0x010600 = SATA, 0x010800 = SCSI
                # NVMe typically has class code 0x010802, AHCI is 0x010601
                if stor.class_code == 0x010802:
                    stor_info.type = "nvme"
                elif stor.class_code in [0x010601, 0x010600]:
                    stor_info.type = "sata"
            info.storage.append(stor_info)

        # Motherboard info
        if computer.reported_model:
            info.motherboard.model = computer.reported_model
        if computer.reported_board_id:
            # board_id format may vary - use full string as vendor identifier
            info.motherboard.vendor = computer.reported_board_id
            # Note: chipset is computed in builder.py, not stored on constants

        return info

    def to_json(self) -> str:
        """Serialize HardwareInfo to JSON string."""
        return json.dumps(asdict(self), indent=2)

    @staticmethod
    def from_json(json_str: str) -> "HardwareInfo":
        """Deserialize HardwareInfo from JSON string."""
        data = json.loads(json_str)

        # Reconstruct nested dataclasses
        cpu = CpuInfo(**data.get("cpu", {}))
        gpu = [GpuInfo(**g) for g in data.get("gpu", [])]
        network = [NetworkInfo(**n) for n in data.get("network", [])]
        storage = [StorageInfo(**s) for s in data.get("storage", [])]
        motherboard = MotherboardInfo(**data.get("motherboard", {}))
        memory = MemoryInfo(**data.get("memory", {}))

        return HardwareInfo(
            version=data.get("version", "1.0"),
            exported_at=data.get("exported_at", ""),
            platform=data.get("platform", ""),
            cpu=cpu,
            gpu=gpu,
            network=network,
            storage=storage,
            motherboard=motherboard,
            memory=memory,
            acpi_paths=data.get("acpi_paths", {}),
            io_paths=data.get("io_paths", {}),
        )

    def validate(self) -> tuple[bool, str]:
        """
        Validate the HardwareInfo has required fields.

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check minimum required fields
        if not self.cpu or not self.cpu.name:
            return False, "CPU name is required"

        if not self.platform:
            return False, "Platform is required"

        # Validate CPU vendor
        if self.cpu.vendor and self.cpu.vendor not in ["intel", "amd", "apple"]:
            return False, f"Invalid CPU vendor: {self.cpu.vendor}"

        # Validate GPU vendors
        for g in self.gpu:
            if g.vendor and g.vendor not in ["amd", "nvidia", "intel"]:
                return False, f"Invalid GPU vendor: {g.vendor}"

        # Validate network types
        for n in self.network:
            if n.type and n.type not in ["ethernet", "wifi", "bluetooth"]:
                return False, f"Invalid network type: {n.type}"

        # Validate storage types
        for s in self.storage:
            if s.type and s.type not in ["nvme", "sata"]:
                return False, f"Invalid storage type: {s.type}"

        return True, ""