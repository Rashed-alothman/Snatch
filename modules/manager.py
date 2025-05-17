# HTTP/P2P session abstraction, proxy logic
import os
import sys
import logging
import requests
import threading
import shutil
import json
import time
import re
import asyncio
import inspect
import math
import statistics
import psutil
from pathlib import Path
from contextlib import contextmanager
from typing import Any, Callable, Dict, Generator, Iterator, List, Optional, Tuple, Union
from rich.console import Console
from rich.progress import Progress
from rich.layout import Layout
from rich.panel import Panel
from colorama import Fore, Style, init

from modules.help_text import show_full_help, show_quick_help
# third party imports
from colorama import Fore, Style, init
from mutagen.oggvorbis import OggVorbis
from mutagen.flac import FLAC
from mutagen.id3 import ID3
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4
import yt_dlp
import mutagen
# Local imports
from .common_utils import (
    is_windows, 
    sanitize_filename, 
    display_system_stats, 
    list_supported_sites, 
    print_banner,
)
from .progress import DownloadStats, Spinner, SpinnerAnimation
from .defaults import (
    CACHE_DIR,
    speedtestresult,
    DOWNLOAD_SESSIONS_FILE,
    MAX_RETRIES,
    RETRY_SLEEP_BASE,
    MAX_MEMORY_PERCENT,
    AUDIO_EXTENSIONS,
    VIDEO_EXTENSIONS,
)
from .session import SessionManager, run_speedtest
from .cache import DownloadCache
from .file_organizer import FileOrganizer
from .ffmpeg_helper import locate_ffmpeg, validate_ffmpeg_installation

# Constants
part_ext = '.part'
webn_ext = '.webm'

logger = logging.getLogger(__name__)

# Best audio format string with quality preferences
bestaudio_ext = (
    "bestaudio[ext=m4a]/bestaudio[ext=mp3]/"
    "bestaudio[ext=opus]/bestaudio[ext=aac]/"
    "bestaudio[ext=wav]/bestaudio[ext=flac]/"
    "bestaudio"
)

# Audio codec constants
CODEC_OPUS = "libopus" 
CODEC_MP3 = "libmp3lame"
CODEC_FLAC = "flac"
CODEC_AAC = "aac"

# Quality settings
QUALITY_HIGH = "high"
QUALITY_MAX = "max"
QUALITY_LOSSLESS = "lossless"

quality_settings = {
    QUALITY_HIGH: {
        CODEC_OPUS: "192k",
        CODEC_MP3: "320k", 
        CODEC_AAC: "192k"
    },
    QUALITY_MAX: {
        CODEC_OPUS: "256k",
        CODEC_MP3: "320k",
        CODEC_AAC: "256k"
    },
    QUALITY_LOSSLESS: {
        CODEC_FLAC: "0"
    }
}

# Audio format constants and requirements
AUDIO_FORMATS = {
    "opus": {
        "min_sample_rate": 48000,
        "optimal_bitrate": 192000,
        "channels": [1, 2, 8],  # Mono, stereo, 7.1
        "codec": CODEC_OPUS
    },
    "mp3": {
        "min_sample_rate": 44100,
        "optimal_bitrate": 320000,
        "channels": [2],  # Stereo only
        "codec": CODEC_MP3
    },
    "flac": {
        "min_sample_rate": 44100,
        "min_bit_depth": 12,
        "optimal_bit_depth": 24,
        "channels": [2,6,8],  # Stereo or 7.1
        "codec": CODEC_FLAC,
        "surround_template": {
            "8": "-ac 8 -af 'pan=7.1|FL=FL|FR=FR|FC=FC|LFE=LFE|BL=BL|BR=BR|SL=SL|SR=SR'"
        }
        
    },
    "m4a": {
        "min_sample_rate": 44100,
        "optimal_bitrate": 256000,
        "channels": [2],  # Stereo only
        "codec": CODEC_AAC
    }
}

class AudioConversionError(Exception):
    """Custom exception for audio conversion failures."""
    pass

