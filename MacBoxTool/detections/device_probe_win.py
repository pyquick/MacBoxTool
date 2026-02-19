"""
device_probe_win.py: Hardware probing for Windows
"""
import enum
import re
import hashlib
import winreg
from dataclasses import dataclass, field
from typing import ClassVar, Optional
import wmi

from ..datasets import pci_data, usb_data


# ---------------------------------------------------------------------------
# Registry / WMI helpers
# ---------------------------------------------------------------------------

_GUID_TO_CLASS = {
    "{4d36e968-e325-11ce-bfc1-08002be10318}": 0x030000,  # Display
    "{4d36e97b-e325-11ce-bfc1-08002be10318}": 0x0c0330,  # USB XHCI
    "{36fc9e60-c465-11cf-8056-444553540000}": 0x0c0320,  # USB EHCI
    "{4d36e96a-e325-11ce-bfc1-08002be10318}": 0x010601,  # SATA
    "{4d36e972-e325-11ce-bfc1-08002be10318}": 0x020000,  # Ethernet
    "{4d36e975-e325-11ce-bfc1-08002be10318}": 0x028000,  # Net/WiFi
    "{4d36e967-e325-11ce-bfc1-08002be10318}": 0x010802,  # NVMe/Disk
}


def _reg_open(did: str):
    return winreg.OpenKey(
        winreg.HKEY_LOCAL_MACHINE,
        r"SYSTEM\CurrentControlSet\Enum\\" + did.replace("/", "\\")
    )


def _get_class_code(did: str) -> int:
    try:
        with _reg_open(did) as k:
            guid, _ = winreg.QueryValueEx(k, "ClassGUID")
            return _GUID_TO_CLASS.get(guid.lower(), 0)
    except Exception:
        return 0


def _pci_path(did: str) -> Optional[str]:
    try:
        with _reg_open(did) as k:
            loc, _ = winreg.QueryValueEx(k, "LocationInformation")
        m = re.search(r'bus\s+(\d+).*device\s+(\d+).*function\s+(\d+)', loc, re.I)
        if m:
            bus, dev, fn = int(m.group(1)), int(m.group(2)), int(m.group(3))
            return f"PciRoot(0x{bus:x})/Pci(0x{dev:x},0x{fn:x})"
    except Exception:
        pass
    return None


def _iter_pci(c):
    """Yield (vendor_id, device_id, class_code, name, pci_path) for all PCI devices."""
    for dev in c.Win32_PnPEntity():
        did = dev.DeviceID or ""
        if "PCI\\" not in did.upper():
            continue
        m = re.search(r'VEN_([0-9A-F]{4})&DEV_([0-9A-F]{4})', did, re.I)
        if not m:
            continue
        yield (int(m.group(1), 16), int(m.group(2), 16),
               _get_class_code(did), dev.Name or did, _pci_path(did))


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class CPU:
    name: str
    flags: list[str]
    leafs: list[str]


