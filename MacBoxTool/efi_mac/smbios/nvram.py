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

        # MBT GUID for version and model info
        mbt_guid = nvram.setdefault("4D1FDA02-38C7-4A6A-9CC6-4BCCA8B30102", {})
        mbt_guid["OCLP-Version"] = self.constants.mactoolbox_version
        mbt_guid["OCLP-Model"] = self.model

        # Boot GUID for boot args and SIP
        boot_guid = nvram.setdefault("7C436110-AB2A-4BBB-A880-FE41995C9F82", {})
        boot_args = boot_guid.get("boot-args", "")

        # Base boot-args (legacy build.py:72)
        if "-lilubetaall" not in boot_args:
            boot_args = (boot_args + " -lilubetaall").strip()
            self._log("  Added boot-arg: -lilubetaall")

        # Model-specific boot-args based on smbios_data
        model_info = smbios_data.smbios_dictionary.get(self.model, {})

        max_os = model_info.get("Max OS Supported", 0)
        cpu_gen = model_info.get("CPU Generation", 999)

        # -no_compat_check for legacy models
        if max_os and max_os < os_data.os_data.sonoma:
            if "-no_compat_check" not in boot_args:
                boot_args += " -no_compat_check"
                self._log("  Added boot-arg: -no_compat_check (legacy model)")

        # ipc_control_port_options=0 and -nokcmismatchpanic only when SIP lowered
        if not self.constants.sip_status:
            if "ipc_control_port_options=0" not in boot_args:
                boot_args += " ipc_control_port_options=0"
                self._log("  Added boot-arg: ipc_control_port_options=0")
            if "-nokcmismatchpanic" not in boot_args:
                boot_args += " -nokcmismatchpanic"
                self._log("  Added boot-arg: -nokcmismatchpanic")

        # AMFI handling (legacy security.py:76-86)
        # amfi=0x80 only when explicitly requested - it breaks TCC (Camera, Mic prompts)
        # AMFIPass.kext is the preferred approach (enabled in security kext manager)
        if getattr(self.constants, 'disable_amfi', False):
            if "amfi=" not in boot_args:
                boot_args += " amfi=0x80"
                self._log("  Added boot-arg: amfi=0x80 (AMFI disable - explicit)")

        # Verbose boot (legacy misc.py:347)
        if self.constants.verbose_debug:
            if "-v" not in boot_args:
                boot_args += " -v"
                self._log("  Added boot-arg: -v (verbose)")

        # Kext debug mode (legacy misc.py:351)
        if self.constants.kext_debug:
            for arg in ("-liludbgall", "liludump=90"):
                if arg not in boot_args:
                    boot_args += f" {arg}"
            self._log("  Added boot-args: -liludbgall liludump=90 (kext debug)")

        # Thread limit for MacPro3,1/Xserve2,1 (legacy firmware.py:208)
        if self.constants.force_quad_thread:
            if "cpus=" not in boot_args:
                boot_args += " cpus=4"
                self._log("  Added boot-arg: cpus=4 (thread limit)")

        # MBT-Settings flags (conditional on SIP status)
        if max_os and max_os < os_data.os_data.sonoma:
            mbt_guid.setdefault("OCLP-Settings", "")
            if not self.constants.sip_status:
                if "-allow_fv" not in mbt_guid["OCLP-Settings"]:
                    mbt_guid["OCLP-Settings"] += " -allow_fv"
            if self.constants.disable_cs_lv:
                if "-allow_amfi" not in mbt_guid["OCLP-Settings"]:
                    mbt_guid["OCLP-Settings"] += " -allow_amfi"

        # Bluetooth NVRAM variables and boot-args
        # Logic from MacBoxTool efi_builder/bluetooth.py (_prebuilt_assumption path)
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

        # SIP: conditional on sip_status and custom_sip_value (legacy security.py)
        if not self.constants.sip_status:
            sip_value = self.constants.custom_sip_value if self.constants.custom_sip_value else 0x803
            if isinstance(sip_value, str):
                sip_value = int(sip_value, 16) if sip_value.startswith("0x") else int(sip_value)
            boot_guid["csr-active-config"] = int(sip_value).to_bytes(4, "little")
            self._log(f"  Set csr-active-config: {hex(sip_value)}")

        # run-efi-updater (legacy smbios.py:257)
        boot_guid["run-efi-updater"] = "No"

        return self.log_lines
