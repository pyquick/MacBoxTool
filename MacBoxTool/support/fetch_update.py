from ..support import (
    network_handler
)
import os
import shutil
import requests
import logging
import markdown2

class UpdateFetch:
    url = "https://api.github.com/repos/pyquick/MacBoxTool/releases/latest"