@dataclass
class USBDevice:
    vendor_id:     int
    device_id:     int
    device_class:  int
    device_speed:  int
    product_name:  str
    vendor_name:   Optional[str] = None
    serial_number: Optional[str] = None

    @classmethod
    def from_wmi(cls, dev):
        did = dev.DeviceID or ""
        m = re.search(r'VID_([0-9A-F]{4})&PID_([0-9A-F]{4})', did, re.I)
        vendor_id = int(m.group(1), 16) if m else 0
        device_id = int(m.group(2), 16) if m else 0
        device_class, serial_number = 0, None
        try:
            results = wmi.WMI().Win32_USBDevice(DeviceID=did.replace('\\', '\\\\'))
            if results:
                u = results[0]
                if getattr(u, 'ClassCode', None) is not None:
                    device_class = int(u.ClassCode)
                serial_number = getattr(u, 'SerialNumber', None) or None
        except Exception:
            pass
        return cls(vendor_id, device_id, device_class, 0,
                   dev.Name or "", dev.Manufacturer or None, serial_number)

    def detect(self):
        self.detect_class()
        self.detect_speed()

    def detect_class(self):
        for c in self.ClassCode:
            if self.device_class == c.value:
                self.device_class = c

    def detect_speed(self):
        for s in self.Speed:
            if self.device_speed == s.value:
                self.device_speed = s

    class Speed(enum.Enum):
        LOW_SPEED        = 0x01
        FULL_SPEED       = 0x02
        HIGH_SPEED       = 0x03
        SUPER_SPEED      = 0x04
        SUPER_SPEED_PLUS = 0x05

    class ClassCode(enum.Enum):
        GENERIC           = 0x00
        AUDIO             = 0x01
        CDC_CONTROL       = 0x02
        HID               = 0x03
        PHYSICAL          = 0x05
        IMAGE             = 0x06
        PRINTER           = 0x07
        MASS_STORAGE      = 0x08
        HUB               = 0x09
        CDC_DATA          = 0x0A
        SMART_CARD        = 0x0B
        CONTENT_SEC       = 0x0D
        VIDEO             = 0x0E
        PERSONAL_HEALTH   = 0x0F
        AUDIO_VIDEO       = 0x10
        BILLBOARD         = 0x11
        USB_TYPE_C_BRIDGE = 0x12
        DISPLAY_BDP       = 0x13
        I3C               = 0x3C
        DIAGNOSTIC        = 0xDC
        WIRELESS          = 0xE0
        MISCELLANEOUS     = 0xEF
        APPLICATION       = 0xFE
        VENDOR_SPEC       = 0xFF


@dataclass
class PCIDevice:
    VENDOR_ID:   ClassVar[int]
    CLASS_CODES: ClassVar[list[int]]

    vendor_id:           int
    device_id:           int
    class_code:          int
    name:                Optional[str]  = None
    model:               Optional[str]  = None
    acpi_path:           Optional[str]  = None
    pci_path:            Optional[str]  = None
    disable_metal:       bool           = False
    force_compatible:    bool           = False
    vendor_id_unspoofed: int            = -1
    device_id_unspoofed: int            = -1

    @classmethod
    def detect(cls, device: "PCIDevice") -> bool:
        return (device.vendor_id == cls.VENDOR_ID and
                device.class_code in getattr(cls, 'CLASS_CODES', []))


@dataclass
class GPU(PCIDevice):
    CLASS_CODES: ClassVar[list[int]] = [0x030000, 0x038000]
    arch: enum.Enum = field(init=False)

    def __post_init__(self):
        self.detect_arch()

    def detect_arch(self):
        raise NotImplementedError


@dataclass
class WirelessCard(PCIDevice):
    CLASS_CODES: ClassVar[list[int]] = [0x028000]
    country_code: Optional[str] = field(init=False, default=None)
    chipset: enum.Enum = field(init=False)

    def __post_init__(self):
        self.detect_chipset()

    def detect_chipset(self):
        raise NotImplementedError


@dataclass
class EthernetController(PCIDevice):
    CLASS_CODES: ClassVar[list[int]] = [0x020000]
    chipset: enum.Enum = field(init=False)

    def __post_init__(self):
        self.detect_chipset()

    def detect_chipset(self):
        raise NotImplementedError


@dataclass
class NVMeController(PCIDevice):
    CLASS_CODES: ClassVar[list[int]] = [0x010802, 0x018002]
    aspm: Optional[int] = None

@dataclass
class SATAController(PCIDevice):
    CLASS_CODES: ClassVar[list[int]] = [0x010601]

@dataclass
class SASController(PCIDevice):
    CLASS_CODES: ClassVar[list[int]] = [0x010400]

@dataclass
class XHCIController(PCIDevice):
    CLASS_CODES: ClassVar[list[int]] = [0x0c0330]

