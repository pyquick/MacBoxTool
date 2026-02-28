"""
device_probe_win.py: Hardware probing for Windows
"""
import sys
import ctypes
import enum
import re
import hashlib
import winreg
from dataclasses import dataclass, field
from typing import ClassVar, Optional
import wmi

from ..datasets import pci_data, usb_data
from ..support import utilities_win as utilities


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

_RE_PCI = re.compile(r'VEN_([0-9A-F]{4})&DEV_([0-9A-F]{4})', re.I)
_RE_USB = re.compile(r'VID_([0-9A-F]{4})&PID_([0-9A-F]{4})', re.I)
_RE_LOC = re.compile(r'bus\s+(\d+).*device\s+(\d+).*function\s+(\d+)', re.I)

_HKLM = winreg.HKEY_LOCAL_MACHINE
_ENUM_BASE = r"SYSTEM\CurrentControlSet\Enum"


def _reg_enum_keys(parent_key):
    """Yield subkey names under an open registry key."""
    i = 0
    while True:
        try:
            yield winreg.EnumKey(parent_key, i)
            i += 1
        except OSError:
            break


def _scan_pci_registry():
    """Scan PCI devices from registry. Returns list of (vid, did, cc, name, pci_path)."""
    pci_list = []
    try:
        with winreg.OpenKey(_HKLM, _ENUM_BASE + r"\PCI") as pci_root:
            for dev_name in _reg_enum_keys(pci_root):
                m = _RE_PCI.search(dev_name)
                if not m:
                    continue
                vid, did = int(m.group(1), 16), int(m.group(2), 16)
                with winreg.OpenKey(pci_root, dev_name) as dev_key:
                    for inst in _reg_enum_keys(dev_key):
                        cc, pp, name = 0, None, dev_name
                        try:
                            with winreg.OpenKey(dev_key, inst) as ik:
                                try:
                                    guid, _ = winreg.QueryValueEx(ik, "ClassGUID")
                                    cc = _GUID_TO_CLASS.get(guid.lower(), 0)
                                except OSError:
                                    pass
                                try:
                                    loc, _ = winreg.QueryValueEx(ik, "LocationInformation")
                                    lm = _RE_LOC.search(loc)
                                    if lm:
                                        pp = f"PciRoot(0x{int(lm.group(1)):x})/Pci(0x{int(lm.group(2)):x},0x{int(lm.group(3)):x})"
                                except OSError:
                                    pass
                                try:
                                    desc, _ = winreg.QueryValueEx(ik, "DeviceDesc")
                                    name = desc.split(";")[-1] if ";" in desc else desc
                                except OSError:
                                    pass
                        except OSError:
                            continue
                        pci_list.append((vid, did, cc, name, pp))
    except OSError:
        pass
    return pci_list


def _scan_usb_registry():
    """Scan USB devices from registry. Returns list of (vid, pid, name, manufacturer, device_id)."""
    usb_list = []
    try:
        with winreg.OpenKey(_HKLM, _ENUM_BASE + r"\USB") as usb_root:
            for dev_name in _reg_enum_keys(usb_root):
                m = _RE_USB.search(dev_name)
                if not m:
                    continue
                vid, pid = int(m.group(1), 16), int(m.group(2), 16)
                with winreg.OpenKey(usb_root, dev_name) as dev_key:
                    for inst in _reg_enum_keys(dev_key):
                        name, mfg, serial = dev_name, None, None
                        try:
                            with winreg.OpenKey(dev_key, inst) as ik:
                                try:
                                    desc, _ = winreg.QueryValueEx(ik, "DeviceDesc")
                                    name = desc.split(";")[-1] if ";" in desc else desc
                                except OSError:
                                    pass
                                try:
                                    mfg_raw, _ = winreg.QueryValueEx(ik, "Mfg")
                                    mfg = mfg_raw.split(";")[-1] if ";" in mfg_raw else mfg_raw
                                except OSError:
                                    pass
                        except OSError:
                            continue
                        usb_list.append((vid, pid, name, mfg, f"USB\\{dev_name}\\{inst}"))
    except OSError:
        pass
    return usb_list


