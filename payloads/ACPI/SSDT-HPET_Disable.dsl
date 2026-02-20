/*
 * Intel ACPI Component Architecture
 * AML/ASL+ Disassembler version 20200925 (64-bit version)
 * Copyright (c) 2000 - 2020 Intel Corporation
 * 
 * Disassembling to symbolic ASL+ operators
 *
 * Disassembly of /Users/ghltbm/Documents/MacBoxTool/payloads/ACPI/SSDT-HPET_Disable.aml, Sun Jan 25 19:17:28 2026
 *
 * Original Table Header:
 *     Signature        "SSDT"
 *     Length           0x00000047 (71)
 *     Revision         0x02
 *     Checksum         0x71
 *     OEM ID           "Hack"
 *     OEM Table ID     "HPETOFF"
 *     OEM Revision     0x00000000 (0)
 *     Compiler ID      "INTL"
 *     Compiler Version 0x20200925 (538970405)
 */
DefinitionBlock ("", "SSDT", 2, "Hack", "HPETOFF", 0x00000000)
{
    External (HPTE, IntObj)

    Scope (\)
    {
        If (_OSI ("Darwin"))
        {
            HPTE = Zero
        }
    }
}