@dataclass
class EHCIController(PCIDevice):
    CLASS_CODES: ClassVar[list[int]] = [0x0c0320]

@dataclass
class OHCIController(PCIDevice):
    CLASS_CODES: ClassVar[list[int]] = [0x0c0310]

@dataclass
class UHCIController(PCIDevice):
    CLASS_CODES: ClassVar[list[int]] = [0x0c0300]

@dataclass
class SDXCController(PCIDevice):
    CLASS_CODES: ClassVar[list[int]] = [0x080501]


# ---------------------------------------------------------------------------
# GPU vendor subclasses
# ---------------------------------------------------------------------------

@dataclass
class NVIDIA(GPU):
    VENDOR_ID: ClassVar[int] = 0x10DE

    class Archs(enum.Enum):
        Curie   = "Curie"
        Tesla   = "Tesla"
        Fermi   = "Fermi"
        Kepler  = "Kepler"
        Maxwell = "Maxwell"
        Pascal  = "Pascal"
        Unknown = "Unknown"

    arch: Archs = field(init=False)

    def detect_arch(self):
        if   self.device_id in pci_data.nvidia_ids.curie_ids:   self.arch = NVIDIA.Archs.Curie
        elif self.device_id in pci_data.nvidia_ids.tesla_ids:   self.arch = NVIDIA.Archs.Tesla
        elif self.device_id in pci_data.nvidia_ids.fermi_ids:   self.arch = NVIDIA.Archs.Fermi
        elif self.device_id in pci_data.nvidia_ids.kepler_ids:  self.arch = NVIDIA.Archs.Kepler
        elif self.device_id in pci_data.nvidia_ids.maxwell_ids: self.arch = NVIDIA.Archs.Maxwell
        elif self.device_id in pci_data.nvidia_ids.pascal_ids:  self.arch = NVIDIA.Archs.Pascal
        else:                                                    self.arch = NVIDIA.Archs.Unknown


@dataclass
class AMD(GPU):
    VENDOR_ID: ClassVar[int] = 0x1002

    class Archs(enum.Enum):
        R500            = "R500"
        TeraScale_1     = "TeraScale 1"
        TeraScale_2     = "TeraScale 2"
        Legacy_GCN_7000 = "Legacy GCN v1"
        Legacy_GCN_8000 = "Legacy GCN v2"
        Legacy_GCN_9000 = "Legacy GCN v3"
        Polaris         = "Polaris"
        Polaris_Spoof   = "Polaris (Spoofed)"
        Vega            = "Vega"
        Navi            = "Navi"
        Unknown         = "Unknown"

    arch: Archs = field(init=False)

    def detect_arch(self):
        if   self.device_id in pci_data.amd_ids.r500_ids:        self.arch = AMD.Archs.R500
        elif self.device_id in pci_data.amd_ids.gcn_7000_ids:    self.arch = AMD.Archs.Legacy_GCN_7000
        elif self.device_id in pci_data.amd_ids.gcn_8000_ids:    self.arch = AMD.Archs.Legacy_GCN_8000
        elif self.device_id in pci_data.amd_ids.gcn_9000_ids:    self.arch = AMD.Archs.Legacy_GCN_9000
        elif self.device_id in pci_data.amd_ids.terascale_1_ids: self.arch = AMD.Archs.TeraScale_1
        elif self.device_id in pci_data.amd_ids.terascale_2_ids: self.arch = AMD.Archs.TeraScale_2
        elif self.device_id in pci_data.amd_ids.polaris_ids:     self.arch = AMD.Archs.Polaris
        elif self.device_id in pci_data.amd_ids.polaris_spoof_ids: self.arch = AMD.Archs.Polaris_Spoof
        elif self.device_id in pci_data.amd_ids.vega_ids:        self.arch = AMD.Archs.Vega
        elif self.device_id in pci_data.amd_ids.navi_ids:        self.arch = AMD.Archs.Navi
        else:                                                     self.arch = AMD.Archs.Unknown


