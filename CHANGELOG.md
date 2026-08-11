# Changelog

## Nightly (0.0.4)

### Build 4636.2 (2026-08-11)
- FIX

### Build 4636.1 (2026-08-11)
- FIX

### Build 4635.5 (2026-08-11)
- FIX

### Build 4635.4 (2026-08-11)
- CLI `--cache_os`: added offline KDK/Metallib caching for staged macOS updates
- Hardware patchset detection integration for cache handler

### Build 4635.1 (2026-08-10)
- OCLP data sync
- Removed local crash report module

### Build 4431.1 (2026-08-10)
- OCLP data sync

### Build 4630.1 (2026-08-10)
- OCLP data sync

### Build 4624.1 (2026-08-09)
- Added `icon_to_assets.py` utility for icon asset generation
- OCLP data sync

### Build 4618.1 (2026-08-07)
- OCLP data sync

### Build 4611.4 (2026-08-07)
- Added `gui_converter.py` module
- Updated introduction page, hardware support page
- OCLP data sync

### Build 4611.1 (2026-08-07)
- OCLP data sync

### Build 4604.1 (2026-08-07)
- OCLP data sync

### Build 4599.1 (2026-08-06)
- OCLP data sync

### Build 4592.1 (2026-08-05)
- OCLP data sync

### Build 4584.1 (2026-08-04)
- OCLP data sync
- UI component updates (navigation panel, theme listener)

### Build 4582.6 (2026-08-03)
- OCLP data sync
- Navigation panel refinements

### Build 4582.1 (2026-08-03)
- OCLP data sync

### Build 4574.1 (2026-08-01)
- OCLP data sync

### Build 45743.4 (2026-07-31)
- OCLP data sync

### Build 4573.1 (2026-07-29)
- OCLP data sync

### Build 4568.2 (2026-07-29)
- OCLP data sync
- Added `UIkit/common/border_radius.py`

### Build 4568.1 (2026-07-28)
- OCLP data sync

### Build 4565.1 (2026-07-27)
- OCLP data sync

### Build 4562.1 (2026-07-26)
- OCLP data sync

### Build 4558.1200 (2026-07-25)
- OCLP data sync

### Build 4558.1000 (2026-07-24)
- OCLP data sync

### Build 4552.1200 (2026-07-24)
- OCLP data sync

### Build 4552.1000 (2026-07-24)
- OCLP data sync

### Build 4547.1000 (2026-07-22)
- OCLP data sync
- Windows setup/build support (added `setup/` directory with Windows spec, setup wizard)

### Build 4544.1000 (2026-07-22)
- Added hardware compatibility checker modules (CPU, GPU, audio, board, disk, memory, WLAN)
- Added `global_settings.py`
- OCLP data sync

### Build 4438.1000 (2026-07-12)
- Added macOS 11 (Big Sur) support

### Build 4535.1000 (2026-07-12)
- OCLP data sync

### Build 4532.1000 (2026-07-11)
- UI visual refresh

### Build 4528.1000 (2026-07-10)
- Added `metallib_handler.py` for MetallibSupportPkg resolution in root patching
- Added patch settings UI
- Cleaned up OCLP device ID handling
- Expanded system patching support

### Build 4522.1000 (2026-07-06)
- Added root-patch system (`sys_patch/` module):
  - Kernel collection handling (kernelcache, mkext, prelinked)
  - Auto patcher (install & start)
  - Hardware patchsets: AMD (Legacy GCN, Navi, Polaris, TeraScale 1/2, Vega), Intel (Broadwell, Haswell, Iron Lake, Ivy Bridge, Sandy Bridge, Skylake), NVIDIA (Kepler, Tesla, WebDriver)
  - Shared patches: Metal 3802, non-Metal GPU, OpenCL, GVA, WebKit
  - Audio patches: legacy/modern/Voodoo audio
  - USB patches: legacy USB 1.1, modern USB
  - Misc patches: CPU missing AVX, display backlight, GMUX, keyboard backlight, PCIe webcam, T1 security
  - Networking: legacy/modern wireless
  - DMG mount & KDK merge utilities
  - System snapshot handling

### Build 4508 (2026-07-04)
- First nightly build of 0.0.4
- Updated app icons (PkgBackground & AppIcon)

---

## Releases

### 0.0.3.2 (2026-06-30)
- Fix update bugs
- API migration: update required as older versions may become obsolete

### 0.0.3.1 (2026-06-28)
- OCLP data sync to build 4413.1100

### 0.0.3 (2026-06-27)
- Added **Updater**: download & install updates from within the app
- GitHub Access Token support for downloading KDK, Metallib & updates
- Faster app startup
- Improved stability
- Fixed KDK & Metallib loading bugs

### 0.0.2 (2026-05-04)
- Added Nightly update channel
- Added About page
- Fixed macOS installers extraction bugs

### 0.0.1 (2026-04-29)
- First release for testing
