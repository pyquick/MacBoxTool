/*
 * Intel ACPI Component Architecture
 * AML/ASL+ Disassembler version 20200925 (64-bit version)
 * Copyright (c) 2000 - 2020 Intel Corporation
 * 
 * Disassembling to symbolic ASL+ operators
 *
 * Disassembly of /Users/ghltbm/Documents/MacBoxTool/payloads/ACPI/SSDT-RTC0-RANGE.aml, Sun Jan 25 19:17:28 2026
 *
 * Original Table Header:
 *     Signature        "SSDT"
 *     Length           0x000000AC (172)
 *     Revision         0x02
 *     Checksum         0x25
 *     OEM ID           "ACDT"
 *     OEM Table ID     "RtcRange"
 *     OEM Revision     0x00000000 (0)
 *     Compiler ID      "INTL"
 *     Compiler Version 0x20200528 (538969384)
 */
DefinitionBlock ("", "SSDT", 2, "ACDT", "RtcRange", 0x00000000)
{
    External (_SB_.PC00.LPC0, DeviceObj)
    External (_SB_.PC00.LPC0.RTC_, DeviceObj)

    Scope (_SB.PC00.LPC0)
    {
        Device (RTC0)
        {
            Name (_HID, EisaId ("PNP0B00") /* AT Real-Time Clock */)  // _HID: Hardware ID
            Name (_CRS, ResourceTemplate ()  // _CRS: Current Resource Settings
            {
                IO (Decode16,
                    0x0070,             // Range Minimum
                    0x0070,             // Range Maximum
                    0x01,               // Alignment
                    0x04,               // Length
                    )
                IO (Decode16,
                    0x0074,             // Range Minimum
                    0x0074,             // Range Maximum
                    0x01,               // Alignment
                    0x04,               // Length
                    )
                IRQNoFlags ()
                    {8}
            })
            Method (_STA, 0, NotSerialized)  // _STA: Status
            {
                If (_OSI ("Darwin"))
                {
                    Return (0x0F)
                }
                Else
                {
                    Return (Zero)
                }
            }
        }
    }
}

