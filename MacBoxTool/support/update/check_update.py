"""
check_update.py: Build update-check results for the GUI layer.
"""
from .support import VisitGithubAPI
from ... import constants


UPDATE_RESULT_TEMPLATE: dict[str, object] = {
    "if_update": False,
    "update_log": "",
    "download_url": "",
    "download_name": "",
    "update_type": "",
    "error": False,
}


class CheckUpdate:
    """Check stable/nightly update availability and return download metadata."""

    def __init__(self, constants: constants.Constants):
        """Store constants and prepare the API helper."""
        self.constants = constants
        # When nightly checks are enabled, defer the stable release API call until
        # the nightly manifest has been checked.

        self.vg = VisitGithubAPI(constants=self.constants, fetch_latest=not self.constants.allow_nightly_check)
        self.changelog = ""
        self.prompt:dict = UPDATE_RESULT_TEMPLATE.copy()

    def check_update(self):
        """Return update availability plus the exact asset to download."""
        self.constants.stable_available = False
        self.stable_is_coming:bool = self.vg.is_higher_stable_is_coming()

        if not hasattr(self.vg, "latest_tag_name"):
            self.vg.find_latest_release_stable()

        if self.constants.allow_nightly_check and not self.stable_is_coming:
            nightly = self.vg.find_and_compare_latest_release_nightly()
            if nightly[0]:
                self.changelog = "Nightly Build didn't have any logs."
                self.prompt["if_update"] = True
                self.prompt["update_log"] = self.changelog
                self.prompt["download_url"] = nightly[1]
                self.prompt["download_name"] = f"{nightly[2]}.zip"
                self.prompt["update_type"] = "nightly"
                return self.prompt
        
        elif self.vg.compare_tags() or self.stable_is_coming:
            asset = self.vg.assets_decode()
            self.changelog = self.vg.update_log()

            self.prompt["if_update"] = True
            self.prompt["update_log"] = self.changelog
            self.prompt["download_url"] = asset["download_url"]
            self.prompt["download_name"] = asset["name"]
            self.prompt["update_type"] = "stable"
            
            self.constants.stable_available = True

        else:
            self.prompt["if_update"] = False
            self.prompt["update_log"] = "N/A"

        return self.prompt
