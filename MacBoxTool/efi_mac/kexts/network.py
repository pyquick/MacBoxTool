"""
network.py: Network (Ethernet/WiFi) related kext management

Logic from efi_builder: networking/wireless.py, networking/wired.py
"""

import logging
from .base import KextManager
from ...datasets import smbios_data, cpu_data,os_data
import sys as _sys
if _sys.platform == "darwin":
    from ...detections import device_probe as _dp
else:
    from ...detections import device_probe_win as _dp

logger = logging.getLogger(__name__)


class NetworkKextManager(KextManager):
    """Manages Network-related kexts."""

    def __init__(self, config: dict, constants, model: str, paths: dict, target_macos: str = ""):
        super().__init__(config, constants, model, paths)
        self.target_macos = target_macos
        # Parse target macOS version as integer (e.g., "14.4 Sonoma" -> 14)
        self._target_macos_major = self._parse_macos_version(target_macos)

    def _parse_macos_version(self, version_str: str) -> int:
        """Parse macOS version string to get major version number."""
        if not version_str:
            # Fallback: default to 13 (Ventura) if no version provided
            # This will be handled gracefully - IO80211 injection only runs for macOS 14+
            return 13
        # Parse "14.4 Sonoma" or "13 Ventura" -> 14 or 13
        try:
            return int(version_str.split()[0].split(".")[0])
        except (IndexError, ValueError):
            return 13  # Default to Ventura

    def apply(self) -> list[str]:
        model_info = smbios_data.smbios_dictionary.get(self.model, {})
        cpu_gen = model_info.get("CPU Generation", 999)

        self._wifi_handling(model_info, cpu_gen)
        self._inject_io80211_kexts()  # Inject IO80211 kexts for macOS 14.0+
        self._ethernet_handling(model_info, cpu_gen)

        return self.log_lines

    def _inject_io80211_kexts(self):
        """Inject IO80211 series kexts for macOS 14.0+.

        - IO80211ElCap for macOS 14.0-14.3
        - IO80211FamilyLegacy for macOS 14.4+
        """
        if self._target_macos_major < 14:
            return

        if 14 <= self._target_macos_major < 15:  # 14.0 - 14.3 (Sonoma 14.0-14.3, Sequoia 15.0)
            self.enable_kext("IO80211ElCap.kext", self.constants.io80211elcap_version)
            self._log("  WiFi: IO80211ElCap injected (macOS 14.0-14.3)")
        elif self._target_macos_major >= 15:  # macOS 15+ (Sequoia+)
            # Check if it's 14.4+ by looking at minor version
            minor_version = 0
            if self.target_macos:
                try:
                    minor_version = int(self.target_macos.split()[0].split(".")[1])
                except (IndexError, ValueError):
                    pass
            if minor_version >= 4:
                self.enable_kext("IO80211FamilyLegacy.kext", self.constants.io80211legacy_version)
                self._log("  WiFi: IO80211FamilyLegacy injected (macOS 14.4+)")
            else:
                self.enable_kext("IO80211ElCap.kext", self.constants.io80211elcap_version)
                self._log("  WiFi: IO80211ElCap injected (macOS 14.0-14.3)")

    def _wifi_handling(self, model_info, cpu_gen):
        """WiFi kext handler: on-model detection first, fallback to prebuilt."""
        # On-model detection
        if not self.constants.custom_model and self.constants.computer and hasattr(self.constants.computer, 'wifi') and self.constants.computer.wifi:
            self._wifi_on_model()
            return

        # Prebuilt fallback
        wireless = model_info.get("Wireless Model")
        if not wireless:
            return

        if wireless == _dp.Broadcom.Chipsets.AirPortBrcm43224:
            self.enable_kext("corecaptureElCap.kext", self.constants.corecaptureelcap_version)
            self.enable_kext("IO80211ElCap.kext", self.constants.io80211elcap_version)
            self._log("  WiFi: AirPortBrcm43224 - IO80211ElCap")
        elif wireless == _dp.Broadcom.Chipsets.AirPortBrcm4331:
            self.enable_kext("corecaptureElCap.kext", self.constants.corecaptureelcap_version)
            self.enable_kext("IO80211ElCap.kext", self.constants.io80211elcap_version)
            self._log("  WiFi: AirPortBrcm4331 - IO80211ElCap")
        elif wireless == _dp.Broadcom.Chipsets.AirPortBrcm4360:
            self.enable_kext("AirportBrcmFixup.kext", self.constants.airportbcrmfixup_version)
            self._log("  WiFi: AirPortBrcm4360 - AirportBrcmFixup")
        elif wireless in (
            _dp.Broadcom.Chipsets.AirportBrcmNIC,
            _dp.Broadcom.Chipsets.AirPortBrcmNICThirdParty,
        ):
            # Block native IOSkywalkFamily (legacy wireless.py:60)
            for entry in self.config.get("Kernel", {}).get("Block", []):
                if entry.get("Identifier") == "com.apple.iokit.IOSkywalkFamily":
                    entry["Enabled"] = True
            self.enable_kext("IOSkywalkFamily.kext", self.constants.ioskywalk_version)
            self.enable_kext("AirportBrcmFixup.kext", self.constants.airportbcrmfixup_version)
            self.enable_kext("IO80211FamilyLegacy.kext", self.constants.io80211legacy_version)
            # Enable AirPortBrcmNIC plugin (inside IO80211FamilyLegacy)
            self.config_mgr.enable_kext(
                "IO80211FamilyLegacy.kext/Contents/PlugIns/AirPortBrcmNIC.kext"
            )
            # Disable BrcmNIC_Injector plugin (legacy wireless.py:153)
            bp = "AirportBrcmFixup.kext/Contents/PlugIns/AirPortBrcmNIC_Injector.kext"
            for entry in self.config.get("Kernel", {}).get("Add", []):
                if entry.get("BundlePath") == bp:
                    entry["Enabled"] = False
            self._log("  WiFi: BrcmNIC - BrcmFixup + IOSkywalk + IO80211Legacy + AirPortBrcmNIC")
        elif hasattr(_dp, 'Atheros') and hasattr(_dp.Atheros, 'Chipsets') and wireless == getattr(_dp.Atheros.Chipsets, 'AirPortAtheros40', None):
            self.enable_kext("corecaptureElCap.kext", self.constants.corecaptureelcap_version)
            self.enable_kext("IO80211ElCap.kext", self.constants.io80211elcap_version)
            self._log("  WiFi: Atheros - IO80211ElCap")

        # Wake on WLAN (legacy wireless.py:73,141)
        if self.constants.enable_wake_on_wlan:
            boot_guid = self.config.setdefault("NVRAM", {}).setdefault("Add", {}).setdefault(
                "7C436110-AB2A-4BBB-A880-FE41995C9F82", {}
            )
            boot_args = boot_guid.get("boot-args", "")
            if "-brcmfxwowl" not in boot_args:
                boot_guid["boot-args"] = (boot_args + " -brcmfxwowl").strip()
                self._log("  WiFi: Wake on WLAN enabled")

    def _wifi_on_model(self):
        """WiFi handler using live hardware detection."""
        wifi = self.constants.computer.wifi
        chipset = wifi.chipset if hasattr(wifi, 'chipset') else None
        country_code = wifi.country_code if hasattr(wifi, 'country_code') else None
        pci_path = wifi.pci_path if hasattr(wifi, 'pci_path') else None

        if chipset in (_dp.Broadcom.Chipsets.AirportBrcmNIC, _dp.Broadcom.Chipsets.AirPortBrcmNICThirdParty):
            for entry in self.config.get("Kernel", {}).get("Block", []):
                if entry.get("Identifier") == "com.apple.iokit.IOSkywalkFamily":
                    entry["Enabled"] = True
            self.enable_kext("IOSkywalkFamily.kext", self.constants.ioskywalk_version)
            self.enable_kext("AirportBrcmFixup.kext", self.constants.airportbcrmfixup_version)
            self.enable_kext("IO80211FamilyLegacy.kext", self.constants.io80211legacy_version)
            self.config_mgr.enable_kext("IO80211FamilyLegacy.kext/Contents/PlugIns/AirPortBrcmNIC.kext")
            bp = "AirportBrcmFixup.kext/Contents/PlugIns/AirPortBrcmNIC_Injector.kext"
            for entry in self.config.get("Kernel", {}).get("Add", []):
                if entry.get("BundlePath") == bp:
                    entry["Enabled"] = False
            self._log("  WiFi: BrcmNIC (on-model) - BrcmFixup + IOSkywalk + IO80211Legacy")
        elif chipset == _dp.Broadcom.Chipsets.AirPortBrcm4360:
            self.enable_kext("AirportBrcmFixup.kext", self.constants.airportbcrmfixup_version)
            self._log("  WiFi: AirPortBrcm4360 (on-model) - AirportBrcmFixup")
        elif chipset == _dp.Broadcom.Chipsets.AirPortBrcm4331:
            self.enable_kext("corecaptureElCap.kext", self.constants.corecaptureelcap_version)
            self.enable_kext("IO80211ElCap.kext", self.constants.io80211elcap_version)
            self._wifi_fake_id(pci_path, country_code)
            self._log("  WiFi: AirPortBrcm4331 (on-model) - IO80211ElCap + FakeID")
        elif chipset == _dp.Broadcom.Chipsets.AirPortBrcm43224:
            self.enable_kext("corecaptureElCap.kext", self.constants.corecaptureelcap_version)
            self.enable_kext("IO80211ElCap.kext", self.constants.io80211elcap_version)
            self._wifi_fake_id(pci_path, country_code)
            self._log("  WiFi: AirPortBrcm43224 (on-model) - IO80211ElCap + FakeID")
        elif hasattr(_dp, 'Atheros') and isinstance(wifi, _dp.Atheros):
            self.enable_kext("corecaptureElCap.kext", self.constants.corecaptureelcap_version)
            self.enable_kext("IO80211ElCap.kext", self.constants.io80211elcap_version)
            self._log("  WiFi: Atheros (on-model) - IO80211ElCap")

        # Apply country code via DeviceProperties for BrcmFixup models
        if country_code and pci_path and chipset in (
            _dp.Broadcom.Chipsets.AirPortBrcm4360,
            _dp.Broadcom.Chipsets.AirportBrcmNIC,
            _dp.Broadcom.Chipsets.AirPortBrcmNICThirdParty,
        ):
            self.config["DeviceProperties"]["Add"].setdefault(pci_path, {})["brcmfx-country"] = country_code
            self._log(f"  WiFi: country code {country_code} at {pci_path}")

    def _wifi_fake_id(self, pci_path=None, country_code=None):
        """WiFi Fake ID for BCM943224/BCM94331 chipsets.

        Spoofs device-id via DeviceProperties and enables AirPortBrcmNIC_Injector.
        """
        model_info = smbios_data.smbios_dictionary.get(self.model, {})

        # Determine PCI path
        if not pci_path:
            if model_info.get("nForce Chipset", False):
                pci_path = "PciRoot(0x0)/Pci(0x15,0x0)/Pci(0x0,0x0)"
            elif self.model in ("iMac7,1", "iMac8,1", "MacPro3,1", "MacBookPro4,1"):
                pci_path = "PciRoot(0x0)/Pci(0x1C,0x4)/Pci(0x0,0x0)"
            elif self.model in ("iMac13,1", "iMac13,2"):
                pci_path = "PciRoot(0x0)/Pci(0x1C,0x3)/Pci(0x0,0x0)"
            elif self.model in ("MacPro4,1", "MacPro5,1"):
                pci_path = "PciRoot(0x0)/Pci(0x1C,0x5)/Pci(0x0,0x0)"
            else:
                pci_path = "PciRoot(0x0)/Pci(0x1C,0x1)/Pci(0x0,0x0)"

        # Inject fake compatible and device-id for BCM94331/BCM943224
        import binascii
        self.config["DeviceProperties"]["Add"].setdefault(pci_path, {}).update({
            "compatible": "pci14e4,4331",
            "device-id": binascii.unhexlify("31430000"),
        })
        if country_code:
            self.config["DeviceProperties"]["Add"][pci_path]["brcmfx-country"] = country_code

        # Enable BrcmNIC_Injector plugin for fake ID
        self.enable_kext("AirportBrcmFixup.kext", self.constants.airportbcrmfixup_version)
        bp = "AirportBrcmFixup.kext/Contents/PlugIns/AirPortBrcmNIC_Injector.kext"
        for entry in self.config.get("Kernel", {}).get("Add", []):
            if entry.get("BundlePath") == bp:
                entry["Enabled"] = True
        self._log(f"  WiFi: Fake ID at {pci_path}")

    # ── Ethernet ──

    def _ethernet_handling(self, model_info, cpu_gen):
        """Ethernet kext handler (two-tier: on-model detection → prebuilt fallback)."""
        if not self.constants.custom_model and self.constants.computer and self.constants.computer.ethernet:
            self._log("  Ethernet: using on-model detection")
            self._on_model_ethernet(cpu_gen)
        else:
            self._log("  Ethernet: using prebuilt assumptions")
            self._prebuilt_ethernet(model_info, cpu_gen)

        # Always enable — hot-plug dongles may be attached at any time
        self._usb_ecm_dongles()
        self._i210_handling(cpu_gen)

    def _on_model_ethernet(self, cpu_gen):
        """Iterate detected Ethernet controllers and enable matching kexts."""
        pre_ivy = cpu_gen < cpu_data.CPUGen.ivy_bridge.value

        for ctrl in self.constants.computer.ethernet:
            if isinstance(ctrl, _dp.BroadcomEthernet):
                self._handle_broadcom_ethernet(ctrl, pre_ivy)
            elif isinstance(ctrl, _dp.IntelEthernet):
                self._handle_intel_ethernet(ctrl, pre_ivy)
            elif isinstance(ctrl, _dp.NVIDIAEthernet):
                self._handle_nvidia_ethernet()
            elif isinstance(ctrl, (_dp.Marvell, _dp.SysKonnect)):
                self._handle_marvell_ethernet()
            elif isinstance(ctrl, _dp.Aquantia):
                self._handle_aquantia_ethernet(ctrl, pre_ivy)

    def _prebuilt_ethernet(self, model_info, cpu_gen):
        """Fall back to smbios_data lookup when no hardware is detected."""
        ethernet = model_info.get("Ethernet Chipset")
        if not ethernet:
            return

        pre_ivy = cpu_gen < cpu_data.CPUGen.ivy_bridge.value

        if ethernet == "Broadcom" and pre_ivy:
            self.enable_kext("CatalinaBCM5701Ethernet.kext", self.constants.bcm570_version)
            self._log("  Ethernet: Broadcom BCM5701 (prebuilt)")
        elif model_info.get("nForce Chipset", False) or ethernet == "Nvidia":
            self.enable_kext("nForceEthernet.kext", self.constants.nforce_version)
            self._log("  Ethernet: nForce (prebuilt)")
        elif ethernet == "Marvell":
            self.enable_kext("MarvelYukonEthernet.kext", self.constants.marvel_version)
            self._log("  Ethernet: Marvell Yukon (prebuilt)")
        elif ethernet == "Intel 80003ES2LAN":
            self.enable_kext("AppleIntel8254XEthernet.kext", self.constants.intel_8254x_version)
            self._log("  Ethernet: Intel 8254X (prebuilt)")
        elif ethernet == "Intel 82574L":
            self.enable_kext("Intel82574L.kext", self.constants.intel_82574l_version)
            self._log("  Ethernet: Intel 82574L (prebuilt)")

    # ── Per-vendor handlers ──

    def _handle_broadcom_ethernet(self, ctrl, pre_ivy: bool):
        """Broadcom BCM5701 — needs Catalina kext on pre-Ivy Bridge (no VT-D)."""
        if ctrl.chipset != _dp.BroadcomEthernet.Chipsets.AppleBCM5701Ethernet:
            return
        if not pre_ivy:
            return
        self.enable_kext("CatalinaBCM5701Ethernet.kext", self.constants.bcm570_version)
        self._log("  Ethernet: Broadcom BCM5701")

    def _handle_intel_ethernet(self, ctrl, pre_ivy: bool):
        """Intel Ethernet — DriverKit requires VT-D, so pre-Ivy uses legacy kexts."""
        if not pre_ivy:
            return
        if ctrl.chipset == _dp.IntelEthernet.Chipsets.AppleIntelI210Ethernet:
            self.enable_kext("CatalinaIntelI210Ethernet.kext", self.constants.i210_version)
            self._log("  Ethernet: Intel i210")
        elif ctrl.chipset == _dp.IntelEthernet.Chipsets.AppleIntel8254XEthernet:
            self.enable_kext("AppleIntel8254XEthernet.kext", self.constants.intel_8254x_version)
            self._log("  Ethernet: Intel 8254X")
        elif ctrl.chipset == _dp.IntelEthernet.Chipsets.Intel82574L:
            self.enable_kext("Intel82574L.kext", self.constants.intel_82574l_version)
            self._log("  Ethernet: Intel 82574L")

    def _handle_nvidia_ethernet(self):
        """NVIDIA nForce — vendor-ID match, all chipsets supported."""
        self.enable_kext("nForceEthernet.kext", self.constants.nforce_version)
        self._log("  Ethernet: nForce")

    def _handle_marvell_ethernet(self):
        """Marvell / SysKonnect Yukon."""
        self.enable_kext("MarvelYukonEthernet.kext", self.constants.marvel_version)
        self._log("  Ethernet: Marvell Yukon")

    def _handle_aquantia_ethernet(self, ctrl, pre_ivy: bool):
        """Aquantia — needs legacy kext on pre-Ivy Bridge."""
        if ctrl.chipset != _dp.Aquantia.Chipsets.AppleEthernetAquantiaAqtion:
            return
        if not pre_ivy:
            return
        self.enable_kext("AppleEthernetAbuantiaAqtion.kext", self.constants.aquantia_version)
        self._log("  Ethernet: Aquantia")

    # ── Global handlers (always run) ──

    def _usb_ecm_dongles(self):
        """ECM-Override for USB Ethernet dongles (pre-Sonoma only).

        Sonoma's WiFi patches downgrade IOSkywalk, breaking DriverKit ECM.
        Force-load the kernel driver to prevent a panic.
        """
        if self.model not in smbios_data.smbios_dictionary:
            return
        if smbios_data.smbios_dictionary[self.model]["Max OS Supported"] >= os_data.os_data.sonoma:
            return
        self.enable_kext("ECM-Override.kext", self.constants.ecm_override_version)
        self._log("  Ethernet: ECM-Override (USB dongle)")

    def _i210_handling(self, cpu_gen):
        """i210 NIC fix — DriverKit regression in macOS 14 (pre-Sonoma models).

        Ivy Bridge+ natively supports DriverKit, so set MinKernel to 23.0.0.
        """
        if self.model not in smbios_data.smbios_dictionary:
            return
        if smbios_data.smbios_dictionary[self.model]["Max OS Supported"] >= os_data.os_data.sonoma:
            return
        self.enable_kext("CatalinaIntelI210Ethernet.kext", self.constants.i210_version)
        if cpu_gen >= cpu_data.CPUGen.ivy_bridge.value:
            for entry in self.config.get("Kernel", {}).get("Add", []):
                if entry.get("BundlePath") == "CatalinaIntelI210Ethernet.kext":
                    entry["MinKernel"] = "23.0.0"
        self._log("  Ethernet: i210 DriverKit fix")
