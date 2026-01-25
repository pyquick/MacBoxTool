/*
 * Intel ACPI Component Architecture
 * AML/ASL+ Disassembler version 20200925 (64-bit version)
 * Copyright (c) 2000 - 2020 Intel Corporation
 * 
 * Disassembling to symbolic ASL+ operators
 *
 * Disassembly of /Users/ghltbm/Documents/MacBoxTool/ payloads/ACPI/SSDT-OSYS.aml, Sun Jan 25 19:17:28 2026
 *
 * Original Table Header:
 *     Signature        "SSDT"
 *     Length           0x00000079 (121)
 *     Revision         0x02
 *     Checksum         0x08
 *     OEM ID           "ACDT"
 *     OEM Table ID     "OSYS"
 *     OEM Revision     0x00000000 (0)
 *     Compiler ID      "INTL"
 *     Compiler Version 0x20190509 (538510601)
 */
DefinitionBlock ("", "SSDT", 2, "ACDT", "OSYS", 0x00000000)
{
    External (OSYS, FieldUnitObj)

    Scope (_SB)
    {
        Device (PCI1)
        {
            Name (_ADR, Zero)  // _ADR: Address
            Method (_INI, 0, NotSerialized)  // _INI: Initialize
            {
                If (CondRefOf (\OSYS))
                {
                    OSYS = 0x07E2
                }
            }

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

