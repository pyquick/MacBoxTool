"""
icon_to_assets.py: Convert macOS 26 .icon files to Assets.car and AppIcon.icns
"""

import json
import shutil
import subprocess
import tempfile
from pathlib import Path


def _ita_project_dir() -> Path:
    """Resolve payloads/ITA/d/ relative to the project root."""
    return Path(__file__).resolve().parent.parent.parent / "payloads" / "ITA" / "d"


def _place_icon(icon_path: Path) -> tuple[Path, Path, Path]:
    """Copy the .icon as AppIcon.icon into the Xcode source tree.

    Returns: (project_dir, source_dir, build_dir)
    """
    project_dir = _ita_project_dir()
    source_dir = project_dir / "d"
    build_dir = project_dir / "build"

    source_dir.mkdir(parents=True, exist_ok=True)
    target_icon = source_dir / "AppIcon.icon"

    if target_icon.exists():
        if target_icon.is_dir():
            shutil.rmtree(target_icon)
        else:
            target_icon.unlink()

    if icon_path.is_dir():
        shutil.copytree(icon_path, target_icon)
    else:
        shutil.copy2(icon_path, target_icon)

    return project_dir, source_dir, build_dir


def _cleanup_icon(source_dir: Path):
    """Remove AppIcon.icon from the Xcode source tree."""
    target = source_dir / "AppIcon.icon"
    if target.exists():
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()


def _extract_assets(build_dir: Path) -> tuple[Path, Path]:
    """Extract Assets.car and AppIcon.icns from the built .app."""
    app_path = build_dir / "Build" / "Products" / "Release" / "d.app"
    resources = app_path / "Contents" / "Resources"

    assets_car = resources / "Assets.car"
    appicon_icns = resources / "AppIcon.icns"

    if not assets_car.exists():
        raise FileNotFoundError(f"Assets.car not found at {assets_car}")
    if not appicon_icns.exists():
        raise FileNotFoundError(f"AppIcon.icns not found at {appicon_icns}")

    out_dir = Path(tempfile.mkdtemp(prefix="icon_assets_"))
    out_car = out_dir / "Assets.car"
    out_icns = out_dir / "AppIcon.icns"
    shutil.copy2(assets_car, out_car)
    shutil.copy2(appicon_icns, out_icns)

    return out_car, out_icns


def convert_icon_file(icon_path: str | Path) -> tuple[Path, Path]:
    """Convert a macOS 26 .icon into Assets.car and AppIcon.icns.

    Returns: (assets_car, appicon_icns) — paths to the output files.
    """
    icon_path = Path(icon_path).resolve()
    if not icon_path.exists():
        raise FileNotFoundError(f"Icon file not found: {icon_path}")

    project_dir, source_dir, build_dir = _place_icon(icon_path)

    try:
        result = subprocess.run(
            [
                "xcodebuild", "-project", "d.xcodeproj",
                "-scheme", "d",
                "-configuration", "Release",
                "-sdk", "macosx",
                "-derivedDataPath", str(build_dir.resolve()),
            ],
            cwd=project_dir,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"xcodebuild failed (exit {result.returncode}):\n"
                f"{result.stderr}\n{result.stdout}"
            )

        return _extract_assets(build_dir)
    finally:
        _cleanup_icon(source_dir)


def convert_icon_file_streaming(icon_path: str | Path, on_log=None) -> tuple[Path, Path]:
    """Same as convert_icon_file but streams xcodebuild output via on_log(line).

    on_log: callable(str) — called with each output line during the build.
    Returns: (assets_car, appicon_icns)
    """
    icon_path = Path(icon_path).resolve()
    if not icon_path.exists():
        raise FileNotFoundError(f"Icon file not found: {icon_path}")

    project_dir, source_dir, build_dir = _place_icon(icon_path)

    try:
        cmd = [
            "xcodebuild", "-project", "d.xcodeproj",
            "-scheme", "d",
            "-configuration", "Release",
            "-sdk", "macosx",
            "-derivedDataPath", str(build_dir.resolve()),
        ]
        proc = subprocess.Popen(
            cmd,
            cwd=project_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        for line in proc.stdout:
            line = line.rstrip("\n\r")
            if on_log:
                on_log(line)

        proc.wait()

        if proc.returncode != 0:
            raise RuntimeError(f"xcodebuild failed (exit {proc.returncode})")

        return _extract_assets(build_dir)
    finally:
        _cleanup_icon(source_dir)


def _is_xcode_available() -> bool:
    """Return True when xcodebuild is on PATH."""
    return shutil.which("xcodebuild") is not None
