# MacBoxTool

Python-based OpenCore EFI builder for genuine Macs and Hackintosh systems.

## Features


- **EFI Building**: Creates a "universal translator" that helps macOS understand and work with your specific hardware combination. Since macOS is designed only for Apple's controlled ecosystem, the EFI (Extensible Firmware Interface) acts as a diplomatic interpreter, containing bootloader, configuration files, drivers (kexts), and ACPI tables. Without this, macOS would be like someone trying to drive a car they've never seen before - MacBoxTool automates this complex process to make Hackintosh building accessible.

- **macOS Installer**: Like having a "personal digital librarian" who instantly fetches and prepares any macOS version you need. Provides direct delivery service from Apple's servers with version management (Monterey, Ventura, Sonoma, etc.) for compatibility testing, and converts raw files into bootable USB installers. Simplifies the complex process of downloading gigabytes of data and creating bootable media - like Netflix for operating systems.

- **KDK/MetalLib**: Advanced tools for power users and developers. KDK (Kernel Debug Kits) acts as an "X-ray machine for operating systems," letting developers see kernel-level activity for troubleshooting, kext development, and crash analysis. MetalLib provides "high-performance graphics translation dictionaries" - Apple's graphics technology libraries that enable games and graphics-intensive apps to run smoothly. Essential for developers building drivers or optimizing the entire Hackintosh experience.

## Usage

### GUI Mode
```bash
python3.14 MaxBoxTool_GUI.command
```

### Command Line
```bash
python3.14 MaxBoxTool_GUI.command --probe-hardware      # Probe hardware
python3.14 MaxBoxTool_GUI.command --build-efi MacPro7,1 # Build EFI for model
python3.14 MaxBoxTool_GUI.command --version             # Show version
```

### Build Application Package
```bash
python3 Build-Project.command
```

## Requirements

- Python 3.10+
- PySide6
- [See requirements_macOS.txt](requirements_macOS.txt)
- Windows [See requirements_Windows.txt](requirements_Windows.txt)


## License

GPL-3.0 · Copyright © 2020-2026 Pyquick
