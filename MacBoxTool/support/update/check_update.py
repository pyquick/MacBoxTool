"""
Check Update.py provide head for GUI
"""
from .support import VisitGithubAPI 
from ... import constants
from ...support import on_nightly

class CheckUpdate:
    def __init__(self,constants:constants.Constants):
        self.constants=constants
        self.vg=VisitGithubAPI(constants=self.constants)
        self.changlog=""
        self.prompt={
            "if_update":bool,
            "update_log":str,
        }
        self.check_update()

    

    def check_update(self):
        if self.constants.allow_nightly_check:
            if self.vg.find_and_compare_latest_release_nightly()[0]:
                self.changlog = "Nightly Build didn't have any logs."
                self.prompt["if_update"]=True
                self.prompt["update_log"]=self.changlog
            else:
                if self.vg.compare_tags():
                    self.changlog=self.vg.update_log()
                    self.prompt["if_update"]=True
                    self.prompt["update_log"]=self.changlog
                    self.constants.stable_available = True
                else:
                    self.prompt["if_update"]=False
                    self.prompt["update_log"]="N/A"
        else:
            if self.vg.compare_tags():
                self.changlog=self.vg.update_log()
                self.prompt["if_update"]=True
                self.prompt["update_log"]=self.changlog
            else:
                self.prompt["if_update"]=False
                self.prompt["update_log"]="N/A"

        return self.prompt