def _handle_conversion_error(self, error: Exception, output_file: str) -> None:
    """Handle audio conversion errors with appropriate logging and cleanup."""
    error_msg = str(error)
    logging.error(f"Audio conversion failed: {error_msg}")
    
    # Clean up any partial output
    if os.path.exists(output_file):
        try:
            os.remove(output_file)
        except OSError as e:
            logging.error(f"Failed to remove failed conversion output: {e}")
            
    # Check specific error conditions
    if "Invalid data found" in error_msg:
        logging.error("Input file appears to be corrupt or invalid")
    elif "Sample rate" in error_msg:
        logging.error("Sample rate conversion failed")
    elif "Permission denied" in error_msg:
        logging.error("Permission error accessing audio files")
    else:
        logging.error("Unknown conversion error occurred")
        
    raise AudioConversionError(f"Conversion failed: {error_msg}")

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
class DownloadManager:
    """Enhanced download manager with improved UI and functionality"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize download manager with robust session handling."""
        if config is None:
            raise ValueError("Configuration cannot be None")
            
        self.config = config.copy()
        
        # Create necessary directories
        for dir_key in ["video_output", "audio_output"]:
            if path := config.get(dir_key):
                os.makedirs(path, exist_ok=True)
            else:
                raise ValueError(f"Missing required configuration field: {dir_key}")
        
        # Set up session management
        self.session_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "sessions")
        os.makedirs(self.session_dir, exist_ok=True)
        
        # Initialize session manager with session file path
        self.session_manager = SessionManager(DOWNLOAD_SESSIONS_FILE)
        
        # Initialize other components
        self.download_cache = DownloadCache()
        self.download_stats = DownloadStats(keep_history=True)
        self.file_organizer = FileOrganizer(config)
        
        # Download tracking
        self.current_download_url = None
        self.download_start_time = None
        self.current_downloads = {}
                # Error handling settings
        self.max_retries = config.get("max_retries", MAX_RETRIES)
        self.retry_delay = config.get("retry_delay", RETRY_SLEEP_BASE)
        self.exponential_backoff = config.get("exponential_backoff", True)
        
        # Resource management
        self.memory_limit = psutil.virtual_memory().total * (MAX_MEMORY_PERCENT / 100)
        self._active_downloads = 0
        self._download_lock = threading.RLock()
        
        # Failure tracking
        self._failed_attempts = {}
        self._failed_lock = threading.RLock()
        
        # Current download info
        self._current_info_dict = {}
        # Validate FFmpeg installation
        self.ffmpeg_path = locate_ffmpeg()
        if not self.ffmpeg_path or not validate_ffmpeg_installation():
            logging.warning("FFmpeg not found or invalid. Some features may be limited.")
    def progress_hook(self, d: Dict[str, Any]) -> None:
        """Consolidated progress hook for tracking download progress"""
        try:
            status = d.get('status', '')

            if status == 'downloading':
                self._handle_downloading_status(d)
            elif status == 'finished':
                self._handle_finished_status(d)
            elif status == 'error':
                self._handle_error_status(d)

        except Exception as e:
            logging.error(f'Error in progress hook: {e}')

    def _handle_downloading_status(self, d: Dict[str, Any]) -> None:
        """Process 'downloading' status with optimized progress tracking."""
        total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
        downloaded = d.get('downloaded_bytes', 0)
        speed = d.get('speed', 0)
            
        if total > 0:
            # Calculate percentage
            percent = (downloaded / total) * 100

            # Update statistics
            if hasattr(self, 'download_stats'):
                self.download_stats.display
                
            # Update session if filename available
            filename = d.get('filename', '')
            if filename:
                self.session_manager.update_session(filename, percent)

            # Update progress display
            if hasattr(self, 'detailed_pbar'):
                self.detailed_pbar.update(
                    downloaded=downloaded,
                    total=total,
                    speed=speed,
                    percentage=percent
                )

    def _handle_finished_status(self, d: Dict[str, Any]) -> None:
        """Process 'finished' status with file handling."""
        # Close progress displays
        if hasattr(self, 'detailed_pbar'):
            self.detailed_pbar.finish(success=True)
            delattr(self, 'detailed_pbar')

        # Get downloaded file path
        filepath = d.get('filename', '')
        if not filepath:
            return

        # Check if this is just a fragment
        is_fragment = any(marker in os.path.basename(filepath) 
                        for marker in ('.f', part_ext, 'tmp'))
                        
        if not is_fragment:
            duration = time.time() - getattr(self, 'download_start_time', time.time())
            
            # Record successful download
            self.download_stats.add_download(
                success=True,
                size_bytes=os.path.getsize(filepath) if os.path.exists(filepath) else 0,
                duration=duration,
            )
            
            # Clear session for completed file
            if self.current_download_url:
                self.download_start_time = None
                self.session_manager.remove_session(self.current_download_url)

            logging.info(f"Download complete: {filepath}")
            print(f"{Fore.GREEN}✓ Download Complete!{Style.RESET_ALL}")

            # Clean up filename if needed
            if os.path.exists(filepath):
                ext = os.path.splitext(filepath)[1].lower()
                if ext not in AUDIO_EXTENSIONS and ext != webn_ext:
                    self._cleanup_filename(filepath)

    def _handle_error_status(self, d: Dict[str, Any]) -> None:
        """Process 'error' status with cleanup."""
        # Clean up progress display
        if hasattr(self, 'detailed_pbar'):
            self.detailed_pbar.finish(success=False)
            delattr(self, 'detailed_pbar')

        # Record error
        error_msg = d.get('error', 'Unknown error')
        logging.error(f"Download error: {error_msg}")
        
        # Update statistics
        self.download_stats.add_download(
            success=False,
            error=error_msg
        )

        # Reset state
        self.download_start_time = None

    def get_download_options(
        self,
        *,
        audio_only: bool = False,
        resolution: Optional[str] = None,
        format_id: Optional[str] = None,
        filename: Optional[str] = None,
        audio_format: str = "opus",
        no_retry: bool = False,
        throttle: Optional[str] = None,
        use_aria2c: bool = False,
        audio_channels: int = 2,
        resume: bool = False,
        test_all_formats: bool = False,
        no_cache: bool = False  # Add support for no_cache option
    ) -> Dict[str, Any]:
        """Get optimized download options with enhanced flexibility."""
        # Get base output configuration
        options = self._get_base_output_config(audio_only, filename)
        
        # Add common options
        options.update(self._get_common_options(resume))
        
        # Add retry configuration
        options.update(self._get_retry_config(no_retry))
        
        # Configure format selection
        options.update(self._get_format_options(
            format_id, audio_only, audio_format, audio_channels, resolution
        ))
        
        # Handle additional options
        self._add_aria2c_config(options, use_aria2c)
        self._add_throttling(options, throttle)
        
        if test_all_formats:
            options["check_formats"] = True
            logging.info("Testing all available formats (may be slower)")
            
        # Handle caching options
        if no_cache:
            options["no_cache"] = True
            options["rm_cache_dir"] = True
            
        return options

    def _get_base_output_config(self, audio_only: bool, filename: Optional[str]) -> Dict[str, Any]:
        """Get base output configuration."""
        # Determine and create output path
        try:
            output_path = (
                self.config["audio_output"]
                if audio_only
                else self.config["video_output"]
            )
            os.makedirs(output_path, exist_ok=True)
        except OSError:
            output_path = str(Path.home() / ("Music" if audio_only else "Videos"))
            os.makedirs(output_path, exist_ok=True)
            logging.warning(f"Using fallback output path: {output_path}")
        
        # Process and sanitize filename
        if filename:
            filename = os.path.splitext(filename)[0]  # Remove extension
            filename = re.sub(r'[\\/*?:"<>|]', "_", filename)  # Sanitize
            output_template = f"{filename}.%(ext)s"
        else:
            output_template = "%(title)s.%(ext)s"
            
        return {
            "outtmpl": os.path.join(output_path, output_template),
            "restrictfilenames": True
        }

    def _get_common_options(self, resume: bool) -> Dict[str, Any]:
        """Get common download options."""
        return {
            "ffmpeg_location": self.config["ffmpeg_location"],
            "progress_hooks": [self.progress_hook],
            "postprocessor_hooks": [self._post_process_hook],
            "ignoreerrors": True,
            "continue": resume,
            "concurrent_fragment_downloads": min(16, os.cpu_count() or 4),
            "http_chunk_size": 10485760,  # 10MB chunks
            "socket_timeout": 30,
            "extractor_retries": 3,
            "file_access_retries": 3,
            "skip_unavailable_fragments": True,
            "force_generic_extractor": False,
            "quiet": True,
            "no_warnings": False,
            "keepvideo": False,
            "merge_output_format": "mp4",
            "ffmpeg_args": ["-loglevel", "warning"]  # Reduce FFmpeg output noise
        }

    def _get_retry_config(self, no_retry: bool) -> Dict[str, Any]:
        """Get retry configuration."""
        if no_retry:
            return {
                "retries": 0,
                "fragment_retries": 0
            }
        else:
            return {
                "retries": 3,
                "fragment_retries": 3,
                "retry_sleep_functions": {
                    "http": lambda attempt: 5 * (2 ** (attempt - 1))
                },
                "network_retries": 3
            }

    def _get_format_options(
        self, 
        format_id: Optional[str],
        audio_only: bool,
        audio_format: str,
        audio_channels: int,
        resolution: Optional[str]
    ) -> Dict[str, Any]:
        """Configure format selection options."""
        if format_id:
            return {"format": format_id}
        
        if audio_only:
            return self._get_audio_format_options(audio_format, audio_channels)
        else:
            return self._get_video_format_options(resolution)

    def _get_audio_format_options(self, audio_format: str, audio_channels: int) -> Dict[str, Any]:
        """Get audio format specific options."""
        quality_settings = {
            "high": {
                "opus": "192k",
                "mp3": "320k",
                "m4a": "192k",
                "flac": "0"  # Lossless
            },
            "max": {
                "opus": "256k",
                "mp3": "320k",
                "m4a": "256k",
                "flac": "0"  # Lossless
            }
        }
        
        options = {
            "format": "bestaudio/best",
            "extract_audio": True,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": audio_format,
                "preferredquality": quality_settings["max"].get(audio_format, "0"),
                "nopostoverwrites": True
            }]
        }
        
        # Add advanced FFmpeg options for better quality
        ffmpeg_args = []
        
        if audio_format == "flac":
            ffmpeg_args.extend([
                "-acodec", "flac",
                "-compression_level", "12",
                "-sample_fmt", "s32",
                "-ar", "96000" if audio_channels == 8 else "48000",
                "-bits_per_raw_sample", "24"
            ])
            
        elif audio_format == "opus":
            ffmpeg_args.extend([
                "-acodec", "libopus",
                "-b:a", quality_settings["max"]["opus"],
                "-vbr", "on",
                "-compression_level", "10"
            ])
            
        elif audio_format == "mp3":
            ffmpeg_args.extend([
                "-acodec", "libmp3lame",
                "-q:a", "0",
                "-b:a", quality_settings["max"]["mp3"],
                "-joint_stereo", "1"
            ])
            
        elif audio_format == "m4a":
            ffmpeg_args.extend([
                "-acodec", "aac",
                "-b:a", quality_settings["max"]["m4a"],
                "-movflags", "+faststart",
                "-profile:a", "aac_low"
            ])

        # Add channel-specific options
        if audio_channels == 8:  # 7.1 surround
            ffmpeg_args.extend([
                "-ac", "8",
                "-channel_layout", "7.1",
                "-af", "aresample=resampler=soxr:precision=28:dither_method=triangular_hp:filter_size=256"
            ])
        else:  # stereo
            ffmpeg_args.extend([
                "-ac", "2",
                "-channel_layout", "stereo",
                "-af", "aresample=resampler=soxr:precision=24:dither_method=triangular_hp:filter_size=128"
            ])
            
        if ffmpeg_args:
            if "postprocessor_args" not in options:
                options["postprocessor_args"] = {}
            options["postprocessor_args"]["FFmpegExtractAudio"] = ffmpeg_args
        
        # Add metadata postprocessor without the problematic metadata field
        options["postprocessors"].append({
            "key": "FFmpegMetadata",
            "add_metadata": True
        })
        
        return options

    def _get_flac_options(self, audio_channels: int, base_options: Dict[str, Any]) -> Dict[str, Any]:
        """Configure FLAC-specific options for maximum quality."""
        options = base_options.copy()
        
        ffmpeg_args = [
            "-acodec", CODEC_FLAC, 
            "-compression_level", "12",
            "-sample_fmt", "s32"
        ]
        
        if audio_channels == 8:  # 7.1 surround
            ffmpeg_args.extend([
                "-ac", "8",
                "-channel_layout", "7.1",
                "-ar", "96000",  # High sample rate for surround
                "-af", (
                    "aformat=channel_layouts=7.1,"
                    "aresample=resampler=soxr:precision=28:dither_method=triangular_hp:filter_size=256,"
                    "loudnorm=I=-16:TP=-1.5:LRA=11"
                )
            ])
        else:  # stereo
            ffmpeg_args.extend([
                "-ac", "2", 
                "-channel_layout", "stereo",
                "-ar", "48000",  # Standard high quality
                "-af", (
                    "aformat=channel_layouts=stereo,"
                    "aresample=resampler=soxr:precision=24:dither_method=triangular_hp,"
                    "loudnorm=I=-14:TP=-1:LRA=9"
                )
            ])
            
        options["postprocessor_args"] = {"FFmpegExtractAudio": ffmpeg_args}
        
        # Add metadata postprocessor
        options["postprocessors"].append({
            "key": "FFmpegMetadata",
            "add_metadata": True
        })
        
        return options

    def _validate_audio_file(self, filepath: str, expected_format: str) -> bool:
        """Validate audio file format and quality."""
        try:
            audio = mutagen.File(filepath)
            if not audio or not audio.info:
                logging.error(f"Failed to read audio file: {filepath}")
                return False
                
            if not self._validate_basic_audio(audio, filepath):
                return False
                
            if not self._validate_format_specific(audio, expected_format):
                return False
                
            return True
            
        except Exception as e:
            logging.error(f"Audio validation error: {str(e)}")
            return False

    def _validate_basic_audio(self, audio: Any, filepath: str) -> bool:
        """Validate basic audio properties."""
        # Check file size
        filesize = os.path.getsize(filepath)
        if filesize < 1024:  # 1KB minimum
            logging.error(f"File too small: {filesize} bytes")
            return False
            
        # Check duration
        duration = getattr(audio.info, "length", 0)
        if duration <= 0:
            logging.error("Invalid duration")
            return False
            
        return True

    def _validate_format_specific(self, audio: Any, format: str) -> bool:
        """Validate format-specific audio properties."""
        sample_rate = getattr(audio.info, "sample_rate", 0)
        bit_depth = getattr(audio.info, "bits_per_raw_sample", 0)
        
        if format == "flac":
            if not isinstance(audio, FLAC):
                logging.error("Not a valid FLAC file")
                return False
            if sample_rate < 44100:
                logging.error(f"Sample rate too low: {sample_rate}")
                return False
            if bit_depth < 16:
                logging.error(f"Bit depth too low: {bit_depth}")
                return False
                
        elif format == "opus":
            if sample_rate < 48000:
                logging.warning(f"Opus sample rate lower than optimal: {sample_rate}")
                
        elif format == "mp3":
            if not hasattr(audio.info, "bitrate") or audio.info.bitrate < 320000:
                logging.warning("MP3 bitrate lower than maximum quality")
                
        return True

    def extract_info(self, url: str) -> Optional[Dict[str, Any]]:
        """Extract comprehensive information about media from a URL."""
        if not url:
            logging.error("No URL provided for info extraction")
            return None

        try:
            yt_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                'format': 'best',
                'extract_info': True,
                'write_all_thumbnails': False,
                'writesubtitles': False,
                'writeautomaticsub': False,
                'socket_timeout': 10,
                'retries': 3
            }
            
            with yt_dlp.YoutubeDL(yt_opts) as ydl:
                try:
                    info_dict = ydl.extract_info(url, download=False)
                    if not info_dict:
                        logging.error("Failed to extract info: No data returned")
                        return None

                    # Validate essential fields
                    if not all(info_dict.get(key) for key in ['title', 'id']):
                        logging.error("Missing essential info fields")
                        return None
                        
                    # Add additional useful fields
                    info_dict['download_url'] = url
                    info_dict['extraction_timestamp'] = int(time.time())
                    
                    # Extract audio-specific info safely
                    audio_info = {
                        'codec': None,
                        'bitrate': None,
                        'sample_rate': None,
                        'channels': None
                    }
                    
                    if 'formats' in info_dict:
                        audio_formats = [f for f in info_dict['formats'] 
                                       if f.get('acodec') and f.get('acodec') != 'none']
                        if audio_formats:
                            best_audio = max(audio_formats, 
                                          key=lambda x: float(x.get('abr', 0) or 0))
                            audio_info.update({
                                'codec': best_audio.get('acodec'),
                                'bitrate': best_audio.get('abr'),
                                'sample_rate': best_audio.get('asr'),
                                'channels': best_audio.get('audio_channels')
                            })
                    
                    info_dict['audio_info'] = audio_info
                    return info_dict
                    
                except yt_dlp.utils.DownloadError as de:
                    logging.error(f"Download error during info extraction: {str(de)}")
                    return None
                    
        except Exception as e:
            logging.error(f"Error extracting info: {str(e)}")
            return None

    def _test_endpoint_speed(self, url: str, timeout: float) -> Optional[float]:
        """Test download speed from a single endpoint."""
        try:
            start = time.time()
            response = requests.get(url, timeout=timeout, stream=True)
            response.raise_for_status()
            
            # Read in chunks to simulate actual download
            chunk_size = 8192
            total_size = 0
            
            for chunk in response.iter_content(chunk_size=chunk_size):
                if time.time() - start > timeout:
                    break
                total_size += len(chunk)
                
            duration = time.time() - start
            if duration > 0:
                return total_size * 8 / duration  # Convert to bits per second
                
        except Exception as e:
            logging.debug(f"Speed test failed for {url}: {e}")
            
        return None

    def measure_network_speed(self, timeout: float = 3.0) -> float:
        """Measure network download speed using multiple test endpoints."""
        endpoints = [
            "https://httpbin.org/stream-bytes/51200",
            "https://speed.cloudflare.com/__down?bytes=1048576",
            "https://speed.hetzner.de/100MB.bin"
        ]
        
        speeds = []
        for url in endpoints:
            speed = self._test_endpoint_speed(url, timeout)
            if speed:
                speeds.append(speed)
                
            if len(speeds) >= 2:  # Got enough samples
                break
                
        if not speeds:
            logging.warning("Speed test failed, using conservative estimate")
            return 1_000_000  # 1 Mbps fallback
            
        # Use median speed to avoid outliers
        return statistics.median(speeds)

    def _get_video_format_options(self, resolution: Optional[str]) -> Dict[str, Any]:
        """Get video format options based on resolution."""
        if not resolution:
            # Automatic resolution selection based on network speed
            speed = self.measure_network_speed()
            resolution = self._select_resolution_by_speed(speed)
            logging.info(f"Auto-selected {resolution}p based on network speed ({speed:.1f} Mbps)")

        return {
            "format": (
                f"bestvideo[height<={resolution}]+bestaudio/best[height<={resolution}]"
                if resolution else
                "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best"
            )
        }

    def _select_resolution_by_speed(self, speed: float) -> str:
        """Select appropriate resolution based on network speed."""
        if speed > 20:
            return "2160"
        if speed > 5:
            return "1080"
        if speed > 2:
            return "720"
        return "480"

    def _add_aria2c_config(self, options: Dict[str, Any], use_aria2c: bool) -> None:
        """Add aria2c configuration if enabled."""
        if use_aria2c and self._check_aria2c_available():
            options.update({
                "external_downloader": "aria2c",
                "external_downloader_args": [
                    "--min-split-size=1M",
                    "--max-connection-per-server=32",
                    "--max-concurrent-downloads=16",
                    "--split=16",
                    "--file-allocation=none",
                    "--optimize-concurrent-downloads=true",
                    "--auto-file-renaming=false",
                    "--allow-overwrite=true",
                    "--disable-ipv6",
                    "--timeout=10",
                    "--connect-timeout=10",
                    "--http-no-cache=true",
                    "--max-tries=3",
                    "--retry-wait=2"
                ]
            })
            logging.info("Using aria2c with optimized settings")
        else:
            options.update({
                "concurrent_fragment_downloads": min(24, os.cpu_count() or 4),
                "http_chunk_size": 20971520  # 20MB chunks
            })

    def _add_throttling(self, options: Dict[str, Any], throttle: Optional[str]) -> None:
        """Add throttling configuration if specified."""
        if throttle:
            rate = self._parse_throttle_rate(throttle)
            if rate > 0:
                options["throttled_rate"] = rate
                logging.info(f"Download speed limited to {throttle}/s")

    def _get_delete_command(self) -> str:
        """Get platform-specific delete command"""
        return (
            'powershell -Command "Remove-Item -LiteralPath \\"%(filepath)s\\" -Force"'
            if is_windows()
            else 'rm "%(filepath)s"'
        )

    async def batch_download(self, urls: List[str], **options) -> List[bool]:
        """Process multiple URLs in sequence with async support"""
        if not urls:
            raise ValueError("No URLs provided for download")
            
        results = []
        for url in urls:
            try:
                if not url:
                    logging.warning("Skipping empty URL")
                    results.append(False)
                    continue
                    
                success = await self.download(url, **options)
                results.append(success if success is not None else False)
            except Exception as e:
                logging.error(f"Error downloading {url}: {str(e)}")
                results.append(False)
                
        return results
        
    async def download(self, url: str, **kwargs) -> bool:
        """Download media with comprehensive error handling and progress tracking."""
        if not url or not any(url.startswith(p) for p in ('http://', 'https://')):
            print(f"{Fore.RED}Invalid URL: {url}{Style.RESET_ALL}")
            return False

        try:
            # Set current URL for tracking
            self.current_download_url = url
            self.download_start_time = time.time()            # Show download options menu and get user choices
            options = await self._show_download_options_and_get_choices(url)
            if not options:
                return False
                
            # Update kwargs with user choices
            kwargs.update(options)
            
            # Prepare download options
            try:
                ydl_opts = self.get_download_options(**kwargs)
            except TypeError as e:
                if 'unexpected keyword argument' in str(e):
                    # Remove unsupported arguments and retry
                    valid_kwargs = {k: v for k, v in kwargs.items() 
                                 if k in self.get_download_options.__code__.co_varnames}
                    ydl_opts = self.get_download_options(**valid_kwargs)
                else:
                    raise
            
            # Ensure session directory exists
            os.makedirs(self.session_dir, exist_ok=True)
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                
                try:
                    loop = asyncio.get_event_loop()
                    try:
                        await loop.run_in_executor(None, ydl.download, [url])
                        error_code = 0
                    except yt_dlp.utils.DownloadError as de:
                        error_code = 1
                    success = error_code == 0
                    
                    if success:
                        self.session_manager.update_session(url, 100, {"status": "completed"})
                    else:
                        self.session_manager.update_session(url, 0, {"error": "Download failed"})
                        
                    return success
                    
                except yt_dlp.utils.DownloadError as de:
                    error_msg = str(de)
                    logging.error(f"Download error for {url}: {error_msg}")
                    self.session_manager.update_session(url, 0, {"error": error_msg})
                    return False
                    
        except Exception as e:
            error_msg = str(e)
            logging.error(f"Download failed for {url}: {error_msg}")
            try:
                self.session_manager.update_session(url, 0, {"error": error_msg})
            except Exception as se:
                logging.error(f"Failed to update session: {se}")
            return False
            
        finally:
            self.current_download_url = None
            self.download_start_time = None

    async def interactive_mode(self) -> None:
        """Interactive download mode with improved UX"""
        console = Console()
        console.print("[cyan]Interactive Download Mode[/cyan]")
        console.print("[yellow]Type 'help' or '?' for commands, Ctrl+C to exit[/yellow]\n")
        
        while True:
            try:
                url = input(f"{Fore.GREEN}Enter URL:{Style.RESET_ALL} ").strip()
                
                if not url:
                    continue
                    
                if url.lower() in ('exit', 'quit', 'q'):
                    break
                    
                # Handle commands
                result = await self._handle_interactive_command(url)
                if result is False:  # Command was handled
                    continue
                    
                # Process download
                success = await self.download_with_retries(url, self.config)
                if success:
                    console.print(f"\n[green]✓ Successfully downloaded: {url}[/green]")
                else:
                    console.print(f"\n[red]✗ Failed to download: {url}[/red]")
                    
            except KeyboardInterrupt:
                console.print("\n[yellow]Exiting interactive mode...[/yellow]")
                break
            except Exception as e:
                console.print(f"[red]Error: {str(e)}[/red]")
                
    async def _handle_interactive_command(self, command: str) -> Optional[bool]:
        """Handle interactive mode commands"""
        if command.lower() in ('help', '?'):
            self._show_help()
            return False
            
        if command.lower() == 'examples':
            self._show_examples()
            return False
            
        if command.startswith('!'):
            await self._handle_special_command(command[1:])
            return False
            
        return None  # Command not handled

    async def _handle_special_command(self, command: str) -> None:
        """Process special commands"""
        command = command.lower().strip()
        
        if command == 'stats':
            display_system_stats()
        elif command == 'speed':
            await self._run_speedtest()
        elif command == 'sites':
            list_supported_sites()
        elif command == 'clear':
            self._clear_screen()
        else:
            print(f"{Fore.RED}Unknown command: !{command}{Style.RESET_ALL}")
            
    def _clear_screen(self) -> None:
        """Clear terminal screen in a platform-independent way"""
        if is_windows():
            os.system('cls')
        else:
            os.system('clear')
        print_banner()

    async def _run_speedtest(self) -> None:
        """Run network speed test"""
        with Progress() as progress:
            task = progress.add_task("[cyan]Running speed test...", total=100)
            result = await run_speedtest()
            progress.update(task, completed=100)
        return result

    def _get_user_choice(self, options: Dict[str, Tuple[str, str]], prompt: str) -> str:
        """Get a valid user choice from the given options."""
        while True:
            choice = input(f"\n{Fore.GREEN}{prompt}:{Style.RESET_ALL} ").strip()
            if choice in options:
                return choice
            print(f"{Fore.RED}Invalid choice. Please select {'-'.join(options.keys())}.{Style.RESET_ALL}")

    def _display_options(self, title: str, options: Dict[str, Tuple[str, str]], emoji: str = "") -> None:
        """Display a set of options with consistent formatting."""
        print(f"\n{Fore.YELLOW}{emoji} {title}:{Style.RESET_ALL}")
        for key, (name, desc) in options.items():
            print(f"{Fore.CYAN}{key}.{Style.RESET_ALL} {name:<6} [{desc}]")

    def _show_header(self, console: Console, title: str, duration: int) -> None:
        """Display the header for download options."""
        console.print(f"\n{Fore.CYAN}┌{'─'*48}┐{Style.RESET_ALL}")
        console.print(f"{Fore.CYAN}│{Style.RESET_ALL} {Fore.GREEN}Download Options for:{Style.RESET_ALL}")
        console.print(f"{Fore.CYAN}│{Style.RESET_ALL} {title[:45] + '...' if len(title) > 45 else title}")
        console.print(f"{Fore.CYAN}│{Style.RESET_ALL} Duration: {time.strftime('%H:%M:%S', time.gmtime(duration))}")
        console.print(f"{Fore.CYAN}└{'─'*48}┘{Style.RESET_ALL}\n")

    def _show_selections(self, console: Console, choices: Dict[str, Any]) -> None:
        """Display the final selections."""
        console.print(f"\n{Fore.CYAN}┌{'─'*48}┐{Style.RESET_ALL}")
        console.print(f"{Fore.CYAN}│{Style.RESET_ALL} {Fore.GREEN}Selected Options:{Style.RESET_ALL}")
        for key, value in choices.items():
            console.print(f"{Fore.CYAN}│{Style.RESET_ALL} {key.replace('_', ' ').title()}: {value}")
        console.print(f"{Fore.CYAN}└{'─'*48}┘{Style.RESET_ALL}\n")

    async def _show_download_options_and_get_choices(self, url: str) -> Dict[str, Any]:
        """
        Display download options menu and get user choices.
        
        Returns:
            Dict containing user's choices for format, quality, and channel options
        """
        console = Console()
        choices = {}
        
        # Extract info for available formats
        info = self.extract_info(url)
        if not info:
            return choices
        
        title = info.get('title', 'Unknown Title')
        duration = info.get('duration', 0)
        
        # Show header
        self._show_header(console, title, duration)

        # Audio format selection
        audio_formats = {
            "1": ("FLAC", "Lossless, Best Quality"),
            "2": ("Opus", "High Quality, Efficient"),
            "3": ("MP3", "320kbps, High Compatibility"),
            "4": ("M4A", "AAC, Good Quality"),
        }
        
        self._display_options("Audio Format", audio_formats, "🎵")
        audio_choice = self._get_user_choice(audio_formats, "Select audio format (1-4)")
        choices['audio_format'] = audio_formats[audio_choice][0].lower()

        # Channel options
        channel_options = {
            "1": ("stereo", "Stereo (2.0)"),
            "2": ("surround", "Surround (7.1) [FLAC Only]")
        }
        
        self._display_options("Channel Options", channel_options, "📢")
        while True:
            channel_choice = self._get_user_choice(channel_options, "Select channel option (1-2)")
            # Only allow surround if FLAC was chosen
            if channel_choice == "2" and choices['audio_format'] != 'flac':
                print(f"{Fore.RED}Surround sound is only available with FLAC format.{Style.RESET_ALL}")
                continue
            choices['channels'] = channel_options[channel_choice][0]
            break

        # Video options if available
        if info.get('formats'):
            video_formats = [f for f in info['formats'] if f.get('vcodec') != 'none']
            if video_formats:
                video_qualities = {
                    "1": ("2160p", "4K Ultra HD"),
                    "2": ("1080p", "Full HD"),
                    "3": ("720p", "HD"),
                    "4": ("480p", "SD"),
                    "5": ("auto", "Auto (Based on network speed)")
                }
                
                self._display_options("Video Quality", video_qualities, "🎥")
                video_choice = self._get_user_choice(video_qualities, "Select video quality (1-5)")
                choices['video_quality'] = video_qualities[video_choice][0]

        # Additional options
        subtitle_options = {
            "1": ("Yes", "Download subtitles if available"),
            "2": ("No", "Skip subtitles")
        }
        
        self._display_options("Additional Options", subtitle_options, "⚙️")
        subtitle_choice = self._get_user_choice(subtitle_options, "Download subtitles? (1-2)")
        choices['download_subtitles'] = subtitle_choice == "1"

        # Show final selections
        self._show_selections(console, choices)
        
        return choices

    def _post_process_hook(self, d: Dict[str, Any]) -> None:
        """Hook for handling post-processing with improved audio handling and error recovery."""
        try:
            status = d.get('status')
            
            if status == 'started':
                self._handle_postprocessing_started(d)
            elif status == 'processing':
                self._handle_postprocessing_progress(d)
            elif status == 'finished':
                self._handle_postprocessing_finished(d)
            elif status == 'error':
                self._handle_postprocessing_error(d)

        except Exception as e:
            logging.error(f'Error in post-processing hook: {e}')
            raise

    def _handle_postprocessing_started(self, d: Dict[str, Any]) -> None:
        """Handle start of post-processing."""
        info_dict = d.get('info_dict', {})
        title = info_dict.get('title', 'Unknown')
        logging.info(f"Post-processing started: {title}")
        print(f"{Fore.CYAN}Post-processing: {title}{Style.RESET_ALL}")

    def _handle_postprocessing_progress(self, d: Dict[str, Any]) -> None:
        """Handle post-processing progress updates."""
        status = d.get('status_msg', '')
        if status:
            print(f"{Fore.CYAN}Progress: {status}{Style.RESET_ALL}")

    def _handle_postprocessing_finished(self, d: Dict[str, Any]) -> None:
        """Handle completion of post-processing."""
        try:
            info_dict = d.get('info_dict', {})
            filepath = info_dict.get('filepath')
            
            if not filepath or not os.path.exists(filepath):
                logging.warning("Post-processing finished but file not found")
                return

            # Handle file cleanup and organization
            processed_path = self._process_downloaded_file(filepath, info_dict)
            
            if processed_path and self._is_audio_file(processed_path):
                self._update_audio_metadata(processed_path, info_dict)
            
            logging.info(f'Post-processing complete: {os.path.basename(processed_path or filepath)}')
            print(f"{Fore.GREEN}✓ Post-processing complete{Style.RESET_ALL}")
            
        except Exception as e:
            logging.error(f'Error in post-processing completion: {e}')
            raise

    def _process_downloaded_file(self, filepath: str, info_dict: Dict[str, Any]) -> Optional[str]:
        """Process a downloaded file with cleanup and organization."""
        try:
            # Clean up the filename if needed
            ext = os.path.splitext(filepath)[1].lower()
            if ext not in AUDIO_EXTENSIONS and ext != webn_ext:
                clean_path = clean_filename(filepath)
                if clean_path != filepath and not os.path.exists(clean_path):
                    os.rename(filepath, clean_path)
                    logging.info(f'File renamed: {os.path.basename(clean_path)}')
                    filepath = clean_path
            
            # Handle organization if enabled
            if self.config.get('organize', False) and self.file_organizer:
                try:
                    new_path = self.file_organizer.organize_file(filepath, info_dict)
                    if new_path:
                        logging.info(f'File organized: {os.path.basename(new_path)}')
                        return new_path
                except Exception as e:
                    logging.error(f'Error organizing file: {e}')
            
            return filepath
            
        except Exception as e:
            logging.error(f'Error processing downloaded file: {e}')
            return filepath

    def _is_audio_file(self, filepath: str) -> bool:
        """Check if file is an audio file."""
        ext = os.path.splitext(filepath)[1].lower()
        return ext[1:] if ext.startswith('.') else ext in AUDIO_EXTENSIONS

    def _update_audio_metadata(self, filepath: str, info_dict: Dict[str, Any]) -> None:
        """Update audio file metadata."""
        try:
            ext = os.path.splitext(filepath)[1].lower()
            
            metadata = {
                'title': info_dict.get('title', ''),
                'artist': info_dict.get('artist', info_dict.get('uploader', '')),
                'album': info_dict.get('album', ''),
                'date': info_dict.get('upload_date', '')[:4],  # Year only
                'comment': f"Downloaded by Snatch\nSource: {info_dict.get('webpage_url', '')}"
            }
            
            if ext == '.mp3':
                self._update_mp3_metadata(filepath, metadata)
            elif ext == '.m4a':
                self._update_m4a_metadata(filepath, metadata)
            elif ext == '.opus':
                self._update_opus_metadata(filepath, metadata)
            elif ext == '.flac':
                self._update_flac_metadata(filepath, metadata)
                
        except Exception as e:
            logging.error(f'Error updating metadata: {e}')

    def _update_mp3_metadata(self, filepath: str, metadata: Dict[str, str]) -> None:
        """Update MP3 metadata."""
        try:
            audio = MP3(filepath)
            if not audio.tags:
                audio.add_tags()
                
            audio.tags.add(
                mutagen.id3.TIT2(encoding=3, text=metadata['title'])
            )
            if metadata['artist']:
                audio.tags.add(
                    mutagen.id3.TPE1(encoding=3, text=metadata['artist'])
                )
            if metadata['album']:
                audio.tags.add(
                    mutagen.id3.TALB(encoding=3, text=metadata['album'])
                )
            if metadata['date']:
                audio.tags.add(
                    mutagen.id3.TDRC(encoding=3, text=metadata['date'])
                )
            if metadata['comment']:
                audio.tags.add(
                    mutagen.id3.COMM(
                        encoding=3, lang='eng', 
                        desc='Comment', text=metadata['comment']
                    )
                )
            audio.save()
            
        except Exception as e:
            logging.error(f'Error updating MP3 metadata: {e}')

    def _update_m4a_metadata(self, filepath: str, metadata: Dict[str, str]) -> None:
        """Update M4A metadata."""
        try:
            audio = MP4(filepath)
            if metadata['title']:
                audio['\xa9nam'] = [metadata['title']]
            if metadata['artist']:
                audio['\xa9ART'] = [metadata['artist']]
            if metadata['album']:
                audio['\xa9alb'] = [metadata['album']]
            if metadata['date']:
                audio['\xa9day'] = [metadata['date']]
            if metadata['comment']:
                audio['\xa9cmt'] = [metadata['comment']]
            audio.save()
            
        except Exception as e:
            logging.error(f'Error updating M4A metadata: {e}')

    def _update_opus_metadata(self, filepath: str, metadata: Dict[str, str]) -> None:
        """Update Opus metadata."""
        try:
            audio = OggVorbis(filepath)
            if metadata['title']:
                audio['title'] = [metadata['title']]
            if metadata['artist']:
                audio['artist'] = [metadata['artist']]
            if metadata['album']:
                audio['album'] = [metadata['album']]
            if metadata['date']:
                audio['date'] = [metadata['date']]
            if metadata['comment']:
                audio['comment'] = [metadata['comment']]
            audio.save()
            
        except Exception as e:
            logging.error(f'Error updating Opus metadata: {e}')

    def _update_flac_metadata(self, filepath: str, metadata: Dict[str, str]) -> None:
        """Update FLAC metadata."""
        try:
            audio = FLAC(filepath)
            if metadata['title']:
                audio['title'] = [metadata['title']]
            if metadata['artist']:
                audio['artist'] = [metadata['artist']]
            if metadata['album']:
                audio['album'] = [metadata['album']]
            if metadata['date']:
                audio['date'] = [metadata['date']]
            if metadata['comment']:
                audio['comment'] = [metadata['comment']]
            audio.save()
            
        except Exception as e:
            logging.error(f'Error updating FLAC metadata: {e}')

    def _handle_postprocessing_error(self, d: Dict[str, Any]) -> None:
        """Handle post-processing errors."""
        error = d.get('error', 'Unknown error')
        logging.error(f"Post-processing error: {error}")
        print(f"{Fore.RED}✗ Post-processing failed: {error}{Style.RESET_ALL}")
        
        # Store error for potential retry
        filepath = d.get('info_dict', {}).get('filepath')
        if filepath:
            self._failed_attempts[filepath] = {
                'error': error,
                'timestamp': time.time()
            }
    async def interactive_mode(self) -> None:
        """Interactive download mode with improved UX"""
        try:
            from .interactive_mode import SnatchUI
            
            # Initialize and run the interactive UI
            ui = SnatchUI(self)
            await ui.run()
        except ImportError as e:
            logging.error(f"Failed to load interactive mode: {e}")
            print(f"{Fore.RED}Failed to load interactive mode. Falling back to command line.{Style.RESET_ALL}")
            # Fallback to basic command line interface
            await self._basic_cli_mode()
    def __init__(self, config: Dict[str, Any]):
        """Initialize download manager with robust session handling."""
        if config is None:
            raise ValueError("Configuration cannot be None")
            
        self.config = config.copy()
        
        # Create necessary directories
        for dir_key in ["video_output", "audio_output"]:
            if path := config.get(dir_key):
                os.makedirs(path, exist_ok=True)
            else:
                raise ValueError(f"Missing required configuration field: {dir_key}")
        
        # Set up session management
        self.session_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "sessions")
        os.makedirs(self.session_dir, exist_ok=True)
        
        # Initialize session manager with session file path
        self.session_manager = SessionManager(DOWNLOAD_SESSIONS_FILE)
        
        # Initialize other components
        self.download_cache = DownloadCache()
        self.download_stats = DownloadStats(keep_history=True)
        self.file_organizer = FileOrganizer(config)
        
        # Download tracking
        self.current_download_url = None
        self.download_start_time = None
        self.current_downloads = {}
        
        # Error handling settings
        self.max_retries = config.get("max_retries", MAX_RETRIES)
        self.retry_delay = config.get("retry_delay", RETRY_SLEEP_BASE)
        self.exponential_backoff = config.get("exponential_backoff", True)
        
        # Resource management
        self.memory_limit = psutil.virtual_memory().total * (MAX_MEMORY_PERCENT / 100)
        self._active_downloads = 0
        self._download_lock = threading.RLock()
        
        # Failure tracking
        self._failed_attempts = {}
        self._failed_lock = threading.RLock()
        
        # Current download info
        self._current_info_dict = {}    
    async def interactive_mode(self) -> None:
        """Interactive download mode with improved UX"""
        from .interactive_mode import SnatchUI
        
        # Initialize and run the interactive UI
        ui = SnatchUI(self)
        await ui.run()
        
    def _update_layout(self, layout: Layout, status: str, message: str, console: Console):
        """Update layout with new status and message"""
        self._draw_layout_sections(layout, status)
        if message:
            console.print(message)
        console.print(layout)
        
    def _draw_layout_sections(self, layout: Layout, status: str = "Ready"):
        """Draw all layout sections"""
        layout["header"].update(self._draw_header())
        layout["main"].update(self._draw_body())
        layout["footer"].update(self._draw_footer(status))
        self._show_sidebar(layout["sidebar"])
        
    def _draw_header(self) -> Panel:
        """Draw header section"""
        return Panel(
            f"{Fore.GREEN}SNATCH DOWNLOAD MANAGER{Style.RESET_ALL}\n"
            f"Status: Active | Press F1 for options | Type 'help' for commands",
            title="[cyan]Header[/cyan]"
        )
        
    def _draw_body(self, content: str = "") -> Panel:
        """Draw main body section"""
        return Panel(content, title="[cyan]Main Area[/cyan]")
        
    def _draw_footer(self, status: str = "Ready") -> Panel:
        """Draw footer section"""
        return Panel(
            f"Status: {status} | F2: Toggle Sidebar | F3: Queue | Ctrl+C: Exit",
            title="[cyan]Footer[/cyan]"
        )
        
    async def _process_user_input(self, url: str, layout: Layout, console: Console) -> bool:
        """Process user input and return False if should exit"""
        if not url:
            return True
            
        if url.lower() in ('exit', 'quit', 'q'):
            console.print("[yellow]Exiting...[/yellow]")
            return False
            
        if url.lower() in ('help', '?'):
            show_full_help(console)
            return True
            
        if url.lower() == 'h':
            show_quick_help(console)
            return True
            
        # Handle advanced commands
        if url.startswith('!'):
            command = url[1:]
            result = await self._handle_interactive_command(command)
            if result is False:
                return True
                
        # Process download
        success = await self.download_with_retries(url, self.config)
        status = "Download completed" if success else "Download failed"
        message = (f"[green]✓ Successfully downloaded: {url}[/green]" if success 
                  else f"[red]✗ Failed to download: {url}[/red]")
        
        # Update layout
        self._update_layout(layout, status, message, console)
        return True
    async def interactive_mode(self) -> None:
        self.interactive_mode()

class UnifiedProgress:
    def __init__(self):
        self.http = Progress()
        self.p2p = Progress()
        self.layout = Layout()
        
    def create_task(self, description: str, total: float) -> str:
        """Create synchronized progress task"""
        task_id = self.http.add_task(description, total=total)
        self.p2p.add_task(description, total=total, id=task_id)
        return task_id
        
    def update(self, task_id: str, **kwargs):
        """Update both progress displays"""
        self.http.update(task_id, **kwargs)
        self.p2p.update(task_id, **kwargs)
