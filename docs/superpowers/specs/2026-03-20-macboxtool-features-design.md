# MacBoxTool Feature Design — 2026-03-20

## Overview

Five features for MacBoxTool: AirportItlwm version selection, SSDTTime ACPI integration, hardware compatibility detection, hardware export/import, and Quick Start Guide enhancements.

Architecture: **Modular with shared data layer** — a unified `HardwareInfo` model shared across compatibility checking, export/import, and wizard mode.

---

## 1. Shared Hardware Data Model

**File:** `MacBoxTool/detections/hardware_info.py`

Foundation layer. Wraps existing `device_probe` / `constants.computer` data into a serializable model.

```
HardwareInfo (dataclass)
├── cpu: CpuInfo (name, vendor, generation, core_count, thread_count, flags)
├── gpu: list[GpuInfo] (name, vendor, family, device_id, is_igpu)
├── network: list[NetworkInfo] (name, type, vendor, chipset)
├── storage: list[StorageInfo] (name, type, model)
├── motherboard: MotherboardInfo (vendor, model, chipset)
├── memory: MemoryInfo (total_gb)
├── acpi_paths: dict  # macOS only — EC, HPET paths etc.
└── io_paths: dict    # IOKit registry paths, macOS only
```

Methods:
- `from_device_probe(constants)` — bridge existing detection data
- `from_json(json_str)` / `to_json()` — serialization
- `to_clipboard()` / `from_clipboard()` — clipboard support via `QApplication.clipboard()`

Key decisions:
- `acpi_paths` and `io_paths` are empty dicts on Windows
- Does NOT contain compatibility logic (that lives in `compatibility_data.py`)
- `from_device_probe()` bridges without refactoring `device_probe`

---

## 2. Hardware Compatibility Database

**File:** `MacBoxTool/datasets/compatibility_data.py`

Based on Dortania OpenCore Install Guide. Maps hardware → macOS support status.

```python
class CompatStatus(Enum):
    SUPPORTED    = "supported"     # Green
    PARTIAL      = "partial"       # Yellow
    UNSUPPORTED  = "unsupported"   # Red
    UNKNOWN      = "unknown"       # Gray

@dataclass
class CompatResult:
    status: CompatStatus
    message: str
    max_macos: str | None
    min_macos: str | None
    notes: list[str]
    kexts_needed: list[str]
```

`CompatibilityChecker` class with methods:
- `check_cpu(cpu)` — Intel 1st gen+ supported, AMD Zen desktop partial, AMD laptop unsupported
- `check_gpu(gpu)` — Polaris/Vega/Navi supported, RDNA3 unsupported, NVIDIA Maxwell+ unsupported, Kepler max Big Sur
- `check_storage(storage)` — Samsung PM981/PM991 unsupported, Intel Optane unsupported
- `check_network(net)` — Broadcom native, Intel WiFi partial (AirportItlwm), Realtek WiFi unsupported
- `check_all(hw)` — returns `dict[str, CompatResult]`
- `get_max_supported_macos(hw)` — returns highest macOS version all hardware supports

CPU data covers all generations: nehalem through raptor_lake (Intel), zen through zen4 (AMD desktop only). All Intel 1st gen Core i (Nehalem/Lynnfield/Westmere) marked SUPPORTED.

---

## 3. Hardware Compatibility UI

**File:** `MacBoxTool/qt_gui/gui_hardware_compat.py`

Card-list dialog with simple/detailed toggle.

**Simple mode:** CpuCard + GpuCard(s) only
**Detailed mode:** All cards — CPU, GPU, Storage, Network, Motherboard, ACPI (macOS only)

Each card shows:
- Icon + category label
- StatusBadge (green ✓ / yellow ⚠ / red ✗)
- Hardware name and key info
- Compatibility message
- [Detailed] Notes, min/max macOS, required kexts/patches

Header: title, simple/detailed toggle, overall status badge, export button
Footer: Import JSON, Copy to Clipboard, Continue to Wizard

StatusBadge color mapping:
- SUPPORTED → green + FluentIcon.ACCEPT
- PARTIAL → yellow + FluentIcon.WARNING
- UNSUPPORTED → red + FluentIcon.CLOSE
- UNKNOWN → gray + FluentIcon.QUESTION

---

## 4. AirportItlwm Version Selection

**Modified files:** `MacBoxTool/qt_gui/gui_build_hackintosh.py`, `MacBoxTool/efi_hack/kexts.py`

Multi-select dropdown (CheckableComboBox) on Build Hackintosh page. Only visible when Intel WiFi detected.

Version mapping:

