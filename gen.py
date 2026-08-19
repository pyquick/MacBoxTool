from pathlib import Path
import json
import requests
from MacBoxTool import constants


DEFAULT_MANIFEST_PATH = Path("deploy/manifest.json")
FETCH_URL="https://pyquick.github.io/MacBoxTool/manifest.json"

def generate_manifest(commit_info: tuple, manifest_path: Path = DEFAULT_MANIFEST_PATH) -> None:
    constant = constants.Constants()

    if not commit_info or len(commit_info) < 1:
        raise ValueError("commit_info is required to generate manifest.json")

    if commit_info[0].startswith("refs/tags"):
        is_nightly = False
    else:
        is_nightly = True
    
    response = requests.get(FETCH_URL,verify=False)
    branch=str(commit_info[0]).split("/")[-1]
    manifest = response.json()
    nightly_latest_on_main_branch = manifest["nightly_latest"]["main"]
    nightly_latest_on_pyside2_branch = manifest["nightly_latest"]["PySide2"]
    stable_latest_on_main_branch = manifest["stable_latest"]["main"]
    stable_latest_on_pyside2_branch = manifest["stable_latest"]["PySide2"]

    if is_nightly:
        if branch=="main":
            version = {
                "nightly_latest": {
                    "main":{
                        "version":constant.macboxtool_version,
                        "build":constant.nightly_build,
                        "core":constant.support_version,
                        "minver":"22",
                    },
                    "PySide2":{
                        "version":nightly_latest_on_pyside2_branch["version"],
                        "build":nightly_latest_on_pyside2_branch["build"],
                        "core":nightly_latest_on_pyside2_branch["core"],
                        "minver":"17",
                    },
                },
                "stable_latest":{
                    "main":{
                        "version":stable_latest_on_main_branch["version"],
                        "build":stable_latest_on_main_branch["build"],
                        "core":stable_latest_on_main_branch["core"],
                        "minver":"22",
                    },
                    "PySide2":{
                        "version":stable_latest_on_pyside2_branch["version"],
                        "build":stable_latest_on_pyside2_branch["build"],
                        "core":stable_latest_on_pyside2_branch["core"],
                        "minver":"17",
                    },
                }
            }
        elif branch=="PySide2":
            version = {
                "nightly_latest": {
                    "main":{
                        "version":nightly_latest_on_main_branch["version"],
                        "build":nightly_latest_on_main_branch["build"],
                        "core":nightly_latest_on_main_branch["core"],
                        "minver":"22",
                    },
                    "PySide2":{
                        "version":constant.macboxtool_version,
                        "build":constant.nightly_build,
                        "core":constant.support_version,
                        "minver":"17",
                    },
                },
                "stable_latest":{
                    "main":{
                        "version":stable_latest_on_main_branch["version"],
                        "build":stable_latest_on_main_branch["build"],
                        "core":stable_latest_on_main_branch["core"],
                        "minver":"22",
                    },
                    "PySide2":{
                        "version":stable_latest_on_pyside2_branch["version"],
                        "build":stable_latest_on_pyside2_branch["build"],
                        "core":stable_latest_on_pyside2_branch["core"],
                        "minver":"17",
                    },
                }
            }
    else:
        if branch=="main":
            version = {
                "nightly_latest": {
                    "main":{
                        "version":nightly_latest_on_main_branch["version"],
                        "build":nightly_latest_on_main_branch["build"],
                        "core":nightly_latest_on_main_branch["core"],
                        "minver":"22",
                    },
                    "PySide2":{
                        "version":nightly_latest_on_pyside2_branch["version"],
                        "build":nightly_latest_on_pyside2_branch["build"],
                        "core":nightly_latest_on_pyside2_branch["core"],
                        "minver":"17",
                    },
                },
                "stable_latest":{
                    "main":{
                        "version":constant.macboxtool_version,
                        "build":constant.nightly_build,
                        "core":constant.support_version,
                        "minver":"22",
                    },
                    "PySide2":{
                        "version":stable_latest_on_pyside2_branch["version"],
                        "build":stable_latest_on_pyside2_branch["build"],
                        "core":stable_latest_on_pyside2_branch["core"],
                        "minver":"17",
                    },
                }
            }
        elif branch=="PySide2":
            version = {
                "nightly_latest": {
                    "main":{
                        "version":nightly_latest_on_main_branch["version"],
                        "build":nightly_latest_on_main_branch["build"],
                        "core":nightly_latest_on_main_branch["core"],
                        "minver":"22",
                    },
                    
                    "PySide2":{
                        "version":nightly_latest_on_pyside2_branch["version"],
                        "build":nightly_latest_on_pyside2_branch["build"],
                        "core":nightly_latest_on_pyside2_branch["core"],
                        "minver":"17",
                    },
                    
                },
                "stable_latest":{
                    "main":{
                        "version":stable_latest_on_main_branch["version"],
                        "build":stable_latest_on_main_branch["build"],
                        "core":stable_latest_on_main_branch["core"],
                        "minver":"22",
                    },
                    "PySide2":{
                        "version":constant.macboxtool_version,
                        "build":constant.nightly_build,
                        "core":constant.support_version,
                        "minver":"17",
                    },
                }
            }
    print(version)
    with open(manifest_path, "w+", encoding="utf-8") as fs:
        json.dump(version, fs, indent=4)

