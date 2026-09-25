"""
net: Network transport and remote API helpers.

Deliberately imports nothing: network_handler.py creates a requests.Session and
does `from PySide6.QtWidgets import *` at import time. Import submodules
explicitly.
"""

__all__ = []
