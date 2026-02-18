"""
utilities.py: Utility functions for MacboxTool for Windows
"""

import os
import re
import math
import atexit
import shutil
import logging
import argparse
import binascii
import plistlib
import subprocess
import py_sip_xnu

from pathlib import Path

from .. import constants
import sys

from ..datasets import (
    os_data,
    sip_data
)

def hexswap(input_hex: str):
    #Example: 0x12345678
    hex_pairs = [input_hex[i : i + 2] for i in range(0, len(input_hex), 2)] 
    hex_rev = hex_pairs[::-1]
    hex_str = "".join(["".join(x) for x in hex_rev])
    return hex_str.upper()

def string_to_hex(input_string):
    if not (len(input_string) % 2) == 0:
        input_string = "0" + input_string
    input_string = hexswap(input_string)
    input_string = binascii.unhexlify(input_string)
    return input_string

def human_fmt(num):
    for unit in ["B", "KB", "MB", "GB", "TB", "PB"]:
        if abs(num) < 1000.0:
            return "%3.1f %s" % (num, unit)
        num /= 1000.0
    return "%.1f %s" % (num, "EB")

def seconds_to_readable_time(seconds) -> str:
    """
    Convert seconds to a readable time format

    Parameters:
        seconds (int | float | str): Seconds to convert

    Returns:
        str: Readable time format
    """
    seconds = int(seconds)
    time = ""

    if 0 <= seconds < 60:
        return "Less than a minute "
    if seconds < 0:
        return "Indeterminate time "

    years, seconds = divmod(seconds, 31536000)
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)

    if years > 0:
        return "Over a year"
    if days > 0:
        if days > 31:
            return "Over a month"
        time += f"{days}d "
    if hours > 0:
        time += f"{hours}h "
    if minutes > 0:
        time += f"{minutes}m "
    #if seconds > 0:
    #    time += f"{seconds}s"
    return time