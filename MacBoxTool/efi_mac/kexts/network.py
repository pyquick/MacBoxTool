"""
network.py: Network (Ethernet/WiFi) related kext management

Logic from efi_builder: networking/wireless.py, networking/wired.py
"""

import logging
from .base import KextManager
from ...datasets import smbios_data, cpu_data
import sys as _sys
if _sys.platform == "darwin":
    from ...detections import device_probe as _dp
else:
    from ...detections import device_probe_win as _dp

logger = logging.getLogger(__name__)


class NetworkKextManager(KextManager):
    """Manages Network-related kexts."""

    def apply(self) -> list[str]:
        model_info = smbios_data.smbios_dictionary.get(self.model, {})
        cpu_gen = model_info.get("CPU Generation", 999)

        self._wifi_handling(model_info, cpu_gen)
        self._ethernet_handling(model_info, cpu_gen)

        return self.log_lines

    def _wifi_handling(self, model_info, cpu_gen):
        """WiFi kext handler (legacy wireless.py)."""
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
            self.enable_kext("IO80211FamilyLegacy.kext", self.constants.io80211legacy_version)
            self.enable_kext("AirportBrcmFixup.kext", self.constants.airportbcrmfixup_version)
            # BrcmNIC_Injector plugin (legacy wireless.py:153)
            bp = "AirportBrcmFixup.kext/Contents/PlugIns/AirPortBrcmNIC_Injector.kext"
            for entry in self.config.get("Kernel", {}).get("Add", []):
                if entry.get("BundlePath") == bp:
                    entry["Enabled"] = False
            self._log("  WiFi: BrcmNIC - IOSkywalk + IO80211Legacy + BrcmFixup + Injector")
        elif hasattr(_dp, 'Atheros') and wireless == getattr(
            getattr(_dp, 'Atheros', None), 'Chipsets', object()
        ).get('AirPortAtheros40', None):
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

    def _ethernet_handling(self, model_info, cpu_gen):
        """Ethernet kext handler (legacy wired.py)."""
        ethernet = model_info.get("Ethernet Chipset")
        nforce = model_info.get("nForce Chipset", False)

        if nforce:
            self.enable_kext("nForceEthernet.kext", self.constants.nforce_version)
            self._log("  Ethernet: nForce")
        elif ethernet == "Broadcom":
            self.enable_kext("CatalinaBCM5701Ethernet.kext", self.constants.bcm570_version)
            self._log("  Ethernet: Broadcom BCM5701")
        elif ethernet == "Intel 80003ES2LAN":
            self.enable_kext("AppleIntel8254XEthernet.kext", self.constants.intel_8254x_version)
            self._log("  Ethernet: Intel 80003ES2LAN")
        elif ethernet == "Intel 82574L":
            self.enable_kext("Intel82574L.kext", self.constants.intel_82574l_version)
            self._log("  Ethernet: Intel 82574L")
        elif ethernet == "Intel i210":
            self.enable_kext("CatalinaIntelI210Ethernet.kext", self.constants.i210_version)
            self._log("  Ethernet: Intel i210")
        elif ethernet == "Marvell":
            self.enable_kext("MarvelYukonEthernet.kext", self.constants.marvel_version)
            self._log("  Ethernet: Marvell Yukon")
        elif ethernet == "Aquantia":
            self.enable_kext("AppleEthernetAbuantiaAqtion.kext", self.constants.aquantia_version)
            self._log("  Ethernet: Aquantia")

        # ECM-Override for USB Ethernet dongles (legacy wired.py:72)
        if model_info.get("Stock Ethernet") == "None":
            self.enable_kext("ECM-Override.kext", self.constants.ecm_override_version)
            self._log("  Ethernet: ECM-Override (USB dongle)")

        return self.log_lines