# ---------------------------------------------------------------------------
# CPU feature detection via cpuinfo
# ---------------------------------------------------------------------------

_PF_FLAGS = {
    "MMX":    3,   "SSE":   6,   "SSE2":  10,  "SSE3":    13,
    "SSSE3": 36,   "SSE4_1": 37, "SSE4_2": 38, "AVX":     39,
    "AVX2":  40,   "AVX512F": 41,
    "CX128": 14,   "RDTSC": 8,
}

# Cache cpuinfo result globally (called once per process)
_cpuinfo_cache: dict | None = None
_cpuflags_cache: list[str] | None = None

# Cached CPU data (reused across all Computer instances)
_cached_cpu_name: str | None = None
_cached_cpu_flags: list[str] | None = None


def _fast_cpu_flags() -> list[str]:
    """
    Get CPU flags via py-cpuinfo (cached).
    First call is slow (~2s), subsequent calls use cached result.
    Returns list of uppercase flag names.
    """
    global _cpuinfo_cache
    try:
        import cpuinfo
        if _cpuinfo_cache is None:
            _cpuinfo_cache = cpuinfo.get_cpu_info()

        flags = _cpuinfo_cache.get("flags", [])
        if not flags:
            raise ValueError("No flags returned")

        # Normalize flags: uppercase, remove dots (AVX1.0 -> AVX)
        normalized = []
        for f in flags:
            f_upper = f.upper().replace(" ", "")
            # SSE4.1/4.2 naming
            if "SSE4.1" in f_upper or "SSE4_1" in f_upper:
                normalized.append("SSE4_1")
            elif "SSE4.2" in f_upper or "SSE4_2" in f_upper:
                normalized.append("SSE4_2")
            # AVX1.0 -> AVX
            elif "AVX1.0" in f_upper:
                normalized.append("AVX")
            # Keep all other flags
            else:
                normalized.append(f_upper)
        return normalized
    except Exception:
        # Fallback to IsProcessorFeaturePresent (instant but limited)
        kernel32 = ctypes.windll.kernel32
        return [name for name, pf_id in _PF_FLAGS.items()
                if kernel32.IsProcessorFeaturePresent(pf_id)]


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
    def from_registry(cls, vid, pid, name, mfg, device_id):
        return cls(vid, pid, 0, 0, name or "", mfg, None)

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


@dataclass
class SysKonnect(EthernetController):
    VENDOR_ID: ClassVar[int] = 0x1148

    class Chipsets(enum.Enum):
        MarvelYukonEthernet = "MarvelYukonEthernet supported"
        Unknown             = "Unknown"

    chipset: Chipsets = field(init=False)

    def detect_chipset(self):
        if self.device_id in pci_data.syskonnect_ids.MarvelYukonEthernet:
            self.chipset = SysKonnect.Chipsets.MarvelYukonEthernet
        else:
            self.chipset = SysKonnect.Chipsets.Unknown


# ---------------------------------------------------------------------------
# Vendor detection helper
# ---------------------------------------------------------------------------

_GPU_VENDORS = [NVIDIA, AMD, Intel]
_ETH_VENDORS = [IntelEthernet, BroadcomEthernet, Aquantia, Marvell, SysKonnect, NVIDIAEthernet]
_WIFI_VENDORS = [Broadcom, IntelWirelessCard, Atheros]


