"""
nvram.py: NVRAM variable management
"""


import logging
from ... import constants
from ...datasets import smbios_data, bluetooth_data, cpu_data, os_data, model_array

logger = logging.getLogger(__name__)


class NVRAMManager:
    """Manages NVRAM variables for EFI building."""

    def __init__(self, config: dict, constants:constants.Constants, model: str, paths: dict):
        self.config = config
        self.constants = constants
        self.model = model
        self.paths = paths
        self.log_lines: list[str] = []

    def _log(self, msg: str):
        logger.info(msg)
        self.log_lines.append(msg)

    def apply(self) -> list[str]:
        """
        Apply NVRAM settings.

        Returns:
            Log lines
        """
        self._log("[STEP] Setting NVRAM variables")

        nvram = self.config.setdefault("NVRAM", {}).setdefault("Add", {})

        # OCLP GUID for version and model info
        oclp_guid = nvram.setdefault("4D1FDA02-38C7-4A6A-9CC6-4BCCA8B30102", {})
        oclp_guid["OCLP-Version"] = self.constants.mactoolbox_version
        oclp_guid["OCLP-Model"] = self.model

        # Boot GUID for boot args and SIP
        boot_guid = nvram.setdefault("7C436110-AB2A-4BBB-A880-FE41995C9F82", {})
        boot_args = boot_guid.get("boot-args", "")

        # Base boot-args from OCLP-R
        # -lilubetaall: macOS Sequoia support for Lilu plugins
        # keepsyms=1: Keep symbols for debugging
        # debug=0x100: Boot debug level
        base_args = ["-lilubetaall", "keepsyms=1", "debug=0x100"]
        for arg in base_args:
            if arg not in boot_args:
                boot_args = (boot_args + " " + arg).strip()
                self._log(f"  Added boot-arg: {arg}")

        # Model-specific boot-args based on smbios_data
        model_info = smbios_data.smbios_dictionary.get(self.model, {})

        max_os = model_info.get("Max OS Supported", 0)
        cpu_gen = model_info.get("CPU Generation", 999)

        # -no_compat_check for legacy models
        if max_os and max_os < os_data.os_data.sonoma:
            if "-no_compat_check" not in boot_args:
                boot_args += " -no_compat_check"
                self._log("  Added boot-arg: -no_compat_check (legacy model)")

        # OCLP-R security.py: ipc_control_port_options=0 (Electron app fix with SIP lowered)
        if "ipc_control_port_options=0" not in boot_args:
            boot_args += " ipc_control_port_options=0"
            self._log("  Added boot-arg: ipc_control_port_options=0 (Electron fix)")

        # OCLP-R security.py: -nokcmismatchpanic (KC UUID mismatch after RSR)
        if "-nokcmismatchpanic" not in boot_args:
            boot_args += " -nokcmismatchpanic"
            self._log("  Added boot-arg: -nokcmismatchpanic (RSR KC UUID)")

        # OCLP-R security.py: amfi=0x80 for models needing AMFI disabled (pre-Sonoma native)
        if max_os and max_os < os_data.os_data.sonoma:
            if "amfi=" not in boot_args:
                boot_args += " amfi=0x80"
                self._log("  Added boot-arg: amfi=0x80 (AMFI disable)")
            oclp_guid.setdefault("OCLP-Settings", "")
            if "-allow_amfi" not in oclp_guid["OCLP-Settings"]:
                oclp_guid["OCLP-Settings"] += " -allow_amfi"
            if "-allow_fv" not in oclp_guid["OCLP-Settings"]:
                oclp_guid["OCLP-Settings"] += " -allow_fv"

        # NVMe ASPM fix for models with NVMe storage
        storage = model_info.get("Stock Storage", [])
        if "NVMe" in storage:
            if "-nvmefaspm" not in boot_args:
                boot_args += " -nvmefaspm"
                self._log("  Added boot-arg: -nvmefaspm (NVMe power management)")

        # GPU-related boot-args based on OCLP-R
        stock_gpus = model_info.get("Stock GPUs", [])

        # Check for NVIDIA/AMD GPUs using string representation
        gpu_str = str(stock_gpus)
        has_nvidia = "NVIDIA" in gpu_str or "Tesla" in gpu_str
        has_amd = "AMD" in gpu_str

        # MacPro/Xserve models need GPU boot-args
        if self.model in model_array.MacPro:
            if has_amd:
                # AMD GPU: shikigva=128 unfairgva=1 agdpmod=pikera radgva=1
                gpu_args = " shikigva=128 unfairgva=1 agdpmod=pikera radgva=1"
                if all(arg not in boot_args for arg in ["shikigva", "unfairgva"]):
                    boot_args += gpu_args
                    self._log(f"  Added boot-arg: {gpu_args} (AMD GPU)")
            elif has_nvidia:
                # NVIDIA GPU: -wegtree agdpmod=vit9696
                gpu_args = " -wegtree agdpmod=vit9696"
                if "-wegtree" not in boot_args:
                    boot_args += gpu_args
                    self._log(f"  Added boot-arg: {gpu_args} (NVIDIA GPU)")

        # Intel-Nvidia DRM models (iMac13,1/13,2/14,2/14,3)
        if self.model in model_array.IntelNvidiaDRM:
            if "shikigva=128" not in boot_args:
                boot_args += " shikigva=128 unfairgva=1 agdpmod=pikera radgva=1"
                self._log("  Added boot-arg: shikigva=128 unfairgva=1 agdpmod=pikera radgva=1 (Intel-Nvidia DRM)")

        # AGDP support models
        if self.model in model_array.AGDPSupport:
            if "agdpmod=pikera" not in boot_args:
                boot_args += " agdpmod=pikera"
                self._log("  Added boot-arg: agdpmod=pikera (AGDP support)")

        # -wegtree for Nvidia-based models (enables GUI on Nvidia GPUs)
        if self.model in model_array.DualGPUPatch and has_nvidia:
            if "-wegtree" not in boot_args:
                boot_args += " -wegtree"
                self._log("  Added boot-arg: -wegtree (Nvidia dual GPU)")

        # Bluetooth NVRAM variables and boot-args
        # Logic from OCLP-R efi_builder/bluetooth.py (_prebuilt_assumption path)
        BT = bluetooth_data.bluetooth_data
        bt_model = model_info.get("Bluetooth Model")
        nvram_delete = self.config.setdefault("NVRAM", {}).setdefault("Delete", {}).setdefault(
            "7C436110-AB2A-4BBB-A880-FE41995C9F82", []
        )

        if bt_model is not None and bt_model <= BT.BRCM20702_v1:
            # BRCM2046/2070: legacy BT firmware can't upload
            # Needs bluetoothInternalControllerInfo + bluetoothExternalDongleFailed cleared
            # Plus -btlfxallowanyaddr boot-arg and Bluetooth-Spoof kext
            if bt_model <= BT.BRCM2070:
                boot_guid["bluetoothInternalControllerInfo"] = b"\x00" * 14
                boot_guid["bluetoothExternalDongleFailed"] = b"\x00"
                for key in ("bluetoothInternalControllerInfo", "bluetoothExternalDongleFailed"):
                    if key not in nvram_delete:
                        nvram_delete.append(key)
                if "-btlfxallowanyaddr" not in boot_args:
                    boot_args += " -btlfxallowanyaddr"
                self._log(f"  BT: legacy ({bt_model.name}) - firmware workaround + -btlfxallowanyaddr")

            # BRCM20702_v1 on pre-Ivy Bridge: also needs firmware workaround
            elif bt_model == BT.BRCM20702_v1:
                if cpu_gen < cpu_data.CPUGen.ivy_bridge.value:
                    boot_guid["bluetoothInternalControllerInfo"] = b"\x00" * 14
                    boot_guid["bluetoothExternalDongleFailed"] = b"\x00"
                    for key in ("bluetoothInternalControllerInfo", "bluetoothExternalDongleFailed"):
                        if key not in nvram_delete:
                            nvram_delete.append(key)
                    self._log(f"  BT: BRCM20702_v1 pre-IvyBridge - firmware workaround")

        # Update boot-args in NVRAM
        boot_guid["boot-args"] = boot_args.strip()

        # SIP: allow unsigned kexts + filesystem modifications (0x803)
        # csr-active-config:
        #   0x803 = CS_UNTRUSTED_KEXTS | CS_ALLOW_USER_TRUST
        #   Allows loading unsigned kexts and user-trusted kexts
        boot_guid["csr-active-config"] = (0x803).to_bytes(4, "little")
        self._log("  Set csr-active-config: 0x803")

        return self.log_lines
