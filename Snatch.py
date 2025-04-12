# Standard library imports
import argparse
import gc
import hashlib
import json
import logging
import math
import os
import platform
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import unicodedata
import urllib.parse
from collections import OrderedDict
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, as_completed, wait
from contextlib import contextmanager, suppress
from datetime import datetime
from difflib import get_close_matches
from functools import lru_cache
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    Generator,
    Iterator,
    List,
    Optional,
    Tuple,
    Union,
)

# Third-party imports
import mutagen
import psutil
import requests
import yt_dlp
from colorama import Fore, Style, init
from mutagen.flac import FLAC
from mutagen.id3 import ID3
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4
from mutagen.oggvorbis import OggVorbis
from tqdm import tqdm

# Initialize colorama for Windows support with autoreset for cleaner code
init(autoreset=True)

# Global validation state to avoid redundant FFmpeg checks
_config_initialized = False
_ffmpeg_validated = False
_background_init_complete = False
_config_updates_available = False
_update_messages = []


def _run_background_init(config: dict) -> None:
    """
    Run background configuration validation and update checks.
    This function runs in a separate thread to avoid delaying the UI.

    Args:
        config: The loaded configuration dictionary
    """
    global _ffmpeg_validated, _background_init_complete, _config_updates_available, _update_messages

    try:
        # Initialize _update_messages to an empty list if we're going to use it
        # Check if FFmpeg version is outdated by comparing version number
        if config.get("ffmpeg_location") and validate_ffmpeg_path(
            config["ffmpeg_location"]
        ):
            _ffmpeg_validated = True
            ffmpeg_path = os.path.join(
                config["ffmpeg_location"], "ffmpeg" + (".exe" if is_windows() else "")
            )

            try:
                # Check FFmpeg version
                result = subprocess.run(
                    [ffmpeg_path, "-version"], capture_output=True, text=True, timeout=3
                )
                if result.returncode == 0:
                    version_info = (
                        result.stdout.splitlines()[0] if result.stdout else ""
                    )
                    # Extract version number - typically in format "ffmpeg version 4.4"
                    match = re.search(r"version\s+(\d+\.\d+)", version_info)
                    if match:
                        version = float(match.group(1))
                        if version < 4.0:
                            _update_messages.append(
                                f"FFmpeg version {version} detected. Consider updating to version 4.0 or newer for better performance."
                            )
                            _config_updates_available = True
                            any_updates_found = False
            except Exception as e:
                logging.debug(f"FFmpeg version check failed: {e}")

        # Check for missing optional config fields
        optional_fields = {
            "theme": "default",
            "download_history": True,
            "concurrent_fragment_downloads": 16,
            "auto_update_check": True,
            "bandwidth_limit": 0,  # 0 means unlimited
            "preferred_video_codec": "h264",
            "preferred_audio_codec": "aac",
        }

        missing_fields = False
        for field, default_value in optional_fields.items():
            if field not in config:
                config[field] = default_value
                missing_fields = True

        if missing_fields:
            _update_messages.append(
                "Added new configuration options. Check your config for new features."
            )
            _config_updates_available = True
            any_updates_found = False

            # Save updated config in the background
            try:
                config_path = Path(CONFIG_FILE)
                with open(config_path, "w") as f:
                    json.dump(config, f, indent=4)
                logging.info("Updated configuration file with new options")
            except Exception as e:
                logging.error(f"Failed to update configuration file: {e}")

    except Exception as e:
        logging.error(f"Background initialization error: {e}")
    finally:
        _background_init_complete = True
        # Only set _update_messages if it's being used in this function
        if any_updates_found:
            _update_messages.append("Updates available")  # Example usage


def initialize_config_async(force_validation: bool = False) -> Dict[str, Any]:
    """
    Load and validate configuration file asynchronously, with intelligent fallbacks.
    Runs critical validation immediately and launches non-blocking background checks.

    Args:
        force_validation: If True, validate FFmpeg path even if config exists

    Returns:
        Dict containing validated configuration
    """
    global _config_initialized, _ffmpeg_validated

    config = {}
    config_path = Path(CONFIG_FILE)
    config_changed = False

    try:
        # Step 1: Fast load of existing config if available
        if config_path.exists():
            try:
                with open(config_path, "r") as f:
                    config = json.load(f)

                # Ensure all default keys are present (critical only)
                for key, value in DEFAULT_CONFIG.items():
                    if key not in config:
                        config[key] = value
                        config_changed = True

            except (json.JSONDecodeError, IOError) as e:
                logging.error(f"Error loading config file: {e}")
                config = DEFAULT_CONFIG.copy()
                config_changed = True
        else:
            # No config file exists, create default
            config = DEFAULT_CONFIG.copy()
            config_changed = True

        # Step 2: Quick check for FFmpeg path - only if forced or not yet done
        if (force_validation or not _ffmpeg_validated) and not config.get(
            "ffmpeg_location", ""
        ):
            ffmpeg_path = find_ffmpeg()

            if ffmpeg_path:
                config["ffmpeg_location"] = ffmpeg_path
                config_changed = True
                _ffmpeg_validated = True
            elif force_validation:  # Only show message if explicitly validating
                print_ffmpeg_instructions()
                config["ffmpeg_location"] = ""
                config_changed = True

        # Step 3: Save critical config changes immediately
        if config_changed:
            try:
                with open(config_path, "w") as f:
                    json.dump(config, f, indent=4)
            except IOError as e:
                logging.error(f"Error saving config file: {e}")

        # Step 4: Launch background thread for non-blocking checks
        if not _config_initialized or force_validation:
            bg_thread = threading.Thread(
                target=_run_background_init,
                args=(config,),
                daemon=True,
                name="ConfigBackgroundInit",
            )
            bg_thread.start()

        _config_initialized = True
        return config

    except Exception as e:
        logging.error(f"Config initialization error: {e}")
        return DEFAULT_CONFIG.copy()


def check_for_updates() -> None:
    """
    Check if any configuration updates were detected in the background thread.
    If so, display notifications to the user.
    """
    if _background_init_complete and _config_updates_available:
        print(f"\n{Fore.YELLOW}Configuration Updates Available:{Style.RESET_ALL}")
        for message in _update_messages:
            print(f"  {Fore.CYAN}• {message}{Style.RESET_ALL}")
        print(
            f"{Fore.YELLOW}Run with --update-config to apply all recommended updates.{Style.RESET_ALL}"
        )


# Set up logging configuration with color support
class ColoramaFormatter(logging.Formatter):
    """Custom formatter to color log levels using Colorama"""

    def format(self, record):
        color_map = {
            logging.DEBUG: Fore.CYAN,
            logging.INFO: Fore.GREEN,
            logging.WARNING: Fore.YELLOW,
            logging.ERROR: Fore.RED,
            logging.CRITICAL: Fore.RED + Style.BRIGHT,
        }
        level_color = color_map.get(record.levelno, Fore.WHITE)
        message = super().format(record)
        return f"{level_color}{message}{Style.RESET_ALL}"


class CustomHelpFormatter(argparse.HelpFormatter):
    def _split_lines(self, text, width):
        return textwrap.wrap(text, width)


# Constants moved to top for better organization and maintainability
CONFIG_FILE = "config.json"
FLAC_EXT = ".flac"
opus_ext = ".opus"
webn_ext = ".webm"
part_ext = ".part"
speedtestresult = "speedtest_result.json"
bestaudio_ext = "bestaudio/best"
VERSION = "1.7.0"  # Centralized version definition
LOG_FILE = "download_log.txt"
SPINNER_CHARS = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
# Default throttling and retry constants
DEFAULT_THROTTLE_RATE = 0  # 0 means no throttling (bytes/second)
MAX_RETRIES = 10  # Maximum number of retry attempts
RETRY_SLEEP_BASE = 5  # Base seconds to wait before retry (used in exponential backoff)
MAX_CONCURRENT_FRAGMENTS = 10  # Maximum number of parallel fragment downloads
DEFAULT_TIMEOUT = 60  # Default connection timeout in seconds
DOWNLOAD_SESSIONS_FILE = "download_sessions.json"  # New session data file

# File organization templates
DEFAULT_ORGANIZATION_TEMPLATES = {
    "audio": "{uploader}/{album}/{title}",
    "video": "{uploader}/{year}/{title}",
    "podcast": "Podcasts/{uploader}/{year}-{month}/{title}",
    "audiobook": "Audiobooks/{uploader}/{title}",
}

# Safe filename characters regex pattern
SAFE_FILENAME_CHARS = re.compile(r"[^\w\-. ]")

DEFAULT_CONFIG = {
    "ffmpeg_location": "",  # Will be auto-detected
    "video_output": str(Path.home() / "Videos"),
    "audio_output": str(Path.home() / "Music"),
    "max_concurrent": 3,
    # Add organization configs
    "organize": False,
    "organization_templates": DEFAULT_ORGANIZATION_TEMPLATES.copy(),
}

# Enhanced spinner characters for better visual appearance
SPINNER_CHARS = ["⣾", "⣽", "⣻", "⢿", "⡿", "⣟", "⣯", "⣷"]
# Alternative spinners that users can select
SPINNER_STYLES = {
    "dots": ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"],
    "line": ["|", "/", "-", "\\"],
    "grow": ["▏", "▎", "▍", "▌", "▋", "▊", "▉", "█", "▉", "▊", "▋", "▌", "▍", "▎", "▏"],
    "pulse": ["█", "▓", "▒", "░", "▒", "▓"],
    "bounce": ["⠁", "⠂", "⠄", "⠂"],
    "moon": ["🌑", "🌒", "🌓", "🌔", "🌕", "🌖", "🌗", "🌘"],
    "aesthetic": ["⣾", "⣽", "⣻", "⢿", "⡿", "⣟", "⣯", "⣷"],
}

# Common file extensions by type for better categorization
AUDIO_EXTENSIONS = {".mp3", FLAC_EXT, ".wav", ".m4a", ".aac", ".ogg", opus_ext}
VIDEO_EXTENSIONS = {".mp4", webn_ext, ".mkv", ".avi", ".mov", ".flv", ".wmv", ".3gp"}

# Create a download cache directory for faster repeated downloads
CACHE_DIR = Path.home() / ".snatch" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Add system resource constraints to prevent overloading
MAX_MEMORY_PERCENT = 80  # Don't use more than 80% of system memory
DEFAULT_CHUNK_SIZE = 8192  # Optimal for most systems


# Set up a handler for SIGINT to ensure clean exits
def signal_handler(sig, frame):
    print(
        f"\n{Fore.YELLOW}Operation cancelled by user. Exiting gracefully...{Style.RESET_ALL}"
    )
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)

# Examples text unchanged
# Add speedtest to the utility commands section in EXAMPLES
EXAMPLES = """
╔══════════════════════════════════════════════════════════════════════════╗
║                          SNATCH COMMAND CENTER                           ║
╠══════════════════════════════════════════════════════════════════════════╣
║                                                                          ║
║  📥 QUICK DOWNLOAD SYNTAX:                                              ║     
║    <URL> <format|quality>      ← URL FIRST, then format or quality       ║
║                                                                          ║
║    Examples:                                                             ║
║      https://example.com/video flac    Download audio in FLAC format     ║
║      https://example.com/video 1080    Download video in 1080p quality   ║
║      https://example.com/music opus    Download audio in Opus format     ║
║                                                                          ║
║  🎵 AUDIO COMMANDS:                                                      ║
║    audio <URL>               Download audio (default format)             ║
║    flac <URL>                Download in lossless FLAC format            ║
║    mp3 <URL>                 Download in MP3 format (320kbps)            ║
║    opus <URL>                Download in Opus format (high quality)      ║
║    wav <URL>                 Download in WAV format (uncompressed)       ║
║    m4a <URL>                 Download in M4A format (AAC)                ║
║                                                                          ║
║  🎬 VIDEO COMMANDS:                                                      ║
║    download, dl <URL>        Download in best available quality          ║
║    video <URL>               Download video (prompts for resolution)     ║
║    <URL> 720                 Download in 720p resolution                 ║
║    <URL> 1080                Download in 1080p resolution                ║
║    <URL> 2160|4k             Download in 4K resolution                   ║
║                                                                          ║
║  ⚙️ DOWNLOAD OPTIONS:                                                    ║
║    --audio-only              Download only audio track                   ║
║    --resolution <res>        Specify video resolution (480/720/1080/216 )║
║    --filename <name>         Set custom output filename                  ║
║    --audio-format <format>   Set audio format (mp3/flac/opus/wav/m4a)    ║
║    --audio-channels <num>    Set audio channels (2=stereo, 8=surround)   ║
║    --output-dir <path>       Specify output directory                    ║
║    --organize                Enable metadata-based file organization     ║
║                                                                          ║
║  🛠️ ADVANCED OPTIONS:                                                    ║
║    --resume                  Resume interrupted downloads                ║
║    --stats                   Show download statistics                    ║
║    --format-id <id>          Select specific format ID                   ║
║    --no-cache                Skip using cached media info                ║
║    --throttle <speed>        Limit download speed (e.g., 2M)             ║
║    --aria2c                  Use aria2c for faster downloads             ║
║    --speedtest               Run network speed test                      ║
║                                                                          ║
║  📋 UTILITY COMMANDS:                                                   ║
║    help, ?                   Show this help menu                         ║
║    clear, cls                Clear the screen                            ║
║    list, sites               List supported sites                        ║
║    speedtest, test           Run network speed test                      ║
║    exit, quit, q             Exit the application                        ║
║                                                                          ║
║  📚 BATCH OPERATIONS:                                                   ║
║    python Snatch.py "URL1" "URL2" "URL3"                                 ║
║    python Snatch.py "URL1" "URL2" --audio-only --stats                   ║
║                                                                          ║
╚══════════════════════════════════════════════════════════════════════════╝
"""


def _cleanup_temporary_files(self) -> None:
    """
    Clean up temporary files created during downloads with robust error handling
    for locked files and permission issues.
    """
    try:
        # Get common temp directories
        temp_dirs = [tempfile.gettempdir()]
        # Add output directories
        if "audio_output" in self.config:
            temp_dirs.append(self.config["audio_output"])
        if "video_output" in self.config:
            temp_dirs.append(self.config["video_output"])

        # Pattern for temporary files created by yt-dlp
        patterns = [
            r".*\.temp\.\w+$",  # Temp files
            r".*\.part$",  # Partial downloads
            r".*\.ytdl$",  # yt-dlp temp files
            r".*\.download$",  # Download in progress
            r".*\.download\.\w+$",  # Partial fragment downloads
            r".*\.f\d+\.\w+$",  # Format fragment files
            r".*tmp\w+\.tmp$",  # Windows-style temp files
        ]

        # Compile patterns for efficiency
        compiled_patterns = [re.compile(pattern) for pattern in patterns]

        # Find and clean up temp files older than 1 hour
        now = time.time()
        max_age = 3600  # 1 hour in seconds
        cleaned_files = 0
        cleaned_bytes = 0
        failed_files = []

        for temp_dir in temp_dirs:
            if not os.path.exists(temp_dir):
                continue

            for filename in os.listdir(temp_dir):
                # Skip non-matching files
                if not any(pattern.match(filename) for pattern in compiled_patterns):
                    continue

                filepath = os.path.join(temp_dir, filename)

                try:
                    # Check file age and size
                    file_stat = os.stat(filepath)
                    file_age = now - file_stat.st_mtime

                    # Only delete older files to avoid interfering with active downloads
                    if file_age > max_age:
                        file_size = file_stat.st_size

                        # Try different deletion methods for Windows vs POSIX systems
                        try:
                            # First attempt: standard deletion
                            os.unlink(filepath)
                            cleaned_files += 1
                            cleaned_bytes += file_size
                        except PermissionError:
                            # Windows-specific: Try using system commands for locked files
                            if os.name == "nt":
                                try:
                                    subprocess.run(
                                        ["cmd", "/c", "del", "/f", "/q", filepath],
                                        stderr=subprocess.PIPE,
                                        stdout=subprocess.PIPE,
                                        timeout=2,
                                    )
                                    if not os.path.exists(filepath):
                                        cleaned_files += 1
                                        cleaned_bytes += file_size
                                    else:
                                        failed_files.append(filepath)
                                except Exception:
                                    failed_files.append(filepath)
                            else:
                                failed_files.append(filepath)
                except (OSError, IOError):
                    # Skip files we can't access
                    failed_files.append(filepath)

        if cleaned_files > 0:
            logging.info(
                f"Cleaned up {cleaned_files} temporary files ({cleaned_bytes / (1024*1024):.2f} MB)"
            )

        # Log failed deletions in debug mode
        if failed_files:
            for failed in failed_files:
                logging.debug(f'Unable to delete temporary file "{failed}"')

            # Print warning for interactive mode feedback if there are failures
            if len(failed_files) <= 3:  # Only show if the list is short
                for failed in failed_files:
                    print(
                        f'{Fore.YELLOW}WARNING: Unable to delete temporary file "{failed}"{Style.RESET_ALL}'
                    )
            else:
                print(
                    f"{Fore.YELLOW}WARNING: Unable to delete {len(failed_files)} temporary files{Style.RESET_ALL}"
                )

    except Exception as e:
        logging.debug(f"Error cleaning temporary files: {e}")


def run_speedtest(detailed: bool = True) -> float:
    """
    Run network speed test and display results to the user.

    Tests multiple endpoints for accurate speed measurement and shows
    results in a user-friendly format. Returns the measured speed in Mbps.

    Args:
        detailed: Whether to show detailed output with recommendations

    Returns:
        Network speed in Mbps
    """
    # Create a spinner to show progress
    spinner = SpinnerAnimation("Running speed test", style="aesthetic", color="cyan")
    spinner.start()

    # Check for cached results first
    cache_file = os.path.join(CACHE_DIR, speedtestresult)
    now = time.time()
    try:
        if os.path.exists(cache_file):
            with open(cache_file, "r") as f:
                data = json.load(f)

            # If test was run within the last hour, use cached result
            if now - data["timestamp"] < 3600:  # 1 hour cache
                speed = data["speed_mbps"]
                spinner.update_status(
                    f"Using cached result ({time.strftime('%H:%M', time.localtime(data['timestamp']))})"
                )
                time.sleep(0.5)
                spinner.stop(clear=True)
                _display_speedtest_results(speed, detailed)
                return speed
    except Exception:
        # If any error occurs with cache, just run a new test
        pass

    # Define test endpoints - multiple CDNs for more accurate measurement
    test_endpoints = [
        # Small payload (~100KB) for initial test
        "https://httpbin.org/stream-bytes/102400",
        # 1MB test file from reliable CDNs
        "https://speed.cloudflare.com/__down?bytes=1048576",
        "https://cdn.jsdelivr.net/npm/jquery@3.6.0/dist/jquery.min.js",
        # Larger test file for higher-speed connections
        "https://proof.ovh.net/files/10Mb.dat",
    ]

    # Run the tests
    speeds = []
    start_time = time.time()
    max_test_time = 8.0  # Maximum 8 seconds for testing

    for i, url in enumerate(test_endpoints):
        if time.time() - start_time > max_test_time:
            break

        spinner.update_status(f"Testing speed ({i+1}/{len(test_endpoints)})")

        try:
            # Create a session for this request
            session = requests.Session()

            # Warm up connection (connect only to avoid measuring DNS overhead)
            session.head(url, timeout=2.0)

            # Measure download speed
            start = time.time()
            response = session.get(url, stream=True, timeout=5.0)

            if response.status_code == 200:
                total_bytes = 0
                for chunk in response.iter_content(chunk_size=65536):
                    total_bytes += len(chunk)
                    # Early exit if we have enough data or exceeded time limit
                    if total_bytes > 5 * 1024 * 1024 or time.time() - start > 3.0:
                        break

                # Calculate speed
                elapsed = time.time() - start
                if elapsed > 0 and total_bytes > 102400:  # Ensure we got at least 100KB
                    mbps = (total_bytes * 8) / (elapsed * 1000 * 1000)
                    speeds.append(mbps)
                    spinner.update_status(f"Measured: {mbps:.2f} Mbps")

            response.close()

        except requests.RequestException:
            continue

    spinner.stop(clear=True)

    # Calculate final speed (use median for robustness against outliers)
    if speeds:
        speeds.sort()
        if len(speeds) >= 3:
            # Remove highest and lowest values if we have enough samples
            speeds = speeds[1:-1]

        speed = sum(speeds) / len(speeds)
    else:
        # Fallback if all tests failed
        speed = 2.0  # Conservative estimate
        print(
            f"{Fore.YELLOW}Speed test encountered issues. Using default value of 2 Mbps.{Style.RESET_ALL}"
        )

    # Cache the result
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(cache_file, "w") as f:
            json.dump(
                {"timestamp": time.time(), "speed_mbps": speed, "samples": speeds}, f
            )
    except Exception:
        # Ignore cache write failures
        pass

    # Display results
    _display_speedtest_results(speed, detailed)

    return speed


def _display_speedtest_results(speed_mbps: float, detailed: bool = True) -> None:
    """
    Display speed test results in a user-friendly format with recommendations.

    Args:
        speed_mbps: Measured speed in Mbps
        detailed: Whether to show detailed recommendations
    """
    # Calculate more intuitive measurements
    mb_per_sec = speed_mbps / 8  # Convert Mbps to MB/s

    # Format numbers for display
    if mb_per_sec >= 1.0:
        speed_str = f"{mb_per_sec:.2f} MB/s"
    else:
        speed_str = f"{mb_per_sec * 1024:.1f} KB/s"

    # Create border width based on terminal
    try:
        term_width = shutil.get_terminal_size().columns
        border_width = min(60, max(40, term_width - 10))
    except (OSError, AttributeError, ValueError) as e:
        logging.debug(f"Could not determine terminal width: {e}")
        # Fallback to a default width
        border_width = 50

    border = f"{Fore.CYAN}{'═' * border_width}{Style.RESET_ALL}"

    # Display results with nice formatting
    print(border)
    print(f"{Fore.GREEN}NETWORK SPEED TEST RESULTS{Style.RESET_ALL}")
    print(border)

    # Determine color based on speed
    if speed_mbps >= 50:
        color = Fore.GREEN
        rating = "Excellent"
    elif speed_mbps >= 20:
        color = Fore.CYAN
        rating = "Very Good"
    elif speed_mbps >= 10:
        color = Fore.BLUE
        rating = "Good"
    elif speed_mbps >= 5:
        color = Fore.YELLOW
        rating = "Average"
    elif speed_mbps >= 2:
        color = Fore.YELLOW
        rating = "Below Average"
    else:
        color = Fore.RED
        rating = "Slow"

    # Main display
    print(
        f"\n  Download Speed: {color}{speed_mbps:.2f} Mbps{Style.RESET_ALL} ({speed_str})"
    )
    print(f"  Rating: {color}{rating}{Style.RESET_ALL}")

    # Add detailed recommendations if requested
    if detailed:
        print(f"\n{Fore.CYAN}DOWNLOAD RECOMMENDATIONS:{Style.RESET_ALL}")

        # Video quality recommendations
        print(f"\n  {Fore.YELLOW}Recommended Video Quality:{Style.RESET_ALL}")
        if speed_mbps >= 50:
            print(f"  • {Fore.GREEN}4K Video:{Style.RESET_ALL} ✓ Excellent")
            print(f"  • {Fore.GREEN}1080p Video:{Style.RESET_ALL} ✓ Excellent")
            print(f"  • {Fore.GREEN}720p Video:{Style.RESET_ALL} ✓ Excellent")
        elif speed_mbps >= 25:
            print(
                f"  • {Fore.YELLOW}4K Video:{Style.RESET_ALL} ⚠ May buffer occasionally"
            )
            print(f"  • {Fore.GREEN}1080p Video:{Style.RESET_ALL} ✓ Excellent")
            print(f"  • {Fore.GREEN}720p Video:{Style.RESET_ALL} ✓ Excellent")
        elif speed_mbps >= 10:
            print(f"  • {Fore.RED}4K Video:{Style.RESET_ALL} ✗ Not recommended")
            print(f"  • {Fore.GREEN}1080p Video:{Style.RESET_ALL} ✓ Good")
            print(f"  • {Fore.GREEN}720p Video:{Style.RESET_ALL} ✓ Excellent")
        elif speed_mbps >= 5:
            print(f"  • {Fore.RED}4K Video:{Style.RESET_ALL} ✗ Not recommended")
            print(f"  • {Fore.YELLOW}1080p Video:{Style.RESET_ALL} ⚠ May buffer")
            print(f"  • {Fore.GREEN}720p Video:{Style.RESET_ALL} ✓ Good")
        else:
            print(f"  • {Fore.RED}4K Video:{Style.RESET_ALL} ✗ Not recommended")
            print(f"  • {Fore.RED}1080p Video:{Style.RESET_ALL} ✗ Not recommended")
            print(f"  • {Fore.YELLOW}720p Video:{Style.RESET_ALL} ⚠ May buffer")
            print(f"  • {Fore.GREEN}480p Video:{Style.RESET_ALL} ✓ Recommended")

        # Audio format recommendations
        print(f"\n  {Fore.YELLOW}Audio Format Recommendations:{Style.RESET_ALL}")
        if speed_mbps >= 10:
            print(
                f"  • {Fore.GREEN}FLAC:{Style.RESET_ALL} ✓ Recommended for best quality"
            )
            print(f"  • {Fore.GREEN}MP3/Opus:{Style.RESET_ALL} ✓ Fast downloads")
        elif speed_mbps >= 3:
            print(f"  • {Fore.YELLOW}FLAC:{Style.RESET_ALL} ⚠ Will work but slower")
            print(
                f"  • {Fore.GREEN}MP3/Opus:{Style.RESET_ALL} ✓ Recommended for faster downloads"
            )
        else:
            print(f"  • {Fore.RED}FLAC:{Style.RESET_ALL} ✗ Not recommended")
            print(f"  • {Fore.GREEN}MP3/Opus:{Style.RESET_ALL} ✓ Recommended")

        # Download settings recommendations
        print(f"\n  {Fore.YELLOW}Optimized Settings:{Style.RESET_ALL}")

        # Determine optimal chunk size and concurrent downloads
        if speed_mbps >= 50:
            chunk_size = "20MB"
            concurrent = "24-32"
            aria2 = "✓ Highly recommended"
            aria_color = Fore.GREEN
        elif speed_mbps >= 20:
            chunk_size = "10MB"
            concurrent = "16-24"
            aria2 = "✓ Recommended"
            aria_color = Fore.GREEN
        elif speed_mbps >= 10:
            chunk_size = "5MB"
            concurrent = "8-16"
            aria2 = "✓ Recommended"
            aria_color = Fore.GREEN
        elif speed_mbps >= 5:
            chunk_size = "2MB"
            concurrent = "4-8"
            aria2 = "✓ Beneficial"
            aria_color = Fore.CYAN
        else:
            chunk_size = "1MB"
            concurrent = "2-4"
            aria2 = "⚠ Limited benefit"
            aria_color = Fore.YELLOW

        print(f"  • {Fore.CYAN}Chunk Size:{Style.RESET_ALL} {chunk_size}")
        print(f"  • {Fore.CYAN}Concurrent Downloads:{Style.RESET_ALL} {concurrent}")
        print(
            f"  • {Fore.CYAN}aria2c:{Style.RESET_ALL} {aria_color}{aria2}{Style.RESET_ALL}"
        )

        print(
            "\n  These settings will be applied automatically to optimize your downloads."
        )

    print(f"\n{border}")

    # Show retest instructions
    print(
        f"\n{Fore.GREEN}Tip:{Style.RESET_ALL} Run {Fore.CYAN}--speedtest{Style.RESET_ALL} again anytime to refresh these results.\n"
    )


