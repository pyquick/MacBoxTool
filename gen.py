from pathlib import Path
import json

from MacBoxTool import constants


DEFAULT_MANIFEST_PATH = Path("deploy/manifest.json")


def generate_manifest(commit_info: tuple, manifest_path: Path = DEFAULT_MANIFEST_PATH) -> None:
    constant = constants.Constants()

    if not commit_info or len(commit_info) < 1:
        raise ValueError("commit_info is required to generate manifest.json")

    if commit_info[0].startswith("refs/tags"):
        is_nightly = False
    else:
        is_nightly = True

    version = {
        "version": constant.macboxtool_version,
        "build": constant.nightly_build,
        "core": constant.support_version,
        "nightly": is_nightly
    }

    with open(manifest_path, "w+", encoding="utf-8") as fs:
        json.dump(version, fs, indent=4)

    print("manifest.json is created.")


