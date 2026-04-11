from ..datasets import (
    cpu_data,
    os_data,
)
from ..constants import *
import platform
cpu_supported = {
    os_data.os_data.tiger.value:{
        cpu_data.CPUGen.yonah.value,
        cpu_data.CPUGen.conroe.value,
        cpu_data.CPUGen.penryn.value,
        cpu_data.CPUGen.nehalem.value,
        cpu_data.CPUGen.sandy_bridge.value,
        cpu_data.CPUGen.ivy_bridge.value,
        cpu_data.CPUGen.haswell.value,
        cpu_data.CPUGen.broadwell.value,
        cpu_data.CPUGen.skylake.value,
        cpu_data.CPUGen.kaby_lake.value,
        cpu_data.CPUGen.coffee_lake.value,
        cpu_data.CPUGen.ice_lake.value,
        cpu_data.CPUGen.comet_lake.value,
        cpu_data.CPUGen.rocket_lake.value,
        cpu_data.CPUGen.alder_lake.value,
        cpu_data.CPUGen.rocket_lake.value,
        cpu_data.CPUGen.arrow_lake.value,
    }
}
supported_intel_cpu_ids = {
    # Because of spoofing, we only list 1-10 gen cpus
    cpu_data.CPUMODEL.penryn.value,
    cpu_data.CPUMODEL.nehalem.value,
    cpu_data.CPUMODEL.sandy_bridge.value,
    cpu_data.CPUMODEL.ivy_bridge.value,
    cpu_data.CPUMODEL.haswell.value,
    cpu_data.CPUMODEL.broadwell.value,
    cpu_data.CPUMODEL.skylake.value,
    cpu_data.CPUMODEL.kaby_lake.value,
    cpu_data.CPUMODEL.coffee_lake.value,
    cpu_data.CPUMODEL.ice_lake.value,
    cpu_data.CPUMODEL.comet_lake.value,
}
intel_all_ids = cpu_data.CPUMODEL.all_intel_ids.value

class CheckCPU:
    def __init__(self,global_constants:Constants):
        self.constants=global_constants
        self.computer=self.constants.computer
    def check_if_x86_64(self):
        if platform.machine=="x86_64":
            return 1
        return 0
    def check_if_intel_cpu(self):
        if 