@dataclass
class Intel(GPU):
    VENDOR_ID: ClassVar[int] = 0x8086

    class Archs(enum.Enum):
        GMA_950     = "GMA 950"
        GMA_X3100   = "GMA X3100"
        Iron_Lake   = "Iron Lake"
        Sandy_Bridge = "Sandy Bridge"
        Ivy_Bridge  = "Ivy Bridge"
        Haswell     = "Haswell"
        Broadwell   = "Broadwell"
        Skylake     = "Skylake"
        Kaby_Lake   = "Kaby Lake"
        Coffee_Lake = "Coffee Lake"
        Comet_Lake  = "Comet Lake"
        Ice_Lake    = "Ice Lake"
        Unknown     = "Unknown"

    arch: Archs = field(init=False)

    def detect_arch(self):
        if   self.device_id in pci_data.intel_ids.gma_950_ids:    self.arch = Intel.Archs.GMA_950
        elif self.device_id in pci_data.intel_ids.gma_x3100_ids:  self.arch = Intel.Archs.GMA_X3100
        elif self.device_id in pci_data.intel_ids.iron_ids:       self.arch = Intel.Archs.Iron_Lake
        elif self.device_id in pci_data.intel_ids.sandy_ids:      self.arch = Intel.Archs.Sandy_Bridge
        elif self.device_id in pci_data.intel_ids.ivy_ids:        self.arch = Intel.Archs.Ivy_Bridge
        elif self.device_id in pci_data.intel_ids.haswell_ids:    self.arch = Intel.Archs.Haswell
        elif self.device_id in pci_data.intel_ids.broadwell_ids:  self.arch = Intel.Archs.Broadwell
        elif self.device_id in pci_data.intel_ids.skylake_ids:    self.arch = Intel.Archs.Skylake
        elif self.device_id in pci_data.intel_ids.kaby_lake_ids:  self.arch = Intel.Archs.Kaby_Lake
        elif self.device_id in pci_data.intel_ids.coffee_lake_ids: self.arch = Intel.Archs.Coffee_Lake
        elif self.device_id in pci_data.intel_ids.comet_lake_ids: self.arch = Intel.Archs.Comet_Lake
        elif self.device_id in pci_data.intel_ids.ice_lake_ids:   self.arch = Intel.Archs.Ice_Lake
        else:                                                      self.arch = Intel.Archs.Unknown


@dataclass
class IntelEthernet(EthernetController):
    VENDOR_ID: ClassVar[int] = 0x8086

    class Chipsets(enum.Enum):
        AppleIntel8254XEthernet = "AppleIntel8254XEthernet Supported"
        AppleIntelI210Ethernet  = "AppleIntelI210Ethernet Supported"
        Intel82574L             = "Intel82574L Supported"
        Unknown                 = "Unknown"

    chipset: Chipsets = field(init=False)

    def detect_chipset(self):
        if   self.device_id in pci_data.intel_ids.AppleIntel8254XEthernet: self.chipset = IntelEthernet.Chipsets.AppleIntel8254XEthernet
        elif self.device_id in pci_data.intel_ids.AppleIntelI210Ethernet:  self.chipset = IntelEthernet.Chipsets.AppleIntelI210Ethernet
        elif self.device_id in pci_data.intel_ids.Intel82574L:             self.chipset = IntelEthernet.Chipsets.Intel82574L
        else:                                                               self.chipset = IntelEthernet.Chipsets.Unknown


