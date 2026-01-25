/*
 * Intel ACPI Component Architecture
 * AML/ASL+ Disassembler version 20200925 (64-bit version)
 * Copyright (c) 2000 - 2020 Intel Corporation
 * 
 * Disassembling to symbolic ASL+ operators
 *
 * Disassembly of /Users/ghltbm/Documents/MacBoxTool/ payloads/ACPI/SSDT-BRG0.aml, Sun Jan 25 19:17:28 2026
 *
 * Original Table Header:
 *     Signature        "SSDT"
 *     Length           0x00000089 (137)
 *     Revision         0x02
 *     Checksum         0x73
 *     OEM ID           "ACDT"
 *     OEM Table ID     "BRG0"
 *     OEM Revision     0x00000000 (0)
 *     Compiler ID      "INTL"
 *     Compiler Version 0x20200528 (538969384)
 */
DefinitionBlock ("", "SSDT", 2, "ACDT", "BRG0", 0x00000000)
{
    External (_SB_.PCI0.PEG0.PEGP, DeviceObj)

    Scope (\_SB.PCI0.PEG0.PEGP)
    {
        Device (BRG0)
        {
            Name (_ADR, Zero)  // _ADR: Address
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

            Device (GFX0)
            {
                Name (_ADR, Zero)  // _ADR: Address
            }
        }
    }
}

