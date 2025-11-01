#!/usr/bin/env python3
# /// script
# requires-python = ">=3.14"
# dependencies = [
#     "numpy",
# ]
# ///
"""
LTC Audio Timecode Extractor and SMPTE Writer

This script extracts LTC (Linear Timecode) audio from the second stereo channel
of a video file, decodes it to timecode, and writes it back to the video as SMPTE metadata.

Requirements:
    - ffmpeg
    - numpy
    - ltctools (for LTC decoding)
"""

import argparse
import subprocess
import sys
import tempfile
import os
import wave
import shutil
import numpy as np
from pathlib import Path
from typing import Tuple, Optional


class LTCDecoder:
    """Decodes Linear Timecode (LTC) audio data"""
    
    # LTC bit duration in samples (for 48kHz audio, a bit is ~1/1920 seconds = 25 samples)
    FRAME_RATES = {
        23.976: (23976, 1000),
        24: (24, 1),
        25: (25, 1),
        29.97: (29970, 1000),
        30: (30, 1),
        59.94: (59940, 1000),
        60: (60, 1),
    }
    
    # LTC sync word patterns
    SYNC_WORDS = {0x3FFC, 0xBFFD, 0x3FFD, 0xBFFC}
    
    def __init__(self, sample_rate: int = 48000):
        self.sample_rate = sample_rate
        self.bit_length = sample_rate // 1920  # 25 samples per bit at 48kHz
    
    def decode_ltc(self, audio_data: np.ndarray, wav_file: Optional[str] = None) -> Optional[Tuple[int, int, int, int, int]]:
        """
        Decode LTC audio data and return timecode.
        
        Args:
            audio_data: Audio samples as numpy array
            wav_file: Path to WAV file (for ltcdump method)
        
        Returns:
            Tuple of (hours, minutes, seconds, frames, frame_rate_flag)
            or None if decoding fails
        """
        # Try ltcdump first if wav_file provided
        if wav_file:
            try:
                result = self._decode_with_ltcdump(wav_file)
                if result:
                    return result
            except Exception as e:
                print(f"Note: ltcdump failed: {e}", file=sys.stderr)
        
        # Fall back to bit-level decoder
        try:
            return self._decode_bits(audio_data)
        except Exception as e:
            print(f"Note: Bit-level decoder failed: {e}", file=sys.stderr)
            return None
    
    def _decode_with_ltcdump(self, wav_file: str) -> Optional[Tuple[int, int, int, int, int]]:
        """Decode using ltcdump tool from ltc-tools"""
        try:
            # Run ltcdump on the WAV file, channel 1 (mono file extracted as channel 1)
            cmd = ["ltcdump", "-c", "1", "-F", wav_file]
            result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=10)
            
            if result.returncode != 0:
                return None
            
            # Parse ltcdump output format: hh:mm:ss:ff
            # Example output lines: "01:23:45:12  ..."
            for line in result.stdout.split('\n'):
                if ':' in line and 'Timecode' not in line and '#' not in line:
                    parts = line.split()
                    if parts:
                        timecode = parts[1]  # Second column is the timecode
                        try:
                            h, m, s, f = timecode.split(':')
                            hours = int(h)
                            minutes = int(m)
                            seconds = int(s)
                            frames = int(f)
                            print(f"✓ Decoded LTC using ltcdump: {hours:02d}:{minutes:02d}:{seconds:02d}:{frames:02d}")
                            return (hours, minutes, seconds, frames, 0)
                        except (ValueError, IndexError):
                            continue
            
            return None
        except FileNotFoundError:
            print("Note: ltcdump not found, trying bit-level decoder", file=sys.stderr)
            raise
        except subprocess.TimeoutExpired:
            print("Note: ltcdump timeout", file=sys.stderr)
            raise
    
    def _decode_bits(self, audio_data: np.ndarray) -> Tuple[int, int, int, int, int]:
        """
        Decode LTC by analyzing bit transitions.
        Converts audio to binary representation and extracts timecode.
        """
        # Normalize audio to [-1, 1] range
        if audio_data.dtype == np.int16:
            audio_normalized = audio_data.astype(np.float32) / 32768.0
        elif audio_data.dtype == np.int32:
            audio_normalized = audio_data.astype(np.float32) / 2147483648.0
        else:
            audio_normalized = audio_data.astype(np.float32)
        
        if audio_normalized.size == 0:
            return (0, 0, 0, 0, 0)
        
        # Normalize to [-1, 1] range
        max_val = np.max(np.abs(audio_normalized))
        if max_val > 0:
            audio_normalized = audio_normalized / max_val
        
        # Calculate frame size in samples (one LTC frame = 80 bits)
        # LTC = 1920 bits per second, so at 48kHz: 48000/1920 = 25 samples per bit
        # One frame = 80 bits = 2000 samples at 48kHz
        samples_per_frame = self.sample_rate // 24  # Approximately 2000 at 48kHz
        
        if len(audio_normalized) < samples_per_frame:
            return (0, 0, 0, 0, 0)
        
        # Extract first complete frame
        frame_audio = audio_normalized[:samples_per_frame]
        
        # Decode bits using zero-crossing detection
        bits = self._extract_bits_from_audio(frame_audio)
        
        if len(bits) < 80:
            return (0, 0, 0, 0, 0)
        
        # Decode the LTC frame
        return self._decode_ltc_frame(bits[:80])
    
    def _extract_bits_from_audio(self, audio: np.ndarray) -> list:
        """
        Extract bit sequence from audio using transition detection.
        A bit is represented as a transition (change from positive to negative or vice versa).
        """
        # Calculate samples per bit
        samples_per_bit = self.bit_length
        
        bits = []
        for i in range(80):
            start = i * samples_per_bit
            end = min((i + 1) * samples_per_bit, len(audio))
            
            if end - start < 2:
                bits.append(0)
                continue
            
            bit_audio = audio[start:end]
            
            # Detect zero crossing (transition)
            sign_changes = np.where(np.diff(np.sign(bit_audio)))[0]
            
            # A bit is 1 if there's a zero crossing, 0 otherwise
            bit_value = 1 if len(sign_changes) > 0 else 0
            bits.append(bit_value)
        
        return bits
    
    def _decode_ltc_frame(self, bits: list) -> Tuple[int, int, int, int, int]:
        """
        Decode an 80-bit LTC frame into timecode.
        
        LTC Frame Structure (80 bits):
        - Bits 0-3: Frame units (BCD)
        - Bits 4-7: Frame tens (BCD)
        - Bits 8-9: Drop frame & color frame flags
        - Bits 10-13: Seconds units (BCD)
        - Bits 14-17: Seconds tens (BCD)
        - Bits 18-19: Flags
        - Bits 20-23: Minutes units (BCD)
        - Bits 24-27: Minutes tens (BCD)
        - Bits 28-29: Flags
        - Bits 30-33: Hours units (BCD)
        - Bits 34-35: Hours tens (BCD)
        - Bits 36-43: Binary group 1-4
        - Bits 44-57: Binary group 5-8
        - Bits 58-63: Binary group 9-11
        - Bits 64-79: Sync word (should be 0x3FFC or 0xBFFD)
        """
        if len(bits) < 80:
            return (0, 0, 0, 0, 0)
        
        try:
            # Extract BCD encoded values
            frames_units = self._bcd_decode(bits[0:4])
            frames_tens = self._bcd_decode(bits[4:8])
            frames = frames_tens * 10 + frames_units
            
            seconds_units = self._bcd_decode(bits[10:14])
            seconds_tens = self._bcd_decode(bits[14:18])
            seconds = seconds_tens * 10 + seconds_units
            
            minutes_units = self._bcd_decode(bits[20:24])
            minutes_tens = self._bcd_decode(bits[24:28])
            minutes = minutes_tens * 10 + minutes_units
            
            hours_units = self._bcd_decode(bits[30:34])
            hours_tens = self._bcd_decode(bits[34:36])
            hours = hours_tens * 10 + hours_units
            
            # Drop frame flag
            drop_frame = bits[8]
            
            # Validate ranges
            if hours > 23 or minutes > 59 or seconds > 59 or frames > 59:
                return (0, 0, 0, 0, 0)
            
            return (hours, minutes, seconds, frames, drop_frame)
        except Exception:
            return (0, 0, 0, 0, 0)
    
    def _bcd_decode(self, bits: list) -> int:
        """Decode 4 bits as BCD (Binary Coded Decimal)"""
        if len(bits) < 4:
            return 0
        value = 0
        for i, bit in enumerate(bits[:4]):
            value += bit * (2 ** (3 - i))
        return value