@dataclass
class Broadcom(WirelessCard):
    VENDOR_ID: ClassVar[int] = 0x14E4

    class Chipsets(enum.Enum):
        AppleBCMWLANBusInterfacePCIe = "AppleBCMWLANBusInterfacePCIe supported"
        AirportBrcmNIC               = "AirportBrcmNIC supported"
        AirPortBrcmNICThirdParty     = "AirPortBrcmNICThirdParty supported"
        AirPortBrcm4360              = "AirPortBrcm4360 supported"
        AirPortBrcm4331              = "AirPortBrcm4331 supported"
        AirPortBrcm43224             = "AppleAirPortBrcm43224 supported"
        Unknown                      = "Unknown"

    chipset: Chipsets = field(init=False)

    def detect_chipset(self):
        if   self.device_id in pci_data.broadcom_ids.AppleBCMWLANBusInterfacePCIe: self.chipset = Broadcom.Chipsets.AppleBCMWLANBusInterfacePCIe
        elif self.device_id in pci_data.broadcom_ids.AirPortBrcmNIC:               self.chipset = Broadcom.Chipsets.AirportBrcmNIC
        elif self.device_id in pci_data.broadcom_ids.AirPortBrcmNICThirdParty:     self.chipset = Broadcom.Chipsets.AirPortBrcmNICThirdParty
        elif self.device_id in pci_data.broadcom_ids.AirPortBrcm4360:              self.chipset = Broadcom.Chipsets.AirPortBrcm4360
        elif self.device_id in pci_data.broadcom_ids.AirPortBrcm4331:              self.chipset = Broadcom.Chipsets.AirPortBrcm4331
        elif self.device_id in pci_data.broadcom_ids.AppleAirPortBrcm43224:        self.chipset = Broadcom.Chipsets.AirPortBrcm43224
        else:                                                                       self.chipset = Broadcom.Chipsets.Unknown


@dataclass
class IntelWirelessCard(WirelessCard):
    VENDOR_ID: ClassVar[int] = 0x8086

    class Chipsets(enum.Enum):
        IntelWirelessIDs = "Intel Wireless supported"
        Unknown          = "Unknown"

    chipset: Chipsets = field(init=False)

    def detect_chipset(self):
        if self.device_id in pci_data.intelwl_ids.IntelWirelessIDs:
            self.chipset = IntelWirelessCard.Chipsets.IntelWirelessIDs
        else:
            self.chipset = IntelWirelessCard.Chipsets.Unknown


@dataclass
class BroadcomEthernet(EthernetController):
    VENDOR_ID: ClassVar[int] = 0x14E4

    class Chipsets(enum.Enum):
        AppleBCM5701Ethernet = "AppleBCM5701Ethernet supported"
        Unknown              = "Unknown"

    chipset: Chipsets = field(init=False)

    def detect_chipset(self):
        if self.device_id in pci_data.broadcom_ids.AppleBCM5701Ethernet:
            self.chipset = BroadcomEthernet.Chipsets.AppleBCM5701Ethernet
        else:
            self.chipset = BroadcomEthernet.Chipsets.Unknown


@dataclass
class Atheros(WirelessCard):
    VENDOR_ID: ClassVar[int] = 0x168C

    class Chipsets(enum.Enum):
        AirPortAtheros40 = "AirPortAtheros40 supported"
        Unknown          = "Unknown"

    chipset: Chipsets = field(init=False)

    def detect_chipset(self):
        if self.device_id in pci_data.atheros_ids.AtherosWifi:
            self.chipset = Atheros.Chipsets.AirPortAtheros40
        else:
            self.chipset = Atheros.Chipsets.Unknown


@dataclass
class Aquantia(EthernetController):
    VENDOR_ID: ClassVar[int] = 0x1D6A

    class Chipsets(enum.Enum):
        AppleEthernetAquantiaAqtion = "AppleEthernetAquantiaAqtion supported"
        Unknown                     = "Unknown"

    chipset: Chipsets = field(init=False)

    def detect_chipset(self):
        if self.device_id in pci_data.aquantia_ids.AppleEthernetAquantiaAqtion:
            self.chipset = Aquantia.Chipsets.AppleEthernetAquantiaAqtion
        else:
            self.chipset = Aquantia.Chipsets.Unknown


