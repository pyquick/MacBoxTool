"""Build the Windows MacBoxTool application and its one-file setup program."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SETUP_DIR = Path(__file__).resolve().parent
ICON_SOURCE = PROJECT_ROOT / "payloads" / "Icon" / "AppIcons" / "AppIcon.icns"
ICON_TARGET = PROJECT_ROOT / "payloads" / "Icon" / "AppIcons" / "AppIcon.ico"
APP_SPEC = SETUP_DIR / "macboxtool_win.spec"
SETUP_SPEC = SETUP_DIR / "setup.spec"
DIST_ROOT = PROJECT_ROOT / "dist" / "windows"
APP_DIST_ROOT = DIST_ROOT / "app"
SETUP_DIST_ROOT = DIST_ROOT / "setup"
BUILD_ROOT = PROJECT_ROOT / "build" / "windows"
COMMIT_INFO_NAME = "commit_info.json"


def run(command: list[str]) -> None:
    print("+", subprocess.list2cmdline(command))
    subprocess.run(command, cwd=PROJECT_ROOT, check=True)


def ensure_windows() -> None:
    if sys.platform != "win32":
        raise RuntimeError("Windows build is only supported on Windows.")


def ensure_requirements() -> None:
    """Fail early with the exact missing build/runtime dependency names."""
    requirements = PROJECT_ROOT / "requirements_Windows.txt"
    if not requirements.is_file():
        raise FileNotFoundError(f"Missing dependency manifest: {requirements}")

    try:
        import PyInstaller  # noqa: F401
        import PySide6  # noqa: F401
        import win32com.client  # noqa: F401
        import wmi  # noqa: F401
    except ImportError as error:
        raise RuntimeError(
            "Windows build dependencies are missing. Install them with:\n"
            f'  "{sys.executable}" -m pip install -r "{requirements}"'
        ) from error


def create_icon() -> None:
    """Convert AppIcon.icns to a Windows .ico using Pillow."""
    if not ICON_SOURCE.is_file():
        raise FileNotFoundError(f"Application icon not found: {ICON_SOURCE}")

    try:
        from PIL import Image
    except ImportError as error:
        raise RuntimeError("Pillow is required to convert AppIcon.icns to AppIcon.ico.") from error

    with Image.open(ICON_SOURCE) as image:
        image.save(
            ICON_TARGET,
            format="ICO",
            sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
        )

    if not ICON_TARGET.is_file():
        raise RuntimeError("Failed to create the Windows application icon.")


def clean_build_outputs() -> None:
    for path in (APP_DIST_ROOT, SETUP_DIST_ROOT, BUILD_ROOT):
        if path.exists():
            shutil.rmtree(path)


def commit_info_path(application_dir: Path) -> Path:
    """Return the metadata file embedded with the Windows application."""
    return application_dir / "_internal" / COMMIT_INFO_NAME


def write_commit_info(
    application_dir: Path,
    git_branch: str | None,
    git_commit_url: str | None,
    git_commit_date: str | None,
) -> Path:
    """Embed CI commit metadata before the application bundle enters setup."""
    metadata = {
        "Branch": git_branch or "Built from source",
        "Commit URL": git_commit_url or "",
        "Commit Date": git_commit_date or "",
    }
    target = commit_info_path(application_dir)
    target.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def verify_commit_info(application_dir: Path) -> None:
    """Ensure setup receives the exact metadata written for this build."""
    target = commit_info_path(application_dir)
    if not target.is_file():
        raise RuntimeError(f"Windows commit metadata was not embedded: {target}")
    data = json.loads(target.read_text(encoding="utf-8"))
    if not all(key in data for key in ("Branch", "Commit URL", "Commit Date")):
        raise RuntimeError(f"Windows commit metadata is invalid: {target}")


def build_application() -> Path:
    """Compile MacBoxTool first; setup always consumes this output."""
    run([
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--distpath",
        str(APP_DIST_ROOT),
        "--workpath",
        str(BUILD_ROOT / "application"),
        str(APP_SPEC),
    ])

    application_dir = APP_DIST_ROOT / "MacBoxTool"
    executable = application_dir / "MacBoxTool.exe"
    if not executable.is_file():
        raise RuntimeError(f"MacBoxTool application build did not produce: {executable}")
    return application_dir


def build_setup(application_dir: Path) -> Path:
    """Compile the installer only after the application bundle is complete."""
    if not (application_dir / "MacBoxTool.exe").is_file():
        raise RuntimeError("Refusing to build setup before MacBoxTool.exe is available.")
    verify_commit_info(application_dir)

    run([
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--distpath",
        str(SETUP_DIST_ROOT),
        "--workpath",
        str(BUILD_ROOT / "setup"),
        str(SETUP_SPEC),
    ])

    executable = SETUP_DIST_ROOT / "MacBoxTool_Setup.exe"
    if not executable.is_file():
        raise RuntimeError(f"Setup build did not produce: {executable}")
    return executable


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the Windows MacBoxTool setup program")
    parser.add_argument("--clean", action="store_true", help="Remove prior Windows build output first")
    parser.add_argument("--git-branch", help="Git branch or ref to embed in the Windows build")
    parser.add_argument("--git-commit-url", help="Git commit URL to embed in the Windows build")
    parser.add_argument("--git-commit-date", help="Git commit date to embed in the Windows build")
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    ensure_windows()
    ensure_requirements()
    if args.clean:
        clean_build_outputs()
    create_icon()
    application_dir = build_application()
    metadata = write_commit_info(
        application_dir,
        args.git_branch,
        args.git_commit_url,
        args.git_commit_date,
    )
    print(f"Embedded Windows commit metadata: {metadata}")
    setup = build_setup(application_dir)
    print(f"Windows setup build completed: {setup}")


if __name__ == "__main__":
    main()
