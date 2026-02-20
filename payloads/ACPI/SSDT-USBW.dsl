/*
 * Intel ACPI Component Architecture
 * AML/ASL+ Disassembler version 20200925 (64-bit version)
 * Copyright (c) 2000 - 2020 Intel Corporation
 * 
 * Disassembling to symbolic ASL+ operators
 *
 * Disassembly of /Users/ghltbm/Documents/MacBoxTool/payloads/ACPI/SSDT-USBW.aml, Sun Jan 25 19:17:28 2026
 *
 * Original Table Header:
 *     Signature        "SSDT"
 *     Length           0x00000096 (150)
 *     Revision         0x02
 *     Checksum         0x2C
 *     OEM ID           "OSY86 "
 *     OEM Table ID     "USBW"
 *     OEM Revision     0x00001000 (4096)
 *     Compiler ID      "INTL"
 *     Compiler Version 0x20200925 (538970405)
 */
DefinitionBlock ("", "SSDT", 2, "OSY86 ", "USBW", 0x00001000)
{
    External (_SB_.PCI0.XHC_._PRW, MethodObj)    // 0 Arguments

    If ((CondRefOf (\_OSI, Local0) && _OSI ("Darwin")))
    {
        Device (\_SB.USBW)
        {
            Name (_HID, "PNP0D10" /* XHCI USB Controller with debug */)  // _HID: Hardware ID
            Name (_UID, "WAKE")  // _UID: Unique ID
            Method (_PRW, 0, NotSerialized)  // _PRW: Power Resources for Wake
            {
                Return (\_SB.PCI0.XHC._PRW ())
            }
        }
    }
}

