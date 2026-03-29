# MacBoxTool Feature Design — 2026-03-20

## Overview

Seven design sections covering five feature areas: AirportItlwm version selection, SSDTTime ACPI integration, hardware compatibility detection, hardware export/import, and Quick Start Guide enhancements. Sections 1-2 are shared infrastructure; sections 3-7 are user-facing features.

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

Field mapping from existing `device_probe`:
- `cpu.name` ← `computer.cpu.name` (str)
- `cpu.vendor` ← derived from `cpu.name` ("Intel"/"AMD" prefix detection)
- `cpu.generation` ← reuse `builder._detect_cpu_gen()` logic
- `cpu.core_count/thread_count` ← `computer.cpu.core_count` / `computer.cpu.thread_count` (may be None on some platforms, default 0)
- `cpu.flags` ← `computer.cpu.flags` (list, may need parsing from cpuid leafs)
- `gpu[].name` ← iterate `computer.gpus` list
- `gpu[].vendor` ← derived from GPU name or PCI vendor ID
- `network[].name/vendor/chipset` ← `computer.wifi` / `computer.ethernet` attributes
- `motherboard.*` ← `computer.motherboard` (if available, else empty strings)
- `memory.total_gb` ← `computer.memory` or system query
- Fields unavailable on a given platform default to empty string / 0 / empty list

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

**Unknown hardware fallback:** When hardware is not recognized (e.g., future Intel 15th gen, AMD RDNA4), `check_*()` methods return `CompatStatus.UNKNOWN` with message "Unrecognized hardware — check Dortania guide for latest compatibility info". `get_max_supported_macos()` treats UNKNOWN as non-blocking (does not lower the max version) but includes a warning note in the result. This allows the tool to degrade gracefully for new hardware without false negatives.

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

Multi-select dropdown on Build Hackintosh page. Only visible when Intel WiFi detected.

UIkit does not have a `CheckableComboBox`. Create a new `CheckableComboBox` widget in `MacBoxTool/UIkit/components/widgets/combo_box.py` extending `ComboBoxBase` — a button that opens a `RoundMenu` with `CheckBox` items. Selected items shown as comma-separated text on the button face.

Version mapping (matches actual payload naming in `payloads/Kexts/Wifi/`):

| Display Name       | Payload Zip                          | Kext Bundle Name              | MinKernel | MaxKernel |
|--------------------|--------------------------------------|-------------------------------|-----------|-----------|
| macOS 11 Big Sur   | AirportItlwm_BigSur-v{ver}.zip      | AirportItlwm_BigSur.kext      | 20.0.0    | 20.99.99  |
| macOS 12 Monterey  | AirportItlwm_Monterey-v{ver}.zip    | AirportItlwm_Monterey.kext    | 21.0.0    | 21.99.99  |
| macOS 13 Ventura   | AirportItlwm_Ventura-v{ver}.zip     | AirportItlwm_Ventura.kext     | 22.0.0    | 22.99.99  |
| macOS 14.0-14.3    | AirportItlwm_Sonoma14.0-v{ver}.zip  | AirportItlwm_Sonoma14.0.kext  | 23.0.0    | 23.3.99   |
| macOS 14.4+        | AirportItlwm_Sonoma14.4-v{ver}.zip  | AirportItlwm_Sonoma14.4.kext  | 23.4.0    | 23.99.99  |

Where `{ver}` is `constants.airportitlwm_version` (currently "2.3.0"). This replaces the old 4-version scheme (BigSur/Monterey/Ventura/Sonoma) with a 5-version scheme that splits Sonoma into 14.0 and 14.4.

Data flow: GUI multi-select → `HackintoshBuilder.build(airportitlwm_versions=[...])` → `HackKexts._select_wifi(target_macos_versions=[...])` → only selected kexts added with precise kernel ranges.

**`_select_wifi()` signature change:** Add `target_macos_versions: list[str] | None = None` parameter. The existing 4-version hardcoded dict is replaced with the new 5-version `AIRPORTITLWM_MAP` constant. Fallback behavior: when `target_macos_versions` is None (non-GUI / legacy call), all 5 versions are added (preserving current "add everything" behavior). When it's an empty list, no AirportItlwm kexts are added (user explicitly deselected all).

---

## 5. SSDTTime Integration

**New file:** `MacBoxTool/efi_hack/ssdt_generator.py`

Wraps SSDTTime (`payloads/Scripts/SSDTTime-master/`) via Python import with an adapter layer.

