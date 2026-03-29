"""
gpu.py: GPU-related kext management

Logic from MacBoxTool: graphics_audio.py
"""

import binascii
import logging
import plistlib
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
        max_os = model_info.get("Max OS Supported", 0)
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
            self.enable_kext("WhateverGreen.kext", self.constants.whatevergreen_version)
            self._log("  WhateverGreen (GPU patching)")

        # Branch based on custom_model
        if self.constants.custom_model:
            self._handling_path(cpu_gen)
        else:
            self._on_model_path(cpu_gen)

        return self.log_lines

    def _on_model_path(self, cpu_gen: int) -> None:
        """On-model GPU handling - uses live hardware detection."""
        computer = self.constants.computer
        model_info = smbios_data.smbios_dictionary.get(self.model, {})

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
        """Prebuilt/custom model GPU handling - uses model_info from datasets."""
        model_info = smbios_data.smbios_dictionary.get(self.model, {})

        # Mac Pro / Xserve dGPU DeviceProperties (prebuilt fallback)
        self._macpro_gpu_handling()

        # iMac MXM DeviceProperties (prebuilt fallback)
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

    def _macpro_gpu_handling(self) -> None:
        """Mac Pro / Xserve dGPU DeviceProperties."""
        if self.model not in model_array.MacPro:
            return

        computer = self.constants.computer if not self.constants.custom_model else None
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

    def _imac_mxm_handling(self) -> None:
        """iMac MXM dGPU DeviceProperties."""
        computer = self.constants.computer if not self.constants.custom_model else None
        model_info = smbios_data.smbios_dictionary.get(self.model, {})

        if self.constants.metal_build is not True and not (computer and computer.dgpu and self.model in model_array.LegacyGPU):
            return
        if self.model not in model_array.MXMiMac:
            return

        # Detect GFX0 path
        gfx0_path = self._detect_gfx0_path()
        if not gfx0_path:
            return

        if self.constants.metal_build is True:
            if self.constants.imac_vendor == "AMD":
                self._amd_mxm_patch(gfx0_path)
            elif self.constants.imac_vendor == "Nvidia":
                self._nvidia_mxm_patch(gfx0_path)
        elif computer and computer.dgpu:
            if computer.dgpu.arch in [
                device_probe.AMD.Archs.Legacy_GCN_7000, device_probe.AMD.Archs.Legacy_GCN_8000,
                device_probe.AMD.Archs.Legacy_GCN_9000, device_probe.AMD.Archs.Polaris,
                device_probe.AMD.Archs.Polaris_Spoof, device_probe.AMD.Archs.Vega,
                device_probe.AMD.Archs.Navi,
            ]:
                self._amd_mxm_patch(gfx0_path)
            elif computer.dgpu.arch == device_probe.NVIDIA.Archs.Kepler:
                self._nvidia_mxm_patch(gfx0_path)

    def _detect_gfx0_path(self) -> str:
        """Detect GFX0 device path for iMac MXM.

        For Navi MXM cards behind a PCIe bridge, iterate all GPUs to find the
        one whose pci_path differs from the primary dgpu path.
        """
        computer = self.constants.computer if not self.constants.custom_model else None
        if computer and computer.dgpu and computer.dgpu.pci_path:
            gfx0_path = computer.dgpu.pci_path
            # Check for alternative GPU path (PCIe bridge, e.g. Navi MXM)
            if hasattr(computer, 'gpus') and computer.gpus:
                for gpu in computer.gpus:
                    if gpu.pci_path and gpu.pci_path != gfx0_path:
                        gfx0_path = gpu.pci_path
                        break
            return gfx0_path
        # Prebuilt fallback
        if self.model in ("iMac11,1", "iMac11,3"):
            return "PciRoot(0x0)/Pci(0x3,0x0)/Pci(0x0,0x0)"
        elif self.model in ("iMac9,1", "iMac10,1"):
            return "PciRoot(0x0)/Pci(0x1,0x0)/Pci(0x0,0x0)"
        elif self.model in ("iMac12,1", "iMac12,2"):
            return "PciRoot(0x0)/Pci(0x1,0x0)/Pci(0x0,0x0)"
        return ""

    def _amd_mxm_patch(self, gfx0_path: str) -> None:
        """AMD MXM dGPU patch."""
        if not gfx0_path:
            return
        self.config["DeviceProperties"]["Add"][gfx0_path] = {
            "shikigva": 128, "unfairgva": 1, "rebuild-device-tree": 1,
            "agdpmod": "pikera", "enable-gva-support": 1,
        }
        self._log(f"  DeviceProperties: AMD MXM patch ({gfx0_path})")

    def _nvidia_mxm_patch(self, gfx0_path: str) -> None:
        """NVIDIA MXM dGPU patch."""
        if not gfx0_path:
            return
        self.config["DeviceProperties"]["Add"][gfx0_path] = {
            "rebuild-device-tree": 1, "agdpmod": "vit9696",
        }
        self.config["UEFI"]["Quirks"]["ForgeUefiSupport"] = True
        self.config["UEFI"]["Quirks"]["ReloadOptionRoms"] = True
        self._log(f"  DeviceProperties: NVIDIA MXM patch ({gfx0_path})")

    def _nvidia_webdriver_handling(self) -> None:
        """Nvidia Web Driver DeviceProperties."""
        computer = self.constants.computer if not self.constants.custom_model else None

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
        """Dual GPU patch DeviceProperties."""
        if self.model not in model_array.DualGPUPatch:
            return

        computer = self.constants.computer if not self.constants.custom_model else None

        # On-model detection
        if computer and computer.gpus and len(computer.gpus) >= 2:
            for device in computer.gpus:
                if device.pci_path:
                    self.config["DeviceProperties"]["Add"][device.pci_path] = {
                        "switch-headless": 1,
                    }
            self._log("  DeviceProperties: Dual GPU patch (on-model)")
            return

        # Prebuilt fallback
        if self.model == "MacBookPro11,3":
            # MacBookPro11,3 - Haswell + Kepler
            self.config["DeviceProperties"]["Add"]["PciRoot(0x0)/Pci(0x2,0x0)"] = {"switch-headless": 1}
            self.config["DeviceProperties"]["Add"]["PciRoot(0x0)/Pci(0x1,0x0)/Pci(0x0,0x0)"] = {"switch-headless": 1}
        elif self.model in ("MacBookPro10,1", "MacBookPro10,2"):
            # MacBookPro10,1/10,2 - Ivy Bridge + NVIDIA
            self.config["DeviceProperties"]["Add"]["PciRoot(0x0)/Pci(0x2,0x0)"] = {"switch-headless": 1}
            self.config["DeviceProperties"]["Add"]["PciRoot(0x0)/Pci(0x1,0x0)/Pci(0x0,0x0)"] = {"switch-headless": 1}
        self._log("  DeviceProperties: Dual GPU patch (prebuilt)")

    def _software_demux_handling(self) -> None:
        """Software demux for MacBookPro8,2/8,3."""
        # AGPM injection
        agpm_path = "MacBookPro8,2/Contents/PlugIns/AGPM.xpc/Contents/Info.plist"
        for entry in self.config.get("Kernel", {}).get("Add", []):
            if entry.get("BundlePath") == agpm_path:
                entry["MaxKernel"] = "13.9.99"  # Block on macOS 14+
        # AppleGPUPowerManagement disabled
        for entry in self.config.get("Kernel", {}).get("Block", []):
            if entry.get("Identifier") == "com.apple.driver.AppleGPUPowerManagement":
                entry["Enabled"] = True

    def _spoof_handling(self) -> None:
        """GPU spoof handling: AGPM/AGDP/AMC Override kexts + DRM priority."""
        spoofed_model = self.constants.override_smbios
        if spoofed_model == "Default":
            spoofed_info = smbios_data.smbios_dictionary.get(self.model, {})
            spoofed_model = spoofed_info.get("Spoofed Model", self.model)
        spoofed_board = smbios_data.smbios_dictionary.get(spoofed_model, {}).get("Board ID", "")
        original_board = smbios_data.smbios_dictionary.get(self.model, {}).get("Board ID", "")

        if not spoofed_board or spoofed_board == original_board:
            return

        # AMC-Override for MacBookPro9,1
        if self.model == "MacBookPro9,1":
            self._create_override_kext(
                "AMC-Override.kext", "AppleMuxControl",
                original_board, spoofed_board
            )

        # AGPM-Override for most models
        if self.model not in getattr(model_array, 'NoAGPMSupport', []):
            self._create_override_kext(
                "AGPM-Override.kext", "AGPM",
                original_board, spoofed_board
            )

        # AGDP-Override for AGDPSupport models
        if self.model in getattr(model_array, 'AGDPSupport', []):
            self._create_override_kext(
                "AGDP-Override.kext", "AppleGraphicsDevicePolicy",
                original_board, spoofed_board
            )

    def _create_override_kext(self, kext_name: str, kext_bundle: str, original_board: str, spoofed_board: str) -> None:
        """Create override kext for GPU spoofing."""
        self._log(f"  {kext_name} ({kext_bundle})")
        if not gpu_model:
            return

        pci_path = None
        if self.model in model_array.MacPro:
            pci_path = "PciRoot(0x0)/Pci(0x1,0x0)/Pci(0x0,0x0)"
        elif self.model in model_array.MXMiMac:
            pci_path = "PciRoot(0x0)/Pci(0x2,0x0)/Pci(0x0,0x0)"
        elif self.model.startswith("MacBookPro"):
            pci_path = "PciRoot(0x0)/Pci(0x1,0x0)/Pci(0x0,0x0)"

        if pci_path:
            self.config["DeviceProperties"]["Add"][pci_path] = rules
            self._log(f"  AGPM injection ({pci_path})")

    def _agdp_inject(self, pci_path: str) -> None:
        """AGDP injection."""
        if not pci_path:
            return
        self.config["DeviceProperties"]["Add"][pci_path] = {"agdpmod": "vit9696"}
        self._log(f"  AGDP injection ({pci_path})")

    def _amc_override(self, pci_path: str) -> None:
        """AMC Override (AppleMuxControl)."""
        if not pci_path:
            return
        self.config["DeviceProperties"]["Add"][pci_path] = {"amc Override": 1}
        self._log(f"  AMC Override ({pci_path})")

    def _drm_patches(self, patches: list) -> None:
        """DRM patches."""
        for patch in patches:
            if patch == "AppleIntelCPUPowerManagement":
                self._drm_apple_intel_cpu_power_management()
            elif patch == "IOPlatformPlugin":
                self._drm_io_platform_plugin()
        self._log(f"  DRM patches applied ({len(patches)})")

    def _drm_apple_intel_cpu_power_management(self) -> None:
        """Patch AppleIntelCPUPowerManagement for DRM."""
        for entry in self.config.get("Kernel", {}).get("Patch", []):
            if entry.get("Identifier") == "com.apple.driver.AppleIntelCPUPowerManagement":
                entry["Enabled"] = True

    def _drm_io_platform_plugin(self) -> None:
        """Patch IOPlatformPlugin for DRM."""
        for entry in self.config.get("Kernel", {}).get("Patch", []):
            if entry.get("Identifier") == "com.apple.driver.IOPlatformPlugin":
                entry["Enabled"] = True

    def _board_id_spoof(self, kext_name: str, original_board: str, spoofed_board: str, gpu_name: str) -> None:
        """Apply board ID spoof."""
        if self.constants.custom_model:
            return

        # Inject Info.plist patch for board-id spoof
        for entry in self.config.get("Kernel", {}).get("Add", []):
            if entry.get("BundlePath") == kext_name:
                info_plist = entry.get("InfoPlistPatch", [])
                info_plist.append({
                    "Key": "board-id",
                    "Value": spoofed_board,
                })
                entry["InfoPlistPatch"] = info_plist
                self._log(f"  Board ID spoof ({gpu_name}): {original_board} → {spoofed_board}")
                break

    def _board_id_to_slot_name(self, board_id: str) -> str:
        """Convert board-id to slot-name."""
        # Example: board-id = "Mac-xxx" -> slot-name = "PCI Slot Name"
        # Simple implementation: return board-id encoded
        return binascii.hexlify(board_id.encode()).decode()

    def _get_board_id_from_model(self, model: str) -> str:
        """Get board ID from model."""
        model_info = smbios_data.smbios_dictionary.get(model, {})
        return model_info.get("Board ID", "")

    def _get_spoofed_board_id(self, model: str, gpu_arch: str) -> str:
        """Get spoofed board ID for GPU architecture."""
        # Map GPU arch to board ID
        board_ids = {
            "AMD_Legacy_GCN": "Mac-1A2B3C4D5E6F",
            "AMD_Polaris": "Mac-7BA5B2DFE27DD84F",
            "AMD_Vega": "Mac-CAD6701F7CEA0481",
            "AMD_Navi": "Mac-8F15E807FF8C6D91",
            "NVIDIA_Kepler": "Mac-9F18E312C5D7E5F3",
            "NVIDIA_Maxwell": "Mac-0DB5E40E3E2B4A9F",
        }
        return board_ids.get(gpu_arch, "")

    def _apply_spoof(self, kext_name: str, original_board: str, spoofed_board: str, gpu_name: str) -> None:
        """Apply GPU spoof by patching board-id."""
        if self.constants.custom_model:
            return

        for entry in self.config.get("Kernel", {}).get("Add", []):
            if entry.get("BundlePath") == kext_name:
                info_plist = entry.get("InfoPlistPatch", [])
                info_plist.append({
                    "Key": "board-id",
                    "Value": spoofed_board,
                })
                entry["InfoPlistPatch"] = info_plist
                self._log(f"  {kext_name} (Board ID: {original_board} → {spoofed_board})")

    def _kdkless_handling(self, cpu_gen: int) -> None:
        """KDKlessWorkaround for KDKless GPUs."""
        computer = self.constants.computer if not self.constants.custom_model else None
        gpu_archs = []
        if not self.constants.custom_model and computer and hasattr(computer, 'gpus') and computer.gpus:
            gpu_archs = [gpu.arch for gpu in computer.gpus]
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