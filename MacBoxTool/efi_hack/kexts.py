"""
kexts.py: Kext selection for Hackintosh EFI

Selects kexts based on detected hardware (CPU, GPU, network, storage).
References: https://dortania.github.io/OpenCore-Install-Guide/
"""

import logging
from ..efi_mac.kexts.base import KextManager
from ..efi_mac.config import ConfigManager

logger = logging.getLogger(__name__)

# AirportItlwm version map: maps macOS version codes to kext names and kernel version ranges
AIRPORTITLWM_MAP = {
    "11": {"display": "macOS 11 Big Sur", "kext": "AirportItlwm_BigSur.kext", "min": "20.0.0", "max": "20.99.99"},
    "12": {"display": "macOS 12 Monterey", "kext": "AirportItlwm_Monterey.kext", "min": "21.0.0", "max": "21.99.99"},
    "13": {"display": "macOS 13 Ventura", "kext": "AirportItlwm_Ventura.kext", "min": "22.0.0", "max": "22.99.99"},
    "14.0": {"display": "macOS 14.0-14.3", "kext": "AirportItlwm_Sonoma14.0.kext", "min": "23.0.0", "max": "23.3.99"},
    "14.4": {"display": "macOS 14.4+", "kext": "AirportItlwm_Sonoma14.4.kext", "min": "23.4.0", "max": "23.99.99"},
}

# Non-native USB controller chipsets that need XHCI-unsupported.kext
# (H370/B360/H310/Z390 desktop, X79/X99 HEDT)
_XHCI_UNSUPPORTED_CHIPSETS = {
    "H370", "B360", "H310", "Z390", "X79", "X99",
}

# AMD platforms that need AppleMCEReporterDisabler (12.3+ dual-die crash fix)
_AMD_GENS = {"zen", "zen2", "zen3", "zen4"}

# Intel ethernet name fragments → kext name mapping
_INTEL_ETH_MAP = {
    "I217": "IntelMausiEthernet.kext",
    "I218": "IntelMausiEthernet.kext",
    "I219": "IntelMausiEthernet.kext",
    "82578": "IntelMausiEthernet.kext",
    "82579": "IntelMausiEthernet.kext",
    "I211": "AppleIGB.kext",
    "I225": "AppleIGC.kext",
    "I226": "AppleIGC.kext",
}

# Realtek ethernet name fragments → kext name mapping
_REALTEK_ETH_MAP = {
    "RTL8111": "RealtekRTL8111.kext",
    "RTL8125": "SimpleRTK5.kext",
}

# Atheros/Killer ethernet
_ATHEROS_ETH_MAP = {
    "AR8": "AtherosE2200Ethernet.kext",
    "E2200": "AtherosE2200Ethernet.kext",
    "KILLER E2": "AtherosE2200Ethernet.kext",
}