class SMPTEWriter:
    """Writes SMPTE timecode metadata to video files"""
    
    @staticmethod
    def format_timecode(hours: int, minutes: int, seconds: int, frames: int) -> str:
        """Format timecode as HH:MM:SS:FF"""
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}:{frames:02d}"
    
    @staticmethod
    def write_to_video(
        input_file: str,
        output_file: str,
        hours: int,
        minutes: int,
        seconds: int,
        frames: int,
        drop_frame: bool = False
    ) -> bool:
        """
        Write SMPTE timecode to video file using ffmpeg.
        
        Args:
            input_file: Path to input video
            output_file: Path to output video
            hours, minutes, seconds, frames: Timecode values
            drop_frame: Whether to use drop-frame timecode
        
        Returns:
            True if successful, False otherwise
        """
        timecode = SMPTEWriter.format_timecode(hours, minutes, seconds, frames)
        
        # Use FFmpeg's -timecode option with copy codec to preserve original format
        # -c:v copy and -c:a copy preserve the original video and audio codecs
        cmd = [
            "ffmpeg",
            "-i", input_file,
            "-timecode", timecode,
            "-c:v", "copy",  # Copy video stream without re-encoding
            "-af", "pan=stereo|c0=c0|c1=c0",  # Copy first channel to both stereo channels
            "-c:a", "aac",  # Re-encode audio since we're filtering
            "-y",
            output_file
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if result.returncode == 0:
                return True
            else:
                print(f"FFmpeg error: {result.stderr}", file=sys.stderr)
                return False
        except Exception as e:
            print(f"Error writing SMPTE timecode: {e}", file=sys.stderr)
            return False


class VideoProcessor:
    """Main processor for handling video and audio"""
    
    def __init__(self, input_file: str):
        self.input_file = input_file
        self.verify_file_exists()
    
    def verify_file_exists(self):
        """Verify input file exists"""
        if not Path(self.input_file).exists():
            raise FileNotFoundError(f"Video file not found: {self.input_file}")
    
    def extract_second_channel_audio(self, output_wav: str) -> bool:
        """
        Extract the second stereo channel as mono WAV file.
        
        Args:
            output_wav: Path to output WAV file
        
        Returns:
            True if successful, False otherwise
        """
        cmd = [
            "ffmpeg",
            "-i", self.input_file,
            "-map", "0:a",
            "-q:a", "9",
            "-ac", "1",
            "-af", "pan=mono|c0=c1",  # Extract right channel (index 1)
            output_wav
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if result.returncode == 0:
                print(f"✓ Extracted second audio channel to {output_wav}")
                return True
            else:
                print(f"✗ Failed to extract audio: {result.stderr}", file=sys.stderr)
                return False
        except Exception as e:
            print(f"✗ Error extracting audio: {e}", file=sys.stderr)
            return False
    
    def read_wav_file(self, wav_file: str) -> Tuple[int, np.ndarray]:
        """
        Read WAV file and return sample rate and audio data.
        
        Returns:
            Tuple of (sample_rate, audio_data)
        """
        try:
            with wave.open(wav_file, 'rb') as wav:
                n_channels = wav.getnchannels()
                frame_rate = wav.getframerate()
                n_frames = wav.getnframes()
                
                # Read audio data
                audio_bytes = wav.readframes(n_frames)
                audio_data = np.frombuffer(audio_bytes, dtype=np.int16)
                
                if n_channels > 1:
                    audio_data = audio_data.reshape((-1, n_channels))
                
                print(f"✓ Loaded WAV file: {frame_rate}Hz, {n_channels} channel(s), {n_frames} frames")
                return frame_rate, audio_data
        except Exception as e:
            print(f"✗ Error reading WAV file: {e}", file=sys.stderr)
            raise
    
    def process(self, output_file: str) -> bool:
        """
        Main processing pipeline: extract, decode, and write timecode.
        
        Args:
            output_file: Path to output video with SMPTE timecode
        
        Returns:
            True if successful, False otherwise
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # Step 1: Extract second channel audio
            wav_file = os.path.join(tmpdir, "second_channel.wav")
            if not self.extract_second_channel_audio(wav_file):
                return False
            
            # Step 2: Read WAV file
            try:
                sample_rate, audio_data = self.read_wav_file(wav_file)
            except Exception as e:
                print(f"✗ Failed to read audio: {e}", file=sys.stderr)
                return False
            
            # Step 3: Decode LTC
            decoder = LTCDecoder(sample_rate=sample_rate)
            print("🔄 Decoding LTC timecode...")
            timecode = decoder.decode_ltc(audio_data, wav_file=wav_file)
            
            if timecode:
                hours, minutes, seconds, frames, frame_rate_flag = timecode
                print(f"✓ Decoded timecode: {hours:02d}:{minutes:02d}:{seconds:02d}:{frames:02d}")
            else:
                print("✗ Failed to decode LTC timecode, using default 00:00:00:00")
                hours, minutes, seconds, frames = 0, 0, 0, 0
            
            # Step 4: Write SMPTE timecode to video
            print("🔄 Writing SMPTE timecode to video...")
            if SMPTEWriter.write_to_video(
                self.input_file,
                output_file,
                hours,
                minutes,
                seconds,
                frames
            ):
                print(f"✓ Successfully created output video: {output_file}")
                return True
            else:
                print("✗ Failed to write SMPTE timecode to video", file=sys.stderr)
                return False

def check_prerequisites(require_ltcdump: bool = False):
    """Check if required external tools are available.

    ffmpeg is required. ltcdump is optional (fallback decoder used if missing).
    If require_ltcdump is True we will exit if ltcdump is unavailable.
    """
    if not shutil.which("ffmpeg"):
        print("✗ Required tool 'ffmpeg' not found in PATH.", file=sys.stderr)
        sys.exit(1)
    if require_ltcdump and not shutil.which("ltcdump"):
        print("✗ Required tool 'ltcdump' not found in PATH (set require_ltcdump=False to allow fallback).", file=sys.stderr)
        sys.exit(1)
    if not shutil.which("ltcdump"):
        print("Note: 'ltcdump' not found – will use internal fallback decoder.")

def process_video(input_path: str, output_path: Optional[str] = None, verbose: bool = False) -> bool:
    """Convenience wrapper for GUI/CLI to process a single video.

    If output_path is None, create one by inserting '_tc' before the extension.
    Returns True on success, False otherwise.
    """
    check_prerequisites(require_ltcdump=False)
    if output_path is None:
        p = Path(input_path)
        output_path = str(p.with_name(p.stem + '_tc' + p.suffix))
    try:
        processor = VideoProcessor(input_path)
        success = processor.process(output_path)
        return success
    except Exception as e:
        print(f"✗ Error processing video: {e}", file=sys.stderr)
        if verbose:
            import traceback
            traceback.print_exc()
        return False

def _gather_tool_info() -> str:
    """Return a multi-line string describing discovered external tool binaries.

    Included in --help epilog so users see what will be used at runtime.
    """
    lines: list[str] = ["External tools detected:"]
    # ffmpeg
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        try:
            r = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, timeout=5)
            first = r.stdout.splitlines()[0] if r.stdout else "(no version output)"
            lines.append(f"  ffmpeg: {ffmpeg_path} | {first}")
        except Exception as e:  # pragma: no cover - diagnostics only
            lines.append(f"  ffmpeg: {ffmpeg_path} | version query failed: {e}")
    else:
        lines.append("  ffmpeg: NOT FOUND in PATH")
    # ltcdump (optional)
    ltcdump_path = shutil.which("ltcdump")
    if ltcdump_path:
        try:
            # ltcdump does not have a --version flag; capture first line of help output
            r = subprocess.run(["ltcdump", "-h"], capture_output=True, text=True, timeout=5)
            first = r.stdout.splitlines()[0] if r.stdout else "(no help output)"
            lines.append(f"  ltcdump: {ltcdump_path} | {first}")
        except Exception as e:  # pragma: no cover
            lines.append(f"  ltcdump: {ltcdump_path} | help query failed: {e}")
    else:
        lines.append("  ltcdump: NOT FOUND (fallback decoder will be used)")
    return "\n" + "\n".join(lines)

def main():
    parser = argparse.ArgumentParser(
        description="Extract LTC audio from video's second stereo channel and write as SMPTE timecode",
        epilog=_gather_tool_info(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "input_file",
        help="Input video file path"
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Output video file path (default: auto append _tc before extension)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    args = parser.parse_args()
    success = process_video(args.input_file, args.output, verbose=args.verbose)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