| Display Name       | Kext File             | MinKernel | MaxKernel |
|--------------------|-----------------------|-----------|-----------|
| macOS 11 Big Sur   | AirportItlwm_11.kext  | 20.0.0    | 20.99.99  |
| macOS 12 Monterey  | AirportItlwm_12.kext  | 21.0.0    | 21.99.99  |
| macOS 13 Ventura   | AirportItlwm_13.kext  | 22.0.0    | 22.99.99  |
| macOS 14.0-14.3    | AirportItlwm_14.kext  | 23.0.0    | 23.3.99   |
| macOS 14.4+        | AirportItlwm_144.kext | 23.4.0    | 23.99.99  |

Data flow: GUI multi-select → `HackintoshBuilder.build(airportitlwm_versions=[...])` → `HackKexts._select_wifi(target_macos_versions=[...])` → only selected kexts added with precise kernel ranges.

---

## 5. SSDTTime Integration

**New file:** `MacBoxTool/efi_hack/ssdt_generator.py`

Wraps SSDTTime (`payloads/Scripts/SSDTTime-master/`) via Python import (no subprocess).

```python
class SSDTGenerator:
    # DSDT acquisition
    auto_dump_dsdt() -> str      # macOS: ioreg; Windows: reserved interface
    load_dsdt(path: str)         # Manual upload

    # Individual SSDT generation
    generate_plug/ec/hpet/usbx/pmc/rtcawac/rhub/xosi/pnlf/dmar/smbus/imei()

    # Smart auto-selection
    auto_generate(hw: HardwareInfo, is_laptop: bool) -> list[SSDTResult]

    # Config integration
    merge_to_config(results, config_mgr)

@dataclass
class SSDTResult:
    name: str           # "SSDT-PLUG"
    aml_path: str       # compiled .aml path
    dsl_source: str     # ASL source
    patches: list[dict] # OpenCore ACPI/Patch entries
    success: bool
```

`auto_generate()` logic:
- All platforms: PLUG, EC, USBX
- 300-series: PMC
- 400-series+: RHUB, RTCAWAC
- Laptop: PNLF, ALS0
- Sandy/Ivy Bridge: IMEI
- DMAR issues: DMAR

Three integration modes:
1. **Wizard auto:** auto_dump → auto_generate → merge_to_config (fully automatic)
2. **Guide manual:** user chooses dump/upload → select SSDTs → generate → export
3. **Builder fallback:** if DSDT available use SSDTGenerator, otherwise fall back to static SSDTs in `acpi.py`

---

## 6. Hardware Export/Import

Uses `HardwareInfo` serialization from Section 1.

**Export:** JSON file (via file dialog) or clipboard copy
**Import:** JSON file (via file dialog) or clipboard paste

JSON format includes `version: "1.0"`, `exported_at`, `platform`, and all hardware fields.

Import validation: requires at least `cpu` and one `gpu` entry.

Wizard Mode integration: new `_choose_source()` step before `_validate_hardware()`:
- "Detect Current Hardware" → existing flow
- "Import Hardware JSON" → load JSON → replace detection data → continue wizard

Imported data temporarily overrides `constants.computer` without affecting original detection.

---

## 7. Quick Start Guide Enhancements

**Modified file:** `MacBoxTool/qt_gui/gui_introduction.py`

Four new cards added BEFORE existing Build/Settings/About entries:

1. **Check Compatibility** → opens HardwareCompatDialog (simple mode), auto-detects hardware
2. **ACPI Patching** → opens ACPI guide dialog: dump/upload DSDT → show available SSDTs → generate → export
3. **WiFi Setup** → opens WiFi config dialog: detect WiFi hardware → AirportItlwm version multi-select (Intel) / native info (Broadcom) / replacement suggestion (unsupported)
4. **Export/Import Hardware** → opens export/import dialog: export current / import file / paste clipboard → continue to wizard

Each card uses UIkit `HeaderCardWidget` or similar component with icon, title, and description.

---

## File Change Summary

| Action | File |
|--------|------|
| NEW | `MacBoxTool/detections/hardware_info.py` |
| NEW | `MacBoxTool/datasets/compatibility_data.py` |
| NEW | `MacBoxTool/qt_gui/gui_hardware_compat.py` |
| NEW | `MacBoxTool/efi_hack/ssdt_generator.py` |
| MODIFY | `MacBoxTool/efi_hack/kexts.py` — `_select_wifi()` accepts `target_macos_versions` |
| MODIFY | `MacBoxTool/efi_hack/builder.py` — pass `airportitlwm_versions` + SSDT generator |
| MODIFY | `MacBoxTool/qt_gui/gui_build_hackintosh.py` — add AirportItlwm multi-select dropdown |
| MODIFY | `MacBoxTool/qt_gui/gui_build_wizard.py` — add import source selection step |
| MODIFY | `MacBoxTool/qt_gui/gui_introduction.py` — add 4 Quick Start Guide cards |
