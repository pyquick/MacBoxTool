"""
network.py: Network (Ethernet/WiFi) related kext management
"""

import logging
from .base import KextManager
from ...datasets import smbios_data
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
        wireless = model_info.get("Wireless Model")
        ethernet = model_info.get("Ethernet Chipset")
        nforce = model_info.get("nForce Chipset", False)

        # WiFi kexts based on chipset
        if wireless == _dp.Broadcom.Chipsets.AirPortBrcm43224:
            self.enable_kext("IO80211ElCap.kext", self.constants.io80211elcap_version)
            self.enable_kext("corecaptureElCap.kext", self.constants.corecaptureelcap_version)
            self._log("  WiFi: AirPortBrcm43224 - IO80211ElCap")
        elif wireless in (
            _dp.Broadcom.Chipsets.AirPortBrcm4331,
            _dp.Broadcom.Chipsets.AirPortBrcm4360,
        ):
            self.enable_kext("AirPortBrcmFixup.kext", self.constants.airportbcrmfixup_version)
            self._log(f"  WiFi: {wireless.name} - AirPortBrcmFixup")
        elif wireless in (
            _dp.Broadcom.Chipsets.AirportBrcmNIC,
            _dp.Broadcom.Chipsets.AirPortBrcmNICThirdParty,
        ):
            self.enable_kext("AirPortBrcmFixup.kext", self.constants.airportbcrmfixup_version)
            self.enable_kext("IOSkywalkFamily.kext", self.constants.ioskywalk_version)
            self.enable_kext("IO80211FamilyLegacy.kext", self.constants.io80211legacy_version)
            self._log("  WiFi: BrcmNIC - AirPortBrcmFixup + IOSkywalk legacy")

        # Ethernet kexts based on chipset
        if nforce:
            self.enable_kext("nForceEthernet.kext", self.constants.nforce_version)
            self._log("  Ethernet: nForce")
        elif ethernet == "Marvell":
            self.enable_kext("MarvelYukonEthernet.kext", self.constants.marvel_version)
            self._log("  Ethernet: Marvell Yukon")
        elif ethernet == "Intel":
            self.enable_kext("Intel82574L.kext", self.constants.intel_82574l_version)
            self._log("  Ethernet: Intel 82574L")

        return self.log_lines
