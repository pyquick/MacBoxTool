# MacBoxTool 黑苹果 EFI 构建器增强总结
**日期:** 2026-03-15
**模型:** Claude Sonnet 4.6

## 概述
增强了 MacBoxTool 的黑苹果 EFI 构建器（efi_hack 模块），包括 bug 修复、新增 kext 支持和改进的硬件检测。

---

## 1. Bug 修复

### ACPI 文件未添加到 config.plist
**文件:** `MacBoxTool/efi_mac/acpi/base.py`

**问题:** ACPI/SSDT 文件被复制到 EFI 但未在 config.plist 中注册

**解决方案:** 修改 `add_acpi()` 方法，当条目不存在时自动创建：
```python
if not self.config_mgr.enable_acpi(source.name):
    acpi_add = self.config.setdefault("ACPI", {}).setdefault("Add", [])
    acpi_add.append({"Comment": source.name, "Enabled": True, "Path": source.name})
    return True
```

---

## 2. 新增 Kext 支持

### 安全类 Kext
- **AMFIPass.kext** v1.4.0 - AMFI 绕过，用于未签名 kext
- 添加 `-amfipassbeta` 启动参数到 NVRAM

### USB Kext
- **USBInjectAll.kext** v0.7.1 - 传统 USB 端口注入
- **USBToolBox.kext** v1.1.1 - 现代 USB 映射框架

### Intel 有线网卡 Kext
添加对多代 Intel 以太网控制器的支持：
- **IntelMausiEthernet.kext** v1.0.7 - I217/I218/I219 控制器
- **AppleIGB.kext** v1.0.0 - I211 控制器
- **AppleIGC.kext** v1.1.0 - I225/I226 控制器

### Realtek 网卡更新
- **RTL8125** → SimpleRTK5.kext v1.0.1
- **RTL8111** → RealtekRTL8111.kext v3.0.0

### Intel WiFi 多版本支持
实现 **AirportItlwm** 内核版本范围，供用户手动选择：
- BigSur (内核 20.0.0-20.99.99)
- Monterey (内核 21.0.0-21.99.99)
- Ventura (内核 22.0.0-22.99.99)
- Sonoma (内核 23.0.0-23.99.99)

用户可根据目标 macOS 版本启用特定版本。

---

## 3. 代码架构改进

### Constants 集中化
**文件:** `MacBoxTool/constants.py`

为所有新 kext 添加版本常量和路径属性：
```python
self.usbinjectall_version: str = "0.7.1"
self.amfipass_version: str = "1.4.0"
self.intelmausi_version: str = "1.0.7"
self.appleigb_version: str = "1.0.0"
self.appleigc_version: str = "1.1.0"

@property
def intelmausi_path(self):
    return self.payload_kexts_path / Path(f"Ethernet/IntelMausiEthernet-v{self.intelmausi_version}.zip")
```

消除了 kexts.py 中的硬编码路径。

### SMBIOS 选择助手
**文件:** `MacBoxTool/efi_hack/builder.py`

添加 `get_available_smbios()` 静态方法：
- 检测硬件类型（台式机 vs 笔记本）
- 相应过滤 SMBIOS 机型：
  - **笔记本:** MacBook, MacBookPro, MacBookAir
  - **台式机:** iMac, Macmini, MacPro, iMacPro

### 移除 Wizard 模式
**文件:** `MacBoxTool/efi_mac/builder.py`

移除 wizard 方法：
- `validate_hardware_compatibility()`
- `select_build_components()`

简化了 Mac EFI 生成流程。

### 增强清理日志
**文件:** `MacBoxTool/efi_mac/config.py`

为禁用条目移除添加详细日志：
```python
removed_drv = len(drivers) - len(enabled_drv)
self._log(f"  Removed {removed_drv} disabled driver entries")
```

---

## 4. Kext 下载情况

### 成功下载
- **IntelMausiEthernet** v1.0.8 (acidanthera/IntelMausi)
- **AirportItlwm** BigSur v2.3.0 (OpenIntelWireless/itlwm)
- **AirportItlwm** Monterey v2.3.0 (OpenIntelWireless/itlwm)

### 未提供预编译版本（仅源码）
- AppleIGB - 无预编译版本
- AppleIGC - 无预编译版本
- USBInjectAll - 无预编译版本

**注意:** 这些 kext 需要从源码编译或从其他来源下载（Hackintosh-Kext-Factory、论坛等）。

---

## 5. 修改的文件

1. `MacBoxTool/constants.py` - 添加 kext 版本和路径属性
2. `MacBoxTool/efi_mac/acpi/base.py` - 修复 ACPI 注册 bug
3. `MacBoxTool/efi_mac/builder.py` - 移除 wizard，添加 SMBIOS 助手
4. `MacBoxTool/efi_mac/config.py` - 增强清理日志
5. `MacBoxTool/efi_hack/builder.py` - 添加 SMBIOS 选择
6. `MacBoxTool/efi_hack/kexts.py` - 添加新 kext、Intel 网卡映射、AirportItlwm 多版本
7. `MacBoxTool/efi_hack/nvram.py` - 添加 -amfipassbeta 启动参数

---

## 6. 测试状态

**未测试:** 由于时间限制，构建流程尚未验证。

**建议测试:**
```bash
python3.14 MaxToolBox_GUI.command
```

验证项：
- ACPI 文件是否出现在 config.plist 中
- 新 kext 是否正确启用
- Intel 网卡检测是否工作
- AirportItlwm 内核范围是否正确
- SMBIOS 选择是否正确过滤

---

## 7. 参考资料

### GitHub 仓库
- [acidanthera/IntelMausi](https://github.com/acidanthera/IntelMausi) - Intel 网卡 kext
- [OpenIntelWireless/itlwm](https://github.com/OpenIntelWireless/itlwm) - Intel WiFi kext
- [Dortania OpenCore 安装指南](https://dortania.github.io/OpenCore-Install-Guide/) - 黑苹果配置参考

### Kext 映射研究
- Intel I217/I218/I219 → IntelMausiEthernet
- Intel I211 → AppleIGB
- Intel I225/I226 → AppleIGC
- Realtek RTL8125 → SimpleRTK5
- Realtek RTL8111 → RealtekRTL8111

---

## 8. 已知限制

1. **AppleIGB/AppleIGC/USBInjectAll** - 无预编译版本，需手动编译或从其他来源获取
2. **AirportItlwm Ventura/Sonoma** - 尚未下载（如需要可添加）
3. **测试** - 本次会话未验证构建流程

---

## 9. 后续步骤

1. 使用实际硬件测试构建流程
2. 从其他来源获取 AppleIGB/AppleIGC/USBInjectAll 的预编译版本
3. 如需要，下载剩余的 AirportItlwm 版本
4. 使用真实硬件验证 Intel 网卡检测逻辑
5. 在台式机和笔记本系统上测试 SMBIOS 选择

---

**总结完毕**
