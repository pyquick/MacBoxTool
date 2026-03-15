# Hackintosh EFI Builder Enhancement Plan

**Date:** 2026-03-15
**Target:** Fix bugs and enhance efi_hack module

---

## Requirements

1. Fix ACPI not added to config.plist
2. Add USBInjectAll.kext
3. RTL8125 → SimpleRTK5.kext
4. RTL8111 → RealtekRTL8111.kext (verify)
5. Add AMFIPass.kext
6. Add `-amfipassbeta` boot-arg
7. Intel ethernet support (I217/I218/I219/I211/I225/I226)
8. AirportItlwm multi-version (Big Sur to Sonoma 14.4)
9. Improve cleanup
10. Remove wizard mode from efi_mac
11. Test build

---

## Phase 1: ACPI Bug Fix

**File:** `efi_hack/acpi.py`, `efi_mac/acpi/base.py`

**Issue:** ACPI files not added to config.plist
**Fix:** Verify `ACPIManager.add_acpi()` updates config dict

---

## Phase 2: Kexts

**File:** `efi_hack/kexts.py`

### 2.1 USBInjectAll
```python
# In _add_usb_kexts()
self.kext_mgr.enable_kext("USBInjectAll.kext", "0.7.1")
```

### 2.2 AMFIPass
```python
# New method _add_security_kexts()
self.kext_mgr.enable_kext("AMFIPass.kext", "1.4.0")
```

### 2.3 RTL8125 → SimpleRTK5
```python
_REALTEK_ETH_MAP = {
    "RTL8111": "RealtekRTL8111.kext",
    "RTL8125": "SimpleRTK5.kext",  # Changed
}
```

### 2.4 Intel Ethernet
```python
_INTEL_ETH_MAP = {
    "I217": "IntelMausiEthernet.kext",
    "I218": "IntelMausiEthernet.kext",
    "I219": "IntelMausiEthernet.kext",
    "I211": "AppleIGB.kext",
    "I225": "AppleIGC.kext",
    "I226": "AppleIGC.kext",
}
```

---

## Phase 3: NVRAM

**File:** `efi_hack/nvram.py`

```python
# In _build_boot_args()
if getattr(self.constants, "use_amfipass", False):
    boot_args = add(boot_args, "-amfipassbeta")
```

---

## Phase 4: AirportItlwm

**File:** `efi_hack/kexts.py`

```python
def _select_wifi(self):
    if "INTEL" in wifi_str:
        versions = ["BigSur", "Monterey", "Ventura", "Sonoma"]
        for ver in versions:
            enabled = self._match_macos_version(ver)
            self.kext_mgr.enable_kext(f"AirportItlwm_{ver}.kext", "2.3.0", enabled)
```

---

## Phase 5: Cleanup

**File:** `efi_mac/config.py`

Ensure cleanup() removes all disabled entries from:
- Kernel/Add
- UEFI/Drivers
- ACPI/Add
- Misc/Tools

---

## Phase 6: Remove Wizard

**File:** `efi_mac/builder.py`

Delete methods (lines 37-121):
- `validate_hardware_compatibility()`
- `select_build_components()`

---

## Constants to Add

**File:** `constants.py`

```python
self.intelmausi_version = "1.0.7"
self.appleigb_version = "1.0.0"
self.appleigc_version = "1.1.0"
self.usbinjectall_version = "0.7.1"
self.amfipass_version = "1.4.0"
```

---

## Testing

**Per Phase:**
1. ACPI: Verify entries in config.plist
2. Kexts: Check Kernel/Add section
3. Intel: Mock detection, verify kext
4. NVRAM: Check boot-args
5. AirportItlwm: Verify all versions
6. Cleanup: Test removal
7. Wizard: No errors after deletion

**Integration:**
```bash
python3.14 MaxToolBox_GUI.command
```

---

## Files Modified

- `efi_hack/kexts.py`
- `efi_hack/nvram.py`
- `efi_hack/acpi.py`
- `efi_mac/acpi/base.py`
- `efi_mac/config.py`
- `efi_mac/builder.py`
- `constants.py`

---

## Sources

- [Intel Ethernet Research 2026](https://github.com/acidanthera)
- [Dortania OpenCore Guide](https://dortania.github.io/OpenCore-Install-Guide/)