class HackKexts:
    """Select and enable kexts for Hackintosh hardware."""

    def __init__(self, config: dict, constants, paths: dict,
                 cpu_gen: str, is_laptop: bool,
                 chipset: str = "", target_macos: str = "",
                 target_macos_versions: list = None):
        self.config = config
        self.constants = constants
        self.paths = paths
        self.cpu_gen = cpu_gen
        self.is_laptop = is_laptop
        self.chipset = chipset.upper() if chipset else ""
        self.target_macos = str(target_macos).lower().replace(" ", "_") if target_macos else ""
        self.target_macos_versions = target_macos_versions or []
        self.log_lines: list[str] = []

        self.kext_mgr = KextManager(config, constants, "", paths)
        self.config_mgr = ConfigManager(config, paths["plist_path"])

    def _log(self, msg: str):
        logger.info(msg)
        self.log_lines.append(msg)

    def _ver(self, attr: str, fallback: str) -> str:
        """Get version string from constants with a fallback."""
        return getattr(self.constants, attr, fallback)

    def _inject_io80211_kexts(self):
        """Inject IO80211 series kexts for macOS 14.0+ (forced,不受设置约束).

        - IO80211ElCap for macOS 14.0-14.3
        - IO80211FamilyLegacy for macOS 14.4+
        """
        # Parse macOS version
        target = self.target_macos.lower().replace(" ", "_") if self.target_macos else ""
        macos_ver = 0
        minor_ver = 0

        # Check for 14.4+ first (more specific)
        if "14.4" in target:
            macos_ver = 14
            minor_ver = 4
        elif "14.3" in target:
            macos_ver = 14
            minor_ver = 3
        elif "14.2" in target:
            macos_ver = 14
            minor_ver = 2
        elif "14.1" in target:
            macos_ver = 14
            minor_ver = 1
        elif "14.0" in target:
            macos_ver = 14
            minor_ver = 0
        elif "sonoma" in target:
            # "sonoma" without version -> assume 14.4+ (latest)
            macos_ver = 14
            minor_ver = 4
        elif "14" in target:
            macos_ver = 14
            minor_ver = 3  # Default to 14.0-14.3 range
        elif "13" in target or "ventura" in target:
            macos_ver = 13
        elif "12" in target or "monterey" in target:
            macos_ver = 12
        elif "11" in target or "big_sur" in target:
            macos_ver = 11

        # Only inject for macOS 14.0+ (forced, no setting control)
        if macos_ver >= 14:
            if minor_ver >= 4:
                # macOS 14.4+ uses IO80211FamilyLegacy
                self.kext_mgr.enable_kext(
                    "IO80211FamilyLegacy.kext",
                    self._ver("io80211legacy_version", "1.0.0")
                )
                self._log("  WiFi: IO80211FamilyLegacy injected (macOS 14.4+)")
            else:
                # macOS 14.0-14.3 uses IO80211ElCap
                self.kext_mgr.enable_kext(
                    "IO80211ElCap.kext",
                    self._ver("io80211elcap_version", "2.0.1")
                )
                self._log("  WiFi: IO80211ElCap injected (macOS 14.0-14.3)")

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def apply(self) -> list[str]:
        """Select and enable kexts based on hardware detection."""
        self._log("[STEP] Selecting Kexts (Hackintosh)")

        self._add_core_kexts()
        self._add_security_kexts()
        self._add_gpu_kexts()
        self._add_audio_kexts()
        self._add_storage_kexts()
        self._add_network_kexts()
        self._inject_io80211_kexts()
        self._add_usb_kexts()
        self._add_amd_extras()
        self._add_smc_plugins()

        if self.is_laptop:
            self._add_laptop_kexts()

        self.log_lines.extend(self.kext_mgr.log_lines)

        enabled = sum(
            1 for k in self.config.get("Kernel", {}).get("Add", [])
            if k.get("Enabled")
        )
        self._log(f"  Total enabled kexts: {enabled}")
        return self.log_lines

    # ------------------------------------------------------------------
    # Core kexts (always required)
    # ------------------------------------------------------------------

    def _add_core_kexts(self):
        """Lilu + VirtualSMC — required on every system."""
        self.kext_mgr.enable_kext("Lilu.kext",
                                   self._ver("lilu_version", "1.6.8"))
        self._log("  + Lilu.kext (patch framework, required)")

        self.kext_mgr.enable_kext("VirtualSMC.kext",
                                   self._ver("virtual_smc_version", "1.3.4"))
        self._log("  + VirtualSMC.kext (SMC emulation, required)")

    # ------------------------------------------------------------------
    # Security kexts
    # ------------------------------------------------------------------

    def _add_security_kexts(self):
        """AMFIPass for AMFI bypass."""
        self.kext_mgr.enable_kext("AMFIPass.kext",
                                   self._ver("amfipass_version", "1.4.0"))
        self._log("  + AMFIPass.kext (AMFI bypass)")

    # ------------------------------------------------------------------
    # GPU
    # ------------------------------------------------------------------

    def _add_gpu_kexts(self):
        """WhateverGreen for GPU patching (always included)."""
        self.kext_mgr.enable_kext("WhateverGreen.kext",
                                   self._ver("whatevergreen_version", "1.6.7"))
        self._log("  + WhateverGreen.kext (GPU patching, DRM, framebuffer)")

    # ------------------------------------------------------------------
    # Audio
    # ------------------------------------------------------------------

    def _add_audio_kexts(self):
        """AppleALC for onboard audio (user opt-in via set_alc_usage)."""
        if self.constants.set_alc_usage:
            self.kext_mgr.enable_kext("AppleALC.kext",
                                       self._ver("applealc_version", "1.9.1"))
            self._log("  + AppleALC.kext (onboard audio)")

    # ------------------------------------------------------------------
    # Storage
    # ------------------------------------------------------------------

    def _add_storage_kexts(self):
        """NVMeFix for NVMe power management (Mojave+)."""
        if self.constants.allow_nvme_fixing:
            self.kext_mgr.enable_kext("NVMeFix.kext",
                                       self._ver("nvmefix_version", "1.1.1"))
            self._log("  + NVMeFix.kext (NVMe power management)")

    # ------------------------------------------------------------------
    # Network
    # ------------------------------------------------------------------

    def _add_network_kexts(self):
        """Select ethernet and WiFi kexts from hardware detection."""
        self._select_ethernet()
        self._select_wifi()
        self._select_bluetooth()

    def _select_ethernet(self):
        computer = self.constants.computer
        if not computer:
            return

        eth = getattr(computer, "ethernet", None)
        if not eth:
            return

        eth_str = str(eth).upper()

        # Intel ethernet
        for fragment, kext_name in _INTEL_ETH_MAP.items():
            if fragment in eth_str:
                ver_attr = "intelmausi_version" if "IntelMausi" in kext_name else \
                           "appleigb_version" if "IGB" in kext_name else "appleigc_version"
                self.kext_mgr.enable_kext(kext_name, self._ver(ver_attr, "1.0.7"))
                self._log(f"  + {kext_name} (Intel {fragment} ethernet)")
                return

        # Realtek
        for fragment, kext_name in _REALTEK_ETH_MAP.items():
            if fragment in eth_str:
                ver_attr = "simplertk_version" if "SimpleRTK5" in kext_name else "realtek8111_version"
                self.kext_mgr.enable_kext(kext_name, self._ver(ver_attr, "1.0.1"))
                self._log(f"  + {kext_name} (Realtek {fragment} ethernet)")
                return

        # Atheros / Killer
        for fragment, kext_name in _ATHEROS_ETH_MAP.items():
            if fragment in eth_str:
                self.kext_mgr.enable_kext(
                    kext_name, self._ver("atherosethernetkext_version", "2.2.2")
                )
                self._log(f"  + {kext_name} (Atheros/Killer ethernet)")
                return

    def _select_wifi(self):
        computer = self.constants.computer
        if not computer:
            return

        wifi = getattr(computer, "wifi", None)
        if not wifi:
            return

        wifi_str = str(wifi).upper()

        if "INTEL" in wifi_str:
            # AirportItlwm: select versions based on user selection or default to all
            # Default versions if none specified: Monterey, Ventura, Sonoma
            target_versions = self.target_macos_versions or ["12", "13", "14.0", "14.4"]

            for ver_code in target_versions:
                if ver_code not in AIRPORTITLWM_MAP:
                    continue
                info = AIRPORTITLWM_MAP[ver_code]
                kext_name = info["kext"]
                self.kext_mgr.enable_kext(kext_name, self._ver("airportitlwm_version", "2.3.0"))
                # Set kernel version range in config
                self._set_kext_kernel_range(kext_name, info["min"], info["max"])
                self._log(f"  + {kext_name} (Intel WiFi, kernel {info['min']}-{info['max']})")

        elif "BROADCOM" in wifi_str or "BCM" in wifi_str:
            self.kext_mgr.enable_kext(
                "AirportBrcmFixup.kext",
                self._ver("airportbrcmfixup_version", "2.1.8")
            )
            self._log("  + AirportBrcmFixup.kext (non-native Broadcom WiFi)")

    def _set_kext_kernel_range(self, kext_name: str, min_kernel: str, max_kernel: str):
        """Set MinKernel and MaxKernel for a kext."""
        for entry in self.config.get("Kernel", {}).get("Add", []):
            if entry.get("BundlePath") == kext_name:
                entry["MinKernel"] = min_kernel
                entry["MaxKernel"] = max_kernel
                break

    def _select_bluetooth(self):
        computer = self.constants.computer
        if not computer:
            return

        bt = getattr(computer, "bluetooth", None)
        if not bt:
            return

        bt_str = str(bt).upper()

        if "INTEL" in bt_str:
            self.kext_mgr.enable_kext(
                "IntelBluetoothFirmware.kext",
                self._ver("intelbt_version", "2.4.0")
            )
            # BlueToolFixup required for macOS 12+
            self.kext_mgr.enable_kext(
                "BlueToolFixup.kext",
                self._ver("bluetool_version", "2.7.1")
            )
            self._log("  + IntelBluetoothFirmware.kext + BlueToolFixup.kext (Intel BT)")

        elif "BROADCOM" in bt_str or "BCM" in bt_str:
            # BrcmPatchRAM3 for macOS 10.15+
            self.kext_mgr.enable_kext(
                "BrcmPatchRAM3.kext",
                self._ver("brcmpatchram_version", "2.6.8")
            )
            self.kext_mgr.enable_kext(
                "BrcmFirmwareData.kext",
                self._ver("brcmpatchram_version", "2.6.8")
            )
            # BlueToolFixup for macOS 12+
            self.kext_mgr.enable_kext(
                "BlueToolFixup.kext",
                self._ver("bluetool_version", "2.7.1")
            )
            self._log("  + BrcmPatchRAM3.kext + BlueToolFixup.kext (Broadcom BT)")

    # ------------------------------------------------------------------
    # USB
    # ------------------------------------------------------------------

    def _add_usb_kexts(self):
        """USB mapping kexts."""
        # USBInjectAll for legacy USB injection
        self.kext_mgr.enable_kext(
            "USBInjectAll.kext",
            self._ver("usbinjectall_version", "0.7.1")
        )
        self._log("  + USBInjectAll.kext (legacy USB port injection)")

        # USBToolBox is the modern replacement for USBInjectAll
        # It requires the companion UTBMap.kext generated by the tool
        self.kext_mgr.enable_kext(
            "USBToolBox.kext",
            self._ver("usbtoolbox_version", "1.1.1")
        )
        self._log("  + USBToolBox.kext (USB port injection framework)")

        # XHCI-unsupported for non-native USB 3.0 controllers
        if any(cs in self.chipset for cs in _XHCI_UNSUPPORTED_CHIPSETS):
            self.kext_mgr.enable_kext(
                "XHCI-unsupported.kext",
                self._ver("xhci_unsupported_version", "0.9.2")
            )
            self._log(f"  + XHCI-unsupported.kext (non-native USB, {self.chipset})")

    # ------------------------------------------------------------------
    # AMD-specific extras
    # ------------------------------------------------------------------

    def _add_amd_extras(self):
        """Kexts required for AMD Zen systems."""
        if self.cpu_gen not in _AMD_GENS:
            return

        # Disables macOS MCE reporter — crashes AMD (and dual-socket Intel) on 12.3+
        self.kext_mgr.enable_kext(
            "AppleMCEReporterDisabler.kext",
            self._ver("applemce_version", "1.2")
        )
        self._log("  + AppleMCEReporterDisabler.kext (AMD / dual-socket, macOS 12.3+)")

    # ------------------------------------------------------------------
    # SMC sensor plugins
    # ------------------------------------------------------------------

    def _add_smc_plugins(self):
        """SMCProcessor and SMCSuperIO for hardware monitoring."""
        if self.cpu_gen in _AMD_GENS:
            # AMD CPU temperature via SMCAMDProcessor
            self.kext_mgr.enable_kext(
                "SMCAMDProcessor.kext",
                self._ver("smcamdprocessor_version", "1.0")
            )
            self._log("  + SMCAMDProcessor.kext (AMD CPU temp)")
        else:
            # Intel CPU temperature
            self.kext_mgr.enable_kext(
                "SMCProcessor.kext",
                self._ver("smcprocessor_version", "1.3.4")
            )
            self._log("  + SMCProcessor.kext (Intel CPU temp)")

        # Fan speed (desktop only)
        if not self.is_laptop:
            self.kext_mgr.enable_kext(
                "SMCSuperIO.kext",
                self._ver("smcsuperio_version", "1.3.4")
            )
            self._log("  + SMCSuperIO.kext (fan speed monitoring)")

    # ------------------------------------------------------------------
    # Laptop-specific
    # ------------------------------------------------------------------

    def _add_laptop_kexts(self):
        """Trackpad, keyboard, battery, backlight for laptops."""
        # VoodooPS2 — PS2 keyboard + mouse/trackpad
        self.kext_mgr.enable_kext(
            "VoodooPS2Controller.kext",
            self._ver("voodoops2_version", "2.3.6")
        )
        self._log("  + VoodooPS2Controller.kext (keyboard/PS2 trackpad)")

        # VoodooI2C — I2C trackpads (Skylake+)
        i2c_gens = ("skylake", "kaby_lake", "coffee_lake", "comet_lake",
                    "rocket_lake", "alder_lake", "raptor_lake")
        if self.cpu_gen in i2c_gens:
            self.kext_mgr.enable_kext(
                "VoodooI2C.kext",
                self._ver("voodooi2c_version", "2.8")
            )
            self.kext_mgr.enable_kext(
                "VoodooI2CHID.kext",
                self._ver("voodooi2chid_version", "2.8")
            )
            self._log("  + VoodooI2C.kext + VoodooI2CHID.kext (I2C trackpad)")

        # ECEnabler — battery status register fix (Skylake+ 8-bit EC fields)
        self.kext_mgr.enable_kext(
            "ECEnabler.kext",
            self._ver("ecenabler_version", "1.0.5")
        )
        self._log("  + ECEnabler.kext (battery EC register fix)")

        # SMCBatteryManager — battery percentage
        self.kext_mgr.enable_kext(
            "SMCBatteryManager.kext",
            self._ver("smcbattery_version", "1.3.4")
        )
        self._log("  + SMCBatteryManager.kext (battery status)")

        # BrightnessKeys — Fn brightness hotkeys
        self.kext_mgr.enable_kext(
            "BrightnessKeys.kext",
            self._ver("brightnesskeys_version", "1.0.3")
        )
        self._log("  + BrightnessKeys.kext (brightness hotkeys)")

        # SMCLightSensor — ambient light sensor (if present)
        if getattr(self.constants.computer, "has_light_sensor", False):
            self.kext_mgr.enable_kext(
                "SMCLightSensor.kext",
                self._ver("smclightsensor_version", "1.3.4")
            )
            self._log("  + SMCLightSensor.kext (ambient light sensor)")
