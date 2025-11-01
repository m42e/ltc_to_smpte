#!/usr/bin/env python3
"""Package built PyInstaller executables into a distributable zip.

Expected prior steps:
  pyinstaller --onefile --name ltc_to_smpte ltc_to_smpte.py
  pyinstaller --onefile --windowed --name timecode_gui timecode_gui.py

This script:
  * Detects platform/arch
  * Copies executables from dist/ into a staging directory
  * Generates CHECKSUMS.txt (SHA256)
  * Creates README_DISTRIBUTION.md subset of main README
  * Zips everything to ltc_to_smpte_<platform>_<arch>.zip

External tools: by default ffmpeg/ffprobe are not bundled. If env var BUNDLE_FFMPEG=1
is set and ffmpeg/ffprobe are found (or placed in ffmpeg_bundle/), they are copied
into the archive under `ffmpeg/` with a minimal NOTICE.
"""
from __future__ import annotations
import hashlib
import platform
import shutil
import sys
import zipfile
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
BUILD = ROOT / "build_dist"
README = ROOT / "README.md"
LICENSE = ROOT / "LICENSE"

CLI_NAME = "ltc_to_smpte"
GUI_NAME = "timecode_gui"

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()

def make_subset_readme(out: Path):
    if not README.exists():
        out.write_text("LTC to SMPTE Tool\n", encoding='utf-8')
        return
    text = README.read_text(encoding='utf-8')
    # Keep only top + prerequisites + usage + GUI Usage
    keep_sections = ["# LTC to SMPTE Converter", "## Prerequisites", "## Usage", "## GUI Usage"]
    lines = text.splitlines()
    kept: list[str] = []
    capture = False
    current_header = None
    for line in lines:
        if line.startswith('#'):
            current_header = line.strip()
            capture = any(current_header.startswith(sec) for sec in keep_sections)
        if capture:
            kept.append(line)
    kept.append("\n---\nFull documentation: See repository README.md online.\n")
    out.write_text("\n".join(kept), encoding='utf-8')

def main():
    if not DIST.exists():
        print("dist/ directory missing. Run PyInstaller first.", file=sys.stderr)
        sys.exit(1)

    exe_suffix = ".exe" if platform.system() == "Windows" else ""
    cli_exec = DIST / f"{CLI_NAME}{exe_suffix}"
    gui_exec = DIST / f"{GUI_NAME}{exe_suffix}"
    if not cli_exec.exists() or not gui_exec.exists():
        print("Required executables not found in dist/", file=sys.stderr)
        sys.exit(1)

    if BUILD.exists():
        shutil.rmtree(BUILD)
    BUILD.mkdir(parents=True)

    # Copy binaries
    shutil.copy2(cli_exec, BUILD / cli_exec.name)
    shutil.copy2(gui_exec, BUILD / gui_exec.name)

    # Copy license
    if LICENSE.exists():
        shutil.copy2(LICENSE, BUILD / LICENSE.name)

    # Generate subset README
    subset = BUILD / "README_DISTRIBUTION.md"
    make_subset_readme(subset)

    # Checksums
    checksums_path = BUILD / "CHECKSUMS.txt"
    with checksums_path.open('w', encoding='utf-8') as f:
        for artifact in [cli_exec.name, gui_exec.name]:
            digest = sha256_file(BUILD / artifact)
            f.write(f"{digest}  {artifact}\n")

    # Optional ffmpeg bundling
    if os.environ.get("BUNDLE_FFMPEG") == "1":
        ffmpeg_dir = BUILD / "ffmpeg"
        ffmpeg_dir.mkdir(exist_ok=True)
        bundle_src = ROOT / "ffmpeg_bundle"
        copied: list[str] = []
        if bundle_src.exists():
            for item in bundle_src.iterdir():
                if item.is_file() and (item.name.startswith("ffmpeg") or item.name.startswith("ffprobe")):
                    shutil.copy2(item, ffmpeg_dir / item.name)
                    copied.append(item.name)
        else:
            for bin_name in ["ffmpeg", "ffprobe"]:
                path = shutil.which(bin_name)
                if path:
                    shutil.copy2(path, ffmpeg_dir / bin_name)
                    copied.append(bin_name)
        notice = ffmpeg_dir / "NOTICE.txt"
        notice.write_text(
            "This distribution includes ffmpeg binaries for user convenience.\n"
            "ffmpeg is licensed under LGPL/GPL depending on build configuration.\n"
            "Project: https://ffmpeg.org | Legal: https://ffmpeg.org/legal.html\n"
            f"Included files: {', '.join(copied) if copied else 'NONE'}\n",
            encoding="utf-8"
        )
        with checksums_path.open('a', encoding='utf-8') as f:
            for item in copied + ["NOTICE.txt"]:
                digest = sha256_file(ffmpeg_dir / item)
                f.write(f"{digest}  ffmpeg/{item}\n")

    plat = platform.system().lower()
    arch = platform.machine().lower()
    zip_name = f"ltc_to_smpte_{plat}_{arch}.zip"
    zip_path = ROOT / zip_name
    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for p in BUILD.iterdir():
            if p.is_dir():
                for sub in p.rglob('*'):
                    z.write(sub, sub.relative_to(BUILD).as_posix())
            else:
                z.write(p, p.name)

    print(f"Created artifact: {zip_path}")

if __name__ == '__main__':
    main()
