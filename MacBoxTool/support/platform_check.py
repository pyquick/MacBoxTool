 

import platform

def platfrom_check():
    machine=platform.machine()
    if "x86_64" in machine:
        return "x86_64"
    if "ARM64" in machine or "Arm64" in machine or "arm64" in machine:
        return "arm64"
    return "x86_64"