"""
gpu.py: GPU-related kext management

Logic from MacBoxTool: graphics_audio.py
"""

import binascii
import logging
from .base import KextManager
from ...datasets import model_array, smbios_data, os_data, cpu_data
from ...detections import device_probe
from ...support import utilities

logger = logging.getLogger(__name__)


class GPUKextManager(KextManager):
    """Manages GPU-related kexts."""

    def apply(self) -> list[str]:
        model_info = smbios_data.smbios_dictionary.get(self.model, {})
        max_os = model_info.get("Max OS Supported", 0)
        cpu_gen = model_info.get("CPU Generation", 999)
        computer = self.constants.computer

        # WhateverGreen for models that need GPU patching
        needs_weg = (
            self.model in model_array.LegacyGPU or
            self.model in model_array.ModernGPU or
            self.model in model_array.MacPro or
            self.model in model_array.MXMiMac or
            self.model in model_array.DualGPUPatch
        )
        if needs_weg:
            self.enable_kext("WhateverGreen.kext", self.constants.whatevergreen_version)
            self._log("  WhateverGreen (GPU patching)")

        # Mac Pro / Xserve dGPU DeviceProperties
        self._macpro_gpu_handling(computer)

        # iMac MXM DeviceProperties
        self._imac_mxm_handling(computer, model_info)

        # Nvidia Web Driver DeviceProperties
        self._nvidia_webdriver_handling(computer)

        # Dual GPU patch DeviceProperties
        self._dual_gpu_handling(computer, model_info)

        # iMac14,1 iGPU agdpmod
        if self.model.startswith("iMac14,1"):
            self.config["DeviceProperties"]["Add"]["PciRoot(0x0)/Pci(0x2,0x0)"] = {"agdpmod": "vit9696"}
            self._log("  DeviceProperties: iMac14,1 iGPU agdpmod")

        # Software demux for MacBookPro8,2/8,3
        if self.constants.software_demux is True and self.model in ("MacBookPro8,2", "MacBookPro8,3"):
            self._software_demux_handling()

        # KDKlessWorkaround
        self._kdkless_handling(computer, model_info, cpu_gen)

        return self.log_lines

    def _macpro_gpu_handling(self, computer) -> None:
        """Mac Pro / Xserve dGPU DeviceProperties."""
        if self.model not in model_array.MacPro:
            return

        if computer and computer.gpus:
            for i, device in enumerate(computer.gpus):
                self._log(f"  Found dGPU ({i+1}): {utilities.friendly_hex(device.vendor_id)}:{utilities.friendly_hex(device.device_id)}")
                self.config["#Revision"][f"Hardware-MacPro-dGPU-{i+1}"] = f"{utilities.friendly_hex(device.vendor_id)}:{utilities.friendly_hex(device.device_id)}"

                if device.pci_path and device.acpi_path:
                    if isinstance(device, device_probe.AMD):
                        self.config["DeviceProperties"]["Add"][device.pci_path] = {
                            "shikigva": 128, "unfairgva": 1, "rebuild-device-tree": 1,
                            "agdpmod": "pikera", "enable-gva-support": 1,
                        }
                    elif isinstance(device, device_probe.NVIDIA):
                        self.config["DeviceProperties"]["Add"][device.pci_path] = {
                            "rebuild-device-tree": 1, "agdpmod": "vit9696",
                        }
                        self.config["UEFI"]["Quirks"]["ForgeUefiSupport"] = True
                        self.config["UEFI"]["Quirks"]["ReloadOptionRoms"] = True
                else:
                    if isinstance(device, device_probe.AMD):
                        if "shikigva=128 unfairgva=1" not in self.config["NVRAM"]["Add"]["7C436110-AB2A-4BBB-A880-FE41995C9F82"]["boot-args"]:
                            self.config["NVRAM"]["Add"]["7C436110-AB2A-4BBB-A880-FE41995C9F82"]["boot-args"] += " shikigva=128 unfairgva=1 agdpmod=pikera radgva=1"
                            if "-wegtree" not in self.config["NVRAM"]["Add"]["7C436110-AB2A-4BBB-A880-FE41995C9F82"]["boot-args"]:
                                self.config["NVRAM"]["Add"]["7C436110-AB2A-4BBB-A880-FE41995C9F82"]["boot-args"] += " -wegtree"
                    elif isinstance(device, device_probe.NVIDIA):
                        if "-wegtree agdpmod=vit9696" not in self.config["NVRAM"]["Add"]["7C436110-AB2A-4BBB-A880-FE41995C9F82"]["boot-args"]:
                            self.config["NVRAM"]["Add"]["7C436110-AB2A-4BBB-A880-FE41995C9F82"]["boot-args"] += " -wegtree agdpmod=vit9696"
                        self.config["UEFI"]["Quirks"]["ForgeUefiSupport"] = True
                        self.config["UEFI"]["Quirks"]["ReloadOptionRoms"] = True
        else:
            # Prebuilt fallback
            self.config["NVRAM"]["Add"]["7C436110-AB2A-4BBB-A880-FE41995C9F82"]["boot-args"] += " shikigva=128 unfairgva=1 -wegtree"

    def _imac_mxm_handling(self, computer, model_info) -> None:
        """iMac MXM dGPU DeviceProperties."""
        if self.constants.metal_build is not True and not (computer and computer.dgpu and self.model in model_array.LegacyGPU):
            return
        if self.model not in model_array.MXMiMac:
            return

        # Detect GFX0 path
        gfx0_path = self._detect_gfx0_path(computer)
        if not gfx0_path:
            return

        if self.constants.metal_build is True:
            if self.constants.imac_vendor == "AMD":
                self._amd_mxm_patch(gfx0_path, computer)
            elif self.constants.imac_vendor == "Nvidia":
                self._nvidia_mxm_patch(gfx0_path)
        elif computer and computer.dgpu:
            if computer.dgpu.arch in [
                device_probe.AMD.Archs.Legacy_GCN_7000, device_probe.AMD.Archs.Legacy_GCN_8000,
                device_probe.AMD.Archs.Legacy_GCN_9000, device_probe.AMD.Archs.Polaris,
                device_probe.AMD.Archs.Polaris_Spoof, device_probe.AMD.Archs.Vega,
                device_probe.AMD.Archs.Navi,
            ]:
                self._amd_mxm_patch(gfx0_path, computer)
            elif computer.dgpu.arch == device_probe.NVIDIA.Archs.Kepler:
                self._nvidia_mxm_patch(gfx0_path)

    def _detect_gfx0_path(self, computer) -> str:
        """Detect GFX0 device path for iMac MXM."""
        if computer and computer.dgpu and computer.dgpu.pci_path:
            return computer.dgpu.pci_path
        # Prebuilt fallback
        if self.model in ("iMac11,1", "iMac11,3"):
            return "PciRoot(0x0)/Pci(0x3,0x0)/Pci(0x0,0x0)"
        elif self.model in ("iMac9,1", "iMac10,1"):
            return "PciRoot(0x0)/Pci(0xc,0x0)/Pci(0x0,0x0)"
        return "PciRoot(0x0)/Pci(0x1,0x0)/Pci(0x0,0x0)"

    def _nvidia_mxm_patch(self, backlight_path: str) -> None:
        """iMac Nvidia Kepler MXM DeviceProperties."""
        self._log("  DeviceProperties: Nvidia MXM backlight + DRM")
        if self.model in ("iMac11,1", "iMac11,2", "iMac11,3", "iMac10,1"):
            self.config["DeviceProperties"]["Add"][backlight_path] = {
                "applbkl": binascii.unhexlify("01000000"),
                "@0,backlight-control": binascii.unhexlify("01000000"),
                "@0,built-in": binascii.unhexlify("01000000"),
                "shikigva": 256, "agdpmod": "vit9696",
            }
            if self.model == "iMac11,2":
                self.config["DeviceProperties"]["Add"]["PciRoot(0x0)/Pci(0x3,0x0)/Pci(0x0,0x0)"] = self.config["DeviceProperties"]["Add"][backlight_path].copy()
        elif self.model in ("iMac12,1", "iMac12,2"):
            self.config["DeviceProperties"]["Add"][backlight_path] = {
                "applbkl": binascii.unhexlify("01000000"),
                "@0,backlight-control": binascii.unhexlify("01000000"),
                "@0,built-in": binascii.unhexlify("01000000"),
                "shikigva": 256, "agdpmod": "vit9696",
            }
            # Disable unsupported iGPU
            self.config["DeviceProperties"]["Add"]["PciRoot(0x0)/Pci(0x2,0x0)"] = {
                "name": binascii.unhexlify("23646973706C6179"),
                "class-code": binascii.unhexlify("FFFFFFFF"),
            }
        self.enable_kext("BacklightInjector.kext", self.constants.backlight_injector_version)
        self.config["UEFI"]["Quirks"]["ForgeUefiSupport"] = True
        self.config["UEFI"]["Quirks"]["ReloadOptionRoms"] = True

    def _amd_mxm_patch(self, backlight_path: str, computer) -> None:
        """iMac AMD GCN/Navi MXM DeviceProperties."""
        self._log("  DeviceProperties: AMD MXM DRM")
        props = {"shikigva": 128, "unfairgva": 1, "agdpmod": "pikera", "rebuild-device-tree": 1, "enable-gva-support": 1}

        if self.model == "iMac9,1":
            self.enable_kext("BacklightInjector.kext", self.constants.backlight_injector_version)

        self.config["DeviceProperties"]["Add"][backlight_path] = props.copy()

        if self.model == "iMac11,2":
            self.config["DeviceProperties"]["Add"]["PciRoot(0x0)/Pci(0x3,0x0)/Pci(0x0,0x0)"] = props.copy()
        if self.model in ("iMac12,1", "iMac12,2"):
            self.config["DeviceProperties"]["Add"]["PciRoot(0x0)/Pci(0x2,0x0)"] = {
                "name": binascii.unhexlify("23646973706C6179"),
                "class-code": binascii.unhexlify("FFFFFFFF"),
            }

        # Legacy GCN Power Gate patches
        if computer and computer.dgpu and computer.dgpu.arch == device_probe.AMD.Archs.Legacy_GCN_7000:
            self.config["DeviceProperties"]["Add"][backlight_path].update({
                "CAIL,CAIL_DisableDrmdmaPowerGating": 1, "CAIL,CAIL_DisableGfxCGPowerGating": 1,
                "CAIL,CAIL_DisableUVDPowerGating": 1, "CAIL,CAIL_DisableVCEPowerGating": 1,
            })
        if self.constants.imac_model == "GCN":
            power_gate = {
                "CAIL,CAIL_DisableDrmdmaPowerGating": 1, "CAIL,CAIL_DisableGfxCGPowerGating": 1,
                "CAIL,CAIL_DisableUVDPowerGating": 1, "CAIL,CAIL_DisableVCEPowerGating": 1,
            }
            self.config["DeviceProperties"]["Add"][backlight_path].update(power_gate)
            if self.model == "iMac11,2":
                self.config["DeviceProperties"]["Add"]["PciRoot(0x0)/Pci(0x3,0x0)/Pci(0x0,0x0)"].update(power_gate)
        elif self.constants.imac_model == "Lexa":
            spoof = {"model": "AMD Radeon Pro WX 3200", "device-id": binascii.unhexlify("FF67")}
            self.config["DeviceProperties"]["Add"][backlight_path].update(spoof)
            if self.model == "iMac11,2":
                self.config["DeviceProperties"]["Add"]["PciRoot(0x0)/Pci(0x3,0x0)/Pci(0x0,0x0)"].update(spoof)

    def _nvidia_webdriver_handling(self, computer) -> None:
        """Nvidia Web Driver DeviceProperties."""
        if not computer:
            return
        for i, device in enumerate(computer.gpus):
            if not isinstance(device, device_probe.NVIDIA):
                continue
            if device.arch not in (
                device_probe.NVIDIA.Archs.Fermi, device_probe.NVIDIA.Archs.Maxwell, device_probe.NVIDIA.Archs.Pascal,
            ) and not (self.constants.force_nv_web is True and device.arch in (device_probe.NVIDIA.Archs.Tesla, device_probe.NVIDIA.Archs.Kepler)):
                continue
            self._log(f"  Nvidia Web Driver for GPU ({i+1})")
            if device.pci_path and device.acpi_path:
                self.config["DeviceProperties"]["Add"].setdefault(device.pci_path, {}).update({"disable-metal": 1, "force-compat": 1})
            else:
                if "ngfxgl=1 ngfxcompat=1" not in self.config["NVRAM"]["Add"]["7C436110-AB2A-4BBB-A880-FE41995C9F82"]["boot-args"]:
                    self.config["NVRAM"]["Add"]["7C436110-AB2A-4BBB-A880-FE41995C9F82"]["boot-args"] += " ngfxgl=1 ngfxcompat=1"
            self.config["NVRAM"]["Add"]["7C436110-AB2A-4BBB-A880-FE41995C9F82"].update({"nvda_drv": binascii.unhexlify("31")})
            if "nvda_drv" not in self.config["NVRAM"]["Delete"]["7C436110-AB2A-4BBB-A880-FE41995C9F82"]:
                self.config["NVRAM"]["Delete"]["7C436110-AB2A-4BBB-A880-FE41995C9F82"] += ["nvda_drv"]

    def _dual_gpu_handling(self, computer, model_info) -> None:
        """Dual GPU patch DeviceProperties (agdpmod)."""
        if self.model not in model_array.DualGPUPatch:
            return
        if computer and computer.dgpu and computer.dgpu.pci_path:
            gfx0_path = computer.dgpu.pci_path
        else:
            gfx0_path = "PciRoot(0x0)/Pci(0x1,0x0)/Pci(0x0,0x0)"

        if self.model in model_array.IntelNvidiaDRM and self.constants.drm_support is True:
            self.config["DeviceProperties"]["Add"][gfx0_path] = {"agdpmod": "vit9696", "shikigva": 256}
            self.config["DeviceProperties"]["Add"]["PciRoot(0x0)/Pci(0x2,0x0)"] = {
                "name": binascii.unhexlify("23646973706C6179"),
                "IOName": "#display",
                "class-code": binascii.unhexlify("FFFFFFFF"),
            }
            self._log("  DeviceProperties: DualGPU DRM (disable iGPU)")
        else:
            if gfx0_path not in self.config["DeviceProperties"]["Add"] or "agdpmod" not in self.config["DeviceProperties"]["Add"].get(gfx0_path, {}):
                self.config["DeviceProperties"]["Add"][gfx0_path] = {"agdpmod": "vit9696"}
            self._log("  DeviceProperties: DualGPU agdpmod")

    def _software_demux_handling(self) -> None:
        """Software demux for MacBookPro8,2/8,3 - disable dGPU via DeviceProperties."""
        self._log("  DeviceProperties: Software demux (disable dGPU)")
        self.config["DeviceProperties"]["Add"]["PciRoot(0x0)/Pci(0x1,0x0)/Pci(0x0,0x0)"] = {
            "class-code": binascii.unhexlify("FFFFFFFF"),
            "device-id": binascii.unhexlify("FFFF0000"),
            "IOName": "Pyquick Disabled Card",
            "name": "Pyquick Disabled Card",
        }
        self.config["DeviceProperties"]["Delete"]["PciRoot(0x0)/Pci(0x1,0x0)/Pci(0x0,0x0)"] = ["class-code", "device-id", "IOName", "name"]
        self.enable_kext("AMDGPUWakeHandler.kext", self.constants.gpu_wake_version)

    def _kdkless_handling(self, computer, model_info, cpu_gen) -> None:
        """KDKlessWorkaround for KDKless GPUs."""
        gpu_archs = []
        if not self.constants.custom_model:
            gpu_archs = [gpu.arch for gpu in self.constants.computer.gpus]
        else:
            if self.model not in smbios_data.smbios_dictionary:
                return
        gpu_archs = smbios_data.smbios_dictionary[self.model]["Stock GPUs"]
        print(gpu_archs)
        has_kdkless_gpu = False
        has_kdk_gpu = False
        
        for arch in gpu_archs:
            # KDKless GPUs (Metal, no KDK required)
            if arch in [ 
                device_probe.Intel.Archs.Ivy_Bridge,
                device_probe.Intel.Archs.Haswell,
                device_probe.Intel.Archs.Broadwell,
                device_probe.Intel.Archs.Skylake,
                device_probe.NVIDIA.Archs.Kepler,
            ]:
                has_kdkless_gpu = True

            # Non-Metal KDK
            if arch in [
                device_probe.NVIDIA.Archs.Tesla,
                device_probe.NVIDIA.Archs.Maxwell,
                device_probe.NVIDIA.Archs.Pascal,
                device_probe.AMD.Archs.TeraScale_1,
                device_probe.AMD.Archs.TeraScale_2,
                device_probe.Intel.Archs.Iron_Lake,
                device_probe.Intel.Archs.Sandy_Bridge,
            ]:
                has_kdk_gpu = True

            # Metal KDK (always)
            if arch in [
                device_probe.AMD.Archs.Legacy_GCN_7000,
                device_probe.AMD.Archs.Legacy_GCN_8000,
                device_probe.AMD.Archs.Legacy_GCN_9000,
            ]:
                has_kdk_gpu = True

            # Metal KDK (pre-AVX2.0)
            if arch in [
                device_probe.AMD.Archs.Polaris,
                device_probe.AMD.Archs.Polaris_Spoof,
                device_probe.AMD.Archs.Vega,
                device_probe.AMD.Archs.Navi,
            ]:
                if self.model == "MacBookPro13,3" or cpu_gen <= cpu_data.CPUGen.ivy_bridge.value:
                    # MacBookPro13,3 has AVX2.0 however the GPU has an unsupported framebuffer
                    has_kdk_gpu = True

        if has_kdkless_gpu and not has_kdk_gpu:
            # KDKlessWorkaround is required for KDKless GPUs
            self.enable_kext("KDKlessWorkaround.kext", self.constants.kdkless_version)
            self._log("  KDKlessWorkaround (KDKless GPU)")
            return

        # KDKlessWorkaround supports disabling native AMD stack on Ventura for pre-AVX2.0 CPUs
        # Applicable for Polaris, Vega, Navi GPUs
        if cpu_gen > cpu_data.CPUGen.ivy_bridge.value:
            return
        for arch in gpu_archs:
            if arch in [                
                device_probe.AMD.Archs.Polaris,
                device_probe.AMD.Archs.Polaris_Spoof,
                device_probe.AMD.Archs.Vega,
                device_probe.AMD.Archs.Navi,
            ]:
                self.enable_kext("KDKlessWorkaround.kext", self.constants.kdkless_version)
                self._log("  KDKlessWorkaround (pre-AVX2 AMD)")
                return
