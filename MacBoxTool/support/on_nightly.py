"""
on_nightly.py: Give Nightly / Stable
"""
from .. import constants
class CheckNightly:
    def __init__(self,global_constants:constants.Constants):
        
        self.constants:constants.Constants=global_constants
        self.commit_info=self.constants.commit_info

    def check(self):
        if self.commit_info[0].startswith("refs/tags"):
            return False
        return True
    
    def warning(self):
        text="The Nightly version is unstable; it may fix previous issues but could also introduce new bugs. Please use it with caution.\nThe Nightly source code originates from main."
        return text