@lru_cache(maxsize=None)
def is_windows() -> bool:
    """Check if running on Windows platform with caching for performance"""
    return platform.system().lower() == "windows"


def find_ffmpeg() -> Optional[str]:
    """Find FFmpeg in common locations or PATH with improved cross-platform support"""
    # Platform specific locations
    common_locations = []

    if is_windows():
        common_locations = [
            r"C:\ffmpeg\bin",
            r"C:\Program Files\ffmpeg\bin",
            r"C:\ffmpeg\ffmpeg-master-latest-win64-gpl\bin",
            r".\ffmpeg\bin",  # Relative to script location
        ]

        # Check if ffmpeg is in PATH on Windows
        try:
            result = subprocess.run(
                ["where", "ffmpeg"], capture_output=True, text=True, timeout=3
            )
            if result.returncode == 0:
                path = result.stdout.strip().split("\n")[0]
                return os.path.dirname(path)
        except (subprocess.SubprocessError, FileNotFoundError):
            pass
    else:
        common_locations = [
            "/usr/bin",
            "/usr/local/bin",
            "/opt/local/bin",
            "/opt/homebrew/bin",
        ]

        # Check if ffmpeg is in PATH on Unix-like systems
        try:
            result = subprocess.run(
                ["which", "ffmpeg"], capture_output=True, text=True, timeout=3
            )
            if result.returncode == 0:
                path = result.stdout.strip()
                return os.path.dirname(path)
        except (subprocess.SubprocessError, FileNotFoundError):
            pass

    # Check common locations for ffmpeg binary
    ffmpeg_exec = "ffmpeg.exe" if is_windows() else "ffmpeg"
    for location in common_locations:
        ffmpeg_path = os.path.join(location, ffmpeg_exec)
        if os.path.exists(ffmpeg_path):
            return location

    return None


