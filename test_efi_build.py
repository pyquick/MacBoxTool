"""
test_efi_build.py: Test script for EFI builder
Run with: python test_efi_build.py --model MacPro7,1
"""
import sys
import os
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from MacBoxTool.support import utilities_win as utilities
from MacBoxTool.efi_mac.build import BuildOpenCore
from MacBoxTool.constants import Constants
from MacBoxTool.datasets import model_array

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)


def main():
    print("=== MacBoxTool EFI Builder Test ===")
    print(f"Supported Models: {len(model_array.SupportedSMBIOS)}")
    print(f"Build Path: {os.path.expanduser('~/.macboxtool/efi_builder')}")
    print()

    # Get test arguments
    args = utilities.get_test_args()
    test_model = args.get("model")

    if not test_model:
        print("Usage: python test_efi_build.py --model <SMBIOS>")
        print("Example: python test_efi_build.py --model MacPro7,1")
        print()
        print("Available models (first 10):")
        for m in model_array.SupportedSMBIOS[:10]:
            print(f"  - {m}")
        if len(model_array.SupportedSMBIOS) > 10:
            print(f"  ... and {len(model_array.SupportedSMBIOS) - 10} more")
        return

    print(f"Test Model: {test_model}")
    print()

    # Validate model
    if test_model not in model_array.SupportedSMBIOS:
        print(f"[ERROR] Model '{test_model}' is NOT in SupportedSMBIOS!")
        print("Build will fail. Choose from the list above.")
        return

    print(f"[OK] Model '{test_model}' is supported.")
    print()

    # Initialize constants
    constants = Constants()

    # Build EFI
    try:
        builder = BuildOpenCore(test_model, constants)
        logs = builder.build()

        print()
        print("=== Build Log ===")
        for line in logs:
            print(line)

        print()
        print("=== Test Complete ===")
        print(f"EFI output: {builder.oc_build}")

    except Exception as e:
        print(f"[ERROR] Build failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
