"""
acpi.py building acpi
"""
from ..include import *

class ACPIChooser:
    def __init__(self,global_constants:Constants):
        self.cpudata=cpu_data.CPUGen()
