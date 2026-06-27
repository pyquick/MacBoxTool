"""
support.py: provide API through update, easy to visit Github API for update
"""
from ... import constants as constants
import requests
import platform

class VisitGithubAPI:
    def __init__(self,constants:constants.Constants,repo_name:str="MacBoxTool",token:str="",user:str="pyquick"):
        self.constants:constants.Constants= constants
        self.token:str = token or getattr(self.constants, "github_token", "") or ""
        self.url=f"https://api.github.com/repos/{user}/{repo_name}/releases/latest"
        self.find_latest_release_stable()

    def _github_headers(self) -> dict:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    # TODO:TOKEN Use
    def find_latest_release_stable(self)->None:
        r=requests.get(self.url, headers=self._github_headers(), verify=False)
        self.information:dict= r.json()
        self.latest_tag_name:str=self.information["tag_name"]
        self.tag_name_list:list=self.latest_tag_name.split(".")

        # assets will deal with on assets_decode function
        self.assets:list=self.information["assets"]

        self.target_branch:str=self.information["target_commitish"] # Usually main branches or others
        self.release_name:str=self.information["name"] # in MBT, same as MBT tag
        self.publish_time:str=self.information["published_at"] # like 2026-05-04T12:21:37Z
        self.changelog:str=self.information["body"] # need markdown decode

    def arch_check(self) -> list:
        import platform
        if platform.machine()=="x86_64": return ["build-app-qt-intel","MacBoxTool-x86_64.pkg"]
        elif platform.machine()=="arm64":return ["build-app-qt-arm","MacBoxTool-arm64.pkg"]

    def find_and_compare_latest_release_nightly(self) -> list[bool,str,str]:
        self.nightly_url = f"https://nightly.link/pyquick/MacBoxTool/workflows/{self.arch_check()[0]}/main/{self.arch_check()[1]}.zip"
        self.check_url="https://pyquick.github.io/MacBoxTool/manifest.json"
        self.local_version_ni=self.constants.nightly_build.split(".")
        request=requests.get(self.check_url,verify=False)
        manifest:dict=request.json()
        self.remote_version_ni = str(manifest["build"]).split(".")
        for ma in range(2):
            if self.remote_version_ni[ma] > self.local_version_ni[ma]:
                return True,self.nightly_url,self.arch_check()[1]
        return False,"",""

    def compare_tags(self)->bool:
        self.local_version:list=self.constants.macboxtool_version.split(".")
        # if Internet version <= local version return false
        # If need update ,return True
        for ma in range(0,3,1):
            if self.local_version[ma] < self.tag_name_list[ma]:
                return True
        return False
    
    def update_log(self)->str:
        return self.changelog
    
    def update_version(self)->str:
        return self.latest_tag_name
    
    def assets_decode(self)->dict:
        self.datas:list=[]
        
        for i in range(len(self.assets)):
            install:dict={
                "name":"",
                "arch":"",
                "download_url":"",
            }
            install["download_url"] = self.assets[i]["browser_download_url"]
            install["name"] = self.assets[i]["name"]
            if "Uninstaller" in self.assets[i]["name"] or "uninstaller" in self.assets[i]["name"]:
                # We dont need to download uninstaller
                continue
            elif "x86_64" in self.assets[i]["name"] and "x86_64" in platform.machine():
                install ["arch"] = "x86_64"
            elif "arm64" in self.assets[i]["name"] and "arm64" in platform.machine():
                install ["arch"] = "arm64" 
            else:
                continue
            self.datas.append(install)

        print(self.datas)  

        return self.datas[0]