/*
 * Intel ACPI Component Architecture
 * AML/ASL+ Disassembler version 20200925 (64-bit version)
 * Copyright (c) 2000 - 2020 Intel Corporation
 * 
 * Disassembling to symbolic ASL+ operators
 *
 * Disassembly of /Users/ghltbm/Documents/MacBoxTool/ payloads/ACPI/SSDT-HV-VMBUS.aml, Sun Jan 25 19:17:28 2026
 *
 * Original Table Header:
 *     Signature        "SSDT"
 *     Length           0x000000E6 (230)
 *     Revision         0x02
 *     Checksum         0xA0
 *     OEM ID           "ACDT"
 *     OEM Table ID     "HVVMBUS"
 *     OEM Revision     0x00000000 (0)
 *     Compiler ID      "INTL"
 *     Compiler Version 0x20200528 (538969384)
 */
DefinitionBlock ("", "SSDT", 2, "ACDT", "HVVMBUS", 0x00000000)
{
    External (_SB_.VMOD, DeviceObj)
    External (_SB_.VMOD.VMBS, DeviceObj)
    External (_SB_.VMOD.VMBS.XHID, MethodObj)    // 0 Arguments
    External (_SB_.VMOD.XHID, MethodObj)    // 0 Arguments

    Scope (\_SB.VMOD)
    {
        Method (_HID, 0, NotSerialized)  // _HID: Hardware ID
        {
            If (_OSI ("Darwin"))
            {
                Return (0x0100A459)
            }

            Return (\_SB.VMOD.XHID ())
        }
    }

    Scope (\_SB.VMOD.VMBS)
    {
        Method (_HID, 0, NotSerialized)  // _HID: Hardware ID
        {
            If (_OSI ("Darwin"))
            {
                Return (0x01005358)
            }

            Return (\_SB.VMOD.VMBS.XHID ())
        }
    }
}

