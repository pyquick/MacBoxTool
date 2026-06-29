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
    manifest = response.json()
    nightly_latest = manifest["nightly_latest"]
    stable_latest = manifest["stable_latest"]

    if is_nightly:
        version = {
            "Note":"Please update to 0.0.3.2(Nightly) by 2026-07-02-00:00:00 UTC.",
            "version": constant.macboxtool_version,
            "build": constant.nightly_build,
            "core": constant.support_version,
            "nightly":is_nightly,
            "nightly_latest": {
                "version":constant.macboxtool_version,
                "build":constant.nightly_build,
                "core":constant.support_version,
            },
            "stable_latest":{
                "version":stable_latest["version"],
                "build":stable_latest["build"],
                "core":stable_latest["core"]
            }
        }
    else:
        version = {
            "Note":"Please update to 0.0.3.2(Nightly) by 2026-07-02-00:00:00 UTC.",
            "version": constant.macboxtool_version,
            "build": constant.nightly_build,
            "core": constant.support_version,
            "nightly":is_nightly,
            "nightly_latest":{
                "version":nightly_latest["version"],
                "build":nightly_latest["build"],
                "core":nightly_latest["core"]
            },
            "stable_latest": {
                "version":constant.macboxtool_version,
                "build":constant.nightly_build,
                "core":constant.support_version,
            }
        }

    with open(manifest_path, "w+", encoding="utf-8") as fs:
        json.dump(version, fs, indent=4)

    print("manifest.json is created.")

