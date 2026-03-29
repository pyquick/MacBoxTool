"""
gpu.py: GPU-related kext management

Logic from MacBoxTool: graphics_audio.py
"""

import binascii
import logging
import shutil
from pathlib import Path
from .base import KextManager
from ...datasets import model_array, smbios_data, os_data, cpu_data
from ...detections import device_probe
from ...support import utilities

logger = logging.getLogger(__name__)


class GPUKextManager(KextManager):
    """Manages GPU-related kexts."""

    def apply(self) -> list[str]:
        model_info = smbios_data.smbios_dictionary.get(self.model, {})
        cpu_gen = model_info.get("CPU Generation", 999)

        # WhateverGreen for models that need GPU patching
        needs_weg = (
            self.model in model_array.LegacyGPU or
            self.model in model_array.ModernGPU or
            self.model in model_array.MacPro or
            self.model in model_array.MXMiMac or
            self.model in model_array.DualGPUPatch
        )
        if needs_weg:
            self.enable_kext("WhateverGreen.kext", self.constants.whatevergreen_version, self.constants.whatevergreen_path)
            self._log("  WhateverGreen (GPU patching)")

        # Branch based on custom_model
        if self.constants.custom_model:
            self._handling_path(cpu_gen)
        else:
            self._on_model_path(cpu_gen)

        return self.log_lines

    def _on_model_path(self, cpu_gen: int) -> None:
        """On-model detection path."""
        # Mac Pro / Xserve dGPU DeviceProperties
        self._macpro_gpu_handling()

        # iMac MXM DeviceProperties
        self._imac_mxm_handling()

        # Nvidia Web Driver DeviceProperties
        self._nvidia_webdriver_handling()

        # Dual GPU patch DeviceProperties
        self._dual_gpu_handling()

        # iMac14,1 iGPU agdpmod
        if self.model.startswith("iMac14,1"):
            self.config["DeviceProperties"]["Add"]["PciRoot(0x0)/Pci(0x2,0x0)"] = {"agdpmod": "vit9696"}
            self._log("  DeviceProperties: iMac14,1 iGPU agdpmod")

        # Software demux for MacBookPro8,2/8,3
        if self.constants.software_demux is True and self.model in ("MacBookPro8,2", "MacBookPro8,3"):
            self._software_demux_handling()

        # GPU spoof handling (AGPM/AGDP/AMC Override, DRM)
        self._spoof_handling()

        # KDKlessWorkaround
        self._kdkless_handling(cpu_gen)

    def _handling_path(self, cpu_gen: int) -> None:
        """Prebuilt/custom model path."""
        # GPU spoof handling for prebuilt
        self._spoof_handling()

        # KDKlessWorkaround for prebuilt
        self._kdkless_handling(cpu_gen)

    def _macpro_gpu_handling(self) -> None:
        """Mac Pro / Xserve dGPU DeviceProperties."""
        if self.model not in model_array.MacPro:
            return

        computer = self.constants.computer
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

    def _imac_mxm_handling(self) -> None:
        """iMac MXM GPU DeviceProperties."""
        if self.model not in model_array.MXMiMac:
            return

        computer = self.constants.computer

        if not computer or not computer.gpus:
            return

        for device in computer.gpus:
            if isinstance(device, device_probe.NVIDIA):
                backlight_path = self._detect_gfx0_path(computer)
                if backlight_path:
                    self._nvidia_mxm_patch(backlight_path)
            elif isinstance(device, device_probe.AMD):
                backlight_path = self._detect_gfx0_path(computer)
                if backlight_path:
                    self._amd_mxm_patch(backlight_path, computer)

    def _detect_gfx0_path(self, computer) -> str:
        """Detect gfx0 ACPI path for MXM GPUs."""
        if not computer:
            return ""
        for device in computer.gpus:
            if device.acpi_path and "gfx0" in str(device.acpi_path).lower():
                return device.pci_path
        # Fallback to default path for iMac12,x
        if self.model in ("iMac12,1", "iMac12,2"):
            return "PciRoot(0x0)/Pci(0x3,0x0)/Pci(0x0,0x0)"
        return "PciRoot(0x0)/Pci(0x1,0x0)/Pci(0x0,0x0)"

    def _nvidia_mxm_patch(self, backlight_path: str) -> None:
        """Nvidia MXM patch DeviceProperties."""
        if self.model in ("iMac12,1", "iMac12,2"):
            self.config["DeviceProperties"]["Add"]["PciRoot(0x0)/Pci(0x2,0x0)"] = {
                "name": binascii.unhexlify("23646973706C6179"),
                "class-code": binascii.unhexlify("FFFFFFFF"),
            }

    def _amd_mxm_patch(self, backlight_path: str, computer) -> None:
        """AMD MXM patch DeviceProperties."""
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

    def _nvidia_webdriver_handling(self) -> None:
        """Nvidia Web Driver DeviceProperties."""
        computer = self.constants.computer
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

    def _dual_gpu_handling(self) -> None:
        """Dual GPU patch DeviceProperties (agdpmod)."""
        if self.model not in model_array.DualGPUPatch:
            return

        computer = self.constants.computer
        if computer and computer.dgpu and computer.dgpu.pci_path:
            gfx0_path = computer.dgpu.pci_path
        else:
            # Fallback paths for prebuilt
            if self.model in ("MacBookPro10,1", "MacBookPro10,2"):
                gfx0_path = "PciRoot(0x0)/Pci(0x1,0x0)/Pci(0x0,0x0)"
            elif self.model == "MacBookPro11,3":
                gfx0_path = "PciRoot(0x0)/Pci(0x1,0x0)/Pci(0x0,0x0)"
            elif self.model == "MacBookPro11,4":
                gfx0_path = "PciRoot(0x0)/Pci(0x2,0x0)/Pci(0x0,0x0)"
            else:
                gfx0_path = "PciRoot(0x0)/Pci(0x1,0x0)/Pci(0x0,0x0)"

        if self.model in ("MacBookPro11,4", "MacBookPro11,5"):
            self.config["DeviceProperties"]["Add"][gfx0_path] = {"agdpmod": "vit9696"}
            self._log(f"  DeviceProperties: {self.model} agdpmod (iGPU)")
        else:
            self.config["DeviceProperties"]["Add"][gfx0_path] = {"agdpmod": "pikera"}
            self._log(f"  DeviceProperties: {self.model} agdpmod (dGPU)")

    def _software_demux_handling(self) -> None:
        """Software demux for MacBookPro8,2/8,3."""
        # AGPM override for both GPUs
        amd_path = "PciRoot(0x0)/Pci(0x1,0x0)/Pci(0x0,0x0)"
        intel_path = "PciRoot(0x0)/Pci(0x2,0x0)"
        self.config["DeviceProperties"]["Add"][intel_path] = {"agdpmod": "vit9696"}
        self.config["DeviceProperties"]["Add"][amd_path] = {"agdpmod": "vit9696"}
        # Create AGPM override kext
        self._create_override_kext("AGPM", "Internal")
        # Patch IOAccelMemoryInfo
        patch = {
            "Base": "IOAccelMemoryInfo",
            "Find": binascii.unhexlify("8945F8904944"),
            "Replace": binascii.unhexlify("8945F8909090"),
            "Mask": binascii.unhexlify("FFFFFFFFFF"),
            "Comment": "IOAccelMemoryInfo patch for software demux",
        }
        self.config["Kernel"]["Patch"].append(patch)
        self._log("  Software demux patches applied")

    def _spoof_handling(self) -> None:
        """GPU spoof handling (AGPM/AGDP/AMC Override, DRM)."""
        computer = self.constants.computer
        model_info = smbios_data.smbios_dictionary.get(self.model, {})

        # AGPM Override for MacPro5,1 and MacPro6,1
        if self.model in ("MacPro5,1", "MacPro6,1"):
            spoofed = "MacPro7,1"
            self.config["DeviceProperties"]["Add"]["PciRoot(0x0)/Pci(0x1,0x0)/Pci(0x0,0x0)"] = {
                "model": spoofed, "device-id": binascii.unhexlify("00020000"), "revision-id": binascii.unhexlify("00040000")
            }
            self.config["DeviceProperties"]["Add"]["PciRoot(0x0)/Pci(0x2,0x0)/Pci(0x0,0x0)"] = {
                "model": spoofed, "device-id": binascii.unhexlify("00020000"), "revision-id": binascii.unhexlify("00040000")
            }
            self._log(f"  DeviceProperties: AGPM Override {spoofed}")

        # Spoof for MacBookPro9,1 (Kepler)
        if self.model == "MacBookPro9,1":
            self.config["DeviceProperties"]["Add"]["PciRoot(0x0)/Pci(0x1,0x0)/Pci(0x0,0x0)"] = {
                "model": "MacBook Pro",
                "device-id": binascii.unhexlify("00010000"),
                "revision-id": binascii.unhexlify("00070000"),
            }
            self._log("  DeviceProperties: MacBookPro9,1 spoof")

        # Spoof for MacBookAir5,1/5,2 (HD3000)
        if self.model in ("MacBookAir5,1", "MacBookAir5,2"):
            self.config["DeviceProperties"]["Add"]["PciRoot(0x0)/Pci(0x2,0x0)"] = {
                "model": "Intel HD 4000",
                "device-id": binascii.unhexlify("01660000"),
                "revision-id": binascii.unhexlify("00080000"),
            }
            self._log("  DeviceProperties: MacBookAir5,x spoof")

        # Spoof for Macmini6,1/6,2 (HD4000)
        if self.model in ("Macmini6,1", "Macmini6,2"):
            self.config["DeviceProperties"]["Add"]["PciRoot(0x0)/Pci(0x2,0x0)"] = {
                "model": "Intel HD 4000",
                "device-id": binascii.unhexlify("01660000"),
                "revision-id": binascii.unhexlify("00080000"),
            }
            self._log("  DeviceProperties: Macmini6,x spoof")

        # iGPU spoofing for Ivy Bridge laptops (MacBookPro10,1)
        if self.model == "MacBookPro10,1":
            self.config["DeviceProperties"]["Add"]["PciRoot(0x0)/Pci(0x2,0x0)"] = {
                "model": "Intel HD Graphics 4000",
                "device-id": binascii.unhexlify("01660000"),
                "revision-id": binascii.unhexlify("00080000"),
            }
            self._log("  DeviceProperties: MacBookPro10,1 iGPU spoof")

        # Spoof for MacBookPro11,5 (Radeon R9 M370X)
        if self.model == "MacBookPro11,5":
            self.config["DeviceProperties"]["Add"]["PciRoot(0x0)/Pci(0x1,0x0)/Pci(0x0,0x0)"] = {
                "model": "AMD Radeon R9 M370X",
                "device-id": binascii.unhexlify("66010000"),
            }
            self._log("  DeviceProperties: MacBookPro11,5 spoof")

        # DRM patches for legacy GPUs
        if self.model in model_array.DRM:
            # AppleMCEReporterDisabler for AMD CPU + dGPU
            self.enable_kext("AppleMCEReporterDisabler.kext", self.constants.applemcreporterdisabler_version, self.constants.applemcreporterdisabler_path)
            # Disable AppleMCEReporter
            for entry in self.config.get("Kernel", {}).get("Block", []):
                if entry.get("Identifier") == "com.apple.driver.AppleMCEReporter":
                    entry["Enabled"] = True
            self._log("  DRM patches for legacy GPU")

        # ATI/AMD framebuffer patches for laptops
        if self.model in model_array.LegacyGPU:
            if self.constants.custom_model:
                # Prebuilt path - use model_info
                gpu_model = model_info.get("GPU Model", "")
            else:
                # On-model path - detect GPU
                gpu_model = ""
                if computer and computer.gpus:
                    for gpu in computer.gpus:
                        if isinstance(gpu, device_probe.AMD):
                            gpu_model = gpu.model
                            break

            if "Radeon" in gpu_model and "Pro" not in gpu_model:
                # Spoof to Radeon Pro
                self._create_override_kext("AMD9000Controller", "Internal")
                self._create_override_kext("AMDRadeonX3000", "Internal")
                self._create_override_kext("AMDRadeonX3000GLDriver", "Internal")
                self._log("  AMD framebuffer patches")

    def _create_override_kext(self, kext_name: str, plist_type: str) -> None:
        """Create an override kext with specified plist type."""
        override_path = self.paths.get("kexts_path", "")
        if not override_path:
            return
        kext_path = Path(override_path) / f"{kext_name}.kext"
        kext_path.mkdir(parents=True, exist_ok=True)
        (kext_path / "Contents").mkdir(exist_ok=True)
        (kext_path / "Contents" / "Info.plist").write_text(
            f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key>
    <string>en</string>
    <key>CFBundleExecutable</key>
    <string></string>
    <key>CFBundleIdentifier</key>
    <string>com.apple.{kext_name}</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>{kext_name}</string>
    <key>CFBundlePackageType</key>
    <string>KEXT</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
    <key>IOKitPersonalities</key>
    <dict>
        <key>{plist_type}</key>
        <dict/>
    </dict>
    <key>OSBundleRequired</key>
    <string>Root</string>
</dict>
</plist>"""
        )
        shutil.chmod(kext_path, 0o755)
        shutil.chmod(kext_path / "Contents", 0o755)
        shutil.chmod(kext_path / "Contents" / "Info.plist", 0o644)

    def _kdkless_handling(self, cpu_gen: int) -> None:
        """KDKlessWorkaround for KDKless GPUs."""
        gpu_archs = []
        if not self.constants.custom_model and self.constants.computer and hasattr(self.constants.computer, 'gpus') and self.constants.computer.gpus:
            gpu_archs = [gpu.arch for gpu in self.constants.computer.gpus]
        else:
            if self.model not in smbios_data.smbios_dictionary:
                return
            gpu_archs = smbios_data.smbios_dictionary[self.model].get("Stock GPUs", [])

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
            self.enable_kext("KDKlessWorkaround.kext", self.constants.kdkless_version, self.constants.kdkless_path)
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
                self.enable_kext("KDKlessWorkaround.kext", self.constants.kdkless_version, self.constants.kdkless_path)
                self._log("  KDKlessWorkaround (pre-AVX2 AMD)")
                return