def _detect_gpu(vendor_id, device_id, class_code, name, pci_path):
    # Filter out "Microsoft Basic Display Adapter" - it's a software adapter, not real hardware
    if name and "Microsoft Basic Display Adapter" in name:
        return None
    # Filter out "Microsoft Hyper-V Video" - virtual GPU
    if name and "Hyper-V" in name:
        return None
    # Filter out "Microsoft Remote Display" - virtual GPU
    if name and "Remote Display" in name:
        return None

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
    mbt_version:         Optional[str]  = None
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
    mbt_sys_version:     Optional[str]  = None
    mbt_sys_date:        Optional[str]  = None
    mbt_sys_url:         Optional[str]  = None
    mbt_sys_signed:      bool           = False
    firmware_vendor:      Optional[str]  = None
    rosetta_active:       bool           = False
    _wmi:                 object         = field(default=None, repr=False)
    _pci_cache:           list           = field(default_factory=list, repr=False)
    _usb_raw:             list           = field(default_factory=list, repr=False)

    @staticmethod
    def probe():
        computer = Computer()
        computer._wmi = wmi.WMI()
        computer._pci_cache = _scan_pci_registry()
        computer._usb_raw = _scan_usb_registry()
        computer.gpu_probe()
        computer.dgpu_probe()
        computer.igpu_probe()
        computer.wifi_probe()
        computer.storage_probe()
        computer.usb_controller_probe()
        computer.sdxc_controller_probe()
        computer.ethernet_probe()
        computer.smbios_probe()
        computer.usb_device_probe()
        computer.cpu_probe()
        computer.bluetooth_probe()
        computer.topcase_probe()
        computer.t1_probe()
        computer.ambient_light_sensor_probe()
        computer.pcie_webcam_probe()
        computer.sata_disk_probe()
        computer.mbt_sys_patch_probe()
        return computer

    def _make_pci(self, cls, vid, did, cc, name, pp):
        return cls(vid, did, cc, name=name, pci_path=pp,
                   vendor_id_unspoofed=vid, device_id_unspoofed=did)

    def gpu_probe(self):
        for vid, did, cc, name, pp in self._pci_cache:
            gpu = _detect_gpu(vid, did, cc, name, pp)
            if gpu:
                self.gpus.append(gpu)

    def dgpu_probe(self):
        """
        Select discrete GPU. Priority: NVIDIA > AMD > others.
        Intel is never selected as dGPU.
        """
        for gpu in self.gpus:
            if isinstance(gpu, NVIDIA):
                self.dgpu = gpu
                return
        for gpu in self.gpus:
            if isinstance(gpu, AMD):
                self.dgpu = gpu
                return

    def igpu_probe(self):
        """
        Select integrated GPU. Intel is the primary iGPU vendor.
        """
        for gpu in self.gpus:
            if isinstance(gpu, Intel):
                self.igpu = gpu
                return

    def wifi_probe(self):
        for vid, did, cc, name, pp in self._pci_cache:
            wifi = _detect_wifi(vid, did, cc, name, pp)
            if wifi:
                self.wifi = wifi
                return

    def storage_probe(self):
        for vid, did, cc, name, pp in self._pci_cache:
            if cc in NVMeController.CLASS_CODES:
                self.storage.append(self._make_pci(NVMeController, vid, did, cc, name, pp))
            elif cc in SATAController.CLASS_CODES:
                self.storage.append(self._make_pci(SATAController, vid, did, cc, name, pp))
            elif cc in SASController.CLASS_CODES:
                self.storage.append(self._make_pci(SASController, vid, did, cc, name, pp))

    def usb_controller_probe(self):
        for vid, did, cc, name, pp in self._pci_cache:
            if cc in XHCIController.CLASS_CODES:
                self.usb_controllers.append(self._make_pci(XHCIController, vid, did, cc, name, pp))
            elif cc in EHCIController.CLASS_CODES:
                self.usb_controllers.append(self._make_pci(EHCIController, vid, did, cc, name, pp))
            elif cc in OHCIController.CLASS_CODES:
                self.usb_controllers.append(self._make_pci(OHCIController, vid, did, cc, name, pp))
            elif cc in UHCIController.CLASS_CODES:
                self.usb_controllers.append(self._make_pci(UHCIController, vid, did, cc, name, pp))

    def sdxc_controller_probe(self):
        for vid, did, cc, name, pp in self._pci_cache:
            if cc in SDXCController.CLASS_CODES:
                self.sdxc_controller.append(self._make_pci(SDXCController, vid, did, cc, name, pp))

    def ethernet_probe(self):
        for vid, did, cc, name, pp in self._pci_cache:
            eth = _detect_eth(vid, did, cc, name, pp)
            if eth:
                self.ethernet.append(eth)

    def usb_device_probe(self):
        for vid, pid, name, mfg, did in self._usb_raw:
            usb = USBDevice.from_registry(vid, pid, name, mfg, did)
            usb.detect()
            self.usb_devices.append(usb)

    def cpu_probe(self):
        # Check if CPU already cached globally
        global _cached_cpu_name, _cached_cpu_flags
        if _cached_cpu_name is not None:
            flags = _cached_cpu_flags or _fast_cpu_flags()
            leafs = [f for f in flags if f.startswith("AVX") or f in ("BMI1", "BMI2", "SHA",
                                                                      "POPCNT", "AES", "PCLMULQDQ")]
            self.cpu = CPU(_cached_cpu_name, flags, leafs)
            return

        try:
            proc = self._wmi.Win32_Processor()[0]
            name = proc.Name.strip() if proc.Name else ""
        except Exception:
            name = ""
        flags = _fast_cpu_flags()
        # Cache for future calls
        _cached_cpu_name = name
        # Extract leafs: AVX extensions and BMI1/BMI2/SHA
        leafs = [f for f in flags if f.startswith("AVX") or f in ("BMI1", "BMI2", "SHA",
                                                                  "POPCNT", "AES", "PCLMULQDQ")]
        self.cpu = CPU(name, flags, leafs)

    def smbios_probe(self):
        try:
            board = self._wmi.Win32_BaseBoard()[0]
            self.reported_board_id = board.Product or None
        except Exception:
            pass
        try:
            sys_info = self._wmi.Win32_ComputerSystemProduct()[0]
            self.reported_model = sys_info.Name or None
            uuid_raw = sys_info.UUID or ""
            self.uuid_sha1 = hashlib.sha1(uuid_raw.encode()).hexdigest()
        except Exception:
            pass

        # NVRAM overrides (OpenCore spoofed values)
        self.real_model = utilities.get_nvram("oem-product", "4D1FDA02-38C7-4A6A-9CC6-4BCCA8B30102", decode=True) or self.reported_model
        self.real_board_id = utilities.get_nvram("oem-board", "4D1FDA02-38C7-4A6A-9CC6-4BCCA8B30102", decode=True) or self.reported_board_id
        self.build_model = utilities.get_nvram("OCLP-Model", "4D1FDA02-38C7-4A6A-9CC6-4BCCA8B30102", decode=True)

        # MBT / OpenCore version
        self.mbt_version = utilities.get_nvram("OCLP-Version", "4D1FDA02-38C7-4A6A-9CC6-4BCCA8B30102", decode=True)
        self.opencore_version = utilities.get_nvram("opencore-version", "4D1FDA02-38C7-4A6A-9CC6-4BCCA8B30102", decode=True)
        self.opencore_path = utilities.get_nvram("boot-path", "4D1FDA02-38C7-4A6A-9CC6-4BCCA8B30102", decode=True)

        # SecureBoot Variables
        self.secure_boot_model = utilities.check_secure_boot_model()
        self.secure_boot_policy = utilities.check_ap_security_policy()

        # Firmware Vendor
        firmware_vendor = utilities.get_firmware_vendor(decode=False)
        if isinstance(firmware_vendor, bytes):
            firmware_vendor = str(firmware_vendor.replace(b"\x00", b"").decode("utf-8"))
        self.firmware_vendor = firmware_vendor

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

    def ambient_light_sensor_probe(self):
        pass  # Not available on Windows

    def pcie_webcam_probe(self):
        pass  # Not available on Windows

    def sata_disk_probe(self):
        try:
            for disk in self._wmi.Win32_DiskDrive():
                media = (disk.MediaType or "").lower()
                model = (disk.Model or "").lower()
                if "ssd" in media or "solid" in media:
                    if "apple" not in model:
                        self.third_party_sata_ssd = True
                        return
        except Exception:
            pass

    def mbt_sys_patch_probe(self):
        from pathlib import Path
        import plistlib
        path = Path("/System/Library/CoreServices/MacBoxTool.plist")
        if not path.exists():
            self.mbt_sys_signed = True
            return
        try:
            sys_plist = plistlib.load(path.open("rb"))
        except Exception:
            return
        if sys_plist:
            self.mbt_sys_version = sys_plist.get("MacBoxTool")
            self.mbt_sys_date = sys_plist.get("Time Patched")
            self.mbt_sys_url = sys_plist.get("Commit URL")
            if "Custom Signature" in sys_plist:
                self.mbt_sys_signed = sys_plist["Custom Signature"]
