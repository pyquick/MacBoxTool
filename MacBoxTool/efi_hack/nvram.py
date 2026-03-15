"""
nvram.py: NVRAM configuration for Hackintosh EFI

Sets boot-args, SIP (csr-active-config), system variables, and other NVRAM
entries required for a Hackintosh build.
References: https://dortania.github.io/OpenCore-Install-Guide/
"""

import logging

logger = logging.getLogger(__name__)

# OpenCore boot GUID
_BOOT_GUID = "7C436110-AB2A-4BBB-A880-FE41995C9F82"
# OEM / vendor info GUID
_OEM_GUID = "4D1FDA02-38C7-4A6A-9CC6-4BCCA8B30102"

# SIP values
# 0x00000000 — SIP fully enabled
# 0x00000803 — SIP disabled (kext loading + FS changes + debugging)
_SIP_ENABLED = bytes([0x00, 0x00, 0x00, 0x00])
_SIP_DISABLED = bytes([0x03, 0x08, 0x00, 0x00])


class HackNVRAM:
    """Configure NVRAM variables for Hackintosh."""

    def __init__(self, config: dict, constants, paths: dict,
                 cpu_gen: str = "", gpu_names: list | None = None):
        self.config = config
        self.constants = constants
        self.paths = paths
        # CPU gen used for AMD-specific boot-args
        self.cpu_gen = cpu_gen
        # List of GPU name strings for GPU-specific boot-args
        self.gpu_names: list[str] = [g.upper() for g in (gpu_names or [])]
        self.log_lines: list[str] = []

    def _log(self, msg: str):
        logger.info(msg)
        self.log_lines.append(msg)

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def apply(self) -> list[str]:
        """Apply all NVRAM settings."""
        self._log("[STEP] Setting NVRAM (Hackintosh)")

        nvram = self.config.setdefault("NVRAM", {})
        nvram_add = nvram.setdefault("Add", {})

        # -- Boot GUID (boot-args, SIP, language) --
        boot_guid = nvram_add.setdefault(_BOOT_GUID, {})

        boot_args = boot_guid.get("boot-args", "")
        boot_args = self._build_boot_args(boot_args)
        boot_guid["boot-args"] = boot_args.strip()

        self._set_sip(boot_guid)
        self._set_system_variables(boot_guid)

        # -- OEM / tool info GUID --
        oem_guid = nvram_add.setdefault(_OEM_GUID, {})
        oem_guid["OCLP-Version"] = self.constants.mactoolbox_version
        oem_guid["OCLP-Model"] = "Hackintosh"

        # Write NVRAM on every boot
        nvram["WriteFlash"] = getattr(self.constants, "nvram_write", True)

        return self.log_lines

    # ------------------------------------------------------------------
    # boot-args builder
    # ------------------------------------------------------------------

    def _build_boot_args(self, boot_args: str) -> str:
        """Compose boot-args string from constants and hardware state."""

        def add(args: str, arg: str) -> str:
            if arg not in args:
                args += f" {arg}"
                self._log(f"  boot-arg: {arg}")
            return args

        # Verbose boot (shows log during boot — useful for debugging)
        if self.constants.verbose_debug:
            boot_args = add(boot_args, "-v")

        # Kernel panic watchdog disable + symbol dump (debugging)
        if self.constants.opencore_debug:
            boot_args = add(boot_args, "debug=0x100")
            boot_args = add(boot_args, "keepsyms=1")

        # Lilu debug (only when kext_debug is explicitly requested)
        if self.constants.kext_debug:
            boot_args = add(boot_args, "-liludbgall")
            boot_args = add(boot_args, "liludump=90")

        # AMFIPass boot-arg
        boot_args = add(boot_args, "-amfipassbeta")

        # AMFI bypass (for custom kext loading)
        if getattr(self.constants, "disable_amfi", False):
            boot_args = add(boot_args, "amfi=0x80")

        # SIP lowered extras
        if not self.constants.sip_status:
            boot_args = add(boot_args, "ipc_control_port_options=0")

        # GPU-specific boot-args
        boot_args = self._add_gpu_boot_args(boot_args, add)

        # AMD-specific
        if self.cpu_gen in {"zen", "zen2", "zen3", "zen4"}:
            # npci=0x3000 is an alternative to "Above 4G Decoding" BIOS setting
            if getattr(self.constants, "amd_npci", False):
                boot_args = add(boot_args, "npci=0x3000")

        return boot_args

    def _add_gpu_boot_args(self, boot_args: str, add) -> str:
        """Add GPU-specific boot-args based on detected GPU."""
        gpu_str = " ".join(self.gpu_names)

        # Navi (RX 5000 / RX 6000): Board-ID check bypass
        if any(x in gpu_str for x in ("RX 5", "RX5", "NAVI10",
                                       "RX 6", "RX6", "NAVI21", "NAVI23")):
            boot_args = add(boot_args, "agdpmod=pikera")

        # AMD GPU DRM (unfairgva=1 enables AMDRadeonX6000 for HW decode)
        if any(x in gpu_str for x in ("VEGA", "POLARIS", "RX 5", "RX 6")):
            if getattr(self.constants, "amd_gpu_drm", False):
                boot_args = add(boot_args, "unfairgva=1")

        # Disable dGPU (e.g., unsupported Nvidia on macOS 12+)
        if getattr(self.constants, "disable_dgpu", False):
            boot_args = add(boot_args, "-wegnoegpu")

        return boot_args

    # ------------------------------------------------------------------
    # SIP
    # ------------------------------------------------------------------

    def _set_sip(self, boot_guid: dict):
        """Set SIP (csr-active-config) level."""
        if self.constants.sip_status:
            boot_guid["csr-active-config"] = _SIP_ENABLED
            self._log("  SIP: Enabled (0x00000000)")
        else:
            boot_guid["csr-active-config"] = _SIP_DISABLED
            self._log("  SIP: Disabled (0x00000803)")

    # ------------------------------------------------------------------
    # System NVRAM variables
    # ------------------------------------------------------------------

    def _set_system_variables(self, boot_guid: dict):
        """Set system-level NVRAM variables."""
        # Prevent macOS from updating EFI firmware (Hackintosh must not update)
        boot_guid["run-efi-updater"] = "No"
        self._log("  NVRAM: run-efi-updater=No (block firmware update)")

        # Keyboard language — empty string lets macOS show the language picker
        # on first boot; can be set to e.g. "en-US:0" to skip picker
        if not boot_guid.get("prev-lang:kbd"):
            boot_guid["prev-lang:kbd"] = getattr(
                self.constants, "keyboard_lang", ""
            )
            self._log("  NVRAM: prev-lang:kbd (keyboard language)")
