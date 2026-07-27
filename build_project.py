#!/usr/bin/env python3
"""Cross-platform build entry point for MacBoxTool."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent


def parse_arguments() -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(description="Build MacBoxTool")
    parser.add_argument(
        "--platform",
        choices=("auto", "win", "macos"),
        default="auto",
        help="Build target platform (default: current platform)",
    )
    parser.add_argument("--clean", action="store_true", help="Clean Windows build files before compiling")
    parser.add_argument("--git-branch", help="Git branch or ref to embed in the build")
    parser.add_argument("--git-commit-url", help="Git commit URL to embed in the build")
    parser.add_argument("--git-commit-date", help="Git commit date to embed in the build")
    return parser.parse_known_args()


def build_git_arguments(args: argparse.Namespace) -> list[str]:
    """Return the commit metadata options accepted by both build entry points."""
    command: list[str] = []
    for option in ("git_branch", "git_commit_url", "git_commit_date"):
        value = getattr(args, option)
        if value:
            command.extend((f"--{option.replace('_', '-')}", value))
    return command


def build_windows(args: argparse.Namespace) -> None:
    command = [sys.executable, str(PROJECT_ROOT / "MacBoxTool" / "setup" / "build_setup.py")]
    if args.clean:
        command.append("--clean")
    command.extend(build_git_arguments(args))
    subprocess.run(command, cwd=PROJECT_ROOT, check=True)


def build_macos(args: argparse.Namespace, passthrough: list[str]) -> None:
    command = [
        sys.executable,
        str(PROJECT_ROOT / "Build-Project.command"),
        *build_git_arguments(args),
        *passthrough,
    ]
    subprocess.run(command, cwd=PROJECT_ROOT, check=True)


def main() -> None:
    args, passthrough = parse_arguments()
    target = args.platform
    if target == "auto":
        target = "win" if sys.platform == "win32" else "macos" if sys.platform == "darwin" else ""

    if target == "win":
        if sys.platform != "win32":
            raise SystemExit("The Windows target must be built on Windows.")
        build_windows(args)
    elif target == "macos":
        if sys.platform != "darwin":
            raise SystemExit("The macOS target must be built on macOS.")
        build_macos(args, passthrough)
    else:
        raise SystemExit("Unsupported host platform. Specify --platform win or --platform macos.")


if __name__ == "__main__":
    main()
