# OpenCore 黑苹果 EFI 配置完整指南

> 基于 Dortania OpenCore Install Guide (https://dortania.github.io/OpenCore-Install-Guide/)
> 生成日期: 2026-03-14

---

## 一、EFI 目录结构

```
EFI/
├── BOOT/
│   └── BOOTx64.efi          # OpenCore 引导加载器
└── OC/
    ├── ACPI/                 # SSDT/DSDT 补丁文件 (.aml)
    ├── Drivers/              # UEFI 固件驱动 (.efi)
    ├── Kexts/                # 内核扩展 (.kext)
    ├── Resources/            # 引导界面资源 (图标/字体)
    ├── Tools/                # UEFI 工具 (Shell 等)
    └── config.plist          # OpenCore 主配置文件
```

---

## 二、UEFI 固件驱动 (Drivers)

### 所有系统必需

| 驱动 | 用途 |
|------|------|
| **HfsPlus.efi** | HFS+ 卷支持 (macOS 安装器、恢复分区) |
| **OpenRuntime.efi** | NVRAM 修复、内存管理 (替代 AptioMemoryFix) |

### 可选 / 传统系统

| 驱动 | 适用场景 |
|------|----------|
| HfsPlusLegacy.efi | 无 RDRAND 指令的旧 CPU (Sandy Bridge 及更早) |
| OpenUsbKbDxe.efi | DuetPkg 传统 BIOS 系统的 USB 键盘 |
| OpenPartitionDxe.efi | OS X 10.7-10.9 恢复分区 |
| OpenCanopy.efi | 图形化引导选择界面 |
| ResetNvramEntry.efi | NVRAM 重置选项 |
| OpenLinuxBoot.efi | Linux 引导支持 |

---

## 三、内核扩展 (Kexts) 分类

### 3.1 必备 Kext (所有系统)

| Kext | 用途 |
|------|------|
| **Lilu.kext** | 补丁框架，绝大多数 kext 的依赖 |
| **VirtualSMC.kext** | SMC 芯片模拟，macOS 不安装此 kext 无法启动 |

### 3.2 VirtualSMC 传感器插件

| 插件 | 用途 | 适用 |
|------|------|------|
| SMCProcessor | Intel CPU 温度监控 | Intel 台式机/笔记本 |
| SMCAMDProcessor | AMD Zen CPU 温度 | AMD |
| SMCRadeonSensors | AMD GPU 温度 | 10.14+ |
| SMCSuperIO | 风扇转速监控 | 台式机 |
| SMCLightSensor | 环境光传感器 | 笔记本 |
| SMCBatteryManager | 电池读数 | 笔记本 |
| SMCDellSensors | Dell 风扇控制 | Dell 系统 |

### 3.3 显卡

| Kext | 用途 |
|------|------|
| **WhateverGreen.kext** | GPU 补丁、DRM 修复、帧缓冲修复、Board-ID 检查绕过 |

### 3.4 音频

| Kext | 用途 |
|------|------|
| **AppleALC.kext** | AppleHDA 补丁，支持板载音频编解码器 |
| VoodooHDA | 传统替代方案 (10.6+) |

### 3.5 有线网络

| Kext | 支持的网卡 |
|------|-----------|
| **IntelMausi** | Intel 82578/82579/I217/I218/I219 (10.9+) |
| SmallTreeIntel82576 | Intel I211 (10.9-12) |
| AppleIGB | Intel I211 (12+) |
| RealtekRTL8111 | Realtek 千兆网卡 (10.8+) |
| LucyRTL8125Ethernet | Realtek 2.5Gb (10.15+) |
| AtherosE2200Ethernet | Atheros/Killer 网卡 (10.8+) |

### 3.6 WiFi 和蓝牙

| Kext | 用途 |
|------|------|
| AirportItlwm | Intel WiFi，原生恢复模式 (10.13+，需 Secure Boot) |
| Itlwm | Intel WiFi，无需 Secure Boot (需 Heliport) |
| IntelBluetoothFirmware | Intel 蓝牙固件 (10.13+) |
| AirportBrcmFixup | 非原装 Broadcom WiFi (10.10+) |
| BrcmPatchRAM3 | Broadcom 蓝牙固件 (10.15+) |
| BlueToolFixup | macOS 12+ 第三方蓝牙 |

### 3.7 USB

| Kext | 用途 |
|------|------|
| USBToolBox | USB 端口映射工具 + kext |
| XHCI-unsupported | 非原生 USB 控制器 (H370/B360/H310/Z390/X79/X99) |

### 3.8 笔记本输入

| Kext | 用途 |
|------|------|
| VoodooPS2 | PS2 键盘、鼠标、触控板 |
| VoodooI2C + 插件 | I2C 触控板 (HID/ELAN/FTE/Atmel/Synaptics) |
| VoodooRMI | Synaptics SMBus 触控板 |
| VoodooSMBus | ELAN SMBus 触控板 |
| ECEnabler | 电池状态修复 |
| BrightnessKeys | 亮度快捷键修复 |

### 3.9 辅助 Kext

| Kext | 用途 |
|------|------|
| AppleMCEReporterDisabler | AMD (12.3+) 和双路 Intel 必需 |
| CpuTscSync | HEDT/服务器主板 TSC 同步 |
| NVMeFix | NVMe 电源管理 (10.14+) |
| RestrictEvents | macOS 各种限制修补 |
| CPUFriend | CPU 电源管理调整 |
| CryptexFixup | Rosetta Cryptex 支持 (pre-AVX2.0) |

---

## 四、ACPI 补丁 (SSDT) — 按平台

### 4.1 Intel 台式机

| 平台 | CPU 电源管理 | EC | AWAC | NVRAM | USB | 其他 |
|------|------------|----|----- |-------|-----|------|
| Penryn | N/A | SSDT-EC | -- | -- | -- | -- |
| Sandy Bridge | CPU-PM (安装后) | SSDT-EC | -- | -- | -- | -- |
| Ivy Bridge | CPU-PM (安装后) | SSDT-EC | -- | -- | -- | SSDT-IMEI (6系芯片组) |
| Haswell | SSDT-PLUG | SSDT-EC | -- | -- | -- | -- |
| Broadwell | SSDT-PLUG | SSDT-EC | -- | -- | -- | -- |
| Skylake | SSDT-PLUG | SSDT-EC-USBX | -- | -- | -- | -- |
| Kaby Lake | SSDT-PLUG | SSDT-EC-USBX | SSDT-AWAC | SSDT-PMC | -- | -- |
| Coffee Lake | SSDT-PLUG | SSDT-EC-USBX | SSDT-AWAC | SSDT-PMC | -- | -- |
| Comet Lake | SSDT-PLUG | SSDT-EC-USBX | SSDT-AWAC | -- | SSDT-RHUB | -- |

### 4.2 Intel HEDT

| 平台 | CPU 电源管理 | EC | RTC | 其他 |
|------|------------|----|----- |------|
| Ivy Bridge-E | N/A | SSDT-EC | -- | SSDT-UNC |
| Haswell-E | SSDT-PLUG | SSDT-EC-USBX | SSDT-RTC0-RANGE | SSDT-UNC |
| Broadwell-E | SSDT-PLUG | SSDT-EC-USBX | SSDT-RTC0-RANGE | -- |
| Skylake-X | SSDT-PLUG | SSDT-EC-USBX | SSDT-RTC0-RANGE | -- |

### 4.3 Intel 笔记本

| 平台 | CPU PM | EC | 背光 | I2C | AWAC | NVRAM | IRQ | IMEI |
|------|--------|----|----- |-----|------|-------|-----|------|
| Ivy Bridge | CPU-PM | SSDT-EC | SSDT-PNLF | -- | -- | -- | IRQ SSDT | SSDT-IMEI (6系) |
| Haswell | SSDT-PLUG | SSDT-EC | SSDT-PNLF | SSDT-GPI0 | -- | -- | -- | -- |
| Broadwell | SSDT-PLUG | SSDT-EC | SSDT-PNLF | SSDT-GPI0 | -- | -- | -- | -- |
| Skylake | SSDT-PLUG | SSDT-EC-USBX | SSDT-PNLF | SSDT-GPI0 | -- | -- | -- | -- |
| Coffee Lake (8代) | SSDT-PLUG | SSDT-EC-USBX | SSDT-PNLF | SSDT-GPI0 | SSDT-AWAC | -- | -- | -- |
| Coffee Lake (9代) | SSDT-PLUG | SSDT-EC-USBX | SSDT-PNLF | SSDT-GPI0 | SSDT-AWAC | SSDT-PMC | -- | -- |
| Comet Lake | SSDT-PLUG | SSDT-EC-USBX | SSDT-PNLF | SSDT-GPI0 | SSDT-AWAC | SSDT-PMC | -- | -- |

### 4.4 AMD

| 平台 | EC | USB | 其他 |
|------|----|-----|------|
| AMD 15h/16h | SSDT-EC | -- | -- |
| AMD 17h/19h (Zen) | SSDT-EC-USBX | -- | SSDT-CPUR (仅 B550/A520) |

### SSDT 说明

| SSDT 文件 | 作用 |
|-----------|------|
| SSDT-PLUG | CPU 电源管理 (XCPM，Haswell+) |
| SSDT-EC / SSDT-EC-USBX | 嵌入式控制器 + USB 电源 (Skylake+ 包含 USBX) |
| SSDT-AWAC | 禁用 AWAC 时钟，启用传统 RTC |
| SSDT-PMC | 启用 NVRAM 支持 (300 系芯片组) |
| SSDT-PNLF | 笔记本背光控制 |
| SSDT-GPI0 | I2C 触控板 GPIO 中断 |
| SSDT-IMEI | IMEI 设备修复 (6 系芯片组配 Ivy Bridge CPU) |
| SSDT-RHUB | USB 根集线器重置 (Comet Lake) |
| SSDT-UNC | 禁用未使用的 ACPI 设备 (Ivy/Haswell-E) |
| SSDT-RTC0-RANGE | RTC 范围修复 (HEDT) |
| SSDT-CPUR | CPU 定义修复 (AMD B550/A520) |

---

## 五、DeviceProperties — iGPU 配置

### 5.1 台式机 iGPU

路径: `PciRoot(0x0)/Pci(0x2,0x0)`

| 平台 | AAPL,ig-platform-id (显示) | AAPL,ig-platform-id (仅加速) | device-id 欺骗 | 帧缓冲补丁 |
|------|--------------------------|-------------------------------|---------------|-----------|
| **Ivy Bridge** | `0A006601` | `07006201` | -- | -- |
| **Haswell HD 4600** | `0300220D` | -- | -- | stolenmem: `00003001`, fbmem: `00009000` |
| **Haswell HD 4400** | `0300220D` | -- | `12040000` | stolenmem: `00003001`, fbmem: `00009000` |
| **Skylake HD 530** | `00001219` | `01001219` | -- | stolenmem: `00003001`, fbmem: `00009000` |
| **Skylake HD P530** | `00001219` | `01001219` | `1B190000` | stolenmem: `00003001`, fbmem: `00009000` |
| **Coffee Lake UHD 630** | `07009B3E` | `0300913E` | -- | stolenmem: `00003001` |
| **Comet Lake UHD 630** | `07009B3E` | `0300C89B` | -- | stolenmem: `00003001` |

需 `framebuffer-patch-enable`: `01000000` 来启用帧缓冲内存补丁。

### 5.2 笔记本 iGPU

| 平台 | AAPL,ig-platform-id | device-id 欺骗 | 备注 |
|------|---------------------|---------------|------|
| **Ivy Bridge** (<=1366x768) | `03006601` | -- | -- |
| **Ivy Bridge** (>=1600x900) | `04006601` | -- | 需帧缓冲补丁 |
| **Haswell HD 5000/5100/5200** | `0500260A` | -- | cursor mem: `00009000` |
| **Haswell HD 4200/4400/4600** | `0600260A` | `12040000` | cursor mem: `00009000` |
| **Skylake HD 520/530/540** | `00001619` | -- | -- |
| **Skylake HD 510** | `00001B19` | `02190000` | -- |
| **Coffee Lake UHD 630** | `0900A53E` | -- | -- |
| **Coffee Lake UHD 620** | `00009B3E` | `9B3E0000` | 需 device-id 欺骗 |

### 5.3 音频 DeviceProperties

推荐使用 boot-arg `alcid=xxx` 而非通过 DeviceProperties 注入 `layout-id`。
音频设备路径: `PciRoot(0x0)/Pci(0x1b,0x0)` (Skylake+: `PciRoot(0x0)/Pci(0x1f,0x3)`)

### 5.4 特殊: Comet Lake I225-V 以太网

路径: `PciRoot(0x0)/Pci(0x1C,0x1)/Pci(0x0,0x0)` (部分主板为 `0x1C,0x4`)
- device-id: `F2150000`

---

## 六、Kernel Quirks — 按平台

### 关键 Quirks 对照表

| Quirk | Ivy B | Haswell | Skylake | Coffee Lake | Comet Lake | HEDT | AMD Zen |
|-------|-------|---------|---------|-------------|-----------|------|---------|
| AppleCpuPmCfgLock | YES | -- | -- | -- | -- | IvyB-E | -- |
| AppleXcpmCfgLock | -- | YES | YES | YES | YES | HasE+ | -- |
| AppleXcpmExtraMsrs | -- | -- | -- | -- | -- | IvyB/HasE | -- |
| DisableIoMapper | YES | YES | YES | YES | YES | YES | -- |
| DisableLinkeditJettison | YES | YES | YES | YES | YES | YES | -- |
| DummyPowerManagement | -- | -- | -- | -- | -- | -- | YES |
| LapicKernelPanic | HP | HP | HP | HP | HP | -- | -- |
| PanicNoKextDump | YES | YES | YES | YES | YES | YES | YES |
| PowerTimeoutKernelPanic | YES | YES | YES | YES | YES | YES | YES |
| ProvideCurrentCpuInfo | -- | -- | -- | -- | -- | -- | YES |
| XhciPortLimit | * | * | * | * | * | * | * |

`*` macOS 11.3+ 需禁用，改用 USB 端口映射

### AMD Zen 专用内核补丁

从 AMD_Vanilla GitHub 仓库下载，包含:
- "algrey - Force cpuid_cores_per_package" 补丁需根据实际核心数修改 (6 核=`06`, 8 核=`08`, 16 核=`10`)

### Ivy Bridge ACPI Delete (安装时临时使用)

- 删除 CpuPm: OemTableId `437075506d000000`
- 删除 Cpu0Ist: OemTableId `4370753049737400`

### Haswell-E CPU 仿真

- Cpuid1Data: `C3060300 00000000 00000000 00000000`
- Cpuid1Mask: `FFFFFFFF 00000000 00000000 00000000`

---

## 七、Booter Quirks — 按平台

### 传统/较旧平台 (Ivy Bridge、Haswell、Skylake)

| Quirk | 值 |
|-------|-----|
| AvoidRuntimeDefrag | YES |
| EnableSafeModeSlide | YES |
| EnableWriteUnprotector | YES |
| ProvideCustomSlide | YES |
| SetupVirtualMap | YES |

### 现代平台 (Coffee Lake、Comet Lake、Skylake-X)

| Quirk | 值 | 备注 |
|-------|-----|------|
| DevirtualiseMmio | YES | -- |
| EnableWriteUnprotector | NO | -- |
| ProtectUefiServices | YES | Z390/Z490 |
| RebuildAppleMemoryMap | YES | -- |
| SyncRuntimePermissions | YES | -- |
| ResizeAppleGpuBars | -1 | -- |
| SetupVirtualMap | NO (Comet Lake) / YES (Coffee Lake) | -- |

### AMD Zen

| Quirk | 值 | 备注 |
|-------|-----|------|
| RebuildAppleMemoryMap | YES | -- |
| SetupVirtualMap | YES | B550/A520/TRx40 需禁用 |
| SyncRuntimePermissions | YES | -- |
| EnableWriteUnprotector | NO | -- |

---

## 八、SMBIOS 推荐

### 8.1 台式机

| 平台 | SMBIOS | 最高支持 macOS | 备注 |
|------|--------|--------------|------|
| Ivy Bridge (iGPU) | iMac13,1 | Monterey | -- |
| Ivy Bridge (dGPU) | iMac13,2 | Monterey | -- |
| Ivy Bridge (Big Sur+) | iMac14,4 / iMac15,1 | -- | 需更新 SMBIOS |
| Haswell (iGPU) | iMac14,4 | -- | -- |
| Haswell (dGPU) | iMac15,1 | -- | 推荐 |
| Skylake | iMac17,1 | Ventura 后淘汰 | 建议用 Kaby Lake SMBIOS |
| Coffee Lake | iMac19,1 | -- | Mojave+ |
| Coffee Lake (High Sierra) | iMac18,3 | -- | Pascal/Maxwell + Web Drivers |
| Comet Lake (<=8核) | iMac20,1 | -- | -- |
| Comet Lake (>=10核) | iMac20,2 | -- | -- |

### 8.2 HEDT

| 平台 | SMBIOS |
|------|--------|
| Ivy Bridge-E | MacPro6,1 |
| Haswell-E | iMacPro1,1 |
| Skylake-X / Cascade Lake | iMacPro1,1 |

### 8.3 笔记本

| 平台 | SMBIOS 选项 | 备注 |
|------|------------|------|
| Ivy Bridge | MacBookAir5,1/5,2, MacBookPro10,1/10,2 | 最高 Catalina；Big Sur 用 Air6/Pro11 |
| Haswell | MacBookAir6,1/6,2, MacBookPro11,1-3 | Monterey 用 Pro11,4/5 |
| Broadwell | MacBookAir7,2, MacBookPro12,1 | -- |
| Skylake | MacBook9,1, MacBookPro13,1/2/3 | Ventura 后淘汰 |
| Coffee Lake | MacBookPro15,1/2, Macmini8,1 | -- |

### 8.4 AMD

| GPU 类型 | SMBIOS |
|----------|--------|
| AMD Polaris+ | MacPro7,1 (10.15+) |
| Maxwell/Pascal 或 Polaris | iMacPro1,1 |
| 仅 Maxwell/Pascal | iMac14,2 |
| AMD GCN (旧) | MacPro6,1 |

---

## 九、NVRAM 常用设置

### 通用调试 boot-args

| 参数 | 作用 |
|------|------|
| `-v` | 详细模式 (显示启动日志) |
| `debug=0x100` | 内核崩溃时禁用看门狗 |
| `keepsyms=1` | 内核崩溃时打印符号 |
| `alcid=xxx` | AppleALC 音频 layout ID |

### GPU 相关 boot-args

| 参数 | 作用 |
|------|------|
| `agdpmod=pikera` | Navi (RX 5000/6000) Board-ID 绕过 |
| `-wegnoegpu` | 禁用独立显卡 |
| `unfairgva=1` | AMD GPU DRM 支持 |
| `-radcodec` | 不支持的 AMD GPU 编码 |
| `ngfxgl=1 ngfxcompat=1` | Nvidia Web Driver 相关 |

### AMD 专用

| 参数 | 作用 |
|------|------|
| `npci=0x3000` | Above 4G Decoding 替代方案 (二选一) |

### 系统变量

| 变量 | 值 | 说明 |
|------|-----|------|
| `csr-active-config` | `00000000` | SIP 完全启用 |
| `run-efi-updater` | `No` | 阻止 macOS 更新固件 |
| `prev-lang:kbd` | `en-US:0` 或留空 | 语言选择 |

---

## 十、UEFI 设置

### APFS 最低版本 (支持旧 macOS)

| macOS | MinVersion | MinDate |
|-------|-----------|---------|
| High Sierra 10.13.6 | `748077008000000` | `20180621` |
| Mojave 10.14.6 | `945275007000000` | `20190820` |
| Catalina 10.15.4 | `1412101001000000` | `20200306` |
| Big Sur+ | `-1` | `-1` |

### 关键 UEFI Quirks

| Quirk | 值 | 适用 |
|-------|-----|------|
| IgnoreInvalidFlexRatio | YES | 仅 pre-Skylake |
| RequestBootVarRouting | YES | 所有系统 |
| ReleaseUsbOwnership | YES | 笔记本 |
| UnblockFsConnect | YES | 仅 HP 系统 |

---

## 十一、BIOS 设置 (通用)

### 需要禁用

- Fast Boot (快速启动)
- Secure Boot (安全启动)
- Serial/COM Port (串口)
- VT-d (或通过 DisableIoMapper quirk)
- CSM (兼容性支持模块)
- Thunderbolt (初次安装时)
- Intel SGX
- CFG Lock

### 需要启用

- VT-x (虚拟化技术)
- Above 4G Decoding (4G 以上解码)
- Hyper-Threading (超线程)
- Execute Disable Bit
- EHCI/XHCI Hand-off
- OS type: Windows 8.1/10 UEFI Mode
- DVMT Pre-Allocated: 64MB 以上
- SATA Mode: AHCI

### AMD 额外要求

- 禁用 IOMMU
- 3990X 必须禁用超线程 (macOS 64 线程内核限制)

---

## 十二、安装后常见任务

| 任务 | 说明 |
|------|------|
| **USB 端口映射** | 必须，替代 XhciPortLimit (macOS 11.3+ 已失效) |
| **音频调整** | AppleALC 编解码器微调，选择正确 layout-id |
| **CPU 电源管理** | SSDT-PM 生成，CPU 空闲/加速状态优化 |
| **睡眠/唤醒** | 诊断和修复睡眠问题 |
| **DRM** | 流媒体修复 (Netflix 等) |
| **iServices** | iMessage、FaceTime、Apple ID 修复 |
| **FileVault** | 全盘加密支持 |
| **GUI/开机音** | OpenCore 启动界面主题、开机声音 |
| **多启动** | LauncherOption、BootCamp 双启动 |
| **GPU 补丁** | 帧缓冲连接器类型、VRAM、BusID 补丁 |
| **CFG Lock** | MSR 0xE2 解锁 (最佳电源管理) |
| **模拟 NVRAM** | 原生 NVRAM 损坏的系统 |

---

## 十三、厂商特殊注意事项

### HP 系统
- LapicKernelPanic: YES
- UnblockFsConnect: YES

### Dell 系统 (Skylake+)
- CustomSMBIOSGuid: YES
- UpdateSMBIOSMode: Custom

### ASUS Z490
- ProtectUefiServices: YES
- SetupVirtualMap: NO (BIOS v3006+)

### Comet Lake I225-V 网卡补丁 (仅 Catalina/Big Sur)
- Kernel patch on `com.apple.driver.AppleIntelI210Ethernet`
- Base: `__Z18e1000_set_mac_typeP8e1000_hw`
- Find: `F2150000`, Replace: `F3150000`

---

## 十四、不支持的硬件 (详细版)

### 14.1 完全不支持的 CPU

**按代次分类:**
- **Pentium 4 及更早**: 最高支持 10.5.8
- **Yonah**: 最高 10.6.8 (仅 32 位)
- **Conroe/Merom**: 无 SSE4 支持,最高 10.11.6
- **Penryn**: 无 SSE4.2 支持,最高 10.13.6
- **Pre-Haswell (无 AVX2)**: macOS 13+ 完全不支持
- **Rocket Lake**: 需伪装为 Comet Lake CPUID
- **所有 AMD 笔记本 CPU**: 完全不支持

**关键限制:**
- macOS 13+ 强制要求 AVX2 指令集 (Haswell 及更新)
- Ivy Bridge 在 macOS 12+ 无 iGPU 支持

### 14.2 完全不支持的 GPU

**NVIDIA (Monterey 12+ 全部不支持):**
- Maxwell (GTX 900 系列): 最高 Mojave 10.14
- Pascal (GTX 10xx): 最高 Mojave 10.14
- Turing (RTX 20xx): 完全无驱动
- Ampere (RTX 30xx): 完全无驱动
- Ada Lovelace (RTX 40xx): 完全无驱动
- Kepler (GTX 600/700): Monterey 12+ 已移除支持

**Intel:**
- Intel Arc (A-series): 完全无驱动

**AMD:**
- RDNA 3 (RX 7000 系列): 部分型号无支持
- Polaris GPU: 在 pre-AVX2 系统上不支持

**笔记本独显限制:**
- 90% 的笔记本独显无法工作 (Optimus/可切换显卡架构)
- NVIDIA 笔记本独显无法驱动内置屏幕

### 14.3 不支持的网卡

**WiFi (完全不支持或需第三方驱动):**
- Intel WiFi: 需第三方 itlwm/AirportItlwm (非原生)
- Qualcomm WiFi: 标准笔记本 WiFi,无驱动
- Atheros 新款: 最高支持 High Sierra
- Realtek WiFi: 无驱动

**有线网卡 (需特殊处理):**
- Intel I225-V 2.5Gb NIC: 需 device-id 欺骗
- Intel I350 1Gb 服务器网卡: 需额外 kext
- Intel 10Gb 服务器网卡: 有限支持
- Mellanox/Qlogic 服务器网卡: 无驱动

### 14.4 不支持的存储设备

**NVMe SSD (会导致内核崩溃):**
- Samsung PM981/PM991
- Micron 2200S
- Intel Optane Memory
- Micron 3D XPoint (HDD 加速)

需使用 NVMeFix.kext 或更换 SSD

### 14.5 不支持的功能/设备

**输入设备:**
- 指纹识别器: 完全无法模拟
- Touch ID: 无法模拟
- Windows Hello 面部识别: 无驱动

**音频:**
- Intel Smart Sound Technology 麦克风: 无驱动
- 部分组合耳机插孔: 无音频输入功能

**接口:**
- Thunderbolt 3: Alpine Ridge 控制器支持不稳定
- HDMI 2.1 / DisplayPort 2.0: 无完整支持

**其他:**
- 笔记本独显 (90% 不可用)
- 可切换显卡 (Optimus/Enduro)

---

## 十五、支持的 GPU 详细列表

### 15.1 AMD GPU (推荐)

**原生支持 (无需额外配置):**
- **Polaris (RX 400/500)**: RX 460-590,需 AVX2 CPU
- **Vega (RX Vega)**: Vega 56/64/VII
- **Navi 10 (RX 5000)**: RX 5500/5600/5700,需 `agdpmod=pikera`
- **Navi 21 (RX 6000)**: RX 6800/6900,需 `agdpmod=pikera`
- **GCN 1-3 (旧卡)**: R7/R9 200-300 系列

**macOS 版本要求:**
- Polaris/Vega: 10.12+
- Navi: 10.15+
- RX 6000: 11.4+

### 15.2 Intel iGPU

**支持的代次:**
- **Ivy Bridge HD 4000**: 最高 Monterey 12
- **Haswell HD 4600/5000**: 当前支持
- **Broadwell HD 5500/6000**: 当前支持
- **Skylake HD 530**: 当前支持
- **Kaby Lake HD 630**: 当前支持
- **Coffee Lake UHD 630**: 当前支持
- **Comet Lake UHD 630**: 当前支持

**不支持:**
- Ice Lake 及更新: 无原生内核支持

### 15.3 NVIDIA (仅旧版 macOS)

**Kepler (最高 Big Sur 11):**
- GTX 600/700 系列
- 需 Web Driver (High Sierra 及更早)

**Maxwell/Pascal (最高 Mojave 10.14):**
- GTX 900/10xx 系列
- 需 NVIDIA Web Driver
- Monterey 12+ 完全移除支持

---

## 十六、SMBIOS 选择详细规则

### 16.1 台式机 SMBIOS 选择逻辑

**有 iGPU 的 CPU:**
- 使用 iMac SMBIOS (iMac13,x - iMac20,x)
- 确保 SMBIOS 代次匹配 CPU 代次

**无 iGPU 的 CPU (F 系列):**
- **必须**使用 iMacPro1,1 或 MacPro7,1
- 否则 Quick Look/后台渲染等功能损坏

**dGPU 重负载工作站:**
- iMacPro1,1: Haswell-E 至 Skylake-X
- MacPro7,1: AMD Polaris+ GPU (10.15+)

### 16.2 笔记本 SMBIOS 选择逻辑

**按 CPU 后缀选择:**
- **U 系列 (低压)**: MacBookAir 或 MacBook
- **H/HQ 系列 (标压)**: MacBookPro 15 寸型号
- **无独显**: MacBookAir 或 MacBookPro 13 寸

**Optimus 笔记本 (独显+iGPU):**
- 外接显示器接 iGPU: 需额外补丁避免黑屏
- 建议禁用独显使用 iGPU

### 16.3 Mac Mini SMBIOS

**仅适用于:**
- Intel NUC
- 无内置显示器的移动硬件

**不适用于:**
- 标准台式机 (应使用 iMac)
- 笔记本 (应使用 MacBookPro/Air)

### 16.4 USB 要求

**Skylake+ SMBIOS:**
- 必须包含 USBX 设备 (SSDT-EC-USBX)
- 否则 USB 供电异常

---

## 十七、构建 EFI 的关键决策树

### 17.1 CPU 兼容性检查 (阻断性)

```
IF CPU 代次 < Haswell AND 目标 macOS >= 13:
    BLOCK: "macOS 13+ 需要 AVX2 指令集 (Haswell+)"

IF CPU 是 AMD 笔记本:
    BLOCK: "AMD 笔记本 CPU 完全不支持 macOS"

IF CPU 是 Rocket Lake:
    WARN: "需要 CPUID 伪装为 Comet Lake"
```

### 17.2 GPU 兼容性检查 (警告性)

```
IF GPU 是 NVIDIA Maxwell/Pascal AND 目标 macOS >= 10.15:
    WARN: "此 GPU 最高支持 Mojave 10.14"

IF GPU 是 NVIDIA Turing/Ampere/Ada:
    WARN: "此 GPU 完全无 macOS 驱动,建议禁用或更换"

IF GPU 是 Intel Arc:
    WARN: "Intel Arc 无 macOS 驱动"

IF 笔记本有独显:
    WARN: "90% 笔记本独显无法工作,建议禁用"
```

### 17.3 存储设备检查 (警告性)

```
IF NVMe 型号 IN [PM981, PM991, Micron 2200S]:
    WARN: "此 SSD 会导致内核崩溃,需添加 NVMeFix.kext 或更换"
```

### 17.4 网卡检查 (提示性)

```
IF WiFi 是 Intel/Qualcomm:
    INFO: "需安装 AirportItlwm + IntelBluetoothFirmware"

IF 以太网是 I225-V:
    INFO: "需添加 device-id 欺骗补丁"
```

---

## 十八、EFI 构建流程建议

### 阶段 1: 硬件检测与验证
1. 检测 CPU 型号和代次
2. 检测 GPU 型号和类型 (iGPU/dGPU)
3. 检测主板芯片组
4. 检测网卡型号
5. 检测存储设备型号

### 阶段 2: 兼容性验证
1. CPU 兼容性检查 (阻断性)
2. GPU 兼容性检查 (警告性)
3. 存储设备检查 (警告性)
4. 网卡检查 (提示性)

### 阶段 3: 用户确认
1. 显示检测到的硬件信息
2. 显示兼容性警告
3. 询问目标 macOS 版本
4. 询问是否继续构建

### 阶段 4: SMBIOS 选择
1. 根据 CPU 代次和 GPU 配置选择 SMBIOS
2. 显示推荐的 SMBIOS 及原因
3. 允许用户手动选择

### 阶段 5: 组件选择
1. 根据平台选择必需的 SSDT
2. 根据硬件选择必需的 Kexts
3. 根据平台选择必需的 Drivers
4. 配置 Kernel Quirks
5. 配置 Booter Quirks

### 阶段 6: 生成 EFI
1. 创建 EFI 目录结构
2. 复制必需文件
3. 生成 config.plist
4. 验证配置完整性

---

## 附录: 数据更新日期

- OpenCore Install Guide: 2026-03-14
- GPU Buyers Guide: 2026-03-14
- Getting Started with ACPI: 2026-03-14
- Kext 列表: 2026-03-14
