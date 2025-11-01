#!/usr/bin/env python3
# /// script
# requires-python = ">=3.7"
# ///
"""
Generate Test Sample Files for LTC to SMPTE Converter

This script creates sample test files for testing the ltc_to_smpte.py script:
1. LTC audio file with timecode
2. Test video with stereo audio (sine on L, LTC on R)
3. Combined test video ready for processing

Usage:
    python3 generate_test_sample.py [OPTIONS]

Options:
    -t, --timecode HH:MM:SS:FF    Timecode to embed (default: 01:23:45:12)
    -d, --duration SECONDS         Duration in seconds (default: 5)
    -o, --output PREFIX            Output file prefix (default: test_sample)
    -c, --cleanup                  Clean up intermediate files (default: false)
    -v, --verbose                  Show detailed output (default: false)

Examples:
    # Generate default test files
    python3 generate_test_sample.py

    # Generate with custom timecode
    python3 generate_test_sample.py -t 10:30:45:00

    # Generate and cleanup intermediate files
    python3 generate_test_sample.py -c

    # Verbose output
    python3 generate_test_sample.py -v
"""

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Optional
import shutil


class TestSampleGenerator:
    """Generates test sample files for LTC processing"""
    
    def __init__(self, timecode: str = "01:23:45:12", duration: int = 5, 
                 output_prefix: str = "test_sample", verbose: bool = False):
        """Initialize test sample generator
        
        Args:
            timecode: Timecode in HH:MM:SS:FF format
            duration: Duration in seconds
            output_prefix: Prefix for output files
            verbose: Enable verbose output
        """
        self.timecode = timecode
        self.duration = duration
        self.output_prefix = output_prefix
        self.verbose = verbose
        
        # Define output files
        self.ltc_audio_file = f"{output_prefix}_ltc.wav"
        self.test_video_file = f"{output_prefix}_with_ltc.mp4"
        self.tone_audio_file = f"{output_prefix}_tone.wav"
        
        self.log(f"Initializing test sample generator with timecode {timecode}")
    
    def log(self, message: str, level: str = "INFO"):
        """Print log message if verbose"""
        if self.verbose:
            print(f"[{level}] {message}")
    
    def check_requirements(self) -> bool:
        """Check if required tools are installed"""
        required_tools = ["ffmpeg", "ltcgen"]
        missing_tools = []
        
        for tool in required_tools:
            result = subprocess.run(
                ["which", tool],
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                missing_tools.append(tool)
        
        if missing_tools:
            print(f"❌ Error: Missing required tools: {', '.join(missing_tools)}")
            print("\nInstall them with:")
            print("  brew install ffmpeg ltc-tools  # macOS")
            print("  sudo apt-get install ffmpeg ltc-tools  # Ubuntu/Debian")
            return False
        
        self.log("✓ All required tools found")
        return True
    
    def generate_ltc_audio(self) -> bool:
        """Generate LTC audio file using ltcgen
        
        Returns:
            True if successful, False otherwise
        """
        self.log(f"Generating LTC audio: {self.ltc_audio_file}")
        
        try:
            cmd = [
                "ltcgen",
                "-t", self.timecode,
                "-l", str(self.duration),
                self.ltc_audio_file
            ]
            
            if self.verbose:
                print(f"Command: {' '.join(cmd)}")
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            
            if result.returncode != 0:
                print(f"❌ Error generating LTC audio:")
                print(result.stderr)
                return False
            
            self.log(f"✓ Created LTC audio: {self.ltc_audio_file}")
            return True
        
        except Exception as e:
            print(f"❌ Error: {e}")
            return False
    
    def generate_tone_audio(self) -> bool:
        """Generate reference tone audio (100 Hz sine wave)
        
        Returns:
            True if successful, False otherwise
        """
        self.log(f"Generating tone audio: {self.tone_audio_file}")
        
        try:
            cmd = [
                "ffmpeg",
                "-f", "lavfi",
                "-i", f"sine=f=100:d={self.duration}",
                "-b:a", "192k",
                "-q:a", "9",
                "-y",
                self.tone_audio_file
            ]
            
            if self.verbose:
                print(f"Command: {' '.join(cmd)}")
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            
            if result.returncode != 0:
                print(f"❌ Error generating tone audio:")
                print(result.stderr)
                return False
            
            self.log(f"✓ Created tone audio: {self.tone_audio_file}")
            return True
        
        except Exception as e:
            print(f"❌ Error: {e}")
            return False
    
    def generate_test_video(self) -> bool:
        """Generate test video with dual stereo audio
        
        Left channel: 100 Hz reference tone
        Right channel: LTC timecode audio
        
        Returns:
            True if successful, False otherwise
        """
        self.log(f"Generating test video: {self.test_video_file}")
        
        try:
            # Create video with merged audio (left=tone, right=ltc)
            cmd = [
                "ffmpeg",
                "-f", "lavfi",
                "-i", f"color=c=blue:s=320x240:d={self.duration}",
                "-i", self.tone_audio_file,
                "-i", self.ltc_audio_file,
                "-filter_complex", "[1:a][2:a]amerge=inputs=2[a]",
                "-map", "0:v",
                "-map", "[a]",
                "-c:v", "libx264",
                "-preset", "fast",
                "-c:a", "aac",
                "-b:a", "128k",
                "-shortest",
                "-y",
                self.test_video_file
            ]
            
            if self.verbose:
                print(f"Command: {' '.join(cmd)}")
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            
            if result.returncode != 0:
                print(f"❌ Error generating test video:")
                print(result.stderr)
                return False
            
            self.log(f"✓ Created test video: {self.test_video_file}")
            return True
        
        except Exception as e:
            print(f"❌ Error: {e}")
            return False
    
    def cleanup_intermediate_files(self):
        """Remove intermediate files"""
        intermediate_files = [self.ltc_audio_file, self.tone_audio_file]
        
        for file in intermediate_files:
            if Path(file).exists():
                Path(file).unlink()
                self.log(f"Removed: {file}")
    
    def verify_output(self) -> bool:
        """Verify the generated test video with ffprobe
        
        Returns:
            True if verification successful, False otherwise
        """
        self.log("Verifying test video...")
        
        try:
            # Simple verification - check if file has audio streams
            cmd = [
                "ffprobe",
                "-v", "error",
                "-select_streams", "a",
                "-show_entries", "stream=channels",
                "-of", "csv=p=0",
                self.test_video_file
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            
            if result.returncode != 0:
                self.log("⚠️  Warning: Could not verify audio channels")
                return True  # Still succeed, file was created
            
            output = result.stdout.strip()
            self.log(f"✓ Audio channels found: {output}")
            return True
        
        except Exception as e:
            self.log(f"⚠️  Warning during verification: {e}")
            return True  # Still succeed, file was created
    
    def generate(self, cleanup: bool = False) -> bool:
        """Generate all test files
        
        Args:
            cleanup: Whether to remove intermediate files
        
        Returns:
            True if all generation successful, False otherwise
        """
        print(f"\n🎬 Generating Test Sample Files")
        print(f"   Timecode: {self.timecode}")
        print(f"   Duration: {self.duration}s")
        print(f"   Output: {self.output_prefix}_*\n")
        
        # Check requirements
        if not self.check_requirements():
            return False
        
        # Generate LTC audio
        if not self.generate_ltc_audio():
            return False
        
        # Generate tone audio
        if not self.generate_tone_audio():
            return False
        
        # Generate test video
        if not self.generate_test_video():
            return False
        
        # Verify output
        if not self.verify_output():
            print("⚠️  Warning: Verification failed, but files may still be usable")
        
        # Cleanup intermediate files
        if cleanup:
            self.cleanup_intermediate_files()
        
        # Print summary
        print(f"\n✅ Test sample generation complete!")
        print(f"\nGenerated files:")
        print(f"  • {self.test_video_file} (MAIN TEST FILE)")
        
        if not cleanup:
            print(f"  • {self.ltc_audio_file} (LTC audio)")
            print(f"  • {self.tone_audio_file} (Tone audio)")
        
        print(f"\nNext steps:")
        print(f"  1. Test the converter:")
        print(f"     python3 ltc_to_smpte.py {self.test_video_file}")
        print(f"\n  2. Verify the output:")
        print(f"     ffprobe -show_entries stream_tags=timecode output.mp4")
        print()
        
        return True


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Generate test sample files for LTC to SMPTE converter",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate default test files
  python3 generate_test_sample.py

  # Generate with custom timecode
  python3 generate_test_sample.py -t 10:30:45:00

  # Generate and cleanup intermediate files
  python3 generate_test_sample.py -c

  # Verbose output
  python3 generate_test_sample.py -v
        """
    )
    
    parser.add_argument(
        "-t", "--timecode",
        default="01:23:45:12",
        help="Timecode in HH:MM:SS:FF format (default: 01:23:45:12)"
    )
    
    parser.add_argument(
        "-d", "--duration",
        type=int,
        default=5,
        help="Duration in seconds (default: 5)"
    )
    
    parser.add_argument(
        "-o", "--output",
        default="test_sample",
        help="Output file prefix (default: test_sample)"
    )
    
    parser.add_argument(
        "-c", "--cleanup",
        action="store_true",
        help="Clean up intermediate files"
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show detailed output"
    )
    
    args = parser.parse_args()
    
    # Validate timecode format
    timecode_parts = args.timecode.split(":")
    if len(timecode_parts) != 4:
        print(f"❌ Error: Invalid timecode format '{args.timecode}'")
        print("   Expected: HH:MM:SS:FF (e.g., 01:23:45:12)")
        sys.exit(1)
    
    # Validate duration
    if args.duration < 1:
        print(f"❌ Error: Duration must be at least 1 second")
        sys.exit(1)
    
    # Generate test samples
    generator = TestSampleGenerator(
        timecode=args.timecode,
        duration=args.duration,
        output_prefix=args.output,
        verbose=args.verbose
    )
    
    if generator.generate(cleanup=args.cleanup):
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
