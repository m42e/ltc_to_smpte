# LTC to SMPTE Converter

Extract LTC (Linear Timecode) audio from a video's second stereo channel, decode it, and write it back as SMPTE timecode metadata — **without re‑encoding the original video/audio streams**.

Fast, lossless metadata injection for professional workflows (edit conforming, batch tagging, archival).

---

## Table of Contents

1. [Features](#features)
2. [How It Works](#how-it-works)
3. [Prerequisites](#prerequisites)
4. [Usage](#usage)
5. [Set Up Python with Astral uv](#set-up-python-with-astral-uv)
6. [Examples](#examples)
7. [Verification](#verification)
8. [Performance](#performance)
9. [Troubleshooting](#troubleshooting)
10. [Roadmap / Ideas](#roadmap--ideas)
11. [License / Attribution](#license--attribution)
12. [Install Dependencies](#install-dependencies)
13. [Quick Start (TL;DR)](#quick-start-tldr)
14. [GUI Usage](#gui-usage)
15. [Binary Distribution](#binary-distribution)

---

## Features

✓ Professional-grade LTC decode via `ltcdump` (from ltc-tools)  
✓ Bit-level fallback decoder (zero‑crossing analysis) if external tool unavailable  
✓ No re-encoding: uses ffmpeg stream copy (`-c copy`) for speed and fidelity  
✓ SMPTE timecode written as metadata tag (`timecode`)  
✓ Supports multiple frame rates & sample rates  
✓ Graceful degradation and error handling  
✓ Cross-platform workflow guidance

---

## How It Works

1. Extracts the second audio channel (assumed to carry LTC) to a mono WAV. Works for RODE Wireless Pro.
2. Attempts decode using `ltcdump` (fast, robust).
3. If `ltcdump` unavailable, performs bit-level / edge detection decoding.
4. Injects SMPTE timecode as metadata into a new container using ffmpeg stream copy.
5. Leaves original video/audio encoding untouched (only container metadata changes).

---

## Prerequisites

You need:

- `ffmpeg` (for extraction / muxing)
- `ltc-tools` (for `ltcdump`) – optional but recommended
- Python (3.9+ recommended)
- `numpy` (signal processing / decoding fallback)

> If you prefer not to manage virtual environments manually, this guide uses **[Astral uv](https://github.com/astral-sh/uv)** for ultra-fast Python environment & dependency management.

---

## Usage

Basic invocation:

```bash
uv run ltc_to_smpte.py input_video.mp4 -o output_video_with_tc.mp4
```

Show help:

```bash
uv run ltc_to_smpte.py --help
```

### Expected Workflow

1. Ensure channel 2 of the source video’s audio track contains a valid LTC signal.
2. Run the script; it extracts mono LTC WAV.
3. Decoding occurs (prefers `ltcdump`).
4. Output file is written with `timecode` metadata.

---

## Set Up Python with Astral uv

### Install uv

macOS / Linux:

```bash
curl -LsSf https://astral.sh/install.sh | sh
```

Windows (PowerShell):

```powershell
irm https://astral.sh/install.ps1 | iex
```

Restart your shell if `uv` is not immediately available.

## Install Dependencies

This section installs both `ffmpeg` and `ltc-tools` (for `ltcdump`). If `ltc-tools` isn't packaged for your OS, a source build fallback is provided.

### macOS (Homebrew)

```bash
brew update
brew install ffmpeg ltc-tools
ffmpeg -version
ltcdump --help || echo "ltcdump installed"
```

### Debian / Ubuntu

```bash
sudo apt update
sudo apt install -y ffmpeg ltc-tools || echo "ltc-tools package missing; will build from source"
ffmpeg -version
command -v ltcdump >/dev/null || {
  # Source build fallback for ltc-tools
  sudo apt install -y build-essential autoconf automake libtool pkg-config git
  git clone https://github.com/x42/libltc.git
  cd libltc && ./autogen.sh && ./configure && make -j$(nproc) && sudo make install && sudo ldconfig || true && cd ..
  git clone https://github.com/x42/ltc-tools.git
  cd ltc-tools && make -j$(nproc) && sudo make install && cd ..
}
ltcdump --help || echo "Warning: ltcdump not found"
```

### Fedora

```bash
sudo dnf install -y ffmpeg ffmpeg-libs || sudo dnf config-manager --set-enabled rpmfusion-free rpmfusion-nonfree && sudo dnf install -y ffmpeg ffmpeg-libs
sudo dnf install -y ltc-tools || echo "ltc-tools not packaged; building from source"
ffmpeg -version
command -v ltcdump >/dev/null || {
  sudo dnf install -y git make autoconf automake libtool pkgconfig gcc
  git clone https://github.com/x42/libltc.git
  cd libltc && ./autogen.sh && ./configure && make -j$(nproc) && sudo make install && cd ..
  git clone https://github.com/x42/ltc-tools.git
  cd ltc-tools && make -j$(nproc) && sudo make install && cd ..
}
ltcdump --help || echo "Warning: ltcdump not found"
```

### Arch / Manjaro

```bash
sudo pacman -Syu --needed ffmpeg || true
sudo pacman -S --needed ltc-tools || echo "Package not found; building from source"
ffmpeg -version
command -v ltcdump >/dev/null || {
  sudo pacman -S --needed git base-devel autoconf automake libtool pkgconf
  git clone https://github.com/x42/libltc.git
  cd libltc && ./autogen.sh && ./configure && make -j$(nproc) && sudo make install && cd ..
  git clone https://github.com/x42/ltc-tools.git
  cd ltc-tools && make -j$(nproc) && sudo make install && cd ..
}
ltcdump --help || echo "Warning: ltcdump not found"
```

### openSUSE

```bash
sudo zypper refresh
sudo zypper install -y ffmpeg || echo "Enable Packman repo if missing"
sudo zypper install -y ltc-tools || echo "ltc-tools not packaged; building from source"
ffmpeg -version
command -v ltcdump >/dev/null || {
  sudo zypper install -y git gcc make autoconf automake libtool pkg-config
  git clone https://github.com/x42/libltc.git
  cd libltc && ./autogen.sh && ./configure && make -j$(nproc) && sudo make install && sudo ldconfig || true && cd ..
  git clone https://github.com/x42/ltc-tools.git
  cd ltc-tools && make -j$(nproc) && sudo make install && cd ..
}
ltcdump --help || echo "Warning: ltcdump not found"
```

### Windows (winget / Chocolatey / Scoop + WSL optional)

```bash
# Option A: winget (global ffmpeg only)
winget install --id=Gyan.FFmpeg -e

# Option B: Chocolatey
choco install ffmpeg -y

# Option C: Scoop
scoop install ffmpeg

# ltc-tools: Use WSL (Ubuntu) for easiest build
wsl --install -d Ubuntu || echo "WSL already installed"
wsl sudo apt update
wsl sudo apt install -y ffmpeg build-essential autoconf automake libtool pkg-config git
wsl bash -lc 'git clone https://github.com/x42/libltc.git && cd libltc && ./autogen.sh && ./configure && make -j$(nproc) && sudo make install && cd ..'
wsl bash -lc 'git clone https://github.com/x42/ltc-tools.git && cd ltc-tools && make -j$(nproc) && sudo make install'
wsl ltcdump --help || echo "ltcdump built inside WSL"
```

### Dependency Verification

```bash
ffmpeg -version || echo "ffmpeg missing" 
ltcdump --help || echo "ltcdump missing (fallback decoder will be used)" 
```

> If `ltcdump` is not available after attempting install, the script will automatically use its internal LTC decoder.

---

## Examples

```bash
# Simple conversion
uv run ltc_to_smpte.py clip.mov -o clip_tc.mov

# Verbose (if supported by script)
uv run ltc_to_smpte.py clip.mov -o clip_tc.mov -v
```

---

## Verification

Use `ffprobe` to inspect the added timecode tag:

```bash
ffprobe -hide_banner -show_entries format_tags=timecode -of default=noprint_wrappers=1:nokey=1 clip_tc.mov
```

Or more broadly:

```bash
ffprobe -hide_banner -show_entries stream_tags=timecode -of json clip_tc.mov
```

If present, you’ll see something like:

```text
01:23:45:12
```

---

## Performance

- Decoding (ltcdump): < 1s typical
- Fallback decode: a few seconds (depends on length & sample rate)
- Muxing (copy): near-instant for small clips; scales with file size but avoids re-encode
- Output size: ≈ input size (only container metadata changes)

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `ltcdump: command not found` | ltc-tools not installed / PATH issue | Install ltc-tools or rebuild from source |
| No `timecode` tag in output | LTC channel empty / low level / wrong channel | Confirm channel mapping; ensure LTC amplitude; try boosting gain before extraction |
| Fallback decoder produces wrong TC | Noisy signal / drift | Prefer `ltcdump`; try cleaning audio or increasing threshold parameters (if exposed) |
| ffprobe shows different frame rate | Container vs LTC mismatch | Ensure LTC frame rate matches intended SMPTE rate; consider adding explicit `-timecode_rate` (future enhancement) |

### Signal Quality Tips

- LTC should be a clean square-like wave; avoid heavy compression.
- Keep sample rate ≥ 48 kHz.
- Avoid dual-mono mixes combining program audio & LTC.

---

## Roadmap / Ideas

- Add pyproject.toml / structured packaging
- Automatic LTC channel detection (energy/profile analysis)
- Batch processing directory mode
- Noise-robust decoder improvements (adaptive edge detection)
- Optional JSON export of timecode spans
- CI workflow (lint + minimal test vector)

---

## License / Attribution

Licensed under the [MIT License](LICENSE). You are free to use, modify, distribute, and sublicense with minimal restriction.

This tool leverages external utilities: `ffmpeg` and `ltc-tools` (libltc by x42). Those projects retain their own licenses; ensure compliance when redistributing combined artifacts.

---

## Quick Start (TL;DR)

```bash
brew install ffmpeg ltc-tools              # macOS example
curl -LsSf https://astral.sh/install.sh | sh
uv venv && source .venv/bin/activate
uv pip install -r requirements.txt         # installs numpy
uv run ltc_to_smpte.py input.mp4 -o output_tc.mp4
ffprobe -show_entries format_tags=timecode -of default=noprint_wrappers=1:nokey=1 output_tc.mp4
```

---

> Need help or found an edge case? Open an issue or extend the script—contributions welcome.

## GUI Usage

A minimal cross‑platform GUI (`timecode_gui.py`) allows drag & drop (when `tkinterdnd2` is installed) or manual file selection.

### Run

```bash
python timecode_gui.py
```

If using `uv`:

```bash
uv run timecode_gui.py
```

### Drag & Drop Support

Drag & drop uses the optional package `tkinterdnd2`. Install it for enhanced UX:

```bash
uv pip install tkinterdnd2  # or: pip install tkinterdnd2
```

Without it, the GUI still works—use the "Select File" button.

### Output Naming

The output file is created next to the input with `_tc` inserted before the extension:

```text
input.mov -> input_tc.mov
clip.mp4  -> clip_tc.mp4
```

### Notes

- Requires `ffmpeg` in PATH.
- `ltcdump` is optional; if missing, the internal fallback decoder is used (slower / less robust).
- Processing runs in a background thread; status and log messages appear in the window.

## Binary Distribution

Pre-built zip bundles for macOS, Windows, and Linux are published on the GitHub Releases page (tagged `v*`). Each archive contains:

```text
ltc_to_smpte           # CLI executable
timecode_gui           # GUI executable (or .exe on Windows)
LICENSE
README_DISTRIBUTION.md # Minimal usage & prerequisites
CHECKSUMS.txt          # SHA256 hashes
```

All Python dependencies (numpy, optional tkinterdnd2 if installed during build) are statically bundled inside the executables via PyInstaller—no Python installation required.

### External Tools Still Required

- `ffmpeg` must be installed and available in your PATH.
- `ltcdump` (from ltc-tools) is optional; if missing the internal fallback decoder is used.

### Verify Integrity

Run a checksum:

```bash
shasum -a 256 ltc_to_smpte  # macOS / Linux
certutil -hashfile ltc_to_smpte.exe SHA256  # Windows (PowerShell)
```

Compare against `CHECKSUMS.txt`.

### Run Binaries

```bash
./ltc_to_smpte input.mp4 -o output_tc.mp4   # macOS / Linux
./timecode_gui                               # macOS / Linux GUI
ltc_to_smpte.exe input.mp4 -o output_tc.mp4 # Windows
timecode_gui.exe                            # Windows GUI
```

If you see errors about `ffmpeg` not found, install it via your platform package manager (see earlier prerequisites section).

Gatekeeper / SmartScreen: Binaries are unsigned; on macOS choose "Open Anyway" in System Settings if prompted. On Windows click "More info" then "Run anyway".