**Adapter approach:** SSDTTime's `SSDT` class has interactive console methods (`plugin_type()`, `fake_ec()`, `fix_hpet()`, `ssdt_pmc()`, etc.) that use `input()` for user prompts and `print()` for output. The adapter:
- Adds `payloads/Scripts/SSDTTime-master/` to `sys.path` and imports `SSDTTime.SSDT` and `Scripts.dsdt.DSDT`
- Monkey-patches `Scripts.utils.Utils.grab()` and `Scripts.utils.Utils.head()` to no-op (suppress interactive prompts)
- Redirects `print()` via `contextlib.redirect_stdout` to capture output as log
- Calls SSDTTime's internal methods directly, mapping: `generate_plug()` → `ssdt.plugin_type()`, `generate_ec()` → `ssdt.fake_ec()`, `generate_hpet()` → `ssdt.fix_hpet()`, etc.

**iasl compiler:** Bundled in `payloads/Scripts/SSDTTime-master/Scripts/iasl` (auto-downloaded by SSDTTime's `downloader.py` on first use). `SSDTGenerator.__init__()` calls `ssdt.d.check_iasl()` to ensure iasl is available; if missing, triggers download from Acidanthera's MaciASL repo.

**DSDT acquisition (`auto_dump_dsdt()`):**
- macOS: `ioreg -lw0 -p IODeviceTree -n ACPI -r` → extract DSDT binary from IOKit registry → save to `{temp_dir}/DSDT.aml`. Does NOT require root on macOS (IOKit ACPI tables are readable by user). If SIP blocks access, falls back to prompting user for manual upload.
- Windows: reserved interface using `acpidump.exe` (not implemented yet, returns None)
- Dumped DSDT stored in `tempfile.mkdtemp()`, cleaned up on `SSDTGenerator` destruction

```python
class SSDTGenerator:
    # DSDT acquisition
    auto_dump_dsdt() -> str | None  # Returns path or None on failure
    load_dsdt(path: str)            # Manual upload
    has_dsdt() -> bool

    # Individual SSDT generation (adapter methods)
    generate_plug() -> SSDTResult      # → ssdt.plugin_type()
    generate_ec() -> SSDTResult        # → ssdt.fake_ec()
    generate_hpet() -> SSDTResult      # → ssdt.fix_hpet()
    generate_usbx() -> SSDTResult      # → ssdt.ssdt_usbx()
    generate_pmc() -> SSDTResult       # → ssdt.ssdt_pmc()
    generate_rtcawac() -> SSDTResult   # → ssdt.ssdt_awac()
    generate_rhub() -> SSDTResult      # → ssdt.ssdt_rhub()
    generate_xosi() -> SSDTResult      # → ssdt.ssdt_xosi()
    generate_pnlf() -> SSDTResult      # → ssdt.ssdt_pnlf()
    generate_dmar() -> SSDTResult      # → ssdt.fix_dmar()
    generate_smbus() -> SSDTResult     # → ssdt.smbus()
    generate_imei() -> SSDTResult      # → ssdt.imei_bridge()

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

Import validation: requires `cpu` field. GPU is optional (headless server builds use `MacPro7,1` SMBIOS with no discrete GPU). Missing optional fields default to empty lists/dicts.

Wizard Mode integration: new `_choose_source()` step before `_validate_hardware()`:
- "Detect Current Hardware" → existing flow
- "Import Hardware JSON" → load JSON → replace detection data → continue wizard

**Override mechanism:** `HardwareInfo` import creates a shadow `HardwareInfo` instance stored on the wizard dialog (`self._imported_hw`). Wizard methods check `self._imported_hw` first; if None, fall back to `HardwareInfo.from_device_probe(constants)`. The override is scoped to the wizard dialog lifetime — no mutation of `constants.computer`. The build worker receives the resolved `HardwareInfo` as a parameter, avoiding thread-safety issues.

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
| MODIFY | `MacBoxTool/UIkit/components/widgets/combo_box.py` — add `CheckableComboBox` widget |
| MODIFY | `MacBoxTool/efi_hack/kexts.py` — `_select_wifi()` accepts `target_macos_versions` |
| MODIFY | `MacBoxTool/efi_hack/builder.py` — pass `airportitlwm_versions` + SSDT generator |
| MODIFY | `MacBoxTool/qt_gui/gui_build_hackintosh.py` — add AirportItlwm multi-select dropdown |
| MODIFY | `MacBoxTool/qt_gui/gui_build_wizard.py` — add import source selection step |
| MODIFY | `MacBoxTool/qt_gui/gui_introduction.py` — add 4 Quick Start Guide cards |
| NEW | `MacBoxTool/detections/__init__.py` — create and export `hardware_info` |
| NEW | `MacBoxTool/datasets/__init__.py` — create and export `compatibility_data` |
| MODIFY | `MacBoxTool/UIkit/components/widgets/__init__.py` — export `CheckableComboBox` |
