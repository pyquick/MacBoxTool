"""
constants.py: Defines versioning, file paths and other settings for the patcher
"""


from pathlib import Path
import sys
if sys.platform=="darwin":
    from .detections import device_probe
else:
    from .detections import device_probe_win as device_probe



class Constants:
    def __init__(self):
        #MacBoxTool Version
        self.mactoolbox_version:        str = "0.0.1"
        self.patcher_support_pkg_version:     str = "1.11.0"  # PatcherSupportPkg
        self.copyright:                        str = "Copyright © 2020-2026 Pyquick"

        # OpenCore Version
        self.opencore_version:           str = "1.0.6"

        # Kext Versioning
        ## Acidanthera
        ## https://github.com/acidanthera
        self.lilu_version:               str = "1.7.0"  #      Lilu
        self.whatevergreen_version:      str = "1.7.1"  #      WhateverGreen
        self.whatevergreen_navi_version: str = "1.6.9-Navi"  # WhateverGreen (Navi Patch)
        self.airportbcrmfixup_version:   str = "2.1.9"  #      AirPortBrcmFixup
        self.nvmefix_version:            str = "1.1.2"  #      NVMeFix
        self.applealc_version:           str = "1.6.3"  #      AppleALC
        self.restrictevents_version:     str = "1.1.7"  #      RestrictEvents
        self.featureunlock_version:      str = "1.1.7"  #      FeatureUnlock
        self.debugenhancer_version:      str = "1.1.1"  #      DebugEnhancer
        self.cpufriend_version:          str = "1.3.0"  #      CPUFriend
        self.bluetool_version:           str = "2.6.9"  #      BlueToolFixup (BrcmPatchRAM)
        self.cslvfixup_version:          str = "2.6.1"  #      CSLVFixup
        self.autopkg_version:            str = "1.0.4"  #      AutoPkgInstaller
        self.cryptexfixup_version:       str = "1.0.5"  #      CryptexFixup
        

        ## Apple
        ## https://www.apple.com
        self.marvel_version:        str = "1.0.1"  #  MarvelYukonEthernet
        self.nforce_version:        str = "1.0.1"  #  nForceEthernet
        self.piixata_version:       str = "1.0.1"  #  AppleIntelPIIXATA
        self.fw_kext:               str = "1.0.1"  #  IOFireWireFamily
        self.apple_trackpad:        str = "1.0.1"  #  AppleUSBTrackpad
        self.apple_isight_version:  str = "1.0.0"  #  AppleiSight
        self.apple_raid_version:    str = "1.0.0"  #  AppleRAIDCard
        self.apfs_zlib_version:     str = "12.3.1"  # NoAVXFSCompressionTypeZlib
        self.apfs_zlib_v2_version:  str = "12.6"  #   NoAVXFSCompressionTypeZlib (patched with AVXpel)
        self.multitouch_version:    str = "1.0.0"  #  AppleUSBMultitouch
        self.topcase_version:       str = "1.0.0"  #  AppleUSBTopCase
        self.topcase_inj_version:   str = "1.0.0"  #  AppleTopCaseInjector
        self.intel_82574l_version:  str = "1.0.0"  #  Intel82574L
        self.intel_8254x_version:   str = "1.0.0"  #  AppleIntel8254XEthernet
        self.apple_usb_11_injector: str = "1.0.0"  #  AppleUSBUHCI/OHCI
        self.aicpupm_version:       str = "1.0.0"  #  AppleIntelCPUPowerManagement/Client
        self.s3x_nvme_version:      str = "1.0.0"  #  IONVMeFamily (14.0 Beta 1, S1X and S3X classes)
        self.apple_camera_version:  str = "1.0.0"  #  AppleCameraInterface (14.0 Beta 1)
        self.t1_sse_version:        str = "1.1.0"  #  AppleSSE      (13.6 - T1 support)
        self.t1_key_store_version:  str = "1.1.0"  #  AppleKeyStore (13.6 - T1 support)
        self.t1_credential_version: str = "1.0.0"  #  AppleCredentialManager (13.6 - T1 support)
        self.t1_corecrypto_version: str = "1.0.1"  #  corecrypto    (13.6 - T1 support)
        self.apple_spi_version:     str = "1.0.0"  #  AppleHSSPISupport   (14.4 Beta 1)
        self.apple_spi_hid_version: str = "1.0.0"  #  AppleHSSPIHIDDriver (14.4 Beta 1)
        self.kernel_relay_version:  str = "1.0.0"  #  KernelRelayHost (15.0 Beta 3)

        ## Apple - Hackdoc Modified
        self.bcm570_version:           str = "1.0.2"  # CatalinaBCM5701Ethernet
        self.i210_version:             str = "1.0.0"  # CatalinaIntelI210Ethernet
        self.corecaptureelcap_version: str = "1.0.2"  # corecaptureElCap
        self.io80211elcap_version:     str = "2.0.1"  # IO80211ElCap
        self.io80211legacy_version:    str = "1.0.0"  # IO80211FamilyLegacy (Ventura)
        self.ioskywalk_version:        str = "1.2.0"  # IOSkywalkFamily (Ventura)
        self.bigsursdxc_version:       str = "1.0.0"  # BigSurSDXC
        self.monterey_ahci_version:    str = "1.0.0"  # CatalinaAHCI

        ## Apple - Jazzzny Modified
        self.aquantia_version: str = "1.1.0"  # AppleEthernetAbuantiaAqtion

        ## Hackdoc
        ## https://github.com/hackdoc
        self.backlight_injector_version:     str = "1.1.0"  # BacklightInjector
        self.backlight_injectorA_version:    str = "1.0.0"  # BacklightInjector (iMac9,1)
        self.smcspoof_version:               str = "1.0.0"  # SMC-Spoof
        self.mce_version:                    str = "1.0.0"  # AppleMCEReporterDisabler
        self.btspoof_version:                str = "1.0.0"  # Bluetooth-Spoof
        self.aspp_override_version:          str = "1.0.1"  # ACPI_SMC_PlatformPlugin Override
        self.ecm_override_version:           str = "1.0.0"  # AppleUSBECM Override
        self.rsrhelper_version:              str = "1.0.2"  # RSRHelper
        self.amfipass_version:               str = "1.4.1"  # AMFIPass
        self.amfipass_compatibility_version: str = "1.2.1"  # Minimum AMFIPass version required

        ## Syncretic
        ## https://forums.macrumors.com/members/syncretic.1173816/
        ## https://github.com/reenigneorcim/latebloom
        self.mousse_version:     str = "0.95-Hackdoc"  # MouSSE
        self.telemetrap_version: str = "1.0.0"  #         telemetrap

        ## cdf
        ## https://github.com/cdf/Innie
        self.innie_version: str = "1.3.1"  # Innie

        ## arter97
        ## https://github.com/arter97/SimpleMSR/
        self.simplemsr_version: str = "1.0.0"  # SimpleMSR

        ## blackgate
        ## https://github.com/blackgate/AMDGPUWakeHandler
        self.gpu_wake_version: str = "1.0.0"

        ## flagersgit
        ## https://github.com/flagersgit/KDKlessWorkaround
        self.kdkless_version: str = "1.0.0"
        
        ## Jazzzny
        self.legacy_keyboard: str = "1.0.0"  # LegacyKeyboardInjector - Jazzzny

        ## zxystd
        self.itlwm_kext:      str = "2.3.0"
        self.intel_bluetooth_firmware: str = "2.5.0"

        self.log_filepath:    str = None
        self.cli_mode:                  bool = False  #  Determine if running in CLI mode

        self.computer: device_probe.Computer = None
        self.custom_model: str = None
