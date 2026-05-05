# MacBoxTool

Python-based OpenCore EFI builder for genuine Macs and Hackintosh systems.

## Features

- **Hardware Detection**: Auto-detect CPU, GPU, chipset, Bluetooth, and more
- **EFI Building**: Generate OpenCore configurations based on detected hardware
- **macOS Installer**: Download and manage macOS installers
- **KDK/MetalLib**: Download and install Kernel Debug Kits and Metal libraries

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

## Architecture

```
MacBoxTool/
├── app_entry.py          # Entry point
├── constants.py          # Version & configuration hub
├── detections/           # Hardware detection
├── datasets/             # SMBIOS/CPU/Bluetooth data
├── efi_builder/          # EFI building logic
├── qt_gui/              # PySide6 GUI
└── UIkit/               # Custom UI component library
```

## License

GPL-3.0 · Copyright © 2020-2026 Pyquick
