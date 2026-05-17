#!/usr/bin/env python3
"""
Test script to verify Fluent-Widgets theme timing behavior
"""

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
import sys
import time

# Add project path
sys.path.insert(0, '/Users/ghltbm/Documents/MacBoxTool')

from MacBoxTool.UIkit.components.widgets import StrongBodyLabel
from MacBoxTool.UIkit.common.config import qconfig, Theme

def test_theme_timing():
    app = QApplication(sys.argv)

    print("=== Testing Fluent-Widgets Theme Timing ===")
    print(f"Initial theme: {qconfig.theme}")

    # Create label
    print("\n1. Creating StrongBodyLabel...")
    title_label = StrongBodyLabel("Test Title")

    # Check initial color
    initial_style = title_label.styleSheet()
    print(f"2. Initial stylesheet: {initial_style}")

    # Set custom color immediately
    custom_color = "#82B4F0"
    print(f"\n3. Setting custom color: {custom_color}")
    title_label.setStyleSheet(f"color: {custom_color}; font-size: 16px;")

    # Check color immediately after setting
    immediate_style = title_label.styleSheet()
    print(f"4. Immediate stylesheet: {immediate_style}")

    # Use timer to check after event loop processes
    def check_after_delay():
        delayed_style = title_label.styleSheet()
        print(f"\n5. Stylesheet after event loop: {delayed_style}")

        # Check if custom color was overridden
        if custom_color in delayed_style:
            print(f"✓ Custom color {custom_color} preserved")
        else:
            print(f"✗ Custom color {custom_color} was overridden!")
            print(f"  Current color likely reverted to default theme color")

        app.quit()

    # Process events and check after delay
    QTimer.singleShot(100, check_after_delay)

    app.exec()

if __name__ == "__main__":
    test_theme_timing()