from MacBoxTool import constants
import json
from MacBoxTool.support import commit_info

constant=constants.Constants()
commit = commit_info.ParseCommitInfo(constant.launcher_binary).generate_commit_info()

if commit[0].startswith("refs/tags"):
    is_nightly = False
else:
    is_nightly = True

version={
    "version":constant.macboxtool_version,
    "build":constant.nightly_build,
    "core":constant.support_version,
    "nightly":is_nightly
}

with open("./deploy/manifest.json","w+",encoding="utf-8") as fs:
    json.dump(version,fs,indent=4)

print("manifest.json is created.")