@dataclass
class Marvell(EthernetController):
    VENDOR_ID: ClassVar[int] = 0x11AB

    class Chipsets(enum.Enum):
        MarvelYukonEthernet = "MarvelYukonEthernet supported"
        Unknown             = "Unknown"

    chipset: Chipsets = field(init=False)

    def detect_chipset(self):
        if self.device_id in pci_data.marvell_ids.MarvelYukonEthernet:
            self.chipset = Marvell.Chipsets.MarvelYukonEthernet
        else:
            self.chipset = Marvell.Chipsets.Unknown


@dataclass
class NVIDIAEthernet(EthernetController):
    VENDOR_ID: ClassVar[int] = 0x10DE

    class Chipsets(enum.Enum):
        nForceEthernet = "nForceEthernet"

    chipset: Chipsets = field(init=False)

    def detect_chipset(self):
        self.chipset = NVIDIAEthernet.Chipsets.nForceEthernet


# ---------------------------------------------------------------------------
# Vendor detection helper
# ---------------------------------------------------------------------------

_GPU_VENDORS = [NVIDIA, AMD, Intel]
_ETH_VENDORS = [IntelEthernet, BroadcomEthernet, Aquantia, Marvell, NVIDIAEthernet]
_WIFI_VENDORS = [Broadcom, IntelWirelessCard, Atheros]


def _detect_gpu(vendor_id, device_id, class_code, name, pci_path):
    for cls in _GPU_VENDORS:
        if vendor_id == cls.VENDOR_ID and class_code in GPU.CLASS_CODES:
            return cls(vendor_id, device_id, class_code, name=name, pci_path=pci_path,
                       vendor_id_unspoofed=vendor_id, device_id_unspoofed=device_id)
    return None


def _detect_eth(vendor_id, device_id, class_code, name, pci_path):
    for cls in _ETH_VENDORS:
        if vendor_id == cls.VENDOR_ID and class_code in EthernetController.CLASS_CODES:
            return cls(vendor_id, device_id, class_code, name=name, pci_path=pci_path,
                       vendor_id_unspoofed=vendor_id, device_id_unspoofed=device_id)
    return None


def _detect_wifi(vendor_id, device_id, class_code, name, pci_path):
    for cls in _WIFI_VENDORS:
        if vendor_id == cls.VENDOR_ID and class_code in WirelessCard.CLASS_CODES:
            return cls(vendor_id, device_id, class_code, name=name, pci_path=pci_path,
                       vendor_id_unspoofed=vendor_id, device_id_unspoofed=device_id)
    return None


# ---------------------------------------------------------------------------
# Computer
# ---------------------------------------------------------------------------