# New function to check if FFmpeg is valid at a specific location
def validate_ffmpeg_path(ffmpeg_location: str) -> bool:
    """
    Validate that the specified ffmpeg_location contains valid FFmpeg binaries.

    Args:
        ffmpeg_location: Path to directory containing FFmpeg binaries

    Returns:
        bool: True if valid FFmpeg binaries found, False otherwise
    """
    if not ffmpeg_location or not os.path.exists(ffmpeg_location):
        return False

    # Check for ffmpeg executable
    ffmpeg_exec = "ffmpeg.exe" if is_windows() else "ffmpeg"
    ffmpeg_path = os.path.join(ffmpeg_location, ffmpeg_exec)

    if not os.path.exists(ffmpeg_path):
        return False

    # Test if executable works
    try:
        result = subprocess.run(
            [ffmpeg_path, "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=3,
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, OSError):
        return False


def print_ffmpeg_instructions():
    """Print instructions for installing FFmpeg with platform-specific guidance"""
    print(
        f"{Fore.YELLOW}FFmpeg not found! Please follow these steps to install FFmpeg:{Style.RESET_ALL}"
    )
    print("\n1. Download FFmpeg:")
    print("   - Visit: https://github.com/BtbN/FFmpeg-Builds/releases")
    print("   - Download: ffmpeg-master-latest-win64-gpl.zip")
    print("\n2. Install FFmpeg:")
    print("   - Extract the downloaded zip file")
    print("   - Copy the extracted folder to C:\\ffmpeg")
    print("   - Ensure ffmpeg.exe is in C:\\ffmpeg\\bin")
    print("\nAlternatively:")
    print("- Use chocolatey: choco install ffmpeg")
    print("- Use winget: winget install ffmpeg")
    print("\nAfter installation, either:")
    print("1. Add FFmpeg to your system PATH, or")
    print("2. Update config.json with the correct ffmpeg_location")
    print(
        "\nFor detailed instructions, visit: https://www.wikihow.com/Install-FFmpeg-on-Windows"
    )


# New function to load and validate the configuration file
def initialize_config(force_validation: bool = False) -> Dict[str, Any]:
    """
    Load and validate the configuration file, with intelligent fallbacks and auto-correction.

    Args:
        force_validation: If True, validate FFmpeg path even if config exists

    Returns:
        Dict containing validated configuration
    """
    config = {}
    config_path = Path(CONFIG_FILE)
    ffmpeg_validated = False
    config_changed = False

    # Set up a spinner for config initialization
    spinner = None
    try:
        from colorama import Fore, Style

        spinner = SpinnerAnimation("Initializing configuration", style="dots")
        spinner.start()
    except (ImportError, NameError):
        pass

    try:
        # Step 1: Load existing config if available
        if config_path.exists():
            try:
                with open(config_path, "r") as f:
                    config = json.load(f)

                # Ensure all default keys are present
                for key, value in DEFAULT_CONFIG.items():
                    if key not in config:
                        config[key] = value
                        config_changed = True

                # Ensure organization templates are complete
                if "organization_templates" in config:
                    for key, value in DEFAULT_ORGANIZATION_TEMPLATES.items():
                        if key not in config["organization_templates"]:
                            config["organization_templates"][key] = value
                            config_changed = True
                else:
                    config["organization_templates"] = (
                        DEFAULT_ORGANIZATION_TEMPLATES.copy()
                    )
                    config_changed = True

                if spinner:
                    spinner.update_status("Configuration loaded")
            except (json.JSONDecodeError, IOError) as e:
                logging.error(f"Error loading config file: {e}")
                config = DEFAULT_CONFIG.copy()
                config_changed = True
                if spinner:
                    spinner.update_status("Creating new configuration")
        else:
            # No config file exists, create default
            config = DEFAULT_CONFIG.copy()
            config_changed = True
            if spinner:
                spinner.update_status("Creating new configuration")

        # Step 2: Validate FFmpeg path if needed
        if (
            force_validation
            or not config.get("ffmpeg_location")
            or not validate_ffmpeg_path(config["ffmpeg_location"])
        ):
            if spinner:
                spinner.update_status("Locating FFmpeg")

            ffmpeg_path = find_ffmpeg()

            if ffmpeg_path:
                config["ffmpeg_location"] = ffmpeg_path
                ffmpeg_validated = True
                config_changed = True
                if spinner:
                    spinner.update_status(f"Found FFmpeg: {ffmpeg_path}")
            else:
                # Could not find a valid FFmpeg installation
                if not config.get("ffmpeg_location", ""):
                    if spinner:
                        spinner.stop(clear=False, success=False)
                        spinner = None  # Prevent stopping again in finally block
                    print_ffmpeg_instructions()
                    # Set to empty but don't raise error yet
                    config["ffmpeg_location"] = ""
                    config_changed = True
        else:
            # Already have a valid FFmpeg path in config
            ffmpeg_validated = True
            if spinner:
                spinner.update_status("Using FFmpeg from config")

        # Step 3: Save updated config if changed
        if config_changed:
            try:
                with open(config_path, "w") as f:
                    json.dump(config, f, indent=4)
                if spinner:
                    spinner.update_status("Configuration saved")
            except IOError as e:
                logging.error(f"Error saving config file: {e}")
                if spinner:
                    spinner.update_status("Error saving configuration")

        # Final verification of critical settings
        if "video_output" in config and not os.path.exists(config["video_output"]):
            try:
                os.makedirs(config["video_output"], exist_ok=True)
            except OSError:
                config["video_output"] = str(Path.home() / "Videos")
                config_changed = True

        if "audio_output" in config and not os.path.exists(config["audio_output"]):
            try:
                os.makedirs(config["audio_output"], exist_ok=True)
            except OSError:
                config["audio_output"] = str(Path.home() / "Music")
                config_changed = True

        # Step 4: Final save if needed after validation
        if config_changed:
            try:
                with open(config_path, "w") as f:
                    json.dump(config, f, indent=4)
            except IOError as e:
                logging.error(f"Error saving final config: {e}")

        # Check if FFmpeg is available and raise error if not
        if not ffmpeg_validated and not validate_ffmpeg_path(config["ffmpeg_location"]):
            if spinner:
                spinner.stop(clear=False, success=False)
                spinner = None  # Prevent stopping again in finally block
            raise FileNotFoundError(
                "FFmpeg is required but could not be found. Please install FFmpeg and update the config file."
            )

        return config

    finally:
        # Always clean up the spinner if it exists
        if spinner:
            spinner.stop(clear=True, success=True)


@contextmanager
def timer(name: str = "", silent: bool = False):
    """
    Context manager for timing code execution with optional logging.

    Args:
        name: Description of the timed operation
        silent: If True, suppresses log output

    Example:
        with timer("Media extraction"):
            # code to time

    Yields:
        None
    """
    start_time = time.time()
    try:
        yield
    finally:
        elapsed = time.time() - start_time
        if not silent:
            logging.info(f"{name} completed in {elapsed:.2f} seconds")
        else:
            logging.debug(f"{name} completed in {elapsed:.2f} seconds")


class ColorProgressBar:
    """Enhanced progress bar with color support and performance optimizations"""

    def __init__(
        self,
        total: int,
        desc: str = "Processing",
        unit: str = "%",
        color_scheme: str = "gradient",
    ):
        # Get terminal width for adaptive sizing with fallback
        try:
            terminal_width = shutil.get_terminal_size().columns
            bar_width = min(terminal_width - 30, 80)  # Ensure reasonable size
        except (AttributeError, OSError):
            bar_width = 80  # Fallback width if terminal size cannot be determined

        # Pre-define color schemes to avoid repetitive calculations
        self.color_schemes = {
            "gradient": [Fore.RED, Fore.YELLOW, Fore.GREEN],
            "rotating": [Fore.BLUE, Fore.CYAN, Fore.GREEN, Fore.YELLOW, Fore.MAGENTA],
            "blue": [Fore.BLUE, Fore.CYAN, Fore.LIGHTBLUE_EX],
            "simple": [Fore.CYAN],
        }

        # Set scheme and prepare variables - use get() with default for safety
        self.colors = self.color_schemes.get(
            color_scheme, self.color_schemes["gradient"]
        )
        self.current_color_idx = 0
        self.last_update = 0
        self.color_scheme = color_scheme
        self.completed = False
        self.last_percent = 0  # Track last percentage to avoid redundant updates
        self.custom_speed = ""  # Store custom speed information

        # Create the tqdm progress bar with fixed format that omits the problematic rate_fmt
        self.progress = tqdm(
            total=total,
            desc=f"{Fore.CYAN}{desc}{Style.RESET_ALL}",
            bar_format="{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]",
            ncols=bar_width,
            unit=unit,
            dynamic_ncols=True,  # Allow resizing with terminal
            smoothing=0.3,  # Add smoothing for more stable rate calculation
        )

    def update(self, n: int = 1) -> None:
        """Update the progress bar with optimized color handling and error tolerance"""
        try:
            current_progress = self.progress.n + n

            # Calculate percentage once for efficiency
            percent_complete = min(
                100, int((current_progress / self.progress.total) * 100)
            )

            # Skip update if percentage hasn't changed (optimization)
            if (
                percent_complete == self.last_percent
                and self.color_scheme != "rotating"
            ):
                self.progress.update(
                    n
                )  # Still update the counter without changing colors
                return

            self.last_percent = percent_complete
            current_time = time.time()

            # Optimized color update logic
            if self.color_scheme == "gradient":
                # Color based on percentage complete - optimize calculation
                color_idx = min(
                    len(self.colors) - 1, percent_complete * len(self.colors) // 100
                )
                current_color = self.colors[color_idx]
            elif (
                current_time - self.last_update > 0.2
            ):  # Limit updates for rotating scheme (performance)
                # Rotating colors
                self.current_color_idx = (self.current_color_idx + 1) % len(self.colors)
                current_color = self.colors[self.current_color_idx]
                self.last_update = current_time
            else:
                current_color = self.colors[self.current_color_idx]

            # Update the bar format with the selected color and custom speed if available
            speed_info = f", {self.custom_speed}" if self.custom_speed else ""
            self.progress.bar_format = (
                "{desc}: {percentage:3.0f}%|"
                f"{current_color}"
                "{bar}"
                f"{Style.RESET_ALL}"
                f"| {{n_fmt}}/{{total_fmt}} [{{elapsed}}<{{remaining}}{speed_info}]"
            )

            # Update the progress bar
            self.progress.update(n)

            # Check if completed - only update format once
            if current_progress >= self.progress.total and not self.completed:
                self.completed = True
                # Ensure final bar is green
                self.progress.bar_format = (
                    "{desc}: {percentage:3.0f}%|"
                    f"{Fore.GREEN}"
                    "{bar}"
                    f"{Style.RESET_ALL}"
                    "| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]"
                )
                self.progress.refresh()
        except Exception:
            # Fallback to normal update in case of issues with color or formatting
            try:
                self.progress.update(n)
            except Exception:
                pass  # Last resort if everything fails

    def set_description(self, description: str) -> None:
        self.progress.set_description_str(description)

    def set_speed(self, speed_str: str) -> None:
        """
        Set custom speed information to display in the progress bar.

        This method updates the speed display in the progress bar, avoiding
        unnecessary refreshes and ensuring thread safety for concurrent calls.

        Args:
            speed_str (str): Formatted speed string to display (e.g. "5.2 MB/s")
                Set to empty string or None to remove speed information.

        Note:
            Changes are applied immediately if the progress bar exists and is active.
            The method is safe to call from any thread or context.
        """
        # Early return if the speed hasn't changed (optimization)
        if speed_str == self.custom_speed:
            return

        # Update the stored speed value
        old_value = self.custom_speed
        self.custom_speed = speed_str

        # Only update display if progress bar exists and is visible
        if not hasattr(self, "progress") or getattr(self.progress, "disable", True):
            return

        try:
            # Prepare the formatted speed info only when needed
            speed_info = f", {self.custom_speed}" if self.custom_speed else ""

            # Get the current color safely
            if hasattr(self, "current_color_idx") and hasattr(self, "colors"):
                color_idx = min(self.current_color_idx, len(self.colors) - 1)
                current_color = self.colors[color_idx]
            else:
                current_color = Fore.CYAN  # Safe default

            # Update bar format with the speed info
            self.progress.bar_format = (
                "{desc}: {percentage:3.0f}%|"
                f"{current_color}"
                "{bar}"
                f"{Style.RESET_ALL}"
                f"| {{n_fmt}}/{{total_fmt}} [{{elapsed}}<{{remaining}}{speed_info}]"
            )

            # Only refresh if needed - visible and not closed
            if not getattr(self.progress, "closed", False):
                self.progress.refresh()

        except Exception as e:
            # Restore previous value on error and log silently
            self.custom_speed = old_value
            logging.debug(f"Error updating speed display: {e}")
            # Continue execution - don't let UI errors affect download

    def close(self, message: Optional[str] = None) -> None:
        """Close the progress bar with optional completion message"""
        if hasattr(self, "progress") and not self.progress.disable:
            try:
                self.progress.close()
                if message:
                    print(f"\n{Fore.GREEN}✓ {message}{Style.RESET_ALL}")
                elif not self.completed:  # Don't print twice if already completed
                    print(f"\n{Fore.GREEN}✓ Complete!{Style.RESET_ALL}")
            except Exception:
                pass  # Ensure we don't crash on close


def print_banner():
    """Display an enhanced colorful welcome banner with snake logo and performance optimizations"""
    terminal_width = shutil.get_terminal_size().columns
    banner = f"""
{Fore.CYAN}╔{'═' * 58}╗
║  {Fore.GREEN}             ____  {Fore.YELLOW}               _        _      {Fore.CYAN}      ║
║  {Fore.GREEN}    _____  / ___| {Fore.YELLOW}_ __    __ _  | |_   __| |__   {Fore.CYAN}       ║
║  {Fore.GREEN}   |_____| \\___ \\ {Fore.YELLOW}| '_ \\  / _` | | __| / _` / /   {Fore.CYAN}      ║
║  {Fore.GREEN}   |_____| |___) |{Fore.YELLOW}| | | || (_| | | |_ | (_| \\ \\   {Fore.CYAN}      ║
║  {Fore.GREEN}           |____/ {Fore.YELLOW}|_| |_| \\__,_|  \\__| \\__,_/_/   {Fore.CYAN}      ║
║  {Fore.GREEN}    /^ ^\\   ___  {Fore.YELLOW}                                  {Fore.CYAN}     ║
║  {Fore.GREEN}   / 0 0 \\ / _ \\ {Fore.YELLOW}        Download Anything!       {Fore.CYAN}      ║
║  {Fore.GREEN}   V\\ Y /V / (_) |{Fore.YELLOW}                                {Fore.CYAN}      ║
║  {Fore.GREEN}    / - \\  \\___/ {Fore.YELLOW}      ~ Videos & Music ~        {Fore.CYAN}       ║
║  {Fore.GREEN}   /    |         {Fore.YELLOW}                                {Fore.CYAN}      ║
║  {Fore.GREEN}  *___/||         {Fore.YELLOW}                                {Fore.CYAN}      ║
╠{'═' * 58}╣
║     {Fore.GREEN}■ {Fore.WHITE}Version: {Fore.YELLOW}1.7.0{Fore.WHITE}                                   {Fore.CYAN}  ║
║     {Fore.GREEN}■ {Fore.WHITE}GitHub : {Fore.YELLOW}github.com/Rashed-alothman/Snatch{Fore.WHITE}        {Fore.CYAN} ║
╠{'═' * 58}╣
║  {Fore.YELLOW}Type {Fore.GREEN}help{Fore.YELLOW} or {Fore.GREEN}?{Fore.YELLOW} for commands  {Fore.WHITE}|  {Fore.YELLOW}Press {Fore.GREEN}Ctrl+C{Fore.YELLOW} to cancel  {Fore.CYAN}║
╚{'═' * 58}╝{Style.RESET_ALL}"""

    # Calculate padding for centering
    lines = banner.split("\n")
    max_content_width = max(
        (len(re.sub(r"\x1b\[[0-9;]+m", "", line)) for line in lines if line), default=0
    )
    padding = max(0, (terminal_width - max_content_width) // 2)

    # Print banner with padding
    print("\n" * 2)  # Add some space above banner
    for line in banner.split("\n"):
        if line:
            print(" " * padding + line)
    print("\n")  # Add space below banner


class SpinnerAnimation:
    """
    Animated spinner for displaying loading states with rich customization options.

    Features:
    - Multiple spinner styles with color support
    - Dynamic message updates and status tracking
    - Thread-safe operations with proper resource cleanup
    - Elapsed time tracking and adaptive terminal width handling
    - Customizable appearance and behavior

    Example:
        spinner = SpinnerAnimation("Loading data", style="aesthetic", color="green")
        spinner.start()
        try:
            # Do some work
            spinner.update_status("Processing files")
            # Do more work
        finally:
            spinner.stop(clear=True, success=True)
    """

    def __init__(
        self,
        message: str = "Processing",
        style: str = "dots",
        color: str = "cyan",
        delay: float = 0.08,
    ):
        # Style selection with fallbacks
        self.style = style.lower()
        self.spinner = SPINNER_STYLES.get(self.style, SPINNER_STYLES["dots"])
        self.message = message

        # Color handling
        self.color_name = color.lower()
        self.color = getattr(Fore, color.upper(), Fore.CYAN)

        # Animation control
        self.delay = delay
        self.running = False
        self.thread = None

        # Thread safety
        self._lock = threading.RLock()
        self._paused = False

        # State tracking
        self._terminal_width = shutil.get_terminal_size().columns
        self._status_text = ""
        self._start_time = None
        self._cursor_hidden = False

    def _get_formatted_message(self) -> str:
        """Format message with elapsed time and status"""
        base_msg = f"{self.message}..."

        # Add status if present
        if self._status_text:
            base_msg += f" {self._status_text}"

        # Add elapsed time if spinner has been running
        if self._start_time:
            elapsed = time.time() - self._start_time
            if elapsed > 2:  # Only show time after 2 seconds
                if elapsed < 60:
                    time_str = f"{elapsed:.1f}s"
                else:
                    mins, secs = divmod(int(elapsed), 60)
                    time_str = f"{mins}m {secs}s"
                base_msg += f" [{time_str}]"

        return base_msg

    def update_message(self, message: str) -> None:
        """Update the spinner message while running"""
        with self._lock:
            self.message = message

    def update_status(self, status: str) -> None:
        """Update additional status text (e.g. '3/10 complete')"""
        with self._lock:
            self._status_text = status

    def update_color(self, color: str) -> None:
        """Update spinner color"""
        with self._lock:
            self.color_name = color.lower()
            self.color = getattr(Fore, color.upper(), Fore.CYAN)

    def update_style(self, style: str) -> None:
        """Change spinner style while running"""
        with self._lock:
            self.style = style.lower()
            self.spinner = SPINNER_STYLES.get(self.style, SPINNER_STYLES["dots"])

    def spin(self) -> None:
        """Core spinner animation function with adaptive terminal handling"""
        self._start_time = time.time()

        while self.running:
            try:
                # Check if terminal size changed
                current_width = shutil.get_terminal_size().columns
                if current_width != self._terminal_width:
                    self._terminal_width = current_width

                # Handle pause state
                if self._paused:
                    time.sleep(0.2)
                    continue

                # Animate the spinner
                for char in self.spinner:
                    if not self.running or self._paused:
                        break

                    # Format the message with current status
                    with self._lock:
                        formatted_msg = self._get_formatted_message()

                    # Ensure we don't exceed terminal width
                    if len(formatted_msg) + 5 > self._terminal_width:
                        # Truncate with ellipsis if needed
                        max_len = self._terminal_width - 5
                        formatted_msg = formatted_msg[: max_len - 3] + "..."

                    # Print the spinner frame
                    print(
                        f"\r{self.color}{char} {formatted_msg}{Style.RESET_ALL}",
                        end="",
                        flush=True,
                    )
                    time.sleep(self.delay)

            except Exception as e:
                # Prevent spinner from crashing the main program
                try:
                    logging.debug(f"Spinner error: {str(e)}")
                except (AttributeError, NameError):
                    # This handles cases where logging module isn't properly initialized
                    # or when logging.debug isn't callable
                    pass
                time.sleep(0.5)

    def pause(self) -> None:
        """Pause the spinner animation"""
        with self._lock:
            self._paused = True

    def resume(self) -> None:
        """Resume the spinner animation"""
        with self._lock:
            self._paused = False

    def start(self) -> None:
        """Start spinner animation safely with daemon thread"""
        with self._lock:
            if not self.running:
                self.running = True
                self._paused = False
                self.thread = threading.Thread(target=self.spin, daemon=True)
                self.thread.start()

                # Hide cursor if supported
                try:
                    if os.name == "posix":
                        print("\033[?25l", end="", flush=True)
                        self._cursor_hidden = True
                except (IOError, UnicodeError) as e:
                    # Ignore errors when terminal doesn't support ANSI escape codes
                    logging.debug(f"Failed to hide cursor: {e}")

    def stop(self, clear: bool = True, success: bool = None) -> None:
        """
        Stop spinner animation with proper cleanup

        Args:
            clear: Whether to clear the spinner line
            success: If provided, shows checkmark (True) or X (False)
        """
        with self._lock:
            self.running = False

        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=0.5)  # Use timeout to avoid hanging

        # Restore cursor if it was hidden
        if self._cursor_hidden:
            try:
                print("\033[?25h", end="", flush=True)
                self._cursor_hidden = False
            except (IOError, UnicodeError) as e:
                logging.debug(f"Failed to restore cursor: {e}")

        if clear:
            # Clear the spinner line completely
            print("\r" + " " * (self._terminal_width - 1) + "\r", end="")
        else:
            # Print final state with optional success/failure indicator
            formatted_msg = self._get_formatted_message()
            if success is True:
                print(f"\r{Fore.GREEN}✓ {formatted_msg}{Style.RESET_ALL}")
            elif success is False:
                print(f"\r{Fore.RED}✗ {formatted_msg}{Style.RESET_ALL}")
            else:
                print(f"\r{self.color}• {formatted_msg}{Style.RESET_ALL}")


class DownloadCache:
    """Cache for optimizing repeated downloads with LRU eviction"""

    def __init__(self, cache_dir: Path = CACHE_DIR, max_size_mb: int = 100):
        self.cache_dir = cache_dir
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        # New LRU dictionary mapping cache key to last access time
        self.lru = OrderedDict()
        # Initialize LRU from existing cache files
        for file in self.cache_dir.glob("*.info.json"):
            key = file.stem
            self.lru[key] = file.stat().st_mtime
        self._cleanup_if_needed()

    def _get_cache_key(self, url: str) -> str:
        """Generate a unique key for a URL"""
        return hashlib.md5(url.encode("utf-8")).hexdigest()

    def get_info(self, url: str) -> Optional[Dict]:
        """Get cached info for a URL"""
        key = self._get_cache_key(url)
        info_path = self.cache_dir / f"{key}.info.json"

        if (
            info_path.exists() and time.time() - info_path.stat().st_mtime < 3600
        ):  # 1 hour cache
            try:
                with open(info_path, "r") as f:
                    data = json.load(f)
                # Update LRU ordering
                self.lru.pop(key, None)
                self.lru[key] = time.time()
                return data
            except (json.JSONDecodeError, IOError):
                return None
        return None

    def save_info(self, url: str, info: Dict) -> None:
        """Save info for a URL"""
        key = self._get_cache_key(url)
        info_path = self.cache_dir / f"{key}.info.json"

        # Convert LazyList objects to regular lists for JSON serialization
        def make_serializable(obj):
            if (
                isinstance(obj, list)
                and hasattr(obj, "__iter__")
                and not isinstance(obj, (str, bytes, dict))
            ):
                return list(obj)  # Convert LazyList to regular list
            elif isinstance(obj, dict):
                return {k: make_serializable(v) for k, v in obj.items()}
            elif hasattr(obj, "__iter__") and not isinstance(obj, (str, bytes, dict)):
                return list(obj)
            else:
                return obj

        try:
            with open(info_path, "w") as f:
                json.dump(make_serializable(info), f)
            # Update LRU ordering
            self.lru.pop(key, None)
            self.lru[key] = time.time()
            self._cleanup_if_needed()  # Evict if capacity exceeded
        except IOError as e:  # Fixed exception handler
            logging.debug(f"Failed to save cache info: {str(e)}")

    def _cleanup_if_needed(self) -> None:
        """Clean up cache if it exceeds size limit using LRU eviction"""
        try:
            cache_files = list(self.cache_dir.glob("*"))
            cache_size = sum(f.stat().st_size for f in cache_files if f.is_file())
            # Evict least recently used entries until under capacity
            while cache_size > self.max_size_bytes and self.lru:
                lru_key, _ = self.lru.popitem(last=False)
                file_path = self.cache_dir / f"{lru_key}.info.json"
                if file_path.exists():
                    file_size = file_path.stat().st_size
                    file_path.unlink(missing_ok=True)
                    cache_size -= file_size
        except Exception:
            pass


# Add this near other utility functions
def make_serializable(obj):
    """Convert complex objects to JSON-serializable format"""
    if (
        isinstance(obj, list)
        and hasattr(obj, "__iter__")
        and not isinstance(obj, (str, bytes, dict))
    ):
        return [make_serializable(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: make_serializable(v) for k, v in obj.items()}
    elif hasattr(obj, "__iter__") and not isinstance(obj, (str, bytes, dict)):
        return [make_serializable(item) for item in obj]
    else:
        return obj


# New Session Manager to track download progress
class SessionManager:
    """
    Manages download sessions with advanced features for resuming interrupted downloads.

    Features:
    - Thread-safe operations for concurrent downloads
    - Memory-efficient caching with automatic persistence
    - Session expiration and automatic cleanup
    - Robust error handling and recovery
    - Optimized I/O with batched writes
    """

    def __init__(
        self,
        session_file: str = DOWNLOAD_SESSIONS_FILE,
        auto_save_interval: int = 30,
        session_expiry: int = 7 * 24 * 60 * 60,
    ):  # 7 days default expiry
        self.session_file = session_file
        self.sessions = {}
        self.lock = threading.RLock()  # Reentrant lock for thread safety
        self.last_save_time = 0
        self.modified = False
        self.auto_save_interval = auto_save_interval  # Seconds between auto-saves
        self.session_expiry = session_expiry  # Session expiry in seconds

        # Load existing sessions and perform maintenance
        self._load_and_maintain_sessions()

        # Start background auto-save thread if interval is positive
        if self.auto_save_interval > 0:
            self._start_auto_save_thread()

    def _load_and_maintain_sessions(self) -> None:
        """Load sessions from disk and remove expired entries"""
        with self.lock:
            # Load existing sessions
            self.sessions = self._load_sessions_from_disk()

            # Perform maintenance - remove expired sessions
            current_time = time.time()
            expired_count = 0

            for url, session in list(self.sessions.items()):
                # Remove sessions that are too old
                if current_time - session.get("timestamp", 0) > self.session_expiry:
                    del self.sessions[url]
                    expired_count += 1

            if expired_count > 0:
                logging.info(f"Removed {expired_count} expired download sessions")
                self.modified = True
                self._save_sessions_to_disk()

    def _load_sessions_from_disk(self) -> dict:
        """Load sessions from disk with robust error handling"""
        if not os.path.exists(self.session_file):
            return {}

        try:
            with open(self.session_file, "r") as f:
                sessions = json.load(f)

            # Validate loaded data
            if not isinstance(sessions, dict):
                logging.warning(
                    f"Invalid session data format, expected dict but got {type(sessions)}"
                )
                return {}

            return sessions
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse session file: {e}")
            # Create backup of corrupted file for recovery
            self._backup_corrupted_file()
            return {}
        except (IOError, OSError) as e:
            logging.error(f"Error reading session file: {e}")
            return {}
        except Exception as e:
            logging.error(f"Unexpected error loading sessions: {e}")
            return {}

    def _backup_corrupted_file(self) -> None:
        """Create backup of corrupted session file"""
        try:
            if os.path.exists(self.session_file):
                backup_file = f"{self.session_file}.bak.{int(time.time())}"
                shutil.copy2(self.session_file, backup_file)
                logging.info(f"Created backup of corrupted session file: {backup_file}")
        except Exception as e:
            logging.error(f"Failed to backup corrupted session file: {e}")

    def _save_sessions_to_disk(self) -> bool:
        """Save sessions to disk with proper error handling and atomic writes"""
        if not self.modified:
            return True  # Skip saving if no changes

        try:
            # Create temp file for atomic write
            temp_file = f"{self.session_file}.tmp"

            # Use a temporary file for atomic write
            with open(temp_file, "w") as f:
                json.dump(self.sessions, f, indent=2)
                f.flush()  # Ensure data is written to disk
                os.fsync(f.fileno())  # Force flush to stable storage

            # Perform atomic replace
            if os.path.exists(self.session_file):
                if is_windows():
                    # Windows needs special handling for atomic replacement
                    os.replace(temp_file, self.session_file)
                else:
                    # POSIX systems can use rename for atomic replacement
                    os.rename(temp_file, self.session_file)
            else:
                os.rename(temp_file, self.session_file)

            self.last_save_time = time.time()
            self.modified = False
            return True

        except (IOError, OSError) as e:
            logging.error(f"Failed to save session data: {e}")
            return False
        except Exception as e:
            logging.error(f"Unexpected error saving sessions: {e}")
            return False

    def _start_auto_save_thread(self) -> None:
        """Start background thread for periodic auto-saving"""

        def auto_save_worker():
            while True:
                try:
                    time.sleep(self.auto_save_interval)
                    with self.lock:
                        if (
                            self.modified
                            and time.time() - self.last_save_time
                            >= self.auto_save_interval
                        ):
                            self._save_sessions_to_disk()
                except Exception as e:
                    logging.error(f"Error in auto-save thread: {e}")

        save_thread = threading.Thread(
            target=auto_save_worker, daemon=True, name="SessionAutoSave"
        )
        save_thread.start()

    def update_session(self, url: str, progress: float, metadata: dict = None) -> bool:
        """
        Update or create a session with the current progress and optional metadata.

        Args:
            url: The download URL as unique identifier
            progress: Download progress percentage (0-100)
            metadata: Optional dict with additional session data

        Returns:
            True if session was updated successfully
        """
        if not url:
            return False

        with self.lock:
            # Create or update session
            if url not in self.sessions:
                self.sessions[url] = {}

            # Update with new data
            self.sessions[url].update(
                {
                    "progress": float(progress),
                    "timestamp": time.time(),
                    "last_active": time.strftime("%Y-%m-%d %H:%M:%S"),
                }
            )

            # Add metadata if provided
            if metadata and isinstance(metadata, dict):
                if "metadata" not in self.sessions[url]:
                    self.sessions[url]["metadata"] = {}
                self.sessions[url]["metadata"].update(metadata)

            self.modified = True

            # Save immediately if this is a significant progress update
            # This ensures we don't lose too much progress if the program crashes
            if progress % 10 < 1:  # Save at each 10% milestone
                self._save_sessions_to_disk()

            return True

    def remove_session(self, url: str) -> bool:
        """
        Remove a session when download completes or is cancelled.

        Args:
            url: The download URL to remove

        Returns:
            True if session was found and removed
        """
        with self.lock:
            if url in self.sessions:
                del self.sessions[url]
                self.modified = True
                return True
            return False

    def get_session(self, url: str) -> Optional[dict]:
        """
        Get session data for a URL if it exists and is valid.

        Args:
            url: The download URL to retrieve

        Returns:
            Session dict or None if not found
        """
        with self.lock:
            session = self.sessions.get(url)
            if not session:
                return None

            # Validate session before returning
            if "progress" not in session or "timestamp" not in session:
                logging.warning(f"Found invalid session for {url}, removing it")
                del self.sessions[url]
                self.modified = True
                return None

            # Check if session is expired
            if time.time() - session["timestamp"] > self.session_expiry:
                logging.info(f"Found expired session for {url}, removing it")
                del self.sessions[url]
                self.modified = True
                return None

            return session.copy()  # Return a copy to prevent external modification

    def get_all_sessions(self) -> dict:
        """Get all active download sessions (thread-safe copy)"""
        with self.lock:
            return {url: session.copy() for url, session in self.sessions.items()}

    def clear_all_sessions(self) -> None:
        """Clear all sessions (for testing or reset)"""
        with self.lock:
            self.sessions.clear()
            self.modified = True
            self._save_sessions_to_disk()

    def get_session_count(self) -> int:
        """Get the number of active sessions"""
        with self.lock:
            return len(self.sessions)

    def get_resumable_sessions(self, max_age: int = None) -> List[Dict]:
        """
        Get a list of sessions that can be resumed, sorted by last activity.

        Args:
            max_age: Optional maximum age in seconds

        Returns:
            List of dicts with session info including URL
        """
        with self.lock:
            current_time = time.time()
            max_age = max_age or self.session_expiry

            # Filter and prepare session data
            resumable = []
            for url, session in self.sessions.items():
                if current_time - session.get("timestamp", 0) <= max_age:
                    # Copy session and add URL
                    session_copy = session.copy()
                    session_copy["url"] = url
                    resumable.append(session_copy)

            # Sort by timestamp (most recent first)
            resumable.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
            return resumable

    def __enter__(self):
        """Support for context manager protocol"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Ensure sessions are saved when used as context manager"""
        if self.modified:
            self._save_sessions_to_disk()


def calculate_speed(downloaded_bytes: int, start_time: float) -> float:
    """
    Calculate download speed with high precision and robust error handling.

    This implementation uses high-resolution performance counters when available
    and includes sophisticated edge case handling to prevent calculation errors
    even under extreme conditions.

    Args:
        downloaded_bytes: Total number of bytes downloaded so far
        start_time: Timestamp when the download started (in seconds)

    Returns:
        Current download speed in bytes per second
    """
    # Input validation with early return for impossible scenarios
    if downloaded_bytes <= 0 or start_time <= 0 or start_time > time.time():
        return 0.0

    # Use high-precision timer for more accurate measurements
    # perf_counter is monotonic and not affected by system clock changes
    current_time = time.perf_counter() if hasattr(time, "perf_counter") else time.time()

    # Calculate elapsed time with protection against negative values
    # (which could happen if system time is adjusted backward)
    elapsed = max(0.001, current_time - start_time)

    # Guard against unrealistically high speeds due to very small elapsed times
    # (prevents showing astronomical speeds in the first few milliseconds)
    if elapsed < 0.1 and downloaded_bytes > 1024 * 1024:
        # With very small elapsed times, use a minimum threshold
        # to avoid reporting unrealistic speeds
        elapsed = 0.1

    # Calculate and return bytes per second
    return downloaded_bytes / elapsed


def format_speed(speed: float) -> str:
    """Return a human-friendly speed string."""
    if speed < 1024:
        return f"{speed:.2f} B/s"
    elif speed < 1024 * 1024:
        return f"{speed/1024:.2f} KB/s"
    else:
        return f"{speed/(1024*1024):.2f} MB/s"


def sanitize_filename(filename: str) -> str:
    """
    Create a sanitized version of a filename that works across platforms.
    Removes illegal characters and limits length.
    """
    # Replace problematic characters including Unicode special chars
    illegal_chars = r'[\\/*?:"<>|⧸⁄∕⧵＼／]'  # Added more Unicode slash variants

    # Normalize unicode characters
    filename = unicodedata.normalize("NFKD", filename)

    # Replace characters that aren't allowed in filenames
    filename = re.sub(illegal_chars, "_", filename)

    # Replace multiple spaces and underscores with a single one
    filename = re.sub(r"[_ ]+", " ", filename).strip()

    # Limit filename length (255 is max on most filesystems)
    # Leave some room for extensions and path
    max_length = 200
    if len(filename) > max_length:
        filename = filename[:max_length]

    return filename


class MetadataExtractor:
    """Extract and organize metadata from media files."""

    def __init__(self):
        self.audio_extensions = {
            ".mp3",
            ".flac",
            ".m4a",
            ".ogg",
            ".opus",
            ".wav",
            ".aac",
        }
        self.video_extensions = {".mp4", webn_ext, ".mkv", ".avi", ".mov", ".flv"}

    def extract(self, filepath: str, info: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Extract metadata from a media file and combine with info-dict if provided.
        Returns organized metadata dictionary.
        """
        metadata = {}

        # Start with info-dict metadata if available
        if info:
            metadata = self._extract_from_info_dict(info)

        # Extract from file if it exists
        if os.path.exists(filepath):
            file_metadata = self._extract_from_file(filepath)
            # Merge file metadata, prioritizing file metadata over info-dict
            metadata.update(file_metadata)

        # Add file information
        metadata.update(self._get_file_info(filepath))

        # Ensure we have basic fields with defaults
        metadata.setdefault("title", os.path.splitext(os.path.basename(filepath))[0])
        metadata.setdefault("uploader", "Unknown")
        metadata.setdefault("album", "Unknown")
        metadata.setdefault("year", datetime.now().year)
        metadata.setdefault("month", datetime.now().month)
        metadata.setdefault("day", datetime.now().day)

        # Sanitize metadata that will be used in filenames
        for key in ["title", "uploader", "album"]:
            if key in metadata:
                metadata[key] = sanitize_filename(str(metadata[key]))

        return metadata

    def _extract_from_info_dict(self, info: Dict) -> Dict[str, Any]:
        """Extract metadata from yt-dlp info dictionary."""
        metadata = {}

        # Basic fields
        metadata["title"] = info.get("title", "")
        metadata["uploader"] = info.get("uploader", info.get("channel", ""))
        metadata["description"] = info.get("description", "")

        # Date information
        upload_date = info.get("upload_date", "")
        if upload_date and len(upload_date) == 8:  # YYYYMMDD format
            metadata["year"] = int(upload_date[0:4])
            metadata["month"] = int(upload_date[4:6])
            metadata["day"] = int(upload_date[6:8])
            metadata["date"] = (
                f"{metadata['year']}-{metadata['month']:02d}-{metadata['day']:02d}"
            )

        # Album/playlist information
        metadata["album"] = info.get("album", "")
        if not metadata["album"] and info.get("playlist"):
            metadata["album"] = info["playlist"]

        # Track information
        metadata["track"] = info.get("track", "")
        metadata["track_number"] = info.get("track_number", 0)
        metadata["artist"] = info.get(
            "artist", info.get("creator", info.get("uploader", ""))
        )

        # Media information
        metadata["duration"] = info.get("duration", 0)
        metadata["format"] = info.get("format", "")
        metadata["format_id"] = info.get("format_id", "")
        metadata["ext"] = info.get("ext", "")
        metadata["width"] = info.get("width", 0)
        metadata["height"] = info.get("height", 0)
        metadata["fps"] = info.get("fps", 0)
        metadata["view_count"] = info.get("view_count", 0)

        # Content type detection (attempt to classify content type)
        if info.get("album") or info.get("track"):
            metadata["content_type"] = "audio"
        elif info.get("season_number") or info.get("episode_number"):
            metadata["content_type"] = "tv_show"
        elif info.get("is_podcast") or "podcast" in str(info.get("tags", "")).lower():
            metadata["content_type"] = "podcast"
        elif info.get("height", 0) > 0:
            metadata["content_type"] = "video"
        else:
            metadata["content_type"] = (
                "audio" if info.get("acodec") and not info.get("vcodec") else "video"
            )

        # Categories and tags
        metadata["category"] = info.get("category", "")
        metadata["categories"] = info.get("categories", [])
        metadata["tags"] = info.get("tags", [])

        return metadata

    def _extract_from_file(self, filepath: str) -> Dict[str, Any]:
        """
        Extract metadata from media file with optimized performance and format detection.

        This implementation uses:
        - Single-pass file analysis
        - Format detection with safe fallbacks
        - Memory-efficient processing
        - Detailed error reporting
        - Format-specific optimizations

        Args:
            filepath: Path to the media file

        Returns:
            Dictionary of extracted metadata
        """
        if not os.path.exists(filepath):
            logging.debug(f"File not found: {filepath}")
            return {}

        metadata = {}
        ext = os.path.splitext(filepath)[1].lower()

        # Performance optimization: Early return for unsupported formats
        if not ext or ext not in self.audio_extensions.union(self.video_extensions):
            return metadata

        try:
            # First attempt using generic mutagen detection - avoids redundant file reads
            audio_file = mutagen.File(filepath)

            if audio_file is None:
                logging.debug(f"Could not identify file format: {filepath}")
                return metadata

            # Extract common properties that exist across formats
            if hasattr(audio_file, "info"):
                if hasattr(audio_file.info, "length"):
                    metadata["duration"] = audio_file.info.length
                if hasattr(audio_file.info, "bitrate"):
                    metadata["bitrate"] = audio_file.info.bitrate
                if hasattr(audio_file.info, "sample_rate"):
                    metadata["sample_rate"] = audio_file.info.sample_rate
                if hasattr(audio_file.info, "channels"):
                    metadata["channels"] = audio_file.info.channels

            # Dispatch to format-specific extractors based on file type
            # This avoids reopening the file multiple times
            file_type = type(audio_file).__name__

            if file_type == "MP3" or ext == ".mp3":
                self._extract_mp3_tags(audio_file, metadata)
            elif file_type == "FLAC" or ext == FLAC_EXT:
                self._extract_flac_tags(audio_file, metadata)
            elif file_type in ("MP4", "M4A") or ext in (".mp4", ".m4a"):
                self._extract_mp4_tags(audio_file, metadata)
            elif file_type in ("OggVorbis", "OggOpus") or ext in (".ogg", opus_ext):
                self._extract_ogg_tags(audio_file, metadata)
            else:
                # Generic tag extraction for other formats
                self._extract_generic_tags(audio_file, metadata)

            # Set content type based on extension if not already determined
            if "content_type" not in metadata:
                if ext in self.audio_extensions:
                    metadata["content_type"] = "audio"
                elif ext in self.video_extensions:
                    metadata["content_type"] = "video"

            return metadata

        except mutagen.MutagenError as e:
            # Specific handling for mutagen errors
            logging.debug(f"Mutagen error for {filepath}: {str(e)}")
            return metadata
        except Exception as e:
            # Fallback for any other errors
            logging.debug(f"Error extracting metadata from {filepath}: {str(e)}")
            return metadata

    def _extract_generic_tags(self, audio_file: Any, metadata: Dict[str, Any]) -> None:
        """Extract generic tags from any audio file format."""
        try:
            if hasattr(audio_file, "tags") and audio_file.tags:
                # Extract common tag names with normalization
                for key_mapping in [
                    ("title", ["title", "TIT2", "\xa9nam"]),
                    ("artist", ["artist", "TPE1", "\xa9ART", "performer"]),
                    ("album", ["album", "TALB", "\xa9alb"]),
                    ("date", ["date", "TDRC", "\xa9day"]),
                    ("genre", ["genre", "TCON", "\xa9gen"]),
                    ("track", ["tracknumber", "TRCK", "trkn"]),
                ]:
                    target_key, source_keys = key_mapping
                    for source_key in source_keys:
                        if source_key in audio_file.tags:
                            try:
                                value = audio_file.tags[source_key]
                                # Handle different tag value types
                                if isinstance(value, list):
                                    metadata[target_key] = str(value[0])
                                else:
                                    metadata[target_key] = str(value)
                                break
                            except (IndexError, KeyError, ValueError):
                                continue
        except Exception as e:
            logging.debug(f"Error in generic tag extraction: {str(e)}")

    def _extract_mp3_tags(self, audio_file: Any, metadata: Dict[str, Any]) -> None:
        """Extract MP3-specific tags with optimized access patterns."""
        try:
            # Fast path: If it's an ID3 object, use direct attribute access
            if hasattr(audio_file, "tags") and audio_file.tags:
                tags = audio_file.tags

                # Map common ID3 frames to metadata using dictionary for performance
                id3_mapping = {
                    "TIT2": "title",
                    "TPE1": "artist",
                    "TALB": "album",
                    "TDRC": "date",
                    "TCON": "genre",
                    "TRCK": "track_number",
                    "TPOS": "disc_number",
                    "TCOM": "composer",
                    "TPUB": "publisher",
                    "TCOP": "copyright",
                }

                for frame_id, meta_key in id3_mapping.items():
                    if frame_id in tags:
                        try:
                            metadata[meta_key] = str(tags[frame_id])
                        except (ValueError, KeyError):
                            pass

                # Handle special formats like track numbers with total tracks
                if "track_number" in metadata and "/" in metadata["track_number"]:
                    try:
                        track, total = metadata["track_number"].split("/")
                        metadata["track_number"] = int(track.strip())
                        metadata["total_tracks"] = int(total.strip())
                    except (ValueError, IndexError):
                        pass

                # Set content type
                metadata["content_type"] = "audio"
        except Exception as e:
            logging.debug(f"Error extracting MP3 tags: {str(e)}")

    def _extract_flac_tags(self, audio_file: Any, metadata: Dict[str, Any]) -> None:
        """Extract FLAC-specific tags with optimized access."""
        try:
            if hasattr(audio_file, "tags"):
                # Map common Vorbis comments to metadata
                vorbis_keys = [
                    "title",
                    "artist",
                    "album",
                    "date",
                    "genre",
                    "tracknumber",
                    "discnumber",
                    "composer",
                    "albumartist",
                    "bpm",
                ]

                for key in vorbis_keys:
                    if key in audio_file:
                        metadata[key.replace("number", "_number")] = str(
                            audio_file[key][0]
                        )

                # Add FLAC-specific technical metadata
                if hasattr(audio_file, "info"):
                    if hasattr(audio_file.info, "bits_per_raw_sample"):
                        metadata["bits_per_raw_sample"] = (
                            audio_file.info.bits_per_sample
                        )

                # Set content type
                metadata["content_type"] = "audio"
        except Exception as e:
            logging.debug(f"Error extracting FLAC tags: {str(e)}")

    def _extract_mp4_tags(self, audio_file: Any, metadata: Dict[str, Any]) -> None:
        """Extract MP4-specific tags with optimized access."""
        try:
            # Map common MP4 atom keys to metadata
            mp4_mapping = {
                "\xa9nam": "title",
                "\xa9ART": "artist",
                "\xa9alb": "album",
                "\xa9day": "date",
                "\xa9gen": "genre",
                "trkn": "track_number",
                "disk": "disc_number",
                "\xa9wrt": "composer",
                "aART": "album_artist",
            }

            for atom, meta_key in mp4_mapping.items():
                if atom in audio_file:
                    if atom in ("trkn", "disk"):
                        # Handle tuple format for track/disc number
                        try:
                            value_tuple = audio_file[atom][0]
                            if len(value_tuple) > 0:
                                metadata[meta_key] = value_tuple[0]
                            if len(value_tuple) > 1 and value_tuple[1]:
                                metadata[f"total_{meta_key}s"] = value_tuple[1]
                        except (IndexError, ValueError):
                            pass
                    else:
                        metadata[meta_key] = str(audio_file[atom][0])

            # Set content type based on extension
            ext = (
                os.path.splitext(audio_file.filename)[1].lower()
                if hasattr(audio_file, "filename")
                else ""
            )
            metadata["content_type"] = "audio" if ext == ".m4a" else "video"
        except Exception as e:
            logging.debug(f"Error extracting MP4 tags: {str(e)}")

    def _extract_ogg_tags(self, audio_file: Any, metadata: Dict[str, Any]) -> None:
        """Extract Ogg Vorbis/Opus tags with optimized access."""
        try:
            # Map common Vorbis comments to metadata (similar to FLAC)
            vorbis_keys = [
                "title",
                "artist",
                "album",
                "date",
                "genre",
                "tracknumber",
                "discnumber",
                "composer",
                "albumartist",
                "bpm",
            ]

            for key in vorbis_keys:
                if key in audio_file:
                    metadata[key.replace("number", "_number")] = str(audio_file[key][0])

            # Set content type
            metadata["content_type"] = "audio"
        except Exception as e:
            logging.debug(f"Error extracting Ogg tags: {str(e)}")

    def _get_file_info(self, filepath: str) -> Dict[str, Any]:
        """Get file information."""
        metadata = {}

        try:
            # Get file stats
            if os.path.exists(filepath):
                stat = os.stat(filepath)
                metadata["filesize"] = stat.st_size
                metadata["modified_time"] = datetime.fromtimestamp(stat.st_mtime)
                metadata["created_time"] = datetime.fromtimestamp(stat.st_ctime)

            # Determine content type based on extension
            ext = os.path.splitext(filepath)[1].lower()
            if ext in self.audio_extensions:
                metadata.setdefault("content_type", "audio")
            elif ext in self.video_extensions:
                metadata.setdefault("content_type", "video")

        except Exception as e:
            logging.debug(f"Error getting file info: {str(e)}")

        return metadata


class FileOrganizer:
    """Organize files into directories based on metadata templates."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.templates = config.get(
            "organization_templates", DEFAULT_ORGANIZATION_TEMPLATES.copy()
        )
        self.metadata_extractor = MetadataExtractor()

    def organize_file(
        self, filepath: str, info: Optional[Dict] = None
    ) -> Optional[str]:
        """
        Organize a file based on its metadata.

        Args:
            filepath: Path to the file to organize
            info: Optional yt-dlp info dictionary

        Returns:
            New file path if successful, None otherwise
        """
        if not os.path.exists(filepath):
            logging.error(f"Cannot organize: File not found: {filepath}")
            return None

        try:
            # Extract metadata
            metadata = self.metadata_extractor.extract(filepath, info)

            # Determine the appropriate base directory and template
            is_audio = metadata.get("content_type") == "audio"
            base_dir = (
                self.config["audio_output"] if is_audio else self.config["video_output"]
            )

            # Select appropriate template
            content_type = metadata.get("content_type", "video")
            if content_type == "podcast" and "podcast" in self.templates:
                template = self.templates["podcast"]
            elif content_type == "audiobook" and "audiobook" in self.templates:
                template = self.templates["audiobook"]
            else:
                template = (
                    self.templates["audio"] if is_audio else self.templates["video"]
                )

            # Format template
            try:
                # Create dictionary with lowercase keys for template formatting
                format_dict = {}
                for key, value in metadata.items():
                    format_dict[key.lower()] = value

                # Use format_map to allow partial template application
                relative_path = template.format_map(
                    # This defaultdict-like approach handles missing keys
                    type(
                        "DefaultDict",
                        (dict,),
                        {"__missing__": lambda self, key: "Unknown"},
                    )(format_dict)
                )
            except Exception as e:
                logging.error(f"Template formatting error: {str(e)}")
                relative_path = os.path.join(
                    metadata.get("uploader", "Unknown"),
                    str(metadata.get("year", "Unknown")),
                    metadata.get("title", os.path.basename(filepath)),
                )

            # Create the full path
            filename = os.path.basename(filepath)
            new_dir = os.path.join(base_dir, relative_path)
            new_filepath = os.path.join(new_dir, filename)

            # Create directory if it doesn't exist
            os.makedirs(new_dir, exist_ok=True)

            # Check if target file already exists
            if os.path.exists(new_filepath) and os.path.samefile(
                filepath, new_filepath
            ):
                # File is already in the right place
                return filepath

            if os.path.exists(new_filepath):
                # File exists but is different - create a unique name
                base, ext = os.path.splitext(filename)
                count = 1
                while os.path.exists(new_filepath):
                    new_filename = f"{base}_{count}{ext}"
                    new_filepath = os.path.join(new_dir, new_filename)
                    count += 1

            # Move the file
            shutil.move(filepath, new_filepath)
            logging.info(f"Organized file: {filepath} -> {new_filepath}")
            return new_filepath

        except Exception as e:
            logging.error(f"Error organizing file {filepath}: {str(e)}")
            return None


class DownloadManager:
    """Enhanced download manager with improved performance and resource management"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config

        # Initialize the download cache
        self.download_cache = DownloadCache()

        # FFmpeg path is already validated during initialization_config
        # No need for redundant validation here

        self.setup_logging()
        self.verify_paths()
        self.last_percentage = 0

        # New: Initialize file organizer for metadata-based organization
        self.file_organizer = (
            FileOrganizer(config) if config.get("organize", False) else None
        )
        # Initialize metadata extractor
        self.metadata_extractor = MetadataExtractor()

        # Convert to tuple for better performance with lru_cache
        self.valid_commands = (
            "download",
            "dl",
            "audio",
            "video",
            "help",
            "?",
            "exit",
            "quit",
            "q",
            "flac",
            "mp3",
            "wav",
            "m4a",
            "opus",
            "list",
            "sites",
            "clear",
            "cls",
        )

        # Cached format descriptions for performance
        self._format_descriptions = {
            "opus": "High quality Opus (192kbps)",
            "mp3": "High quality MP3 (320kbps)",
            "flac": "Lossless audio (best quality)",
            "wav": "Uncompressed audio",
            "m4a": "AAC audio (good quality)",
        }

        # Track active downloads for better resource management
        self._active_downloads = set()
        self._download_lock = threading.RLock()
        self.current_download_url = None  # New attribute for current download URL
        self.download_start_time = None  # New attribute to mark download start
        self.session_manager = SessionManager()  # Initialize session manager
        # Store info_dict for post-processing
        self._current_info_dict = {}

    def setup_logging(self):
        """Set up logging with console and file handlers"""
        verbose = self.config.get("verbose", False)
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)  # Capture all levels

        # Remove existing handlers
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        # Console handler with color
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
        console_formatter = ColoramaFormatter(
            "%(asctime)s - %(levelname)s - %(message)s"
        )
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)

        # File handler
        try:
            file_handler = logging.FileHandler(LOG_FILE)
            file_handler.setLevel(logging.DEBUG)
            file_formatter = logging.Formatter(
                "%(asctime)s - %(levelname)s - %(message)s"
            )
            file_handler.setFormatter(file_formatter)
            root_logger.addHandler(file_handler)
        except Exception as e:
            logging.error("Failed to setup file logger: %s", e)

    def verify_paths(self) -> None:
        """
        Verify and create output directories. FFmpeg validation is handled during startup.

        This method only checks for output directories and creates them if needed,
        with appropriate fallbacks if the requested directories cannot be created.
        """

        # Step 1: Verify and create output directories
        dir_map = {
            "video_output": ("Videos", "video files"),
            "audio_output": ("Music", "audio files"),
        }

        for key, (folder_name, content_type) in dir_map.items():
            output_dir = self.config[key]
            logging.debug(
                f"Verifying output directory for {content_type}: {output_dir}"
            )

            # Create directory if it doesn't exist
            if not os.path.exists(output_dir):
                try:
                    os.makedirs(output_dir, exist_ok=True)
                    logging.info(
                        f"Created output directory for {content_type}: {output_dir}"
                    )

                    # Verify write permissions with a canary file
                    self._verify_directory_writable(output_dir, key)

                except OSError as e:
                    # Try user home directory as first fallback
                    fallback_dir = str(Path.home() / folder_name)
                    logging.warning(f"Failed to create {key} at {output_dir}: {str(e)}")
                    print(
                        f"{Fore.YELLOW}Warning: Could not create {key} at {output_dir}: {str(e)}{Style.RESET_ALL}"
                    )
                    print(
                        f"{Fore.CYAN}Trying fallback location: {fallback_dir}{Style.RESET_ALL}"
                    )

                    try:
                        os.makedirs(fallback_dir, exist_ok=True)
                        self._verify_directory_writable(fallback_dir, key)
                        self.config[key] = fallback_dir
                        logging.info(
                            f"Using fallback directory for {content_type}: {fallback_dir}"
                        )

                    except OSError as e2:
                        # Try temp directory as last resort
                        temp_dir = os.path.join(
                            tempfile.gettempdir(), f"snatch_{folder_name.lower()}"
                        )
                        logging.warning(
                            f"Failed to use fallback directory {fallback_dir}: {str(e2)}"
                        )
                        print(
                            f"{Fore.YELLOW}Warning: Could not use fallback location. Trying temporary directory: {temp_dir}{Style.RESET_ALL}"
                        )

                        try:
                            os.makedirs(temp_dir, exist_ok=True)
                            self._verify_directory_writable(temp_dir, key)
                            self.config[key] = temp_dir
                            logging.info(
                                f"Using temporary directory for {content_type}: {temp_dir}"
                            )
                            print(
                                f"{Fore.YELLOW}Note: Using temporary directory {temp_dir} for {content_type}. Files may be removed on system restart.{Style.RESET_ALL}"
                            )

                        except Exception as e3:
                            logging.error(
                                f"All directory options failed for {key}: {str(e3)}"
                            )
                            raise RuntimeError(
                                f"Cannot create any output directory for {content_type}. Please specify a valid directory manually."
                            )
            else:
                # Directory exists, check if it's writable
                self._verify_directory_writable(output_dir, key)

            # Check available disk space (warn if less than 1GB available)
            try:
                disk_usage = shutil.disk_usage(self.config[key])
                free_space_gb = disk_usage.free / (1024 * 1024 * 1024)
                if free_space_gb < 1:
                    print(
                        f"{Fore.YELLOW}Warning: Less than 1GB of free space ({free_space_gb:.2f}GB) on drive containing {self.config[key]}{Style.RESET_ALL}"
                    )
                    logging.warning(
                        f"Low disk space ({free_space_gb:.2f}GB) for {key} at {self.config[key]}"
                    )
            except Exception as e:
                logging.warning(f"Failed to check disk space for {key}: {str(e)}")

    def _verify_directory_writable(self, directory: str, purpose: str) -> bool:
        """
        Verify a directory is writable by creating and removing a test file.

        Args:
            directory: Directory to check
            purpose: Description for error messages

        Returns:
            True if writable

        Raises:
            PermissionError: If directory is not writable
        """
        test_file = os.path.join(directory, f".snatch_write_test_{int(time.time())}")
        try:
            # Attempt to write a small file
            with open(test_file, "w") as f:
                f.write("write test")
            # Clean up
            os.remove(test_file)
            return True
        except OSError as e:
            logging.error(
                f"Directory {directory} is not writable for {purpose}: {str(e)}"
            )
            raise PermissionError(
                f"Cannot write to {directory} (needed for {purpose}): {str(e)}"
            )

    def progress_hook(self, d: Dict[str, Any]) -> None:
        """
        Enhanced download progress hook with optimized performance, better error handling,
        and smarter file management.

        This method processes progress updates from yt-dlp during downloads and handles
        various status transitions with optimized resource usage.
        """
        try:
            # Fast path: Skip processing for temporary fragment files
            filename = d.get("filename", "")
            if filename and any(
                marker in os.path.basename(filename)
                for marker in (".f", part_ext, "tmp")
            ):
                return

            status = d["status"]

            # Main dispatch based on download status
            if status == "downloading":
                self._handle_downloading_status(d)
            elif status == "finished":
                self._handle_finished_status(d)
            elif status == "error":
                self._handle_error_status(d)

        except Exception as e:
            # Global error handler to prevent hook failures from crashing the application
            logging.error(f"Progress hook error: {str(e)}")
            # Try to clean up UI if possible
            self._ensure_progress_cleanup()

    def _handle_downloading_status(self, d: Dict[str, Any]) -> None:
        """Process 'downloading' status with optimized progress tracking."""
        # Get download size information
        total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
        downloaded = d.get("downloaded_bytes", 0)

        # Early return if no download information available
        if downloaded <= 0:
            return

        # Calculate percentage with bounds checking
        percentage = min(100, int((downloaded / total) * 100) if total > 0 else 0)

        # Use appropriate progress display based on configuration
        if self.config.get("detailed_progress", False):
            self._update_detailed_progress(downloaded, total, percentage)
        else:
            self._update_simple_progress(downloaded, total, percentage)

        # Update session information for resume support
        if percentage > 0 and self.current_download_url:
            self.session_manager.update_session(self.current_download_url, percentage)

        # Periodically check for memory pressure during large downloads
        if total > 100 * 1024 * 1024 and downloaded % (10 * 1024 * 1024) < 1024 * 1024:
            self._check_memory_pressure()

    def _handle_finished_status(self, d: Dict[str, Any]) -> None:
        """Process 'finished' status with improved file handling."""
        # Close progress displays
        self._ensure_progress_cleanup()

        # Reset progress state
        self.last_percentage = 0

        # Only clear download session if this is a complete file, not a fragment
        filepath = d.get("filename", "")
        is_fragment = filepath and any(
            marker in os.path.basename(filepath) for marker in (".f", part_ext, "tmp")
        )

        if not is_fragment and self.current_download_url:
            self.download_start_time = None
            self.session_manager.remove_session(self.current_download_url)

        # Don't show completion message for fragment files
        if not is_fragment:
            logging.info("Download complete: %s", filepath)
            print(f"{Fore.GREEN}✓ Download Complete!{Style.RESET_ALL}")

            # Process downloaded file - but skip for audio files and formats that need post-processing
            if filepath and os.path.exists(filepath):
                ext = os.path.splitext(filepath)[1].lower()

                # Skip filename cleanup for audio files to ensure post-processing works correctly
                if ext in AUDIO_EXTENSIONS or ext == webn_ext:
                    logging.debug(
                        f"Skipping filename cleanup for audio file: {filepath}"
                    )
                else:
                    self._cleanup_filename(filepath)

        # Clear any cached data no longer needed
        if not is_fragment:
            self._current_info_dict = {
                k: v for k, v in self._current_info_dict.items() if os.path.exists(k)
            }

    def _handle_error_status(self, d: Dict[str, Any]) -> None:
        """Process 'error' status with graceful cleanup."""
        # Clean up UI elements
        self._ensure_progress_cleanup()

        # Reset state
        self.last_percentage = 0
        self.download_start_time = None

        # Log detailed error information if available
        error_msg = d.get("error", "Unknown error")
        logging.error("Download error: %s", error_msg)

    def _update_detailed_progress(
        self, downloaded: int, total: int, percentage: int
    ) -> None:
        """Update the detailed progress display with optimized rendering."""
        # Create progress display if needed
        if not hasattr(self, "detailed_pbar"):
            self.detailed_pbar = DetailedProgressDisplay(
                total_size=total, title="Downloading", detailed=True, show_eta=True
            )
            self.detailed_pbar.start()
            if self.download_start_time is None:
                self.download_start_time = time.time()

        # Update the display
        self.detailed_pbar.downloaded = downloaded
        self.detailed_pbar.total_size = total

        # Calculate speed metrics only when needed (every ~250ms)
        now = time.time()
        if hasattr(self, "last_speed_update") and now - self.last_speed_update < 0.25:
            return

        # Update speed calculations
        if self.download_start_time:
            elapsed = now - self.download_start_time
            if elapsed > 0:
                speed = downloaded / elapsed
                self.detailed_pbar.current_speed = speed
                self.detailed_pbar.avg_speed = speed  # Simple average
                self.detailed_pbar.peak_speed = max(
                    speed, getattr(self.detailed_pbar, "peak_speed", 0)
                )
                self.detailed_pbar.eta_seconds = (
                    (total - downloaded) / speed if speed > 0 else 0
                )

        # Update the display
        self.detailed_pbar.display()
        self.last_speed_update = now

    def _update_simple_progress(
        self, downloaded: int, total: int, percentage: int
    ) -> None:
        """Update the simple progress bar with optimized updates."""
        # Create progress bar if needed
        if not hasattr(self, "pbar"):
            self.pbar = ColorProgressBar(100, desc="Downloading")
            self.last_percentage = 0
            if self.download_start_time is None:
                self.download_start_time = time.time()

        # Only update if percentage changed (optimization)
        if percentage <= self.last_percentage:
            return

        # Calculate speed only when updating display
        speed = calculate_speed(downloaded, self.download_start_time or time.time())
        speed_str = format_speed(speed)

        # Update progress bar with minimal UI operations
        self.pbar.set_description("Downloading")
        self.pbar.set_speed(speed_str)
        self.pbar.update(percentage - self.last_percentage)
        self.last_percentage = percentage

    def _ensure_progress_cleanup(self) -> None:
        """Safely clean up progress UI elements."""
        with suppress(Exception):  # Using imported suppress directly
            if hasattr(self, "detailed_pbar"):
                self.detailed_pbar.finish(success=True)
                delattr(self, "detailed_pbar")

        with suppress(Exception):  # Using imported suppress directly
            if hasattr(self, "pbar"):
                self.pbar.close()
                delattr(self, "pbar")

    def _cleanup_filename(self, filepath: str) -> str:
        """Clean up filename with proper error handling and return the new path."""
        if not os.path.exists(filepath):
            return filepath

        try:
            clean_filepath = clean_filename(filepath)
            if clean_filepath != filepath and not os.path.exists(clean_filepath):
                # Safely rename with proper checks
                os.rename(filepath, clean_filepath)
                print(f"{Fore.GREEN}✓ Cleaned up filename: {Style.RESET_ALL}")
                print(
                    f"  {Fore.CYAN}→ {os.path.basename(clean_filepath)}{Style.RESET_ALL}"
                )
                return clean_filepath
        except OSError as e:
            logging.error(f"Error renaming file {filepath}: {str(e)}")

        return filepath

    # FLAC verification methods with performance improvements
    def _verify_flac_properties(self, audio):
        """Verify FLAC format-specific properties with optimized checks"""
        bit_depth = getattr(audio.info, "bits_per_raw_sample", 0)
        if bit_depth not in [16, 24, 32]:
            logging.error(f"Invalid bit depth: {bit_depth}")
            return False

        if audio.info.channels not in [1, 2]:
            logging.error(f"Invalid channel count: {audio.info.channels}")
            return False

        if audio.info.sample_rate not in [44100, 48000, 88200, 96000, 192000]:
            logging.error(f"Invalid sample rate: {audio.info.sample_rate}")
            return False

        return True

    def _verify_flac_quality(self, audio) -> bool:
        """Verify FLAC quality and metadata with early returns for performance"""
        # Additional quality checks
        minimum_bitrate = 400000  # 400kbps minimum for FLAC
        if (
            audio.info.bits_per_sample * audio.info.sample_rate * audio.info.channels
            < minimum_bitrate
        ):
            logging.error("FLAC quality too low")
            return False

        # Check STREAMINFO block
        if not audio.info.total_samples or not audio.info.length:
            logging.error("Invalid FLAC stream info")
            return False

        return True

    def verify_audio_file(self, filepath: str) -> bool:
        """Enhanced audio file verification with faster checks and better error handling"""
        if not os.path.exists(filepath):
            logging.error(f"File not found: {filepath}")
            return False

        # Fast check - skip verification for non-FLAC files
        if not filepath.lower().endswith(FLAC_EXT):
            return True

        try:
            # Quick header check first (much faster)
            with open(filepath, "rb") as f:
                header = f.read(4)
                if header != b"fLaC":
                    logging.error("Invalid FLAC signature")
                    return False

            # Load FLAC file once and reuse for all checks
            audio = FLAC(filepath)

            # Basic verification
            if not audio or not audio.info:
                logging.error("Invalid FLAC file (no audio info)")
                return False

            # Complete verification using existing methods
            if not self._verify_flac_properties(audio) or not self._verify_flac_quality(
                audio
            ):
                return False
            return True
        except Exception as e:
            logging.error(f"FLAC verification error: {str(e)}")
            return False

    def _prepare_ffmpeg_command(
        self, input_file: str, output_file: str, channels: int = 2
    ) -> list:
        """Prepare FFmpeg command with improved option handling"""
        return [
            os.path.join(self.config["ffmpeg_location"], "ffmpeg"),
            "-i",
            input_file,
            "-c:a",
            "flac",
            "-compression_level",
            "12",
            "-sample_fmt",
            "s32",
            "-ar",
            "48000",
            "-ac",
            str(channels),  # Dynamic channel configuration
            "-progress",
            "pipe:1",
            output_file,
        ]

    def _monitor_conversion_progress(self, process, duration, pbar):
        """
        Monitor FFmpeg conversion progress and update the progress bar.

        This function reads process.stdout line by line until the process completes.
        It parses lines containing 'out_time_ms=' to calculate the conversion progress
        and updates the progress bar accordingly. Detailed debug logging is added to trace
        any parsing issues.

        Args:
            process: The subprocess running FFmpeg.
            duration: Total duration of the media (in seconds).
            pbar: The progress bar to update.

        Returns:
            The return code of the FFmpeg process.
        """
        last_progress = 0
        for line in iter(process.stdout.readline, ""):
            if not line:
                continue
            if "out_time_ms=" in line:
                try:
                    # Example line: "out_time_ms=12345678"
                    # Split only once to get the value part
                    _, value = line.split("=", 1)
                    time_ms = int(value.strip())
                    # Calculate progress percentage based on duration (converted to milliseconds)
                    progress = min(int((time_ms / 1000) / duration * 100), 100)
                    if progress > last_progress:
                        # Update progress bar with the incremental difference
                        pbar.update(progress - last_progress)
                        last_progress = progress
                except Exception as e:
                    logging.debug(
                        f"Error parsing conversion progress line: '{line.strip()}' - {e}"
                    )
        # Ensure process completion and return its exit status
        return process.wait()

    def _copy_metadata(self, original_audio, output_file):
        """Copy metadata with error handling and validation"""
        if original_audio and original_audio.tags:
            flac_audio = FLAC(output_file)
            for key, value in original_audio.tags.items():
                flac_audio[key] = value
            flac_audio.save()

    def _verify_conversion(self, input_file, output_file):
        """Verify conversion with more comprehensive checks"""
        orig_info = mutagen.File(input_file).info
        conv_info = mutagen.File(output_file).info

        if abs(orig_info.length - conv_info.length) > 0.1:  # Allow 100ms difference
            raise ValueError("Duration mismatch between input and output files")

    def convert_to_flac(self, input_file: str, output_file: str) -> bool:
        """Convert audio to FLAC with improved error handling and performance"""
        try:
            # First verify the input file
            if not self.verify_audio_file(input_file):
                raise ValueError("Input file verification failed")

            # Get original metadata and info
            original_audio = mutagen.File(input_file)

            # Create progress bar
            pbar = ColorProgressBar(100, desc="Converting to FLAC")

            # Execute conversion with progress monitoring
            cmd = self._prepare_ffmpeg_command(input_file, output_file)
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )

            # Monitor conversion progress
            returncode = self._monitor_conversion_progress(
                process, original_audio.info.length, pbar
            )

            # Close progress bar
            pbar.close()

            # Check conversion result
            if returncode != 0:
                raise RuntimeError(f"FFmpeg conversion failed: {process.stderr.read()}")

            # Verify output file and handle metadata
            if not self.verify_audio_file(output_file):
                raise ValueError("Output file verification failed")

            self._copy_metadata(original_audio, output_file)
            self._verify_conversion(input_file, output_file)

            return True

        except Exception as e:
            print(f"\n{Fore.RED}✗ Conversion Failed: {str(e)}{Style.RESET_ALL}")
            if os.path.exists(output_file):
                os.remove(output_file)
            return False

    def get_download_options(
        self,
        url: str,
        audio_only: bool,
        resolution: Optional[str] = None,
        format_id: Optional[str] = None,
        filename: Optional[str] = None,
        audio_format: str = "opus",
        no_retry: bool = False,
        throttle: Optional[str] = None,
        use_aria2c: bool = False,
        audio_channels: int = 2,
        *,
        test_all_formats: bool = False,
    ) -> Dict[str, Any]:
        """
        Get download options with optimized format selection and minimal temporary file creation.

        Args:
            url: URL to download from
            audio_only: Whether to download audio only
            resolution: Target video resolution
            format_id: Specific format ID to use
            filename: Custom output filename
            audio_format: Target audio format for conversion
            no_retry: Disable retry on error
            throttle: Download speed limit
            use_aria2c: Use aria2c for downloading
            audio_channels: Number of audio channels
            test_all_formats: Whether to test all available formats (slow)

        Returns:
            Dictionary of download options for yt-dlp
        """
        # Determine output path with fallback
        try:
            output_path = (
                self.config["audio_output"]
                if audio_only
                else self.config["video_output"]
            )
            if not os.path.exists(output_path):
                os.makedirs(output_path, exist_ok=True)
        except OSError:
            output_path = str(Path.home() / ("Music" if audio_only else "Videos"))
            os.makedirs(output_path, exist_ok=True)

        # Process filename if provided
        output_template = "%(title)s.%(ext)s"  # Default template

        if filename:
            # Remove any existing extension from the filenam
            filename = os.path.splitext(filename)[0]
            output_template = f"{filename}.%(ext)s"

            # Sanitize the filename (remove invalid characters)
            filename = re.sub(r'[\\/*?:"<>|]', "_", filename)
        else:
            # Set output template with the sanitized filename without extension
            # yt-dlp will add the appropriate extension based on the final format
            output_template = sanitize_filename("%(title)s.%(ext)s")

        # Adaptive format selection: if video download and no resolution/format_id provided
        if not audio_only and resolution is None and not format_id:
            speed = self.measure_network_speed()
            if speed < 1.0:
                resolution = "480"
            elif speed < 3.0:
                resolution = "720"
            else:
                resolution = "1080"

        options = {
            "outtmpl": os.path.join(output_path, output_template),
            "restrictfilenames": True,  # Add this to ensure ytdlp also sanitizes filenames
            "ffmpeg_location": self.config["ffmpeg_location"],
            "progress_hooks": [self.progress_hook],
            "ignoreerrors": True,
            "continue": True,
            "postprocessor_hooks": [self.post_process_hook],
            "concurrent_fragment_downloads": min(
                16, os.cpu_count() or 4
            ),  # Reduced to prevent memory issues + new Increased from 4 to utilize more cores
            "no_url_cleanup": True,
            "clean_infojson": False,
            "prefer_insecure": True,
            "fragment_retries": 3,
            "socket_timeout": 30,  # Increased from 15 to allow more time for large data transfers
            "http_chunk_size": 10485760,
            "merge_output_format": "mp4",  # Use MP4 as default output format for better compatibility
            "keepvideo": False,
            "extractor_retries": 3,  # Retry info extraction
            "file_access_retries": 3,  # Retry on file access issues
            "skip_unavailable_fragments": True,  # Skip unavailable fragments rather than failing
            "force_generic_extractor": False,  # Fallback to generic extractor if specific one fails
            "retry_sleep_functions": {
                "http": lambda attempt: 5 * (2 ** (attempt - 1))
            },  # Exponential backoff
            "network_retries": 3,  # Retry on network errors
            "allow_unplayable_formats": False,  # Avoid formats that might cause merge issues
            "check_formats": False,  # Don't test all formats unless explicitly requested
            "quiet": True,  # Suppress verbose output for speed
            "no_warnings": False,  # Keep important warnings
            "postprocessor_args": [
                "-c:v",
                "copy",
                "-c:a",
                "copy",
                "-movflags",
                "+faststart",
                "-max_muxing_queue_size",
                "9999",
            ],  # Faster processing
        }
        # Only test all formats if explicitly requested
        if test_all_formats:
            options["check_formats"] = True
            logging.info("Testing all available formats (may be slow)")
        # For faster downloads with aria2c
        if use_aria2c:
            # For faster downloads
            if use_aria2c and self._check_aria2c_available():
                options["external_downloader"] = "aria2c"
            options["external_downloader_args"] = [
                "--min-split-size=1M",
                "--max-connection-per-server=32",  # Significantly increased connections
                "--max-concurrent-downloads=16",  # More concurrent downloads
                "--split=16",  # Split downloads into more parts
                "--file-allocation=none",  # Skip file allocation for speed
                "--optimize-concurrent-downloads=true",  # Auto-optimize concurrency
                "--auto-file-renaming=false",  # Don't rename files
                "--allow-overwrite=true",  # Allow overwriting files
                "--disable-ipv6",  # Disable IPv6 for faster connections
            ]
            logging.info("Using aria2c with optimized settings for maximum speed")
        else:
            # If aria2c not available, optimize native downloader
            options["concurrent_fragment_downloads"] = min(24, os.cpu_count() or 4)
            options["http_chunk_size"] = 20971520  # 20MB chunks for faster downloads

        # Handle no_retry option
        if no_retry:
            options["retries"] = 0
            options["fragment_retries"] = 0
        else:
            options["retries"] = 3
            options["retry_sleep"] = lambda n: 2 * n  # Linear growth: 2s, 4s, 6s
            options["fragment_retries"] = 3  # Add explicit fragment retry limit

        # Handle throttle option
        if throttle:
            # Parse the throttle rate (e.g. "500K", "1.5M", "2G")
            rate = self._parse_throttle_rate(throttle)
            if rate > 0:
                options["throttled_rate"] = rate
                logging.info(f"Download speed limited to {throttle}/s")

        # Use aria2c as external downloader if requested
        if use_aria2c:
            # Check if aria2c is available
            if self._check_aria2c_available():
                options["external_downloader"] = "aria2c"
                options["external_downloader_args"] = [
                    "--min-split-size=1M",
                    "--max-connection-per-server=32",  # Increased from 16
                    "--max-concurrent-downloads=32",  # Increased from 16
                    "--split=32",  # Increased from 16
                    "--file-allocation=none",
                    "--optimize-concurrent-downloads=true",
                    "--auto-file-renaming=false",
                    "--allow-overwrite=true",
                    "--disable-ipv6",
                    "--timeout=10",  # Added timeout option
                    "--connect-timeout=10",  # Added connect timeout
                    "--http-no-cache=true",  # Added to bypass cache
                    "--max-tries=3",  # Limit retries for speed
                    "--retry-wait=2",  # Shorter retry wait time
                ]
                logging.info("Using aria2c with optimized settings for maximum speed")
            else:
                options["concurrent_fragment_downloads"] = min(32, os.cpu_count() or 4)
                options["http_chunk_size"] = (
                    20971520  # 20MB chunks for faster downloads
                )
                logging.warning("aria2c not found, falling back to default downloader")

        # Handle format_id explicitly if provided
        if format_id:
            options["format"] = format_id
        elif audio_only:
            options["format"] = bestaudio_ext
            options["extract_audio"] = True
            if audio_format == "flac":
                # Use a temporary .wav file as intermediate
                # temp_format = '%(title)s.temp.wav'
                # Build FFmpeg executable path
                ffmpeg_bin = os.path.join(self.config["ffmpeg_location"], "ffmpeg")
                if audio_channels == 8:  # 7.1 surround
                    # Optimized 7.1 surround settings
                    exec_cmd = (
                        f'"{ffmpeg_bin}" -i "%(filepath)s" '
                        f"-c:a flac -compression_level 8 -sample_fmt s32 "
                        f"-ar 96000 -ac 8 -bits_per_raw_sample 24 -vn "
                        # Use a proper channel mapping filter that doesn't rely on FL/FR input names
                        f'-af "aformat=channel_layouts=stereo[stereo]; '
                        # Create a proper 7.1 upmix from stereo using pan filter
                        f"[stereo]pan=7.1|FL=c0|FR=c1|FC=0.5*c0+0.5*c1|LFE=0.5*c0+0.5*c1|"
                        f"BL=0.7*c0|BR=0.7*c1|SL=0.5*c0|SR=0.5*c1,"
                        f"loudnorm=I=-16:TP=-1.5:LRA=11:measured_I=-27:measured_TP=-4:measured_LRA=15:linear=true:dual_mono=false,"
                        f'aresample=resampler=soxr:precision=32:dither_method=triangular_hp:filter_size=256" '
                        f'-metadata encoded_by="Snatch" '
                        f'-metadata SURROUND="7.1" '
                        f'-metadata CHANNELS="8" '
                        f'-metadata BITDEPTH="24" '
                        f'-metadata SAMPLERATE="96000" '
                        f'"%(filepath)s.flac" && powershell -Command "Remove-Item -LiteralPath \\"%(filepath)s\\" -Force"'
                    )
                else:  # Standard stereo
                    exec_cmd = (
                        f'"{ffmpeg_bin}" -i "%(filepath)s" '
                        f"-c:a flac -compression_level 8 -sample_fmt s32 "
                        f"-ar 48000 -ac {audio_channels} -bits_per_raw_sample 24 -vn "
                        f'-af "loudnorm=I=-14:TP=-2:LRA=7,aresample=resampler=soxr:precision=24:dither_method=triangular" '
                        f'-metadata encoded_by="Snatch" '
                        f'"%(filepath)s.flac" && powershell -Command "Remove-Item -LiteralPath \\"%(filepath)s\\" -Force"'
                    )
                # *** IMPORTANT: Add nopostoverwrites option to prevent premature file removal ***
                options["postprocessors"] = [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "wav",
                        "preferredquality": "0",
                        "nopostoverwrites": True,  # Prevents source file deletion before processing
                    },
                    {
                        "key": "FFmpegMetadata",
                        "add_metadata": True,
                    },
                    {
                        "key": "ExecAfterDownload",
                        "exec_cmd": exec_cmd,
                    },
                ]
                options["postprocessor_args"] = [
                    "-acodec",
                    "pcm_s32le",
                    "-ar",
                    "96000",
                    "-bits_per_raw_sample",
                    "32",
                ]
            else:
                # For non-FLAC formats such as opus, wav, or m4a
                # Set appropriate quality settings based on format
                # Optimized format strings for other audio formats
                # Use format selectors that prefer higher quality sources
                # but don't require testing all formats
                options["format"] = bestaudio_ext
                options["extract_audio"] = True

                if audio_format == "opus":
                    preferredquality = (
                        "192"  # High quality for opus (128-256 is usually excellent)
                    )
                elif audio_format == "mp3":
                    preferredquality = "320"  # Highest for mp3
                else:
                    preferredquality = "0"  # Lossless for other formats

                options["postprocessors"] = [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": audio_format,
                        "preferredquality": preferredquality,
                    },
                    {
                        "key": "FFmpegMetadata",
                        "add_metadata": True,
                    },
                ]
        else:
            # Video downloads: optimized format selection without testing
            if resolution:
                # Use optimized format string that avoids testing all formats
                # but still gets the desired resolution
                format_str = f"bestvideo[height<={resolution}]+bestaudio/best[height<={resolution}]/best"
            else:
                format_str = (
                    "bestvideo[ext=mp4]+bestaudio[ext=m4a]/"
                    "bestvideo[ext=webm]+bestaudio[ext=webm]/"
                    "bestvideo+bestaudio/"
                    "best"
                )
                options["format"] = format_str
                options["merge_output_format"] = (
                    "mp4"  # Use MP4 as default output format for better compatibility
                )
        return options

    def _get_optimal_format_ids(
        self,
        url: str,
        info_dict: Dict,
        audio_only: bool = False,
        resolution: Optional[str] = None,
    ) -> str:
        """
        Get optimal format IDs for the given URL without testing all formats.

        Args:
            url: The URL to download
            info_dict: The media info dictionary from yt-dlp
            audio_only: Whether to download audio only
            resolution: Target video resolution

        Returns:
            Format ID string for yt-dlp
        """
        # If no formats available, return default format string
        if "formats" not in info_dict or not info_dict["formats"]:
            return "bestvideo+bestaudio/best" if not audio_only else bestaudio_ext

        formats = info_dict["formats"]

        # For audio-only downloads
        if audio_only:
            # Extract audio formats with quality metrics
            audio_formats = []
            for fmt in formats:
                # Check if format is audio-only or has audio
                if fmt.get("acodec") != "none" and (
                    fmt.get("vcodec") == "none" or audio_only
                ):
                    # Calculate a quality score based on bitrate and other factors
                    score = 0
                    if fmt.get("abr"):  # Audio bitrate
                        score += fmt.get("abr", 0) * 10
                    if fmt.get("asr"):  # Audio sample rate
                        score += fmt.get("asr", 0) / 1000

                    # Preferred format bonuses
                    if fmt.get("ext") in ["m4a", "aac"]:
                        score += 500  # Prefer AAC formats
                    elif fmt.get("ext") in ["opus"]:
                        score += 400  # Good quality-size trade-off
                    elif fmt.get("ext") in ["vorbis", "ogg"]:
                        score += 300
                    elif fmt.get("ext") in ["mp3"]:
                        score += 200

                    audio_formats.append((fmt, score))

            # Sort by score and take the best
            if audio_formats:
                audio_formats.sort(key=lambda x: x[1], reverse=True)
                best_audio = audio_formats[0][0]
                return f"{best_audio['format_id']}/bestaudio/best"

            # Fallback to default audio selector
            return bestaudio_ext

        # For video downloads with resolution constraint
        if resolution:
            resolution_int = int(resolution)

            # Find best video format that meets resolution constraint
            video_formats = []
            for fmt in formats:
                # Check if it's a video format
                if fmt.get("vcodec") != "none":
                    # Check resolution constraint
                    if fmt.get("height", 0) <= resolution_int:
                        # Calculate quality score based on codecs, resolution, and fps
                        score = 0
                        score += fmt.get("height", 0) * 10  # Resolution is important
                        score += fmt.get("fps", 0) * 5  # FPS is nice to have

                        # Codec preferences
                        if (
                            fmt.get("vcodec", "").startswith("avc")
                            or fmt.get("vcodec", "") == "h264"
                        ):
                            score += 300  # Most compatible
                        elif fmt.get("vcodec", "").startswith(("vp9", "av1")):
                            score += 200  # Good quality but less compatible

                        # Container preferences
                        if fmt.get("ext") == "mp4":
                            score += 100  # Most compatible

                        # Add bitrate factor
                        if fmt.get("vbr"):
                            score += min(
                                fmt.get("vbr", 0) / 100, 30
                            )  # Cap the influence

                        video_formats.append((fmt, score))

            # Sort by score
            if video_formats:
                video_formats.sort(key=lambda x: x[1], reverse=True)
                best_video = video_formats[0][0]

                # Now find best audio to pair with it
                audio_formats = []
                for fmt in formats:
                    if fmt.get("acodec") != "none" and fmt.get("vcodec") == "none":
                        # Calculate audio quality score
                        score = 0
                        if fmt.get("abr"):
                            score += fmt.get("abr", 0) * 10

                        # Prefer compatible containers
                        if fmt.get("ext") == best_video.get("ext"):
                            score += 500

                        audio_formats.append((fmt, score))

                if audio_formats:
                    audio_formats.sort(key=lambda x: x[1], reverse=True)
                    best_audio = audio_formats[0][0]
                    return f"{best_video['format_id']}+{best_audio['format_id']}/{best_video['format_id']}/best"

        # Default to smart format selection based on extension
        # This avoids the need for testing while still giving good results
        return "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best"

    def _check_memory_pressure(self) -> None:
        """Monitor and respond to memory pressure during downloads"""
        try:
            vm = psutil.virtual_memory()
            # Take action if memory usage is high
            if vm.percent > 90:  # Changed from 80% to 90%
                # Force garbage collection

                gc.collect()

                # Clear caches
                self._current_info_dict.clear()
                self.download_cache._cleanup_if_needed()

                # If memory is critically high, pause a moment
                if vm.percent > 95:
                    time.sleep(0.2)  # Brief pause to let system recover
                    # Close file handles and other resources
                    gc.collect(2)  # Full collection

        except Exception:
            pass  # Fail silently

    def _ensure_file_exists(
        self, filepath: str, timeout: float = 5.0, check_interval: float = 0.1
    ) -> bool:
        """Wait for file to exist with timeout, returns True if file exists
        -----------
        Args:
        filepath: Path to the file to check
        timeout: Maximum time to wait in seconds
        check_interval: Time between checks in seconds
        -----------
        Returns:
        True if file exists within timeout, False otherwise
        """
        start_time = time.time()
        # Check if path is absolute or needs to be resolved
        if not os.path.isabs(filepath):
            filepath = os.path.abspath(filepath)

        logging.debug(f"Waiting for file to exist: {filepath}")
        while time.time() - start_time < timeout:
            if os.path.exists(filepath):
                # Verify file is not empty and is readable
                try:
                    if os.path.getsize(filepath) > 0:
                        logging.debug(f"File exists and has content: {filepath}")
                    else:
                        logging.debug(f"File exists but is empty, waiting: {filepath}")
                except (OSError, IOError) as e:
                    logging.debug(f"Error checking file: {e}")

            time.sleep(check_interval)

        logging.warning(f"Timed out waiting for file: {filepath}")
        return False

    def post_process_hook(self, d: Dict[str, Any]) -> None:
        """
        Post-processing hook with enhanced error handling for FLAC conversions.

        This version improves filename tracking through the entire conversion pipeline
        and prevents "no filename provided" errors with robust null checking.
        """
        # Always check for missing filename first to prevent errors
        if "filename" not in d or not d.get("filename"):
            # Only log a debug message if this is a temporary/intermediate file status
            if d.get("status") in ["error", "stopped"]:
                logging.debug(f"Post-process status {d.get('status')} with no filename")
            return

        filename = d["filename"]
        status = d.get("status", "")

        # Skip processing for temporary fragments
        if filename and any(
            marker in os.path.basename(filename) for marker in (".f", part_ext, "tmp")
        ):
            return

        if status == "started":
            # Skip early processing for fragmented downloads
            if os.path.basename(filename).startswith("."):
                return

            # For FLAC files, run verification
            if filename.lower().endswith(FLAC_EXT):
                print(f"\n{Fore.CYAN}Verifying FLAC conversion...{Style.RESET_ALL}")
                try:
                    # Wait until the file is fully available
                    if not self._ensure_file_exists(filename, timeout=10.0):
                        print(
                            f"{Fore.RED}File not found after waiting: {filename}{Style.RESET_ALL}"
                        )
                        return

                    # Track the FLAC file in our internal registry to prevent orphaned references
                    self._current_info_dict[filename] = self._current_info_dict.get(
                        os.path.splitext(filename)[0], {}
                    )

                    # Run ffprobe to analyze the audio
                    ffprobe_info = self._run_ffprobe_with_retry(filename)
                    if not ffprobe_info:
                        print(
                            f"{Fore.YELLOW}⚠️ Could not analyze FLAC file: {filename}{Style.RESET_ALL}"
                        )
                        return

                    # Process audio analysis using mutagen (FLAC)
                    try:
                        audio = FLAC(filename)
                        filesize = os.path.getsize(filename)
                        bitrate = (
                            (filesize * 8) / (audio.info.length * 1000)
                            if audio.info.length > 0
                            else 0
                        )

                        # Display audio properties
                        print(
                            f"\n{Fore.GREEN}✓ FLAC conversion successful:{Style.RESET_ALL}"
                        )
                        print(f"   - Sample Rate: {audio.info.sample_rate} Hz")
                        print(f"   - Bit Depth: {audio.info.bits_per_sample} bit")
                        print(f"   - Channels: {audio.info.channels}")
                        print(
                            f"   - Duration: {int(audio.info.length // 60)}:{int(audio.info.length % 60):02d}"
                        )
                        print(f"   - Average Bitrate: {int(bitrate)} kbps")
                        print(f"   - File Size: {filesize // 1024 // 1024} MB")
                    except Exception as e:
                        logging.debug(f"Error analyzing FLAC file: {e}")
                except Exception as e:
                    logging.debug(f"Error in FLAC verification: {e}")

        elif status == "finished":
            # Handle both the original file and the converted file
            try:
                ext = os.path.splitext(filename)[1].lower()

                # If this is the source file for a FLAC conversion, record its completion
                if ext == webn_ext or ext == ".wav":
                    flac_output = f"{filename}.flac"
                    if os.path.exists(flac_output):
                        # Transfer info dict reference for proper tracking
                        self._current_info_dict[flac_output] = (
                            self._current_info_dict.get(filename, {})
                        )
                        logging.info(f"FLAC conversion succeeded: {flac_output}")

                # Skip filename cleanup for audio files to preserve pipeline
                if ext in AUDIO_EXTENSIONS or ext == webn_ext:
                    logging.debug(f"Skipping filename cleanup for {ext} file")
                else:
                    # For video files, perform normal cleanup
                    sanitized = sanitize_filename(os.path.basename(filename))
                    dirname = os.path.dirname(filename)
                    sanitized_path = os.path.join(dirname, sanitized)
                    if sanitized_path != filename and os.path.exists(filename):
                        try:
                            os.rename(filename, sanitized_path)
                            logging.info(
                                f"Renamed file to remove invalid characters: {sanitized}"
                            )
                            filename = sanitized_path
                        except Exception as e:
                            logging.error(f"Failed to rename file: {e}")

                # Continue with organization if enabled
                if (
                    self.config.get("organize")
                    and self.file_organizer
                    and os.path.exists(filename)
                ):
                    info_dict = self._current_info_dict.get(filename, {})
                    try:
                        new_filepath = self.file_organizer.organize_file(
                            filename, info_dict
                        )
                        if new_filepath:
                            print(f"\n{Fore.GREEN}File organized:{Style.RESET_ALL}")
                            print(
                                f"  {Fore.CYAN}→ {os.path.basename(new_filepath)}{Style.RESET_ALL}"
                            )
                    except Exception as e:
                        logging.error(f"Error organizing file: {e}")

            except Exception as e:
                logging.error(f"Error in post-processing finish: {e}")

    def check_network_connectivity(self) -> Tuple[bool, str]:
        """
        Check if the system has an active internet connection.

        Tests connectivity by attempting to reach reliable DNS servers and web services.
        Uses multiple fallback mechanisms for reliability.

        Returns:
            Tuple[bool, str]: (is_connected, message)
        """
        # List of reliable hosts to test connectivity
        test_hosts = [
            ("8.8.8.8", 53),  # Google DNS
            ("1.1.1.1", 53),  # Cloudflare DNS
        ]

        # Try socket connection first (faster)
        for host, port in test_hosts:
            try:
                socket_obj = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                socket_obj.settimeout(2.0)
                socket_obj.connect((host, port))
                socket_obj.close()
                return True, "Connected successfully"
            except (socket.timeout, socket.error):
                continue

        # Fall back to HTTP request
        try:
            requests.head("https://www.google.com", timeout=3.0)
            return True, "Connected via HTTP"
        except requests.RequestException as e:
            return False, f"Network error: {str(e)}"

    def estimate_download_size(self, info: dict) -> int:
        """
        Estimate download size from media info with fallback strategies.

        This function intelligently estimates the size of a download using multiple
        approaches from most accurate to least accurate:
        1. Direct filesize from info dict
        2. Format-specific filesize estimation
        3. Duration-based estimation
        4. Type-based conservative guess

        Args:
            info: Media info dictionary from yt-dlp

        Returns:
            Estimated size in bytes
        """
        # Check direct filesize first (most accurate)
        if "filesize" in info and info["filesize"]:
            return info["filesize"]

        if "filesize_approx" in info and info["filesize_approx"]:
            return info["filesize_approx"]

        # Look at format entries for size info
        if "formats" in info:
            # Try to find size in best format
            formats = info["formats"]

            # Sort formats by preference: with filesize, higher resolution
            def format_quality(fmt):
                has_size = 1000000 if fmt.get("filesize") else 0
                height = fmt.get("height", 0) or 0
                return has_size + height

            sorted_formats = sorted(formats, key=format_quality, reverse=True)

            for fmt in sorted_formats:
                if fmt.get("filesize"):
                    return fmt["filesize"]

        # Estimate based on duration and bitrate
        duration = info.get("duration", 0)
        if duration > 0:
            # For video, use resolution to estimate
            height = info.get("height", 0)
            if height > 0:
                # Estimate bitrate based on resolution
                if height >= 2160:  # 4K
                    bitrate = 35000000  # ~35 Mbps
                elif height >= 1080:  # Full HD
                    bitrate = 8000000  # ~8 Mbps
                elif height >= 720:  # HD
                    bitrate = 5000000  # ~5 Mbps
                else:  # SD
                    bitrate = 2500000  # ~2.5 Mbps

                # Calculate: bitrate (bits/sec) * duration (sec) / 8 bits per byte
                return int(bitrate * duration / 8)

            # For audio only
            if info.get("audio_channels", 0) > 0 and not info.get("width"):
                # Estimate based on format
                if info.get("format", "").lower().find("flac") >= 0:
                    bitrate = 900000  # ~900 kbps for FLAC
                else:
                    bitrate = 192000  # ~192 kbps for most lossy formats

                return int(bitrate * duration / 8)

        # Last resort: make a conservative guess based on type and some properties
        is_audio = "audio_channels" in info and info.get("width", 0) == 0
        is_playlist = info.get("_type") == "playlist"
        is_high_quality = info.get("height", 0) >= 1080

        if is_playlist:
            # Rough estimate for a playlist: assume 10 items at 50MB each
            return 10 * 50 * 1024 * 1024
        elif is_audio:
            # Rough estimate for audio: ~10MB for a song
            return 10 * 1024 * 1024
        elif is_high_quality:
            # High quality video: ~200MB
            return 200 * 1024 * 1024
        else:
            # Default conservative estimate
            return 50 * 1024 * 1024

    def is_memory_sufficient(self, threshold_mb: int = 1024) -> bool:
        """
        Check if system has sufficient memory for downloads.

        This function evaluates both available memory and virtual memory
        to determine if the system has enough resources for downloading.

        Args:
            threshold_mb: Minimum required memory in MB

        Returns:
            True if sufficient memory is available
        """
        try:
            # Get memory info
            mem = psutil.virtual_memory()
            swap = psutil.swap_memory()

            # Available physical memory in MB
            avail_physical_mb = mem.available / (1024 * 1024)

            # Available swap in MB
            avail_swap_mb = swap.free / (1024 * 1024)

            # Total available memory
            total_available = avail_physical_mb + (
                avail_swap_mb * 0.5
            )  # Count swap at half value

            # Memory is sufficient if:
            # 1. Available physical memory > 80% of threshold, OR
            # 2. Total available (counting swap at half value) > threshold
            return (avail_physical_mb > threshold_mb * 0.8) or (
                total_available > threshold_mb
            )

        except Exception as e:
            # In case of error, assume sufficient (don't block downloads)
            logging.debug(f"Memory check error: {e}")
            return True

    def get_available_memory(self) -> int:
        """
        Get available system memory in bytes with multi-platform support.

        Returns:
            Available memory in bytes
        """
        try:
            mem = psutil.virtual_memory()
            # Return available memory in bytes
            return mem.available
        except Exception as e:
            logging.debug(f"Error getting available memory: {e}")
            # Return conservative default (1GB) if detection fails
            return 1 * 1024 * 1024 * 1024

    def measure_network_speed(self, timeout: float = 3.0) -> float:
        """
        Get network speed by using cached results from previous speed tests.
        Simply returns the cached result if available, or a conservative default.

        Args:
            timeout: Ignored, kept for compatibility

        Returns:
            Network speed in Mbps (megabits per second)
        """
        logging.debug(f"Measuring network speed with timeout={timeout}s")

        # Check for cached speed test result first
        cache_file = os.path.join(CACHE_DIR, speedtestresult)
        now = time.time()
        try:
            if os.path.exists(cache_file):
                with open(cache_file, "r") as f:
                    data = json.load(f)
                    # Use cached result if less than 1 hour old
                    if now - data["timestamp"] < 3600:
                        return data["speed_mbps"]
        except Exception:
            pass
        # No cached result or cache expired - perform a quick speed test with timeout constraint
        spinner = SpinnerAnimation("Testing network speed", style="dots", color="cyan")
        spinner.start()

        speeds = []
        start_time = time.time()
        max_test_time = min(
            timeout, 8.0
        )  # Respect the provided timeout, but cap at 8 seconds
        logging.debug(f"Using max test time of {max_test_time}s")
        # Define a small test endpoint for quick measurement
        test_endpoints = [
            "https://httpbin.org/stream-bytes/51200",  # 50KB - very quick test
            "https://speed.cloudflare.com/__down?bytes=524288",  # 512KB - quick but more accurate
        ]
        for url in test_endpoints:
            # Check if we've exceeded our timeout
            if time.time() - start_time >= max_test_time:
                spinner.update_status(f"Reached timeout limit of {timeout}s")
                break
            spinner.update_status(f"Testing speed with {url}")
            logging.debug(f"Testing endpoint: {url}")
            try:
                # Create a session with a timeout constraint
                session = requests.Session()
                # Measure download speed with the specified timeout
                start = time.time()
                response = session.get(url, stream=True, timeout=min(timeout / 2, 2.0))

                if response.status_code == 200:
                    total_bytes = 0
                    for chunk in response.iter_content(chunk_size=8192):
                        total_bytes += len(chunk)
                        # Early exit if we're approaching the timeout
                        if time.time() - start_time >= max_test_time * 0.8:
                            logging.debug(
                                "Approaching timeout, stopping download early"
                            )
                            break
                    # Calculate speed
                    elapsed = time.time() - start
                    if elapsed > 0 and total_bytes > 0:
                        mbps = (total_bytes * 8) / (elapsed * 1000 * 1000)
                        speeds.append(mbps)
                        logging.debug(
                            f"Speed test result: {mbps:.2f} Mbps ({total_bytes} bytes in {elapsed:.2f}s)"
                        )
                        spinner.update_status(f"Measured: {mbps:.2f} Mbps")
                    else:
                        logging.debug(
                            f"Invalid measurement: {total_bytes} bytes in {elapsed:.2f}s"
                        )
                else:
                    logging.debug(f"HTTP error: {response.status_code}")
                response.close()
            except requests.RequestException as e:
                logging.debug(
                    f"Request error testing {url}: {type(e).__name__}: {str(e)}"
                )
                spinner.update_status(f"Connection error: {e.__class__.__name__}")
                continue
        spinner.stop(clear=True)
        if speeds:
            speed = sum(speeds) / len(speeds)
            logging.debug(
                f"Final speed calculated from {len(speeds)} samples: {speed:.2f} Mbps"
            )
        else:
            # Fallback if all tests failed
            speed = 5.0  # Conservative estimate
            logging.debug(
                f"No speed measurements succeeded, using fallback value: {speed} Mbps"
            )
        # Cache the result
        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
            with open(cache_file, "w") as f:
                cache_data = {
                    "timestamp": time.time(),
                    "speed_mbps": speed,
                    "samples": speeds,
                    "timeout_used": timeout,
                }
                json.dump(cache_data, f)
                logging.debug(f"Cached speed test result: {speed:.2f} Mbps")
        except Exception as e:
            # Ignore cache write failures
            logging.debug(f"Failed to cache speed test result: {e}")
        return speed

    def _check_speedtest_needed(self) -> float:
        """
        Check if a speed test is needed and prompt user if appropriate.

        Returns:
            float: Measured speed in Mbps, or 0 if no test was run
        """
        # Check for cached speed test result
        cache_file = os.path.join(CACHE_DIR, speedtestresult)
        now = time.time()

        try:
            if os.path.exists(cache_file):
                with open(cache_file, "r") as f:
                    data = json.load(f)

                # If test was run within the last day, use cached result without prompting
                if now - data["timestamp"] < 86400:  # 24 hours
                    return data["speed_mbps"]
        except Exception:
            pass

        # No recent speed test found, prompt user
        print(f"\n{Fore.CYAN}No recent network speed test found.{Style.RESET_ALL}")
        print(
            f"{Fore.YELLOW}Running a speed test will help optimize your download settings.{Style.RESET_ALL}"
        )

        try:
            choice = (
                input(f"{Fore.GREEN}Run speed test now? (Y/n): {Style.RESET_ALL}")
                .strip()
                .lower()
            )
            if choice == "" or choice.startswith("y"):
                return run_speedtest(detailed=False)

            print(f"{Fore.YELLOW}Proceeding with default settings.{Style.RESET_ALL}")
            return 0
        except KeyboardInterrupt:
            print(
                f"\n{Fore.YELLOW}Speed test skipped. Using default settings.{Style.RESET_ALL}"
            )
            return 0

    def _apply_speed_optimized_settings(self, speed_mbps: float, options: dict) -> None:
        """
        Apply optimized download settings based on measured network speed.

        Args:
            speed_mbps: Network speed in Mbps
            options: Download options dictionary to modify
        """
        if speed_mbps <= 0:
            return

        # Determine optimal settings based on speed
        if speed_mbps >= 50:  # Very fast connection
            if self._check_aria2c_available() and not options.get("use_aria2c", False):
                print(
                    f"\n{Fore.GREEN}Enabling aria2c for faster downloads based on your network speed.{Style.RESET_ALL}"
                )
                options["use_aria2c"] = True

            # Automatically select video resolution if not specified
            if not options.get("resolution") and not options.get("audio_only", False):
                # Fast enough for 4K
                options["resolution"] = "2160"
                print(
                    f"{Fore.GREEN}Your connection supports 4K video. Selecting highest quality.{Style.RESET_ALL}"
                )

        elif speed_mbps >= 20:  # Fast connection
            if self._check_aria2c_available() and not options.get("use_aria2c", False):
                print(
                    f"\n{Fore.GREEN}Enabling aria2c for faster downloads based on your network speed.{Style.RESET_ALL}"
                )
                options["use_aria2c"] = True

            # Good for 1080p
            if not options.get("resolution") and not options.get("audio_only", False):
                options["resolution"] = "1080"
                print(
                    f"{Fore.GREEN}Your connection is good for 1080p video.{Style.RESET_ALL}"
                )

        elif speed_mbps >= 10:  # Decent connection
            # Can handle 1080p but not 4K
            if not options.get("resolution") and not options.get("audio_only", False):
                options["resolution"] = "1080"
                print(
                    f"{Fore.GREEN}Your connection is suitable for 1080p video.{Style.RESET_ALL}"
                )

        elif speed_mbps >= 5:  # Medium connection
            # Better for 720p
            if not options.get("resolution") and not options.get("audio_only", False):
                options["resolution"] = "720"
                print(
                    f"{Fore.YELLOW}Your connection is best suited for 720p video.{Style.RESET_ALL}"
                )

            # For audio downloads on slower connections, suggest opus instead of flac
            if (
                options.get("audio_only", False)
                and options.get("audio_format") == "flac"
            ):
                print(
                    f"{Fore.YELLOW}Note: FLAC downloads may be slow on your connection. Consider using opus format.{Style.RESET_ALL}"
                )

        else:  # Slow connection
            # Recommend 480p
            if not options.get("resolution") and not options.get("audio_only", False):
                options["resolution"] = "480"
                print(
                    f"{Fore.YELLOW}Your connection is slow. Using 480p video for better experience.{Style.RESET_ALL}"
                )

            # For slow connections, strongly recommend against flac
            if (
                options.get("audio_only", False)
                and options.get("audio_format") == "flac"
            ):
                print(
                    f"{Fore.RED}Warning: FLAC downloads will be very slow on your connection.{Style.RESET_ALL}"
                )
                print(
                    f"{Fore.YELLOW}Consider using opus or mp3 format instead.{Style.RESET_ALL}"
                )

    def download(self, url: str, **kwargs) -> bool:
        """Download media with optimized metadata extraction, progress handling, and error management."""
        # Validate URL
        try:
            parsed = urllib.parse.urlparse(url)
            if not all([parsed.scheme, parsed.netloc]):
                print(f"{Fore.RED}Invalid URL: {url}{Style.RESET_ALL}")
                return False
        except Exception:
            print(f"{Fore.RED}Invalid URL format: {url}{Style.RESET_ALL}")
            return False

        # Check network connectivity with spinner feedback
        network_spinner = SpinnerAnimation(
            "Checking network connection", style="dots", color="cyan"
        )
        network_spinner.start()
        is_connected, message = self.check_network_connectivity()
        if not is_connected:
            network_spinner.stop(clear=False, success=False)
            print(f"{Fore.RED}Network Error: {message}{Style.RESET_ALL}")
            print(
                f"{Fore.YELLOW}Please check your internet connection and try again.{Style.RESET_ALL}"
            )
            return False
        else:
            network_spinner.stop(clear=True)
            # Check if the user wants to test all formats (only if not explicitly set)
        if "test_all_formats" not in kwargs and not kwargs.get(
            "non_interactive", False
        ):
            test_formats = False
            if not kwargs.get(
                "format_id"
            ):  # Only need to ask if no specific format ID is given
                try:
                    choice = input(
                        f"\n{Fore.CYAN}Test all available formats for best quality? (slower) (y/N): {Style.RESET_ALL}"
                    )
                    test_formats = choice.strip().lower() == "y"
                    if test_formats:
                        print(
                            f"{Fore.YELLOW}Testing all formats may take longer but can find better quality...{Style.RESET_ALL}"
                        )
                except KeyboardInterrupt:
                    print("\nSkipping format testing.")
            kwargs["test_all_formats"] = test_formats

        # New: Check for speed test results and prompt if needed
        if not kwargs.get("no_speedtest_prompt", False) and not kwargs.get(
            "non_interactive", False
        ):
            speed_mbps = self._check_speedtest_needed()
            if speed_mbps > 0:
                # Apply optimized settings based on speed test
                self._apply_speed_optimized_settings(speed_mbps, kwargs)

        # Set current download URL for session tracking
        self.current_download_url = url

        # Check if we need to prompt for audio channels for audio downloads in interactive mode
        # This only applies if we're doing an audio download and not already specified audio_channels
        if (
            kwargs.get("audio_only", False)
            and "audio_channels" not in kwargs
            and not kwargs.get("non_interactive", False)
        ):
            audio_format = kwargs.get("audio_format", "opus")
            # Only prompt for formats that benefit from channel configuration
            if audio_format == "flac" and not getattr(self, "non_interactive", False):
                print(f"\n{Fore.CYAN}Audio Channel Configuration:{Style.RESET_ALL}")
                print(
                    f"  {Fore.GREEN}1. Stereo (2.0){Style.RESET_ALL} - Standard quality, compatible with all devices"
                )
                print(
                    f"  {Fore.GREEN}2. Surround (7.1){Style.RESET_ALL} - High quality for home theater systems"
                )
                try:
                    choice = input(
                        f"{Fore.GREEN}Select audio configuration [1-2] (default: 1): {Style.RESET_ALL}"
                    )
                    if choice.strip() == "2":
                        kwargs["audio_channels"] = 8  # 7.1 surround
                    else:
                        kwargs["audio_channels"] = 2  # Default stereo
                except Exception:
                    kwargs["audio_channels"] = 2  # Default to stereo on error

        # Auto-enable aria2c if available and not already requested by kwargs
        if not kwargs.get("use_aria2c", False) and self._check_aria2c_available():
            print(f"{Fore.CYAN}Using aria2c for faster downloads{Style.RESET_ALL}")
            kwargs["use_aria2c"] = True

        # Add fast mode by default, can be overridden with test_all_formats
        fast_mode = not kwargs.get("test_all_formats", False)

        # Start the info spinner and try to get media info (using cache if available)
        info_spinner = SpinnerAnimation("Analyzing media", style="aesthetic")
        info_spinner.start()
        time.sleep(0.3)  # Brief pause to allow spinner message display

        if not kwargs.get("no_cache", False):
            cached_info = self.download_cache.get_info(url)
        else:
            cached_info = None

        if cached_info:
            info_spinner.update_message("Using cached media information")
            time.sleep(0.1)
            info = cached_info
        else:
            try:
                # Prepare options: get_download_options handles defaults for audio/video and other kwargs
                ydl_opts = self.get_download_options(
                    url,
                    kwargs.get("audio_only", False),
                    kwargs.get("resolution"),
                    kwargs.get("format_id"),
                    kwargs.get("filename"),
                    kwargs.get("audio_format", "opus"),
                    kwargs.get("no_retry", False),
                    kwargs.get("throttle"),
                    kwargs.get("use_aria2c", False),
                    kwargs.get("audio_channels", 2),
                    test_all_formats=kwargs.get("test_all_formats", False),
                )

                # For video downloads, force merged MP4 output when possible
                if not kwargs.get("audio_only", False):
                    ydl_opts["merge_output_format"] = "mp4"
                    ydl_opts["postprocessor_args"] = ["-c", "copy"]
                    if not kwargs.get("format_id"):
                        ydl_opts["format"] = (
                            "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best"
                        )

                with timer("Media info extraction", silent=True):
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        # Use a single extraction call with process=True
                        info = ydl.extract_info(url, download=False, process=True)
                        if info:
                            # Update spinner status (with display=False to avoid duplicate printing)
                            if info.get("_type") != "playlist":
                                info_spinner.update_status(
                                    "Processing media information"
                                )
                            else:
                                info_spinner.update_status("Processing playlist")
                            serializable_info = self._display_media_info(
                                info, display=False
                            )
                            self.download_cache.save_info(url, serializable_info)
                        else:
                            info_spinner.stop(clear=False, success=False)
                            print(
                                f"{Fore.RED}Media info extraction returned no data.{Style.RESET_ALL}"
                            )
                            return False
            except yt_dlp.utils.DownloadError as e:
                info_spinner.stop(clear=False, success=False)
                print(f"{Fore.RED}Error fetching media info: {str(e)}{Style.RESET_ALL}")
                return False
        info_spinner.stop(clear=True)

        if not info:
            print(
                f"{Fore.RED}Could not fetch media information for: {url}{Style.RESET_ALL}"
            )
            return False

        # Display media info to the user (if not already suppressed)
        self._display_media_info(info)

        # If info is a playlist, handle accordingly.
        if info.get("_type") == "playlist":
            return self._handle_playlist(url, info, **kwargs)

            # OPTIMIZATION: If using fast mode, determine optimal format IDs now
        explicit_format_id = kwargs.get("format_id")
        if fast_mode and not explicit_format_id:
            audio_only = kwargs.get("audio_only", False)
            resolution = kwargs.get("resolution")
            optimal_format = self._get_optimal_format_ids(
                url, info, audio_only, resolution
            )
            kwargs["format_id"] = optimal_format
            logging.debug(f"Selected optimal format: {optimal_format}")

        # Check system resource conditions based on estimated download size.
        est_size = self.estimate_download_size(info)
        if est_size > 500 * 1024 * 1024 and not self.is_memory_sufficient():
            print(
                f"{Fore.YELLOW}⚠️ Warning: System memory is low. Download may be slow or fail.{Style.RESET_ALL}"
            )
            proceed = (
                input(f"{Fore.CYAN}Continue anyway? (y/n): {Style.RESET_ALL}")
                .lower()
                .startswith("y")
            )
            if not proceed:
                return False

        # Prepare download options with dynamic chunk size
        ydl_opts = self.get_download_options(
            url,
            kwargs.get("audio_only", False),
            kwargs.get("resolution"),
            kwargs.get("format_id"),
            kwargs.get("filename"),
            kwargs.get("audio_format", "opus"),
            kwargs.get("no_retry", False),
            kwargs.get("throttle"),
            kwargs.get("use_aria2c", False),
            kwargs.get("audio_channels", 2),
        )
        ydl_opts["http_chunk_size"] = self._adaptive_chunk_size()

        # Register this download as active for improved resource management.
        with self._download_lock:
            self._active_downloads.add(url)
        self.download_start_time = time.time()

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Store expected output info for post-processing
                if not kwargs.get("no_cache", False):
                    downloaded_info = ydl.extract_info(url, download=False)
                    if downloaded_info:
                        expected_filename = ydl.prepare_filename(downloaded_info)
                        self._current_info_dict[expected_filename] = downloaded_info

                # Execute the download
                ydl.download([url])
                return True

        except KeyboardInterrupt:
            print(f"\n{Fore.YELLOW}Download cancelled by user{Style.RESET_ALL}")
            return False
        except yt_dlp.utils.DownloadError as e:
            error_msg = str(e)
            logging.error("Download Error: %s", error_msg)
            if "unavailable" in error_msg.lower():
                print(
                    f"{Fore.YELLOW}This media may have been removed or is private.{Style.RESET_ALL}"
                )
            elif "ffmpeg" in error_msg.lower():
                print(
                    f"{Fore.YELLOW}FFmpeg error. Try running 'python setup_ffmpeg.py' to fix.{Style.RESET_ALL}"
                )
            elif any(
                net_err in error_msg.lower()
                for net_err in ["timeout", "connection", "network"]
            ):
                print(
                    f"{Fore.YELLOW}Network error. Check your internet connection and try again.{Style.RESET_ALL}"
                )
            return False
        finally:
            # Clean up any temporary files that might have been created
            self._cleanup_temporary_files()
            with self._download_lock:
                self._active_downloads.discard(url)
            self.current_download_url = None
            self.download_start_time = None

    def validate_metadata(self, info: Dict[str, Any]) -> None:
        """Ensure required metadata fields exist"""
        required_fields = ["title", "ext"]
        for field in required_fields:
            if field not in info:
                raise ValueError(f"Missing required metadata field: {field}")

    def _display_media_info(
        self, info: Dict[str, Any], display: bool = True
    ) -> Dict[str, Any]:
        """
        Display and return a serializable version of media information.

        Args:
            info: Media information dictionary from yt-dlp extraction.
            display: Controls whether info is printed.

        Returns:
            A version of the info that is JSON-serializable.
        """

        def make_serializable(obj):
            # Recursively convert non-serializable items to lists/dicts
            if isinstance(obj, list) and not isinstance(obj, (str, bytes, dict)):
                return [make_serializable(item) for item in obj]
            elif isinstance(obj, dict):
                return {k: make_serializable(v) for k, v in obj.items()}
            elif hasattr(obj, "__iter__") and not isinstance(obj, (str, bytes, dict)):
                return list(obj)
            else:
                return obj

        try:
            # Create a serializable copy of the info once
            serializable_info = make_serializable(info)

            # Cache frequently used fields with defaults
            title = serializable_info.get("title", "Unknown Title")
            uploader = serializable_info.get(
                "uploader", serializable_info.get("channel", "Unknown Uploader")
            )
            duration = serializable_info.get("duration", 0)
            height = serializable_info.get("height", 0)
            width = serializable_info.get("width", 0)
            filesize = serializable_info.get(
                "filesize", serializable_info.get("filesize_approx", 0)
            )
            upload_date = serializable_info.get("upload_date")
            view_count = serializable_info.get("view_count")

            # Format duration
            if duration:
                total_secs = int(duration)
                hours, remainder = divmod(total_secs, 3600)
                mins, secs = divmod(remainder, 60)
                duration_str = (
                    f"{hours}:{mins:02d}:{secs:02d}" if hours else f"{mins}:{secs:02d}"
                )
            else:
                duration_str = "Unknown duration"

            # Determine video quality if available
            quality = ""
            if width and height:
                if height >= 2160:
                    quality = "4K"
                elif height >= 1080:
                    quality = "Full HD"
                elif height >= 720:
                    quality = "HD"

            # Format file size
            if filesize:
                if filesize > 1024**3:
                    filesize_str = f"{filesize / (1024**3):.2f} GB"
                else:
                    filesize_str = f"{filesize / (1024**2):.2f} MB"
            else:
                filesize_str = "Unknown"

            if display:
                print(f"\n{Fore.CYAN}{'=' * 40}{Style.RESET_ALL}")
                print(f"{Fore.GREEN}Title:{Style.RESET_ALL} {title}")
                print(f"{Fore.GREEN}Channel/Uploader:{Style.RESET_ALL} {uploader}")
                print(f"{Fore.GREEN}Duration:{Style.RESET_ALL} {duration_str}")
                if quality:
                    print(
                        f"{Fore.GREEN}Quality:{Style.RESET_ALL} {quality} ({width}x{height})"
                    )
                print(f"{Fore.GREEN}Estimated Size:{Style.RESET_ALL} {filesize_str}")

                # Display upload date if available and correctly formatted YYYYMMDD
                if upload_date and len(str(upload_date)) == 8:
                    try:
                        formatted_date = (
                            f"{upload_date[0:4]}-{upload_date[4:6]}-{upload_date[6:8]}"
                        )
                        print(
                            f"{Fore.GREEN}Upload Date:{Style.RESET_ALL} {formatted_date}"
                        )
                    except Exception:
                        pass

                # Format view count with commas if available
                if view_count:
                    print(f"{Fore.GREEN}Views:{Style.RESET_ALL} {int(view_count):,}")
                print(f"{Fore.CYAN}{'=' * 40}{Style.RESET_ALL}\n")

            return serializable_info

        except Exception as e:
            logging.error(f"Error displaying media info: {str(e)}")
            if display:
                print(
                    f"{Fore.YELLOW}⚠️ Limited media information available. Continuing with download...{Style.RESET_ALL}"
                )
            return info  # Return the original info if an error occurs

    def _handle_playlist(self, url: str, info: Dict[str, Any], **kwargs) -> bool:
        """Handle playlist downloads with better UX and resource management"""
        entries = list(info.get("entries", []))
        entry_count = len(entries)

        if entry_count == 0:
            print(f"{Fore.YELLOW}Playlist contains no videos{Style.RESET_ALL}")
            return False

        print(f"\n{Fore.CYAN}Playlist Information:{Style.RESET_ALL}")
        print(f"Title: {info.get('title', 'Unknown Playlist')}")
        print(f"Contains: {entry_count} videos")

        # Offer download options
        print(f"\n{Fore.CYAN}Download Options:{Style.RESET_ALL}")
        print("1. Download the entire playlist")
        print("2. Download the first few videos only")
        print("3. Select specific videos to download")
        print("4. Cancel")

        choice = input(f"{Fore.GREEN}Enter choice (1-4): {Style.RESET_ALL}")

        if choice == "1":
            return self._download_entire_playlist(url, **kwargs)
        elif choice == "2":
            try:
                count = int(
                    input(f"{Fore.GREEN}How many videos to download: {Style.RESET_ALL}")
                )
                return self._download_partial_playlist(url, count, **kwargs)
            except ValueError:
                print(f"{Fore.RED}Invalid number{Style.RESET_ALL}")
                return False
        elif choice == "3":
            return self._download_selected_playlist_items(info, **kwargs)
        else:
            print(f"{Fore.YELLOW}Download cancelled{Style.RESET_ALL}")
            return False

    def _download_entire_playlist(self, url: str, **kwargs) -> bool:
        """Download an entire playlist"""
        ydl_opts = self.get_download_options(
            url,
            kwargs.get("audio_only", False),
            kwargs.get("resolution"),
            kwargs.get("format_id"),
            kwargs.get("filename"),
            kwargs.get("audio_format", "opus"),
        )

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            return True
        except Exception as e:
            print(f"{Fore.RED}Error downloading playlist: {str(e)}{Style.RESET_ALL}")
            return False

    def _download_partial_playlist(self, url: str, count: int, **kwargs) -> bool:
        """Download first N videos from a playlist"""
        # Use playlist_items option to limit downloads
        ydl_opts = self.get_download_options(
            url,
            kwargs.get("audio_only", False),
            kwargs.get("resolution"),
            kwargs.get("format_id"),
            kwargs.get("filename"),
            kwargs.get("audio_format", "opus"),
        )

        # Add playlist item limit (1-based indexing for yt-dlp)
        ydl_opts["playliststart"] = 1
        ydl_opts["playlistend"] = count

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            return True
        except Exception as e:
            print(
                f"{Fore.RED}Error downloading playlist items: {str(e)}{Style.RESET_ALL}"
            )
            return False

    def _download_selected_playlist_items(self, info: Dict[str, Any], **kwargs) -> bool:
        """Download specific videos selected by the user"""
        entries = list(info.get("entries", []))

        if not entries:
            print(f"{Fore.YELLOW}No videos found in playlist{Style.RESET_ALL}")
            return False

        # Display videos with numbers
        print(f"\n{Fore.CYAN}Available Videos:{Style.RESET_ALL}")
        for i, entry in enumerate(entries, 1):
            title = entry.get("title", f"Video {i}")
            duration = entry.get("duration", 0)
            duration_str = (
                f"{int(duration // 60)}:{int(duration % 60):02d}"
                if duration
                else "??:??"
            )
            print(f"{i}. {title} [{duration_str}]")

        # Get user selection
        try:
            selection = input(
                f"\n{Fore.GREEN}Enter video numbers to download (e.g. 1,3,5-7): {Style.RESET_ALL}"
            )
            selected_indices = []

            # Parse the selection string
            for part in selection.split(","):
                if "-" in part:
                    start, end = map(int, part.split("-"))
                    selected_indices.extend(range(start, end + 1))
                else:
                    selected_indices.append(int(part))

            # Validate indices
            selected_indices = [i for i in selected_indices if 1 <= i <= len(entries)]

            if not selected_indices:
                print(f"{Fore.YELLOW}No valid videos selected{Style.RESET_ALL}")
                return False

            # Download selected videos
            success_count = 0
            for idx in selected_indices:
                entry = entries[idx - 1]
                url = entry.get("webpage_url", entry.get("url", None))

                if not url:
                    print(
                        f"{Fore.YELLOW}Could not get URL for video #{idx}{Style.RESET_ALL}"
                    )
                    continue

                print(
                    f"\n{Fore.CYAN}Downloading #{idx}: {entry.get('title', 'Unknown')}{Style.RESET_ALL}"
                )
                if self.download(url, **kwargs):
                    success_count += 1

            print(
                f"\n{Fore.GREEN}Downloaded {success_count} of {len(selected_indices)} selected videos{Style.RESET_ALL}"
            )
            return success_count > 0

        except (ValueError, IndexError) as e:
            print(f"{Fore.RED}Error parsing selection: {str(e)}{Style.RESET_ALL}")
            return False

    def batch_download(self, urls: List[str], **kwargs) -> List[bool]:
        """Enhanced parallel download with improved resource management"""
        results = []
        total = len(urls)

        if total == 0:
            print(f"{Fore.YELLOW}No URLs provided{Style.RESET_ALL}")
            return []

        print(
            f"{Fore.CYAN}Starting batch download of {total} items...{Style.RESET_ALL}"
        )

        # Determine optimal concurrency based on system resources
        available_memory = self.get_available_memory()
        memory_based_limit = max(
            1, int(available_memory / (500 * 1024 * 1024))
        )  # ~500MB per download

        # Balance between config, memory limitations and CPU cores
        max_workers = min(
            self.config.get("max_concurrent", 3),  # From config
            memory_based_limit,  # Based on available memory
            os.cpu_count() or 4,  # Based on CPU cores
            total,
        )

        # Use ThreadPoolExecutor for parallel downloads
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_url = {
                executor.submit(self.download, url, **kwargs): url for url in urls
            }

            for future in as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    print(
                        f"{Fore.RED}Error downloading {url}: {str(e)}{Style.RESET_ALL}"
                    )
                    results.append(False)

        print(
            f"\n{Fore.GREEN}Batch download complete. {sum(results)} of {total} items downloaded successfully.{Style.RESET_ALL}"
        )
        return results
        # Add this to the DownloadManager class

    def _cleanup_fragment_files(self, directory: str, base_filename: str) -> None:
        """Clean up any orphaned fragment files after a download completes"""
        try:
            basename = os.path.basename(base_filename)
            name_without_ext = os.path.splitext(basename)[0]

            # Look for fragment files with pattern: name.f123.ext
            pattern = re.compile(rf"{re.escape(name_without_ext)}\.f\d+\..+")

            for filename in os.listdir(directory):
                if pattern.match(filename):
                    fragment_path = os.path.join(directory, filename)
                    logging.debug(f"Removing orphaned fragment file: {fragment_path}")
                    try:
                        os.remove(fragment_path)
                    except OSError as e:
                        logging.debug(f"Failed to remove fragment file: {e}")
        except Exception as e:
            logging.debug(f"Error during fragment cleanup: {e}")

    def fuzzy_match_command(self, input_cmd: str, valid_commands: tuple) -> str:
        """
        Match user input to a valid command using fuzzy matching.

        This function helps users by matching their input to the closest valid command,
        providing a more forgiving command interface that handles typos and variations.

        Args:
            input_cmd: The user's input command
            valid_commands: Tuple of valid commands to match against

        Returns:
            The matched command or the original input if no good match found
        """
        # Direct match - return immediately
        if input_cmd in valid_commands:
            return input_cmd

        # Check for command prefix match (e.g. "dow" -> "download")
        prefix_matches = [cmd for cmd in valid_commands if cmd.startswith(input_cmd)]
        if prefix_matches:
            return prefix_matches[0]  # Return the first prefix match

        # Check for close matches using difflib
        matches = get_close_matches(input_cmd, valid_commands, n=1, cutoff=0.6)
        if matches:
            return matches[0]

        # Check for substring match (e.g. "load" in "download")
        substring_matches = [cmd for cmd in valid_commands if input_cmd in cmd]
        if substring_matches:
            return substring_matches[0]  # Return the first substring match

        # No good match found, return original
        return input_cmd

    def interactive_mode(self) -> None:
        """Interactive mode for user-friendly operation with improved command dispatch and error handling."""
        print_banner()
        print(f"{Fore.CYAN}Welcome to Snatch Interactive Mode!{Style.RESET_ALL}")

        # Helper function to prompt for a URL.
        def prompt_url(prompt_text: str = "Enter URL: ") -> str:
            return input(f"{Fore.GREEN}{prompt_text}{Style.RESET_ALL}").strip()

        # Helper function to prompt for audio configuration
        def prompt_audio_channels() -> int:
            print(f"\n{Fore.CYAN}Audio Channel Configuration:{Style.RESET_ALL}")
            print(
                f"  {Fore.GREEN}1. Stereo (2.0){Style.RESET_ALL} - Standard quality, compatible with all devices"
            )
            print(
                f"  {Fore.GREEN}2. Surround (7.1){Style.RESET_ALL} - High quality for home theater systems"
            )
            try:
                choice = input(
                    f"{Fore.GREEN}Select audio configuration [1-2] (default: 1): {Style.RESET_ALL}"
                )
                if not choice or choice.strip() == "1":
                    return 2  # Default: Stereo (2 channels)
                elif choice.strip() == "2":
                    return 8  # 7.1 surround (8 channels)
                else:
                    print(
                        f"{Fore.YELLOW}Invalid choice, using stereo (2.0) configuration.{Style.RESET_ALL}"
                    )
                    return 2
            except Exception:
                print(
                    f"{Fore.YELLOW}Error reading input, using stereo (2.0) configuration.{Style.RESET_ALL}"
                )
                return 2

        while True:
            try:
                # Get input command from user.
                command = input(f"\n{Fore.GREEN}snatch> {Style.RESET_ALL}").strip()
                if not command:
                    continue

                # Exit condition.
                if command.lower() in ("exit", "quit", "q"):
                    print(f"{Fore.CYAN}Exiting Snatch. Goodbye!{Style.RESET_ALL}")
                    break

                # Help command.
                if command.lower() in ("help", "?"):
                    print(EXAMPLES)
                    continue
                # Speed test command
                if command.lower() in ("speedtest", "speed", "test"):
                    run_speedtest()
                    continue

                # If the input looks like a URL, parse potential options.
                if "://" in command:
                    parts = command.split(maxsplit=1)
                    url = parts[0]
                    options = {}
                    if len(parts) > 1:
                        option_text = parts[1].strip().lower()
                        # If an audio format is specified.
                        if option_text in ["opus", "mp3", "wav", "flac", "m4a"]:
                            # Prompt for audio channel configuration for audio formats
                            # that benefit from configuration (primarily flac)
                            audio_channels = 2  # Default to stereo
                            if option_text in [
                                "flac"
                            ]:  # Only prompt for formats that benefit from surround
                                audio_channels = prompt_audio_channels()

                            options = {
                                "audio_only": True,
                                "audio_format": option_text,
                                "audio_channels": audio_channels,  # Pass the selected audio channels
                            }
                        # If a resolution is specified.
                        elif option_text in ["720", "1080", "2160", "4k", "480", "360"]:
                            options = {
                                "resolution": (
                                    "2160" if option_text == "4k" else option_text
                                )
                            }

                    # For URL-only input, download best quality video by default
                    print(f"{Fore.CYAN}Downloading from URL: {url}{Style.RESET_ALL}")
                    self.download(url, **options)
                    continue

                # Use fuzzy matching to adjust the command.
                matched_command = self.fuzzy_match_command(
                    command.lower(), self.valid_commands
                )
                if matched_command:
                    command = matched_command

                # Dispatch standard commands using the helper to avoid repetition.
                if command.startswith("download") or command.startswith("dl"):
                    self.download(prompt_url())
                elif command.startswith("audio"):
                    self.download(prompt_url(), audio_only=True)
                elif command.startswith("video"):
                    url = prompt_url()
                    resolution = input(
                        f"{Fore.GREEN}Enter resolution (e.g., 1080): {Style.RESET_ALL}"
                    ).strip()
                    self.download(url, resolution=resolution)
                elif command.startswith("flac"):
                    # For FLAC, prompt for audio channel configuration
                    url = prompt_url()
                    audio_channels = prompt_audio_channels()
                    self.download(
                        url,
                        audio_only=True,
                        audio_format="flac",
                        audio_channels=audio_channels,
                    )
                elif command.startswith("mp3"):
                    self.download(prompt_url(), audio_only=True, audio_format="mp3")
                elif command.startswith("wav"):
                    self.download(prompt_url(), audio_only=True, audio_format="wav")
                elif command.startswith("m4a"):
                    self.download(prompt_url(), audio_only=True, audio_format="m4a")
                elif command.startswith("opus"):
                    # For opus, also give the option for channel configuration
                    url = prompt_url()
                    audio_channels = 2  # Default to stereo for opus

                    # Check if running in non-interactive mode (attribute might not be set)
                    is_non_interactive = (
                        hasattr(self, "non_interactive") and self.non_interactive
                    )
                    if not is_non_interactive:
                        audio_channels = prompt_audio_channels()
                    self.download(
                        url,
                        audio_only=True,
                        audio_format="opus",
                        audio_channels=audio_channels,
                    )
                elif command.startswith("list") or command.startswith("sites"):
                    list_supported_sites()
                elif command.startswith("clear") or command.startswith("cls"):
                    os.system("cls" if is_windows() else "clear")
                else:
                    # Unknown command fallback.
                    print(f"{Fore.RED}Unknown command: {command}{Style.RESET_ALL}")
                    print(
                        f"{Fore.YELLOW}Type 'help' or '?' for a list of commands.{Style.RESET_ALL}"
                    )
                    print(
                        f"{Fore.YELLOW}If you're trying to download, ensure the URL includes 'http://' or 'https://'{Style.RESET_ALL}"
                    )

            except KeyboardInterrupt:
                print(
                    f"\n{Fore.YELLOW}Operation cancelled by user. Exiting interactive mode...{Style.RESET_ALL}"
                )
                break
            except Exception as e:
                print(f"{Fore.RED}An error occurred: {str(e)}{Style.RESET_ALL}")

    def _adaptive_chunk_size(self) -> int:
        """Dynamically determine optimal chunk size based on available memory"""
        # Get available memory in bytes
        available_memory = self.get_available_memory()

        # Check network speed to adjust chunk size
        network_speed = self.measure_network_speed()

        # Calculate optimal chunk size based on both network speed and memory
        # Higher speeds need larger chunks to reduce overhead
        if (
            network_speed > 10.0 and available_memory > 4 * 1024 * 1024 * 1024
        ):  # >10Mbps and >4GB
            return 40 * 1024 * 1024  # 40MB chunks for very fast connections
        elif (
            network_speed > 5.0 and available_memory > 2 * 1024 * 1024 * 1024
        ):  # >5Mbps and >2GB
            return 20 * 1024 * 1024  # 20MB chunks for fast connections
        elif (
            network_speed > 2.0 and available_memory > 1024 * 1024 * 1024
        ):  # >2Mbps and >1GB
            return 10 * 1024 * 1024  # 10MB chunks
        else:
            return 5 * 1024 * 1024  # 5MB chunks for slower connections

    def _parse_throttle_rate(self, throttle: str) -> int:
        """
        Parse a throttle rate string like '500K', '1.5M', '2G' into bytes per second.
        Returns 0 if parsing fails.
        """
        if not throttle:
            logging.warning("Throttle rate is empty or None, using unlimited speed.")
            return 0

        try:
            # Extract number and unit
            match = re.match(r"^([\d.]+)([KMGkmg])?$", throttle)
            if not match:
                return 0

            value, unit = match.groups()
            value = float(value)

            # Convert to bytes based on unit
            if unit:
                unit = unit.upper()
                if unit == "K":
                    value = value * 1024
                elif unit == "M":
                    value = value * 1024 * 1024
                elif unit == "G":
                    value = value * 1024 * 1024 * 1024

            return int(value)
        except Exception:
            logging.warning(
                f"Could not parse throttle rate: {throttle}, using unlimited speed."
            )
            return 0

    def _check_aria2c_available(self) -> bool:
        """Check if aria2c is available in the system PATH"""
        try:
            cmd = ["aria2c", "--version"]
            subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True
            )
            return True
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

    def _run_ffprobe(
        self,
        filepath: str,
        timeout: float = 10.0,
        cache: bool = True,
        fast_mode: bool = False,
    ) -> Dict[str, Any]:
        """
        Run ffprobe with optimized performance, caching, and robust error handling.

        This implementation includes:
        - LRU caching with intelligent cache invalidation
        - Safe handling of paths with special characters
        - Advanced error recovery
        - Proper resource management
        - Cross-platform compatibility
        - Fast mode for quicker analysis when full details aren't needed

        Args:
            filepath: Path to media file to analyze
            timeout: Maximum time in seconds to wait for ffprobe
            cache: Whether to use cached results if available
            fast_mode: If True, only get essential information (format, duration)

        Returns:
            Dictionary containing ffprobe results or empty dict on failure
        """
        # 1. Validate and normalize filepath
        if not filepath or not os.path.exists(filepath):
            logging.error(f"ffprobe error: File not found: {filepath}")
            return {}

        # Normalize path for consistency and cache lookup
        filepath = os.path.abspath(filepath)

        # 2. Try to use cached result if allowed
        if cache:
            # Initialize cache if not exist using OrderedDict for efficient LRU
            if not hasattr(self, "_ffprobe_cache"):
                self._ffprobe_cache = OrderedDict()

            # Generate cache key based on file metadata
            try:
                file_stat = os.stat(filepath)
                cache_key = f"{filepath}:{file_stat.st_size}:{file_stat.st_mtime}"

                if cache_key in self._ffprobe_cache:
                    # Move to end for LRU behavior
                    self._ffprobe_cache.move_to_end(cache_key)
                    logging.debug(f"Using cached ffprobe result for {filepath}")
                    return self._ffprobe_cache[cache_key]
            except (OSError, IOError) as e:
                logging.debug(f"Cache lookup failed for {filepath}: {str(e)}")

        # 3. Prepare ffprobe command with properly escaped filepath
        ffprobe_bin = os.path.join(
            self.config["ffmpeg_location"], "ffprobe" + (".exe" if is_windows() else "")
        )

        # Check if ffprobe exists
        if not os.path.exists(ffprobe_bin):
            logging.error(f"ffprobe binary not found at: {ffprobe_bin}")
            return {}

        # Build command based on mode
        cmd = [
            ffprobe_bin,
            "-v",
            "quiet",
            "-print_format",
            "json",
        ]

        # In fast mode, only get format info which is much faster
        if fast_mode:
            cmd.extend(["-show_format"])
        else:
            cmd.extend(["-show_format", "-show_streams"])

        # Add the filepath at the end
        cmd.append(filepath)

        # 4. Run ffprobe with comprehensive error handling
        try:
            # Use a process context for better resource management
            start_time = time.time()
            logging.debug(
                f"Running ffprobe on {filepath} ({'fast mode' if fast_mode else 'full mode'})"
            )

            # Run process with proper encoding handling
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding="utf-8",
                errors="replace",  # Handle encoding errors gracefully
            )

            duration = time.time() - start_time
            logging.debug(f"ffprobe completed in {duration:.2f} seconds")

            if result.returncode != 0:
                error_msg = result.stderr.strip() if result.stderr else "Unknown error"
                logging.error(
                    f"ffprobe failed with code {result.returncode}: {error_msg}"
                )
                return {}

            # Parse output with error handling
            if not result.stdout.strip():
                logging.error("ffprobe returned empty output")
                return {}

            # Parse JSON with specific error handling
            try:
                data = json.loads(result.stdout)
            except json.JSONDecodeError as e:
                logging.error(
                    f"ffprobe returned invalid JSON: {e} (first 100 chars: {result.stdout[:100]})"
                )
                return {}

            # 5. Cache the successful result if caching is enabled
            if cache:
                try:
                    file_stat = os.stat(filepath)
                    cache_key = f"{filepath}:{file_stat.st_size}:{file_stat.st_mtime}"

                    # Use OrderedDict for LRU behavior
                    self._ffprobe_cache[cache_key] = data
                    self._ffprobe_cache.move_to_end(cache_key)

                    # Limit cache size to prevent memory issues (keep most recent 100 entries)
                    if len(self._ffprobe_cache) > 100:
                        # Remove oldest entries (OrderedDict makes this efficient)
                        while len(self._ffprobe_cache) > 100:
                            self._ffprobe_cache.popitem(last=False)
                except Exception as e:
                    logging.debug(f"Failed to cache ffprobe result: {str(e)}")

            return data

        except subprocess.TimeoutExpired:
            logging.error(f"ffprobe timed out after {timeout} seconds for {filepath}")
            return {}
        except (OSError, IOError) as e:
            logging.error(f"ffprobe OS/IO error: {str(e)}")
            return {}
        except Exception as e:
            logging.error(f"ffprobe unexpected error: {str(e)}")
            return {}

    def _run_ffprobe_with_retry(
        self, filepath: str, max_retries: int = 3, retry_delay: float = 1.0
    ) -> Dict[str, Any]:
        """
        Run ffprobe with robust error handling and retry logic.

        Args:
            filepath: Path to media file to analyze
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds

        Returns:
            Dictionary containing ffprobe results or empty dict on failure
        """
        for attempt in range(max_retries):
            # First ensure the file exists
            if not self._ensure_file_exists(filepath, timeout=3.0):
                logging.warning(
                    f"FFprobe attempt {attempt+1}/{max_retries}: File not found: {filepath}"
                )
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                return {}

            try:
                ffprobe_bin = os.path.join(self.config["ffmpeg_location"], "ffprobe")
                cmd = [
                    ffprobe_bin,
                    "-v",
                    "quiet",
                    "-print_format",
                    "json",
                    "-show_format",
                    "-show_streams",
                    filepath,
                ]

                logging.debug(f"Running ffprobe: {' '.join(cmd)}")
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=10,
                    encoding="utf-8",
                    errors="replace",  # Handle encoding errors gracefully
                )

                if result.returncode != 0:
                    logging.warning(
                        f"FFprobe failed (attempt {attempt+1}/{max_retries}): {result.stderr}"
                    )
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        continue
                    return {}

                try:
                    return json.loads(result.stdout)
                except json.JSONDecodeError as e:
                    logging.warning(f"FFprobe JSON parse error: {e}")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        continue
                    return {}

            except subprocess.TimeoutExpired:
                logging.warning(f"FFprobe timeout (attempt {attempt+1}/{max_retries})")
            except Exception as e:
                logging.warning(
                    f"FFprobe error (attempt {attempt+1}/{max_retries}): {str(e)}"
                )

            # Wait before retry
            if attempt < max_retries - 1:
                time.sleep(retry_delay)

        logging.error(
            f"FFprobe failed after {max_retries} attempts on file: {filepath}"
        )
        return {}


def load_config() -> Dict[str, Any]:
    """Load configuration from file with defaults and error handling"""
    try:
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        config = DEFAULT_CONFIG.copy()

    # Ensure all default keys are present
    for key, value in DEFAULT_CONFIG.items():
        config.setdefault(key, value)

    # Ensure organization templates are complete
    if "organization_templates" in config:
        for key, value in DEFAULT_ORGANIZATION_TEMPLATES.items():
            config["organization_templates"].setdefault(key, value)
    else:
        config["organization_templates"] = DEFAULT_ORGANIZATION_TEMPLATES.copy()

    return config


def list_supported_sites() -> bool:
    """Display a clean, cool, and organized list of supported sites using a pager with clear separators."""
    import pydoc
    from pathlib import Path

    sites_file = Path("Supported-sites.txt")
    if not sites_file.exists():
        print(
            f"{Fore.RED}Supported-sites.txt not found. Cannot list supported sites.{Style.RESET_ALL}"
        )
        return False

    try:
        with sites_file.open("r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
    except Exception as e:
        print(f"{Fore.RED}Error reading Supported-sites.txt: {e}{Style.RESET_ALL}")
        return False

    # Skip header lines if they start with "below is a list"
    header_end = 0
    for i, line in enumerate(lines):
        if line.lower().startswith("below is a list"):
            header_end = i + 1
            break
    sites = lines[header_end:]

    output_lines = []
    # Horizontal border line for clear separation
    border = f"{Fore.CYAN}" + "─" * 60 + f"{Style.RESET_ALL}"
    title = f"{Fore.GREEN}{'SUPPORTED SITES':^60}{Style.RESET_ALL}"
    output_lines.append(border)
    output_lines.append(title)
    output_lines.append(border)
    output_lines.append("")

    total_sites = 0
    current_category = None
    # Prepare a separator to insert between categories
    category_separator = f"\n{border}\n"
    for line in sites:
        if line.startswith('"'):
            continue
        if ":" in line:
            category, site = map(str.strip, line.split(":", 1))
            cat_upper = category.upper()
            if current_category != cat_upper:
                # Add a separator if this isn't the first category
                if current_category is not None:
                    output_lines.append(category_separator)
                current_category = cat_upper
                output_lines.append(
                    f"{Fore.MAGENTA}{current_category:^60}{Style.RESET_ALL}"
                )
            if site:
                output_lines.append(f"{Fore.YELLOW} • {site}{Style.RESET_ALL}")
                total_sites += 1
        else:
            output_lines.append(f"{Fore.YELLOW} • {line}{Style.RESET_ALL}")
            total_sites += 1

    output_lines.append("")
    output_lines.append(
        f"{Fore.CYAN}Total supported sites: {total_sites}{Style.RESET_ALL}"
    )
    output_lines.append(border)

    final_output = "\n".join(output_lines)
    pydoc.pager(final_output)
    return True


def test_functionality() -> bool:
    """Run basic tests to verify functionality"""
    print(f"{Fore.CYAN}Running basic tests...{Style.RESET_ALL}")
    try:
        # Test configuration initialization
        print(f"{Fore.CYAN}Testing configuration...{Style.RESET_ALL}")
        config = initialize_config(force_validation=True)

        # Check if FFmpeg is available in the config
        if not config.get("ffmpeg_location") or not validate_ffmpeg_path(
            config["ffmpeg_location"]
        ):
            print(f"{Fore.RED}FFmpeg not found or invalid!{Style.RESET_ALL}")
            return False
        # Wait briefly for background validation to complete
        for _ in range(10):  # Wait up to 1 second
            if _ffmpeg_validated:
                break
            time.sleep(0.1)
        if _ffmpeg_validated:
            print(
                f"{Fore.GREEN}FFmpeg found at: {config['ffmpeg_location']}{Style.RESET_ALL}"
            )
        else:
            print(
                f"{Fore.YELLOW}FFmpeg validation still in progress...{Style.RESET_ALL}"
            )

        print(
            f"{Fore.GREEN}FFmpeg found at: {config['ffmpeg_location']}{Style.RESET_ALL}"
        )

        print(
            f"{Fore.GREEN}yt-dlp version: {yt_dlp.version.__version__}{Style.RESET_ALL}"
        )

        # Test download manager
        print(f"{Fore.CYAN}Testing download manager...{Style.RESET_ALL}")
        config = load_config()
        manager = DownloadManager(config)
        manager.interactive_mode()
        print(f"{Fore.GREEN}Download manager initialized successfully{Style.RESET_ALL}")

        return True
    except Exception as e:
        print(f"{Fore.RED}Test failed: {str(e)}{Style.RESET_ALL}")
        return False


def main() -> None:
    """Enhanced main function with new CLI options and error management"""
    # Optimized early handling of special args
    if "--version" in sys.argv:
        print(f"Snatch v{VERSION}")
        sys.exit(0)

    if "--speedtest" in sys.argv:
        run_speedtest()
        sys.exit(0)

    if "--test" in sys.argv:
        print(f"\n{Fore.CYAN}╔{'═' * 40}╗")
        print("║          Snatch Test Suite              ║")
        print(f"╚{'═' * 40}╝{Style.RESET_ALL}")
        sys.exit(0 if test_functionality() else 1)

    if len(sys.argv) == 2 and sys.argv[1] == "--list-sites":
        list_supported_sites()
        sys.exit(0)

    if "--interactive" in sys.argv or "-i" in sys.argv:
        try:
            # Use async initialization to avoid UI delay
            config = initialize_config_async()
            manager = DownloadManager(config)
            manager.interactive_mode()
            sys.exit(0)
        except Exception as e:
            print(
                f"{Fore.RED}Error starting interactive mode: {str(e)}{Style.RESET_ALL}"
            )
            sys.exit(1)

    if len(sys.argv) == 1:
        try:
            # Use async initialization to avoid UI delay
            config = initialize_config_async()
            manager = DownloadManager(config)
            manager.interactive_mode()
            sys.exit(0)
        except Exception as e:
            print(
                f"{Fore.RED}Error starting interactive mode: {str(e)}{Style.RESET_ALL}"
            )
            sys.exit(1)

    parser = argparse.ArgumentParser(
        description="Snatch - Download Anything!",
        formatter_class=CustomHelpFormatter,
        epilog=EXAMPLES,
    )
    parser.add_argument("urls", nargs="*", help="URLs to download")
    parser.add_argument("--audio-only", action="store_true", help="Download audio only")
    parser.add_argument(
        "--resolution", type=str, help="Specify video resolution (e.g., 1080)"
    )
    parser.add_argument("--format-id", type=str, help="Select specific format IDs")
    parser.add_argument("--filename", type=str, help="Specify custom filename")
    parser.add_argument(
        "--audio-format",
        type=str,
        choices=["opus", "mp3", "flac", "wav", "m4a"],
        default="opus",
        help="Specify audio format",
    )
    parser.add_argument(
        "--output-dir", type=str, help="Specify custom output directory"
    )
    parser.add_argument(
        "--list-sites", action="store_true", help="List all supported sites"
    )
    parser.add_argument(
        "--version", action="store_true", help="Show version information"
    )
    parser.add_argument(
        "--test", action="store_true", help="Run basic tests to verify functionality"
    )
    parser.add_argument(
        "--interactive", "-i", action="store_true", help="Run in interactive mode"
    )
    # New CLI options:
    parser.add_argument(
        "--resume", action="store_true", help="Resume interrupted downloads"
    )
    parser.add_argument("--stats", action="store_true", help="Show download statistics")
    parser.add_argument(
        "--system-stats", action="store_true", help="Show system resource stats"
    )
    parser.add_argument(
        "--no-cache", action="store_true", help="Skip using cached info"
    )
    parser.add_argument(
        "--no-retry", action="store_true", help="Do not retry failed downloads"
    )
    parser.add_argument(
        "--throttle", type=str, help="Limit download speed (e.g., 500KB/s)"
    )
    parser.add_argument(
        "--aria2c", action="store_true", help="Use aria2c for downloading"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable detailed output for troubleshooting",
    )
    parser.add_argument(
        "--detailed-progress",
        action="store_true",
        help="Show detailed progress with real-time statistics",
    )
    # New organize option
    parser.add_argument(
        "--organize",
        action="store_true",
        help="Organize files into directories based on metadata",
    )
    parser.add_argument(
        "--no-organize",
        action="store_true",
        help="Disable file organization (overrides config)",
    )
    parser.add_argument(
        "--org-template",
        type=str,
        help='Custom organization template (e.g. "{uploader}/{year}/{title}")',
    )
    # Audio channels option
    parser.add_argument(
        "--audio-channels",
        type=int,
        choices=[2, 8],
        default=2,
        help="Audio channels: 2 (stereo) or 8 (7.1 surround)",
    )
    parser.add_argument(
        "--non-interactive", action="store_true", help="Disable interactive prompts"
    )
    # New option to force FFmpeg validation
    parser.add_argument(
        "--validate-ffmpeg", action="store_true", help="Force validation of FFmpeg path"
    )
    # New option to apply all config updates
    parser.add_argument(
        "--update-config",
        action="store_true",
        help="Apply all recommended configuration updates",
    )
    parser.add_argument(
        "--speedtest",
        action="store_true",
        help="Run network speed test to optimize download settings",
    )
    parser.add_argument(
        "--test-formats",
        action="store_true",
        help="Test all available formats (slower but may find better quality)",
    )
    parser.add_argument(
        "--fast", action="store_true", help="Use fast format selection (default)"
    )
    args = parser.parse_args()

    if args.version:
        print(f"Snatch v{VERSION}")
        sys.exit(0)

    if args.test:
        print(f"\n{Fore.CYAN}╔{'═' * 40}╗")
        print("║          Snatch Test Suite              ║")
        print(f"╚{'═' * 40}╝{Style.RESET_ALL}")
        sys.exit(0 if test_functionality() else 1)

    if args.list_sites:
        list_supported_sites()
        sys.exit(0)

    # Setup logging level if verbose is enabled
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
        logging.getLogger().setLevel(logging.DEBUG)
        print(
            f"{Fore.CYAN}Verbose mode enabled. Detailed logging active.{Style.RESET_ALL}"
        )

    # Initialize and validate configuration
    force_validation = args.validate_ffmpeg or args.update_config
    try:
        # Use async initialization for better UX
        config = initialize_config_async(force_validation=force_validation)
    except FileNotFoundError as e:
        print(f"{Fore.RED}Error: {str(e)}")
        print(
            f"{Fore.RED}Please install FFmpeg and try again, or specify a valid path in config.json"
        )
        sys.exit(1)

    # Add verbose and detailed_progress setting to config
    config["verbose"] = args.verbose
    config["detailed_progress"] = args.detailed_progress

    if args.output_dir:
        if args.audio_only:
            config["audio_output"] = args.output_dir
        else:
            config["video_output"] = args.output_dir

    # Handle organization settings
    if args.organize:
        config["organize"] = True
    elif args.no_organize:
        config["organize"] = False

    # Handle custom organization template
    if args.org_template:
        content_type = "audio" if args.audio_only else "video"
        config["organization_templates"][content_type] = args.org_template

    # Initialize the download manager with our validated config
    try:
        manager = DownloadManager(config)
    except Exception as e:
        print(f"{Fore.RED}Error initializing download manager: {str(e)}")
        sys.exit(1)

    # Check for config updates in the background
    if not args.update_config:  # Don't show if already applying updates
        check_for_updates()

    # Show system stats if requested
    if args.system_stats:
        display_system_stats()

    # Create a download stats tracker
    download_stats = DownloadStats()

    if args.interactive:
        manager.interactive_mode()
        sys.exit(0)

    if args.urls:
        # Prepare download options
        download_options = {
            "audio_only": args.audio_only,
            "resolution": args.resolution,
            "format_id": args.format_id,
            "filename": args.filename,
            "audio_format": args.audio_format,
            "resume": args.resume,
            "no_cache": args.no_cache,
            "no_retry": args.no_retry,
            "throttle": args.throttle,
            "use_aria2c": args.aria2c,  # Make sure aria2c is passed properly
            "audio_channels": args.audio_channels,  # Pass audio channels configuration
            "non_interactive": args.non_interactive,  # Pass non-interactive flag
            "test_all_formats": args.test_formats,  # Add the new option
        }

        start_time = time.time()
        results = manager.batch_download(args.urls, **download_options)

        # Track download results in stats
        success_count = sum(1 for r in results if r)
        failure_count = len(results) - success_count

        # Report stats if requested
        if args.stats:
            # Add basic stats from the results
            for _ in range(success_count):
                download_stats.add_download(True)
            for _ in range(failure_count):
                download_stats.add_download(False)

            # Calculate duration
            download_stats.total_time = time.time() - start_time

            # Display stats
            download_stats.display()
    else:
        print(
            f"{Fore.RED}No URLs provided. Use --interactive for interactive mode.{Style.RESET_ALL}"
        )
        sys.exit(1)


def display_system_stats():
    """Display detailed system resource statistics"""
    print(f"\n{Fore.CYAN}{'=' * 40}")
    print(f"{Fore.GREEN}SYSTEM STATISTICS{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'=' * 40}{Style.RESET_ALL}\n")

    # CPU information
    cpu_percent = psutil.cpu_percent(interval=1)
    cpu_count = psutil.cpu_count(logical=False)
    cpu_logical = psutil.cpu_count(logical=True)
    print(f"{Fore.YELLOW}CPU Usage:{Style.RESET_ALL} {cpu_percent}%")
    print(
        f"{Fore.YELLOW}CPU Cores:{Style.RESET_ALL} {cpu_count} physical, {cpu_logical} logical"
    )

    # Memory information
    mem = psutil.virtual_memory()
    print(f"\n{Fore.YELLOW}Memory Usage:{Style.RESET_ALL} {mem.percent}%")
    print(f"{Fore.YELLOW}Total Memory:{Style.RESET_ALL} {mem.total / (1024**3):.2f} GB")
    print(
        f"{Fore.YELLOW}Available Memory:{Style.RESET_ALL} {mem.available / (1024**3):.2f} GB"
    )
    print(f"{Fore.YELLOW}Used Memory:{Style.RESET_ALL} {mem.used / (1024**3):.2f} GB")

    # Disk information
    print(f"\n{Fore.YELLOW}Disk Information:{Style.RESET_ALL}")
    for part in psutil.disk_partitions(all=False):
        if os.name == "nt" and "cdrom" in part.opts or part.fstype == "":
            # Skip CD-ROM drives with no disk or other special drives
            continue
        usage = psutil.disk_usage(part.mountpoint)
        print(f"  {Fore.CYAN}Drive {part.mountpoint}{Style.RESET_ALL}")
        print(f"    Total: {usage.total / (1024**3):.2f} GB")
        print(f"    Used: {usage.used / (1024**3):.2f} GB ({usage.percent}%)")
        print(f"    Free: {usage.free / (1024**3):.2f} GB")


class DownloadStats:
    """
    Enhanced download statistics tracker with optimized monitoring and comprehensive reporting.

    This implementation features:
    - Memory-efficient statistics tracking using running aggregates
    - Comprehensive performance metrics (avg/median/peak speeds)
    - Time-series analysis capabilities
    - Thread-safe operation for concurrent downloads
    - Export capabilities for further analysis
    - Adaptive visualization based on terminal capabilities
    """

    def __init__(self, keep_history: bool = False, history_limit: int = 100):
        # Core statistics with optimized memory usage
        self.total_downloads = 0
        self.successful_downloads = 0
        self.failed_downloads = 0
        self.total_bytes = 0
        self.total_time = 0.0
        self.start_time = time.time()

        # Performance tracking with running aggregates
        self.peak_speed = 0.0
        self._speed_sum = 0.0
        self._squared_speed_sum = 0.0  # For calculating variance/std dev

        # Thread safety
        self._lock = threading.RLock()

        # Optional history tracking for time-series analysis
        self.keep_history = keep_history
        self.history_limit = history_limit
        self.download_history = [] if keep_history else None

        # Terminal capabilities detection for optimal display
        self.term_width = min(shutil.get_terminal_size().columns, 100)

        # Cached properties for efficient repeated access
        self._cached = {}
        self._last_cache_time = 0
        self._cache_ttl = 1.0  # Recalculate values after 1 second

    def add_download(
        self, success: bool, size_bytes: int = 0, duration: float = 0.0
    ) -> None:
        """
        Record a completed download with thread-safe statistics updates.

        Args:
            success: Whether the download completed successfully
            size_bytes: Size of the downloaded file in bytes
            duration: Duration of the download in seconds
        """
        with self._lock:
            self.total_downloads += 1

            # Clear cache on new data
            self._cached.clear()

            if success:
                self.successful_downloads += 1

                if size_bytes > 0 and duration > 0:
                    # Update aggregated statistics
                    self.total_bytes += size_bytes
                    self.total_time += duration

                    # Calculate speed and update running statistics
                    speed = size_bytes / max(
                        duration, 0.001
                    )  # Prevent division by zero
                    self._speed_sum += speed
                    self._squared_speed_sum += speed * speed
                    self.peak_speed = max(self.peak_speed, speed)

                    # Store history if enabled
                    if self.keep_history:
                        self.download_history.append(
                            {
                                "timestamp": time.time(),
                                "size": size_bytes,
                                "duration": duration,
                                "speed": speed,
                            }
                        )

                        # Auto-prune history to limit memory usage
                        if len(self.download_history) > self.history_limit:
                            self.download_history = self.download_history[
                                -self.history_limit :
                            ]
            else:
                self.failed_downloads += 1

    @property
    def average_speed(self) -> float:
        """Calculate average download speed with minimal computational overhead."""
        with self._lock:
            # Use cached value if available and recent
            if (
                "average_speed" in self._cached
                and time.time() - self._last_cache_time < self._cache_ttl
            ):
                return self._cached["average_speed"]

            if self.successful_downloads == 0:
                return 0.0

            # Two calculation methods:
            # 1. Based on individual download speeds (more accurate)
            # 2. Based on aggregate bytes/time (fallback)
            if self.keep_history and self.download_history:
                avg_speed = self._speed_sum / self.successful_downloads
            elif self.total_time > 0:
                avg_speed = self.total_bytes / self.total_time
            else:
                avg_speed = 0.0

            # Cache the result
            self._cached["average_speed"] = avg_speed
            self._last_cache_time = time.time()
            return avg_speed

    @property
    def median_speed(self) -> float:
        """Calculate median download speed (central tendency with outlier resistance)."""
        with self._lock:
            if (
                "median_speed" in self._cached
                and time.time() - self._last_cache_time < self._cache_ttl
            ):
                return self._cached["median_speed"]

            if (
                not self.keep_history
                or not self.download_history
                or len(self.download_history) == 0
            ):
                return self.average_speed

            speeds = sorted(item["speed"] for item in self.download_history)
            n = len(speeds)

            # Calculate true median
            if n % 2 == 0:
                median = (speeds[n // 2 - 1] + speeds[n // 2]) / 2
            else:
                median = speeds[n // 2]

            self._cached["median_speed"] = median
            return median

    @property
    def std_deviation(self) -> float:
        """Calculate standard deviation of download speeds (for consistency analysis)."""
        with self._lock:
            if self.successful_downloads < 2:
                return 0.0

            # Calculate variance using the computational formula:
            # var = E(X²) - (E(X))²
            mean_speed = self._speed_sum / self.successful_downloads
            mean_squared = self._squared_speed_sum / self.successful_downloads
            variance = mean_squared - (mean_speed * mean_speed)

            # Handle numerical precision issues that can cause small negative values
            if variance <= 0:
                return 0.0

            return math.sqrt(variance)

    @property
    def success_rate(self) -> float:
        """Calculate percentage of successful downloads."""
        with self._lock:
            if self.total_downloads == 0:
                return 0.0
            return (self.successful_downloads / self.total_downloads) * 100

    @property
    def session_duration(self) -> float:
        """Get total duration of the download session in seconds."""
        return time.time() - self.start_time

    def _format_size(self, bytes_value: float) -> str:
        """Format file size in human-readable units."""
        if bytes_value == 0:
            return "0 B"

        units = ["B", "KB", "MB", "GB", "TB"]
        unit_index = 0

        while bytes_value >= 1024 and unit_index < len(units) - 1:
            bytes_value /= 1024
            unit_index += 1

        precision = 0 if unit_index == 0 else 2
        return f"{bytes_value:.{precision}f} {units[unit_index]}"

    def _format_speed(self, speed: float) -> str:
        """Format speed with appropriate units and precision."""
        return f"{self._format_size(speed)}/s"

    def _format_time(self, seconds: float) -> str:
        """Format time duration in a human-readable format."""
        if seconds < 60:
            return f"{seconds:.1f} seconds"

        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        if hours > 0:
            return f"{int(hours)}h {int(minutes)}m {int(seconds)}s"
        else:
            return f"{int(minutes)}m {int(seconds)}s"

    def display(self, detailed: bool = False, graph: bool = False) -> None:
        """
        Display formatted download statistics with optional detailed analysis.

        Args:
            detailed: Show additional statistics and analysis
            graph: Display visual performance graphs (when supported)
        """
        with self._lock:
            bar_length = min(50, self.term_width - 30)

            # Calculate core statistics
            avg_speed = self.average_speed

            # Header
            print(f"\n{Fore.CYAN}{'═' * self.term_width}")
            print(
                f"{Fore.GREEN}{'DOWNLOAD STATISTICS SUMMARY':^{self.term_width}}{Style.RESET_ALL}"
            )
            print(f"{Fore.CYAN}{'═' * self.term_width}{Style.RESET_ALL}\n")

            # Core metrics
            print(
                f"  {Fore.YELLOW}Session Duration:{Style.RESET_ALL} {self._format_time(self.session_duration)}"
            )
            print(
                f"  {Fore.YELLOW}Total Downloads:{Style.RESET_ALL} {self.total_downloads}"
            )
            print(
                f"  {Fore.YELLOW}Successful:{Style.RESET_ALL} {self.successful_downloads} "
                + f"({self.success_rate:.1f}%)"
            )
            print(f"  {Fore.YELLOW}Failed:{Style.RESET_ALL} {self.failed_downloads}")

            if self.successful_downloads > 0:
                print(
                    f"\n  {Fore.YELLOW}Total Downloaded:{Style.RESET_ALL} {self._format_size(self.total_bytes)}"
                )
                print(
                    f"  {Fore.YELLOW}Average Speed:{Style.RESET_ALL} {self._format_speed(avg_speed)}"
                )
                print(
                    f"  {Fore.YELLOW}Peak Speed:{Style.RESET_ALL} {self._format_speed(self.peak_speed)}"
                )

                # Create visual speed bar (relative to peak)
                if avg_speed > 0:
                    ratio = min(1.0, avg_speed / (self.peak_speed or 1))
                    filled_len = int(bar_length * ratio)
                    speed_bar = f"{Fore.GREEN}{'█' * filled_len}{Style.RESET_ALL}{'░' * (bar_length - filled_len)}"
                    print(f"\n  Speed: {speed_bar} {ratio*100:.1f}% of peak")

            # Detailed statistics
            if detailed and self.successful_downloads > 1:
                print(f"\n{Fore.CYAN}{'─' * self.term_width}")
                print(f"{Fore.GREEN}DETAILED METRICS{Style.RESET_ALL}")

                # Show more advanced statistics
                print(
                    f"\n  {Fore.YELLOW}Median Speed:{Style.RESET_ALL} {self._format_speed(self.median_speed)}"
                )
                print(
                    f"  {Fore.YELLOW}Speed Deviation:{Style.RESET_ALL} {self._format_speed(self.std_deviation)}"
                )
                print(
                    f"  {Fore.YELLOW}Download Efficiency:{Style.RESET_ALL} "
                    + f"{self.total_bytes / (self.total_time or 1) / avg_speed * 100:.1f}%"
                )

                # Time-series analysis for trend detection
                if self.keep_history and len(self.download_history) >= 5:
                    print(f"\n  {Fore.YELLOW}Download Rate Trend:{Style.RESET_ALL}")

                    # Calculate trend by comparing first and last third of downloads
                    history = self.download_history
                    third_size = max(1, len(history) // 3)

                    early_speeds = [item["speed"] for item in history[:third_size]]
                    recent_speeds = [item["speed"] for item in history[-third_size:]]

                    early_avg = sum(early_speeds) / len(early_speeds)
                    recent_avg = sum(recent_speeds) / len(recent_speeds)

                    change_pct = (
                        ((recent_avg / early_avg) - 1) * 100 if early_avg > 0 else 0
                    )

                    if change_pct > 10:
                        trend = f"{Fore.GREEN}Improving ({change_pct:.1f}%↑){Style.RESET_ALL}"
                    elif change_pct < -10:
                        trend = f"{Fore.RED}Declining ({abs(change_pct):.1f}%↓){Style.RESET_ALL}"
                    else:
                        trend = (
                            f"{Fore.YELLOW}Stable ({change_pct:+.1f}%){Style.RESET_ALL}"
                        )

                    print(f"    {trend}")

                    # Visual trend graph if requested
                    if graph and self.term_width >= 80:
                        self._draw_trend_graph()

            # Footer
            print(f"\n{Fore.CYAN}{'═' * self.term_width}{Style.RESET_ALL}")

    def _draw_trend_graph(self, height: int = 5) -> None:
        """Draw a simple ASCII trend graph of download speeds over time."""
        if not self.keep_history or len(self.download_history) < 5:
            return

        # Get speed values and normalize
        speeds = [item["speed"] for item in self.download_history]
        max_speed = max(speeds)
        if max_speed <= 0:
            return

        # Create graph width based on terminal
        width = min(self.term_width - 8, len(speeds))

        # Sample points to fit width
        if len(speeds) > width:
            sample_rate = len(speeds) / width
            sampled_speeds = []
            for i in range(width):
                start_idx = int(i * sample_rate)
                end_idx = int((i + 1) * sample_rate)
                segment = speeds[start_idx : max(start_idx + 1, end_idx)]
                sampled_speeds.append(sum(segment) / len(segment))
            speeds = sampled_speeds

        # Draw the graph
        print(f"\n    Speed over time ({self._format_speed(max_speed)} max):")
        print(f"    {Fore.CYAN}┌{'─' * width}┐{Style.RESET_ALL}")

        for h in range(height - 1, -1, -1):
            row = "    " + f"{Fore.CYAN}│{Style.RESET_ALL}"
            for speed in speeds:
                # Calculate if this point should be plotted in this row
                threshold = max_speed * (h / (height - 1)) if height > 1 else 0
                if speed >= threshold:
                    row += f"{Fore.GREEN}█{Style.RESET_ALL}"
                else:
                    row += " "
            row += f"{Fore.CYAN}│{Style.RESET_ALL}"
            print(row)

        print(f"    {Fore.CYAN}└{'─' * width}┘{Style.RESET_ALL}")
        print(f"    {Fore.CYAN}Start{' ' * (width - 9)}End{Style.RESET_ALL}")

    def export(self, format_type: str = "json", filename: str = None) -> bool:
        """
        Export statistics to a file for further analysis.

        Args:
            format_type: Export format ('json' or 'csv')
            filename: Target filename, or auto-generated if None

        Returns:
            Success status
        """
        if not filename:
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            filename = f"download_stats_{timestamp}.{format_type}"

        try:
            if format_type.lower() == "json":
                return self._export_json(filename)
            elif format_type.lower() == "csv":
                return self._export_csv(filename)
            else:
                logging.error(f"Unsupported export format: {format_type}")
                return False
        except Exception as e:
            logging.error(f"Failed to export statistics: {str(e)}")
            return False

    def _export_json(self, filename: str) -> bool:
        """Export statistics as JSON."""
        with self._lock:
            data = {
                "timestamp": time.time(),
                "date": time.strftime("%Y-%m-%d %H:%M:%S"),
                "session_duration": self.session_duration,
                "downloads": {
                    "total": self.total_downloads,
                    "successful": self.successful_downloads,
                    "failed": self.failed_downloads,
                    "success_rate": self.success_rate,
                },
                "data": {
                    "total_bytes": self.total_bytes,
                    "total_time": self.total_time,
                },
                "performance": {
                    "average_speed": self.average_speed,
                    "median_speed": self.median_speed,
                    "peak_speed": self.peak_speed,
                    "std_deviation": self.std_deviation,
                },
            }

            # Include download history if available
            if self.keep_history and self.download_history:
                data["history"] = self.download_history

            with open(filename, "w") as f:
                json.dump(data, f, indent=2)

            print(f"{Fore.GREEN}Statistics exported to {filename}{Style.RESET_ALL}")
            return True

    def _export_csv(self, filename: str) -> bool:
        """Export download history as CSV for spreadsheet analysis."""
        if not self.keep_history or not self.download_history:
            print(
                f"{Fore.YELLOW}No download history to export to CSV.{Style.RESET_ALL}"
            )
            return False

        import csv

        with open(filename, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                ["Timestamp", "Size (bytes)", "Duration (s)", "Speed (B/s)"]
            )

            for item in self.download_history:
                writer.writerow(
                    [
                        time.strftime(
                            "%Y-%m-%d %H:%M:%S", time.localtime(item["timestamp"])
                        ),
                        item["size"],
                        item["duration"],
                        item["speed"],
                    ]
                )

        print(f"{Fore.GREEN}Download history exported to {filename}{Style.RESET_ALL}")
        return True

    def reset(self) -> None:
        """Reset all statistics while maintaining the same start time."""
        with self._lock:
            # Preserve the original start time but reset everything else
            original_start = self.start_time
            self.__init__(
                keep_history=self.keep_history, history_limit=self.history_limit
            )
            self.start_time = original_start


class DetailedProgressDisplay:
    """
    Advanced progress display with real-time statistics, dynamic rendering, and optimized performance.

    Features:
    - Adaptive terminal rendering with responsive layout
    - Efficient update throttling with minimal CPU usage
    - Rich statistics with smoothed metrics
    - Multi-line display with color-coded sections
    - Graceful degradation in limited terminals
    - Memory-efficient operation with minimal string allocations
    """

    def __init__(
        self,
        total_size: int = 0,
        title: str = "Download",
        detailed: bool = False,
        show_eta: bool = True,
    ):
        # Core metrics
        self.total_size = total_size  # Total size in bytes
        self.downloaded = 0  # Current downloaded bytes
        self.title = title  # Display title
        self.start_time = 0  # Start time (set on first display)
        self._lock = threading.RLock()  # Thread-safe lock for shared state
        # Display settings
        self.detailed = detailed  # Whether to show detailed stats
        self.show_eta = show_eta  # Whether to show ETA
        self.max_width = 0  # Terminal width (determined on start)
        self.bar_style = "gradient"  # Progress bar style (gradient, solid, pulse)
        self.bar_size = 40  # Default progress bar width
        self.smooth_speed = True  # Whether to use smoothed speed
        self.last_lines = 0  # Number of lines in previous display
        self.enabled = True  # Whether display is enabled

        # Performance optimization
        self.last_update_time = 0  # Last display update time
        self.min_update_interval = 0.2  # Minimum seconds between visual updates
        self._cached_display = {}  # Cache for formatted components
        self._cache_valid_until = 0  # Timestamp when cache expires
        self._first_display = True  # Flag for first display
        self._task_started = False  # Task started flag
        self._finished = False  # Task finished flag

        # Statistics tracking
        self.current_speed = 0  # Current speed (bytes/second)
        self.avg_speed = 0  # Average speed (bytes/second)
        self.peak_speed = 0  # Peak speed (bytes/second)
        self.eta_seconds = 0  # Estimated time remaining in seconds

        # Speed sampling for smoothing
        self._speed_samples = []  # List of recent speed samples
        self._max_samples = 20  # Number of samples to keep
        self._last_sample_time = 0  # Time of last sample
        self._last_sample_bytes = 0  # Bytes at last sample
        self._sample_interval = 0.5  # Seconds between samples

        # Terminal state management
        self._supports_ansi = (
            self._detect_ansi_support()
        )  # Whether terminal supports ANSI
        self._cursor_hidden = False  # Whether cursor is hidden

    def _detect_ansi_support(self) -> bool:
        """Detect if terminal supports ANSI escape sequences"""
        # Default to True for most platforms; Windows 10+ supports ANSI
        if os.name == "nt":
            # Check Windows version - 10 and later support ANSI with colorama
            try:
                version = platform.version().split(".")
                major_version = int(version[0])
                return major_version >= 10
            except (IndexError, ValueError):
                return False
        return True

    def _get_terminal_width(self) -> int:
        """Get terminal width with fallback and caching"""
        try:
            return shutil.get_terminal_size().columns
        except (AttributeError, OSError):
            return 80

    def _format_size(self, size_bytes: int) -> str:
        """Format size in human-readable format with appropriate precision"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes/1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes/(1024*1024):.2f} MB"
        else:
            return f"{size_bytes/(1024*1024*1024):.2f} GB"

    def _format_time(self, seconds: float) -> str:
        """Format time in human-readable format with adaptive precision"""
        if seconds < 0:
            return "Unknown"
        elif seconds < 10:
            return f"{seconds:.1f}s"  # Higher precision for short times
        elif seconds < 60:
            return f"{seconds:.0f}s"
        elif seconds < 3600:
            minutes, seconds = divmod(seconds, 60)
            return f"{int(minutes)}m {int(seconds)}s"
        else:
            hours, remainder = divmod(seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            if hours < 10:  # Show seconds only for shorter durations
                return f"{int(hours)}h {int(minutes)}m {int(seconds)}s"
            else:
                return f"{int(hours)}h {int(minutes)}m"

    def _update_speed_metrics(self) -> None:
        """Update speed metrics with smoothing and ETA calculation"""
        # Skip if no data yet
        if not self._task_started or self.total_size <= 0:
            return

        now = time.time()
        elapsed = now - self.start_time

        if elapsed <= 0:
            return

        # Calculate instantaneous speed
        instant_speed = self.downloaded / elapsed

        # Add speed sample for smoothing if enough time has passed
        if now - self._last_sample_time >= self._sample_interval:
            bytes_since_sample = self.downloaded - self._last_sample_bytes
            time_since_sample = now - self._last_sample_time

            if time_since_sample > 0:
                # Calculate speed for this sample interval
                sample_speed = bytes_since_sample / time_since_sample

                with self._lock:  # Add lock protection for thread-safe list modification
                    self._speed_samples.append(sample_speed)
                    # Limit samples list size
                    if len(self._speed_samples) > self._max_samples:
                        self._speed_samples.pop(0)

                # Limit samples list size
                if len(self._speed_samples) > self._max_samples:
                    self._speed_samples.pop(0)

                # Update last sample info
                self._last_sample_time = now
                self._last_sample_bytes = self.downloaded

        # Calculate smoothed speed if samples are available, otherwise use instant
        if self.smooth_speed and len(self._speed_samples) >= 3:
            # Apply exponentially weighted moving average
            weights = [0.6**i for i in range(len(self._speed_samples))]
            weighted_sum = sum(
                s * w for s, w in zip(reversed(self._speed_samples), weights)
            )
            weight_sum = sum(weights[: len(self._speed_samples)])
            self.current_speed = weighted_sum / weight_sum
        else:
            self.current_speed = instant_speed

        # Update peak speed
        self.peak_speed = max(self.peak_speed, self.current_speed)

        # Simple moving average for average speed
        self.avg_speed = self.downloaded / elapsed

        # Calculate ETA based on smoothed speed
        if self.current_speed > 0 and self.total_size > self.downloaded:
            self.eta_seconds = (self.total_size - self.downloaded) / self.current_speed
        else:
            self.eta_seconds = -1  # Unknown

    def _format_speed(self, speed: float) -> str:
        """Format speed with appropriate precision and units"""
        if speed <= 0:
            return "0 B/s"
        elif speed < 1024:
            return f"{speed:.1f} B/s"
        elif speed < 1024 * 1024:
            return f"{speed/1024:.1f} KB/s"
        elif speed < 1024 * 1024 * 1024:
            return f"{speed/(1024*1024):.2f} MB/s"
        else:
            return f"{speed/(1024*1024*1024):.2f} GB/s"

    def _get_progress_bar(self, percent: float) -> str:
        """Generate a progress bar with adaptive width and visual style"""
        # Adjust bar width based on terminal
        bar_width = min(self.bar_size, max(10, self.max_width - 30))
        filled_width = int(bar_width * percent / 100)

        # Select bar style based on percentage
        if self.bar_style == "gradient":
            if percent < 30:
                bar_color = Fore.RED
            elif percent < 70:
                bar_color = Fore.YELLOW
            else:
                bar_color = Fore.GREEN

            # Build the bar with colors
            bar = f"{bar_color}{'█' * filled_width}{Style.RESET_ALL}"
            bar += f"{Fore.WHITE}{'░' * (bar_width - filled_width)}{Style.RESET_ALL}"

        elif self.bar_style == "pulse":
            # Create pulsing effect with different character densities
            bar_chars = ["█", "▓", "▒", "░"]
            bar = ""

            for i in range(bar_width):
                if i < filled_width:
                    # For filled portion, use different characters based on position
                    char_idx = (i + int(time.time() * 3)) % len(bar_chars)
                    bar += f"{Fore.GREEN}{bar_chars[char_idx]}{Style.RESET_ALL}"
                else:
                    bar += f"{Fore.WHITE}░{Style.RESET_ALL}"
        else:
            # Simple solid bar
            bar = f"{Fore.GREEN}{'█' * filled_width}{Style.RESET_ALL}"
            bar += f"{Fore.WHITE}{'░' * (bar_width - filled_width)}{Style.RESET_ALL}"

        # Return bar with percentage
        return f"{bar} {percent:5.1f}%"

    def start(self) -> None:
        """Initialize and start the progress display."""
        if self._task_started:
            return

        # Initialize timers
        self.start_time = time.time()
        self.last_update_time = 0
        self._last_sample_time = self.start_time
        self._last_sample_bytes = 0
        self._task_started = True
        self._finished = False

        # Get terminal dimensions
        self.max_width = self._get_terminal_width()
        self.bar_size = min(50, max(20, self.max_width // 3))

        # Clear any cache
        self._cached_display = {}
        self._cache_valid_until = 0

        # Prepare terminal
        if self._supports_ansi:
            # Allocate lines for initial display
            lines_needed = 4 if self.detailed else 2
            print("\n" * (lines_needed - 1))
            # Move cursor back up
            print(f"\033[{lines_needed - 1}A", end="", flush=True)
            self.last_lines = lines_needed

            # Hide cursor for cleaner display
            print("\033[?25l", end="", flush=True)
            self._cursor_hidden = True

        # Show initial display
        self._first_display = True
        self.display()

    def display(self) -> None:
        """Display the current progress with statistics."""
        if not self.enabled or self._finished:
            return

        # Set task started if not already
        if not self._task_started:
            self.start()

        # Check if display update is needed based on time throttling
        now = time.time()
        if (
            not self._first_display
            and now - self.last_update_time < self.min_update_interval
        ):
            return

        # Update timing information
        self.last_update_time = now

        # Check if terminal width has changed
        current_width = self._get_terminal_width()
        if current_width != self.max_width:
            self.max_width = current_width
            self.bar_size = min(50, max(20, self.max_width // 3))
            # Invalidate cache when terminal changes
            self._cached_display = {}

        # Update speed metrics
        self._update_speed_metrics()

        # Calculate percentage - ensure bounds and handle zero division
        if self.total_size > 0:
            percent = min(100.0, max(0.0, (self.downloaded / self.total_size) * 100))
        else:
            percent = 0.0

        # Generate display lines
        lines = []

        # First line: Title and progress bar
        progress_bar = self._get_progress_bar(percent)
        lines.append(f"{Fore.CYAN}{self.title}: {Style.RESET_ALL}{progress_bar}")

        # Second line: Size info and speed
        downloaded_str = self._format_size(self.downloaded)
        total_str = (
            self._format_size(self.total_size) if self.total_size > 0 else "Unknown"
        )
        speed_str = self._format_speed(self.current_speed)
        lines.append(
            f"  {Fore.YELLOW}Size:{Style.RESET_ALL} {downloaded_str}/{total_str}   {Fore.YELLOW}Speed:{Style.RESET_ALL} {speed_str}"
        )

        # Add detailed stats if enabled
        if self.detailed:
            # Average and peak speeds
            avg_speed_str = self._format_speed(self.avg_speed)
            peak_speed_str = self._format_speed(self.peak_speed)
            lines.append(
                f"  {Fore.YELLOW}Avg:{Style.RESET_ALL} {avg_speed_str}   {Fore.YELLOW}Peak:{Style.RESET_ALL} {peak_speed_str}"
            )

            # ETA and elapsed time
            if self.show_eta:
                elapsed = now - self.start_time
                eta_str = self._format_time(self.eta_seconds)
                elapsed_str = self._format_time(elapsed)

                # Add completion percentage
                eta_line = f"  {Fore.YELLOW}ETA:{Style.RESET_ALL} {eta_str}   {Fore.YELLOW}Elapsed:{Style.RESET_ALL} {elapsed_str}"
                lines.append(eta_line)

        # Handle terminal display with or without ANSI support
        if self._supports_ansi:
            # Clear current line
            print("\r\033[K", end="")

            if not self._first_display and self.last_lines > 0:
                # Move up to overwrite previous lines
                print(f"\033[{self.last_lines}A", end="")

            # Print each line with clear-to-end and line feed
            for line in lines:
                print(f"{line}\033[K")

            # If we have fewer lines now than before, clear the excess
            if not self._first_display and len(lines) < self.last_lines:
                for _ in range(self.last_lines - len(lines)):
                    print("\033[K")
                # Move back up
                print(f"\033[{self.last_lines - len(lines)}A", end="")

        else:
            # Fallback for terminals without ANSI support: simple overwrite
            if not self._first_display:
                # Move to beginning of line with carriage return
                print("\r", end="")

            # Just print the first line
            print(lines[0])

        # Store number of lines for next update
        self.last_lines = len(lines)
        self._first_display = False

    def finish(self, success: bool = True) -> None:
        """Finalize the progress display with summary statistics."""
        if self._finished:
            return

        self._finished = True

        # Move cursor to bottom of display area
        if self._supports_ansi and self.last_lines > 0:
            print(f"\033[{self.last_lines}B", end="", flush=True)

        # Restore cursor
        if self._cursor_hidden:
            print("\033[?25h", end="", flush=True)
            self._cursor_hidden = False

        # Calculate final statistics
        elapsed = time.time() - self.start_time
        avg_speed = self.downloaded / max(0.001, elapsed)  # Avoid division by zero

        # Show completion message
        if success:
            print(f"\n{Fore.GREEN}✓ Download complete!{Style.RESET_ALL}")
        else:
            print(f"\n{Fore.RED}✗ Download failed!{Style.RESET_ALL}")

        # Show final statistics with enhanced formatting
        print(f"{Fore.CYAN}{'─' * 40}{Style.RESET_ALL}")
        print(
            f"  {Fore.YELLOW}Total Downloaded:{Style.RESET_ALL} {self._format_size(self.downloaded)}"
        )
        print(
            f"  {Fore.YELLOW}Time Taken:{Style.RESET_ALL} {self._format_time(elapsed)}"
        )
        print(
            f"  {Fore.YELLOW}Average Speed:{Style.RESET_ALL} {self._format_speed(avg_speed)}"
        )

        # Add efficiency metric for detailed information
        if self.detailed and self.peak_speed > 0:
            efficiency = (avg_speed / self.peak_speed) * 100
            print(
                f"  {Fore.YELLOW}Transfer Efficiency:{Style.RESET_ALL} {efficiency:.1f}%"
            )

        print(f"{Fore.CYAN}{'─' * 40}{Style.RESET_ALL}")

    def pause(self) -> None:
        """Pause the display updates temporarily."""
        self.enabled = False

    def resume(self) -> None:
        """Resume paused display updates."""
        self.enabled = True
        # Force refresh on resume
        self.last_update_time = 0
        self.display()

    def update(self, bytes_downloaded: int = 0) -> None:
        """Update progress with downloaded bytes and refresh display."""
        # Update downloaded count
        if bytes_downloaded > 0:
            self.downloaded += bytes_downloaded

        # Update display (throttled internally)
        self.display()


def clean_filename(filename: str) -> str:
    """
    Clean up filename with redundant or extra extensions.

    Args:
        filename: Original filename

    Returns:
        Cleaned filename
    """
    # First, handle the case where the filename has multiple extensions
    # like "song.wav.flac" -> "song.flac"
    basename = os.path.basename(filename)

    # Match patterns like "name.ext1.ext2" where ext2 is the target extension
    pattern = r"^(.+?)(\.[^.]+)*(\.[^.]+)$"
    match = re.match(pattern, basename)

    if match:
        # Get directory path
        dir_path = os.path.dirname(filename)

        # Extract the base name and the final extension
        base_name = match.group(1)
        final_ext = match.group(3)

        # Remove any redundant extensions from the base name
        # Check if base_name itself ends with the same extension
        for ext in AUDIO_EXTENSIONS.union(VIDEO_EXTENSIONS):
            if base_name.lower().endswith(ext) and ext != final_ext.lower():
                base_name = base_name[: -len(ext)]

        # Construct the clean filename
        clean_name = f"{base_name}{final_ext}"

        # Return the full path
        return os.path.join(dir_path, clean_name)

    return filename


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"{Fore.RED}An unexpected error occurred: {str(e)}{Style.RESET_ALL}")
        print(
            f"{Fore.YELLOW}Try running with --interactive flag for easier usage.{Style.RESET_ALL}"
        )
        sys.exit(1)
