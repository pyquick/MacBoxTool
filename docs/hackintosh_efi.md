# Hackintosh EFI 配置完全指南

> 基于 OpenCore Install Guide v1.0.5
> 最后更新：2026-03-04

## ⚠️ 重要声明

**这不是一个简单的一键安装工具。** 你必须：
- 仔细阅读并理解每个步骤
- 独立研究和学习
- 为你的特定硬件配置做出正确的选择

**OpenCore 仍在持续更新中**，配置文件格式会随版本变化。请始终参考最新的官方文档。

---

## 目录

1. [什么是 OpenCore](#什么是-opencore)
2. [硬件要求与限制](#硬件要求与限制)
3. [准备工作](#准备工作)
4. [创建安装 USB](#创建安装-usb)
5. [收集必需文件](#收集必需文件)
6. [Config.plist 配置](#configplist-配置)
7. [安装 macOS](#安装-macos)
8. [故障排除](#故障排除)
9. [安装后配置](#安装后配置)

---

## 什么是 OpenCore

OpenCore 是一个**引导加载器**，用于：
- 注入 SMBIOS 信息
- 加载 ACPI 表
- 注入内核扩展（Kexts）
- 准备系统以运行 macOS

**核心特性：**
- ✅ 支持系统完整性保护（SIP）
- ✅ 支持 FileVault 2 加密
- ✅ 支持安全启动
- ✅ 原生 NVRAM 支持
- ✅ 原生休眠支持

---

## 硬件要求与限制

### 必须了解的硬件信息

在开始之前，你**必须**知道：
- ✅ CPU 型号和代数
- ✅ GPU 型号
- ✅ 存储设备类型（HDD/SSD，NVMe/AHCI/RAID/IDE）
- ✅ 以太网芯片型号
- ✅ WiFi/蓝牙芯片型号

### 存储要求

**USB 驱动器：**
- macOS 创建安装盘：16GB 或更大
- Windows/Linux 创建安装盘：4GB 或更大

**硬盘空间：**
- Windows/Linux：15GB 可用空间
- macOS：30GB 可用空间

### 网络要求

⚠️ **关键要求：必须有以太网连接**

- ❌ 不支持 WiFi 网卡（安装过程中）
- ❌ 不支持 WiFi USB 适配器
- ✅ 以太网 USB 适配器可能可用（取决于 macOS 支持）
- ⚠️ 大多数 WiFi 卡不受支持（但有兼容选项）

### 系统要求

**操作系统：**
- macOS（最新版本）
- Windows 10 1703 或更高版本
- Linux（需要 Python 2.7+，仅 UEFI）

**其他：**
- ✅ 安装最新 BIOS（MSI 500 系列 AMD 主板除外）
- ✅ 基本命令行知识
- ✅ 能够阅读和理解英文文档

---

## 硬件兼容性详解

### CPU 兼容性

**Intel 桌面 CPU：**
- ✅ 支持：Yonah 到 Comet Lake
- ⚠️ macOS 10.14+：需要 SSE4.2 支持
- ⚠️ macOS 13+：需要 AVX2 支持（Haswell 及更新）
- ❌ 不支持：Atom、Celeron、Pentium 移动版

**Intel 笔记本 CPU：**
- ✅ 支持：Arrandale 到 Ice Lake
- ❌ 不支持：移动版 Atom、Celeron、Pentium

**AMD CPU：**
- ✅ 支持：Ryzen 桌面 CPU
- ❌ 不支持：AMD 笔记本 CPU

### GPU 兼容性

⚠️ **笔记本独立显卡：90% 不可用**
- 原因：可切换显卡配置不兼容
- 建议：使用集成显卡

**存储设备兼容性：**
- ✅ 大多数 SATA 和 NVMe 驱动器
- ⚠️ 需要修复：Samsung PM981/PM991、Micron 2200S（需要 NVMeFix.kext）
- ❌ 问题设备：Intel 600p

### 网络设备兼容性

**有线网络：**
- ✅ 大多数适配器可用
- ❌ Intel I225-V 2.5Gb NIC
- ❌ 服务器级网卡

**无线网络：**
- ❌ 大多数笔记本自带 WiFi 卡（Intel/Qualcomm）
- ✅ 推荐：Broadcom 芯片

### 完全不支持的硬件

- ❌ 指纹识别器 / Touch ID 传感器
- ❌ Windows Hello 面部识别
- ❌ Intel Smart Sound Technology
- ❌ Thunderbolt 端口（不可靠，USB-C 热插拔有问题）
- ❌ 组合耳机插孔（音频输入通常失败）

---

## 准备工作

### 必需工具

**1. OpenCorePkg**
- 下载地址：[OpenCorePkg Releases](https://github.com/acidanthera/OpenCorePkg/releases)
- ⚠️ 推荐使用 DEBUG 版本（便于故障排除）
- ❌ 不要使用 OpenCore Configurator 等第三方工具（会损坏配置）

**2. ProperTree**
- 用途：编辑 config.plist
- 下载地址：[ProperTree](https://github.com/corpnewt/ProperTree)
- 跨平台支持：macOS/Windows/Linux

**3. USB 驱动器**
- macOS：16GB+
- Windows/Linux：4GB+

### 从 Clover 迁移

⚠️ **关键步骤：**
1. 完全移除 Clover
2. 备份现有 EFI
3. 不要混用 Clover 和 OpenCore

---

## 创建安装 USB

### 安装器类型

**离线安装器（推荐）：**
- ✅ 包含完整 macOS
- ✅ 安装速度快
- ❌ 只能在 macOS 上创建
- 大小：~12GB

**在线安装器：**
- ✅ 体积小（~500MB）
- ✅ 可在 Windows/Linux 创建
- ❌ 需要从 Apple 服务器下载
- ❌ 安装速度慢
- 支持：macOS 10.7+

### macOS 创建安装盘

支持创建：OS X 10.4 及更新版本

### Windows 创建安装盘

- 仅支持在线安装器
- 支持：OS X 10.7 及更新版本

### Linux 创建安装盘

- 仅 UEFI 系统
- 仅支持在线安装器
- 支持：OS X 10.7 及更新版本

---

## 收集必需文件

### 必需 Kexts（所有系统）

**1. Lilu.kext**
- 作用：修补多个进程的基础 kext
- 必需性：⭐⭐⭐⭐⭐ 必须
- 依赖：AppleALC、WhateverGreen、VirtualSMC 等都需要它

**2. VirtualSMC.kext**
- 作用：模拟真实 Mac 的 SMC 芯片
- 必需性：⭐⭐⭐⭐⭐ 必须
- ⚠️ 没有它 macOS 无法启动

### 通用 Kexts（强烈推荐）

**3. WhateverGreen.kext**
- 作用：显卡补丁、DRM 修复、帧缓冲修正
- 适用：所有 GPU 类型
- 必需性：⭐⭐⭐⭐⭐ 强烈推荐

**4. AppleALC.kext**
- 作用：板载声卡支持
- 适用：大多数板载声卡
- ❌ 不适用：AMD 15h/16h 系统
- 必需性：⭐⭐⭐⭐ 推荐

### 网络 Kexts（根据硬件选择）

**Intel 网卡：**
- **IntelMausi.kext** - 适用于 I217/I218/I219

**Realtek 网卡：**
- **RealtekRTL8111.kext** - 适用于 Realtek 千兆以太网

**Atheros/Killer 网卡：**
- **AtherosE2200Ethernet.kext**

### 笔记本输入设备 Kexts

**PS2 键盘/触控板：**
- **VoodooPS2.kext** - PS2 设备支持

**I2C 触控板：**
- **VoodooI2C.kext** + 插件
- 需要配合特定插件使用

**Synaptics SMBus 触控板：**
- **VoodooRMI.kext**

### 无线网络 Kexts

**Intel WiFi：**
- **AirportItlwm.kext** - Intel WiFi 卡支持

**Broadcom WiFi：**
- **AirportBrcmFixup.kext** - Broadcom 卡支持

**Intel 蓝牙：**
- **IntelBluetoothFirmware.kext**

### AMD 系统专用 Kexts

**AMD CPU 电源管理：**
- **AMDRyzenCPUPowerManagement.kext**

**AMD 音频（替代方案）：**
- **VoodooHDA.kext** - AppleALC 的替代品

### 可选 Kexts

**VirtualSMC 插件：**
- **SMCProcessor.kext** - CPU 温度监控
- **SMCBatteryManager.kext** - 笔记本电池监控
- **SMCLightSensor.kext** - 环境光传感器
- ⚠️ 非启动必需，仅用于硬件监控

**NVMe 优化：**
- **NVMeFix.kext** - 改善 NVMe 电源管理

**USB 控制器：**
- **XHCI-unsupported.kext** - 特定芯片组的非原生 USB 控制器

---

## ACPI 配置

### 什么是 ACPI

ACPI（高级配置和电源接口）表用于：
- 描述硬件配置
- 电源管理
- 设备启用/禁用

### 必需的 SSDTs

⚠️ **根据平台不同，需要不同的 SSDT**

详细信息请参考：[Getting Started With ACPI](https://dortania.github.io/Getting-Started-With-ACPI/)

**添加 SSDTs 到 EFI：**
1. 将 .aml 文件放入 `EFI/OC/ACPI/`
2. 使用 ProperTree 的 "Clean Snapshot" 功能
3. 自动添加到 config.plist

---

## Config.plist 配置

### 配置工具

**推荐：ProperTree**
- ✅ 跨平台
- ✅ 不会损坏配置
- ❌ 不要使用：OpenCore Configurator、Clover Configurator

### 平台特定配置

⚠️ **每个平台都有独特的配置要求**

**Intel 桌面：**
- Penryn
- Clarkdale
- Sandy Bridge
- Ivy Bridge
- Haswell
- Skylake
- Kaby Lake
- Coffee Lake
- Comet Lake

**Intel 笔记本：**
- Arrandale
- Sandy Bridge
- Ivy Bridge
- Haswell
- Broadwell
- Skylake
- Kaby Lake
- Coffee Lake
- Ice Lake

**Intel HEDT：**
- Nehalem/Westmere
- Sandy/Ivy Bridge-E
- Haswell-E
- Broadwell-E
- Skylake-X/W/Cascade Lake-X/W

**AMD：**
- Bulldozer/Jaguar
- Zen

### Clean Snapshot 功能

**作用：**
1. 移除 config.plist 中的所有条目
2. 自动添加所有 SSDTs
3. 自动添加所有 Kexts
4. 自动添加所有固件驱动

**使用方法：**
- ProperTree → File → OC Clean Snapshot
- 选择 EFI/OC 文件夹

---

## 故障排除

### 问题分类

**1. OpenCore 启动问题**
- USB 无法启动
- 无法到达 OpenCore 选择器菜单

**2. 内核空间问题**
- 从 OpenCore 选择 macOS 后
- 到 Apple 标志出现之前

**3. 用户空间问题**
- GUI 加载阶段
- macOS 安装到硬盘过程

**4. 安装后问题**
- macOS 完全安装并启动后的问题

**5. 其他问题**
- 安装相关
- 多系统启动问题

### 调试资源

**官方文档：**
- Configuration.pdf - 技术细节和 quirks 说明
- Understanding the macOS Boot Process - 了解启动流程

**社区支持：**
- r/Hackintosh subreddit
- Discord 服务器

---

## 安装后配置

### 通用配置

安装完成后需要进行的配置：
- USB 端口映射
- 音频配置
- 显卡优化
- 电源管理
- iServices 配置

### 笔记本特定配置

额外需要配置：
- 电池电量显示
- 触控板手势
- 亮度控制
- 睡眠/唤醒

---

## 重要注意事项

### ⚠️ 安全警告

1. **备份数据**
   - 在开始之前备份所有重要数据
   - 保留原有 EFI 的备份

2. **BIOS 设置**
   - 禁用安全启动
   - 禁用快速启动
   - 启用 UEFI 模式

3. **更新注意**
   - macOS 更新前检查兼容性
   - OpenCore 更新需要重新配置
   - 保持 Kexts 更新

### 📚 学习资源

- [OpenCore Install Guide](https://dortania.github.io/OpenCore-Install-Guide/)
- [Getting Started With ACPI](https://dortania.github.io/Getting-Started-With-ACPI/)
- [OpenCore Post-Install](https://dortania.github.io/OpenCore-Post-Install/)
- [GPU Buyers Guide](https://dortania.github.io/GPU-Buyers-Guide/)
- [Wireless Buyers Guide](https://dortania.github.io/Wireless-Buyers-Guide/)

---

## 结语

Hackintosh 不是一个简单的过程，需要：
- ✅ 耐心和时间
- ✅ 学习和研究能力
- ✅ 问题解决能力
- ✅ 英文阅读能力

**记住：**
- 每个系统都是独特的
- 没有通用的配置
- 必须根据自己的硬件调整
- 遇到问题时查阅官方文档

**祝你好运！** 🍀

---

*本文档基于 OpenCore Install Guide v1.0.5 编写，内容可能随版本更新而变化。请始终参考最新的官方文档。*