@dataclass
class Computer:
    real_model:           Optional[str]  = None
    real_board_id:        Optional[str]  = None
    reported_model:       Optional[str]  = None
    reported_board_id:    Optional[str]  = None
    build_model:          Optional[str]  = None
    uuid_sha1:            Optional[str]  = None
    gpus:                 list           = field(default_factory=list)
    igpu:                 Optional[GPU]  = None
    dgpu:                 Optional[GPU]  = None
    storage:              list           = field(default_factory=list)
    usb_controllers:      list           = field(default_factory=list)
    sdxc_controller:      list           = field(default_factory=list)
    ethernet:             list           = field(default_factory=list)
    wifi:                 Optional[WirelessCard] = None
    cpu:                  Optional[CPU]  = None
    usb_devices:          list           = field(default_factory=list)
    oclp_version:         Optional[str]  = None
    opencore_version:     Optional[str]  = None
    opencore_path:        Optional[str]  = None
    bluetooth_chipset:    Optional[str]  = None
    internal_keyboard_type: Optional[str] = None
    trackpad_type:        Optional[str]  = None
    ambient_light_sensor: bool           = False
    third_party_sata_ssd: bool           = False
    pcie_webcam:          bool           = False
    t1_chip:              bool           = False
    secure_boot_model:    Optional[str]  = None
    secure_boot_policy:   Optional[int]  = None
    oclp_sys_version:     Optional[str]  = None
    oclp_sys_date:        Optional[str]  = None
    oclp_sys_url:         Optional[str]  = None
    oclp_sys_signed:      bool           = False
    firmware_vendor:      Optional[str]  = None
    rosetta_active:       bool           = False

    @staticmethod
    def probe():
        computer = Computer()
        c = wmi.WMI()
        computer.cpu_probe(c)
        computer.pci_probe(c)
        computer.usb_probe(c)
        computer.smbios_probe(c)
        computer.bluetooth_probe()
        computer.topcase_probe()
        computer.t1_probe()
        computer.sata_disk_probe(c)
        return computer

    def pci_probe(self, c):
        for vendor_id, device_id, class_code, name, pci_path in _iter_pci(c):
            gpu = _detect_gpu(vendor_id, device_id, class_code, name, pci_path)
            if gpu:
                self.gpus.append(gpu)
                continue
            eth = _detect_eth(vendor_id, device_id, class_code, name, pci_path)
            if eth:
                self.ethernet.append(eth)
                continue
            if self.wifi is None:
                wifi = _detect_wifi(vendor_id, device_id, class_code, name, pci_path)
                if wifi:
                    self.wifi = wifi
                    continue
            if class_code in NVMeController.CLASS_CODES:
                self.storage.append(NVMeController(vendor_id, device_id, class_code, name=name, pci_path=pci_path,
                                                   vendor_id_unspoofed=vendor_id, device_id_unspoofed=device_id))
            elif class_code in SATAController.CLASS_CODES:
                self.storage.append(SATAController(vendor_id, device_id, class_code, name=name, pci_path=pci_path,
                                                   vendor_id_unspoofed=vendor_id, device_id_unspoofed=device_id))
            elif class_code in SASController.CLASS_CODES:
                self.storage.append(SASController(vendor_id, device_id, class_code, name=name, pci_path=pci_path,
                                                  vendor_id_unspoofed=vendor_id, device_id_unspoofed=device_id))
            elif class_code in XHCIController.CLASS_CODES:
                self.usb_controllers.append(XHCIController(vendor_id, device_id, class_code, name=name, pci_path=pci_path,
                                                           vendor_id_unspoofed=vendor_id, device_id_unspoofed=device_id))
            elif class_code in EHCIController.CLASS_CODES:
                self.usb_controllers.append(EHCIController(vendor_id, device_id, class_code, name=name, pci_path=pci_path,
                                                           vendor_id_unspoofed=vendor_id, device_id_unspoofed=device_id))
            elif class_code in OHCIController.CLASS_CODES:
                self.usb_controllers.append(OHCIController(vendor_id, device_id, class_code, name=name, pci_path=pci_path,
                                                           vendor_id_unspoofed=vendor_id, device_id_unspoofed=device_id))
            elif class_code in UHCIController.CLASS_CODES:
                self.usb_controllers.append(UHCIController(vendor_id, device_id, class_code, name=name, pci_path=pci_path,
                                                           vendor_id_unspoofed=vendor_id, device_id_unspoofed=device_id))
            elif class_code in SDXCController.CLASS_CODES:
                self.sdxc_controller.append(SDXCController(vendor_id, device_id, class_code, name=name, pci_path=pci_path,
                                                           vendor_id_unspoofed=vendor_id, device_id_unspoofed=device_id))
        # dgpu = first non-Intel GPU, igpu = Intel GPU
        for gpu in self.gpus:
            if isinstance(gpu, Intel) and self.igpu is None:
                self.igpu = gpu
            elif not isinstance(gpu, Intel) and self.dgpu is None:
                self.dgpu = gpu

    def usb_probe(self, c):
        for dev in c.Win32_PnPEntity():
            did = dev.DeviceID or ""
            if "USB\\" not in did.upper() or "VID_" not in did.upper():
                continue
            usb = USBDevice.from_wmi(dev)
            usb.detect()
            self.usb_devices.append(usb)

    def cpu_probe(self, c):
        try:
            proc = c.Win32_Processor()[0]
            name = proc.Name.strip() if proc.Name else ""
        except Exception:
            name = ""
        flags = self._cpu_flags()
        leafs = self._cpu_leafs()
        self.cpu = CPU(name, flags, leafs)

    def _cpu_flags(self) -> list[str]:
        try:
            import cpuinfo
            return cpuinfo.get_cpu_info().get("flags", [])
        except Exception:
            return []

    def _cpu_leafs(self) -> list[str]:
        try:
            import cpuinfo
            flags = cpuinfo.get_cpu_info().get("flags", [])
            return [f for f in flags if f.startswith("avx") or f in ("bmi1", "bmi2", "sha")]
        except Exception:
            return []

    def smbios_probe(self, c):
        try:
            board = c.Win32_BaseBoard()[0]
            self.real_board_id  = board.Product or None
            self.reported_board_id = self.real_board_id
        except Exception:
            pass
        try:
            sys_info = c.Win32_ComputerSystemProduct()[0]
            self.real_model     = sys_info.Name or None
            self.reported_model = self.real_model
            uuid_raw = sys_info.UUID or ""
            self.uuid_sha1 = hashlib.sha1(uuid_raw.encode()).hexdigest()
        except Exception:
            pass
        try:
            bios = c.Win32_BIOS()[0]
            self.firmware_vendor = bios.Manufacturer or None
        except Exception:
            pass

    def bluetooth_probe(self):
        if not self.usb_devices:
            return
        for dev in self.usb_devices:
            name = dev.product_name or ""
            if "BRCM20702" in name:
                self.bluetooth_chipset = "BRCM20702 Hub"; return
            if "BCM20702A0" in name or "BCM2045A0" in name:
                self.bluetooth_chipset = "3rd Party Bluetooth 4.0 Hub"; return
            if "BRCM2070 Hub" in name:
                self.bluetooth_chipset = "BRCM2070 Hub"; return
            if "BRCM2046 Hub" in name:
                self.bluetooth_chipset = "BRCM2046 Hub"; return
            if "Bluetooth" in name:
                self.bluetooth_chipset = "Generic"; return

    def topcase_probe(self):
        for dev in self.usb_devices:
            if dev.vendor_id != 0x5ac:
                continue
            if dev.device_id in usb_data.AppleIDs.Legacy_AppleUSBTCKeyboard:
                self.internal_keyboard_type = "Legacy"
            elif dev.device_id in usb_data.AppleIDs.Modern_AppleUSBTCKeyboard:
                self.internal_keyboard_type = "Modern"
            if dev.device_id in usb_data.AppleIDs.AppleUSBTrackpad:
                self.trackpad_type = "Legacy"
            elif dev.device_id in usb_data.AppleIDs.AppleUSBMultiTouch:
                self.trackpad_type = "Modern"

    def t1_probe(self):
        for dev in self.usb_devices:
            if dev.vendor_id != 0x5ac:
                continue
            if dev.device_id == 0x8600:
                self.t1_chip = True; return
            if dev.device_id == 0x1281 and dev.serial_number:
                parts = dev.serial_number.split(" ")
                if "CPID:8002" in parts and ("BDID:12" in parts or "BDID:13" in parts):
                    self.t1_chip = True; return

    def sata_disk_probe(self, c):
        try:
            for disk in c.Win32_DiskDrive():
                media = (disk.MediaType or "").lower()
                model = (disk.Model or "").lower()
                if "ssd" in media or "solid" in media:
                    if "apple" not in model:
                        self.third_party_sata_ssd = True
                        return
        except Exception:
            pass
