/*
 * Intel ACPI Component Architecture
 * AML/ASL+ Disassembler version 20200925 (64-bit version)
 * Copyright (c) 2000 - 2020 Intel Corporation
 * 
 * Disassembling to symbolic ASL+ operators
 *
 * Disassembly of /Users/ghltbm/Documents/MacBoxTool/ payloads/ACPI/SSDT-HV-PLUG.aml, Sun Jan 25 19:17:28 2026
 *
 * Original Table Header:
 *     Signature        "SSDT"
 *     Length           0x00000072 (114)
 *     Revision         0x02
 *     Checksum         0x53
 *     OEM ID           "ACDT"
 *     OEM Table ID     "HVPLUG"
 *     OEM Revision     0x00000000 (0)
 *     Compiler ID      "INTL"
 *     Compiler Version 0x20200528 (538969384)
 */
DefinitionBlock ("", "SSDT", 2, "ACDT", "HVPLUG", 0x00000000)
{
    External (_SB_.EPC_, DeviceObj)
    External (_SB_.EPC_.XSTA, MethodObj)    // 0 Arguments
    External (_SB_.NVDR, DeviceObj)
    External (_SB_.NVDR.XSTA, MethodObj)    // 0 Arguments
    External (_SB_.P001, ProcessorObj)
    External (_SB_.UAR1, DeviceObj)
    External (_SB_.UAR2, DeviceObj)
    External (_SB_.VMOD.AC1_, DeviceObj)
    External (_SB_.VMOD.BAT1, DeviceObj)
    External (_SB_.VMOD.BAT1.XSTA, MethodObj)    // 0 Arguments
    External (_SB_.VMOD.TPM2, DeviceObj)
    External (_SB_.VMOD.TPM2.XSTA, MethodObj)    // 0 Arguments
    External (BCFG, FieldUnitObj)
    External (NCFG, FieldUnitObj)
    External (PCNT, FieldUnitObj)
    External (SCFG, FieldUnitObj)
    External (SGXE, FieldUnitObj)
    External (TCFG, FieldUnitObj)

    Scope (\_SB.P001)
    {
        If (_OSI ("Darwin"))
        {
            Method (_DSM, 4, NotSerialized)  // _DSM: Device-Specific Method
            {
                If ((Arg2 == Zero))
                {
                    Return (Buffer (One)
                    {
                         0x03                                             // .
                    })
                }

                Return (Package (0x02)
                {
                    "plugin-type", 
                    0x02
                })
            }
        }
    }
}

