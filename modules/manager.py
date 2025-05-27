"""Enhanced download manager implementation with both async and sync support.

Features:
- Advanced error recovery and retry mechanisms
- Memory and bandwidth management
- Cross-platform compatibility
- Session persistence
- Multi-source fragment downloading
- Progress tracking and reporting
"""

import asyncio
import hashlib
import json
import logging
import os
import psutil
import re
import threading
import time
import aiohttp
import backoff
from abc import ABC, abstractmethod
from contextlib import contextmanager, asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable, Tuple, TypeVar, Protocol, Union, Set, TYPE_CHECKING
import platform
import tempfile
import sys
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

if TYPE_CHECKING:
    from .performance_monitor import PerformanceMonitor
    from .advanced_scheduler import AdvancedScheduler
    from .ffmpeg_helper import VideoUpscaler

# Format string constants
DEFAULT_VIDEO_FORMAT = "bestvideo+bestaudio/best"
BESTAUDIO_FORMAT = "bestaudio/best"

# Resolution-based format strings
FORMAT_4K = "bestvideo[height<=2160]+bestaudio/best[height<=2160]"
FORMAT_1440P = "bestvideo[height<=1440]+bestaudio/best[height<=1440]"
FORMAT_1080P = "bestvideo[height<=1080]+bestaudio/best[height<=1080]"
FORMAT_720P = "bestvideo[height<=720]+bestaudio/best[height<=720]"
FORMAT_480P = "bestvideo[height<=480]+bestaudio/best[height<=480]"

# Define custom exception classes
class DownloadError(Exception):
    """Base exception for download errors"""
    pass
    
class NetworkError(DownloadError):
    """Network-related errors"""
    pass
    
class ResourceError(DownloadError):
    """Resource-related errors (file not found, etc.)"""
    pass
    
class AudioConversionError(DownloadError):
    """Raised when audio conversion fails"""
    pass

# Import local utils to avoid circular imports
try:
    from .common_utils import sanitize_filename, format_size
except ImportError:
    # Define minimal versions if imports fail
    def sanitize_filename(filename: str) -> str:
        """Fallback sanitize_filename function"""
        invalid_chars = r'[<>:"/\\|?*\x00-\x1F]'
        return re.sub(invalid_chars, '', filename).strip(' .')
        
    def format_size(bytes_value: float, precision: int = 2) -> str:
        """Fallback format_size function"""
        if bytes_value < 0:
            return "0 B"
        units = ["B", "KB", "MB", "GB", "TB", "PB"]
        i = 0
        while bytes_value >= 1024 and i < len(units) - 1:
            bytes_value /= 1024
            i += 1
        return f"{bytes_value:.{precision}f} {units[i]}"

# Import error handling
from .error_handler import EnhancedErrorHandler, handle_errors, ErrorCategory, ErrorSeverity

from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn, DownloadColumn, TransferSpeedColumn
from rich.console import Console
from rich.live import Live
from rich.table import Table

from textual.app import App
from textual.widgets import Button, Header, Footer, Static

from .progress import DownloadStats, Spinner, SpinnerAnimation
from .defaults import (
    CACHE_DIR,
    DOWNLOAD_SESSIONS_FILE,
    MAX_RETRIES,
    RETRY_SLEEP_BASE,
    MAX_MEMORY_PERCENT,
    AUDIO_EXTENSIONS,
    VIDEO_EXTENSIONS,
)
from .session import SessionManager
from .cache import DownloadCache
from .file_organizer import FileOrganizer
from .ffmpeg_helper import locate_ffmpeg, validate_ffmpeg_installation
from .audio_processor import AudioProcessor
from .network import check_internet_connection, run_speedtest
from .constants import DEFAULT_TIMEOUT, DEFAULT_USER_AGENT, DEFAULT_CHUNK_SIZE

# File extensions
PART_EXT = '.part'
WEBM_EXT = '.webm'

# Format selection strings - use the more comprehensive version
COMPREHENSIVE_BESTAUDIO_FORMAT = (
    "bestaudio[ext=m4a]/bestaudio[ext=mp3]/"
    "bestaudio[ext=opus]/bestaudio[ext=aac]/"
    "bestaudio[ext=wav]/bestaudio[ext=flac]/"
    "bestaudio"
)

# FFmpeg filter configurations
FFMPEG_FILTERS = {
    "spatial": {
        "default": (
            "afir=dry=5:wet=5:length=100:lpf=1000:hpf=20,"
            "firequalizer=gain_entry='entry(0,0);entry(250,-6);entry(1000,0);entry(4000,3);entry(16000,6)'"
        ),
        "small_room": (
            "afir=dry=6:wet=4:length=50:lpf=2000:hpf=100,"
            "firequalizer=gain_entry='entry(0,0);entry(500,-2);entry(2000,1);entry(8000,3)'"
        )
    },
    "denoise": {
        "light": "anlmdn=s=3:p=0.001:m=15:b=256",  # Light touch NR
        "medium": "anlmdn=s=5:p=0.002:m=20:b=256", # Balanced NR
        "heavy": "anlmdn=s=7:p=0.003:m=25:b=256"   # Aggressive NR
    },
    "normalize": {
        "standard": "loudnorm=I=-14:TP=-1:LRA=11",  # EBU R128
        "podcast": "loudnorm=I=-16:TP=-1:LRA=9",    # Podcast standard  
        "film": "loudnorm=I=-23:TP=-1:LRA=20"       # Film standard
    }
}

# Error messages
ERROR_MSGS = {
    "INVALID_DATA": "Invalid data found",
    "CORRUPT_FILE": "Input file appears to be corrupt or invalid",
    "SAMPLE_RATE": "Sample rate",
    "SAMPLE_RATE_ERROR": "Sample rate conversion failed",
    "PERMISSION": "Permission denied",
    "PERMISSION_ERROR": "Permission error accessing audio files",
    "UNKNOWN_ERROR": "Unknown conversion error occurred",
    "CONFIG_NONE": "Configuration cannot be None",
    "FFMPEG_MISSING": "FFmpeg not found or invalid. Some features may be limited.",
    "NETWORK_ERROR": "Network error occurred. Check your connection and try again.",
    "DOWNLOAD_FAILED": "Download failed: {0}",
    "RESUME_FAILED": "Failed to resume download: {0}",
    "FILE_ACCESS_ERROR": "Failed to access file: {0}",
    "SERVER_ERROR": "Server error occurred: {0}",
    "RESOURCE_NOT_FOUND": "Resource not found: {0}",
    "MEMORY_LIMIT": "System memory limit reached. Try lowering concurrent downloads.",
    "DISK_SPACE": "Insufficient disk space to complete download."
}

# Regex patterns
FILENAME_PATTERN = r"^(.+?)(\.[^.]+)*(\.[^.]+)$"

# Constants
part_ext = '.part'
webn_ext = WEBM_EXT

logger = logging.getLogger(__name__)

# Custom exception hierarchy for better error handling
class DownloadError(Exception):
    """Base class for all download errors"""
    pass

class NetworkError(DownloadError):
    """Raised when network communication fails"""
    pass

class ResourceError(DownloadError):
    """Raised when a requested resource has issues"""
    pass

class FileSystemError(DownloadError):
    """Raised when file operations fail"""
    pass

class SystemResourceError(DownloadError):
    """Raised when system resources are insufficient"""
    pass

class AuthenticationError(DownloadError):
    """Raised when authentication fails"""
    pass

@dataclass
class DownloadChunk:
    """Represents a chunk of a download file"""
    start: int
    end: int
    url: str
    data: bytes = field(default=b"", repr=False)

@dataclass 
class DownloadConfig:
    """Configuration for a download operation"""
    url: str
    output_path: str
    chunk_size: int = DEFAULT_CHUNK_SIZE
    max_retries: int = MAX_RETRIES
    timeout: int = DEFAULT_TIMEOUT
    user_agent: str = DEFAULT_USER_AGENT
    resume: bool = True
    progress_callback: Optional[Callable] = None
    throttle_rate: int = 0  # 0 means no throttling
    metadata: Dict[str, Any] = field(default_factory=dict)
    headers: Dict[str, str] = field(default_factory=dict)

@dataclass
class ProgressUpdate:
    """Progress update for a download"""
    bytes_downloaded: int
    total_bytes: int
    speed_bps: float
    eta_seconds: float
    url: str
    filename: str
    status: str

class DownloadPostProcessor(ABC):
    """Abstract base class for download post-processors"""
    
    @abstractmethod
    async def process(self, file_path: str, metadata: Dict[str, Any]) -> str:
        """Process a downloaded file and return the path to the processed file"""
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
    """Enhanced download manager with improved UI and dependency injection.
    
    Features:
    - Dependency injection for core services
    - Plugin system for extensibility 
    - Improved session handling
    - Advanced audio/video format options
    - Resource-aware downloads
    """
    def __init__(
        self,
        config: Dict[str, Any],
        session_manager: Optional[SessionManager] = None,
        download_cache: Optional[DownloadCache] = None,
        file_organizer: Optional[FileOrganizer] = None,
        download_stats: Optional[DownloadStats] = None,
        performance_monitor: Optional['PerformanceMonitor'] = None,
        advanced_scheduler: Optional['AdvancedScheduler'] = None
    ):
        """Initialize download manager with injected dependencies."""
        if not config:
            raise ValueError(ERROR_MSGS["CONFIG_NONE"])
            
        self.config = config.copy()
        
        # Validate required paths
        for dir_key in ["video_output", "audio_output"]:
            if path := config.get(dir_key):
                os.makedirs(path, exist_ok=True)
            else:
                raise ValueError(f"Missing required configuration field: {dir_key}")
        
        # Initialize dependencies (with defaults if not injected)
        self.session_manager = session_manager or SessionManager(DOWNLOAD_SESSIONS_FILE)
        self.download_cache = download_cache or DownloadCache() 
        self.file_organizer = file_organizer or FileOrganizer(config)
        self.download_stats = download_stats or DownloadStats(keep_history=True)
    def __init__(
        self,
        config: Dict[str, Any],
        session_manager: Optional[SessionManager] = None,
        download_cache: Optional[DownloadCache] = None,
        file_organizer: Optional[FileOrganizer] = None,
        download_stats: Optional[DownloadStats] = None
    ):
        """Initialize download manager with injected dependencies."""
        if not config:
            raise ValueError(ERROR_MSGS["CONFIG_NONE"])
            
        self.config = config.copy()
        
        # Validate required paths
        for dir_key in ["video_output", "audio_output"]:
            if path := config.get(dir_key):
                os.makedirs(path, exist_ok=True)
            else:
                raise ValueError(f"Missing required configuration field: {dir_key}")
        
        # Initialize dependencies (with defaults if not injected)
        self.session_manager = session_manager or SessionManager(DOWNLOAD_SESSIONS_FILE)
        self.download_cache = download_cache or DownloadCache() 
        self.file_organizer = file_organizer or FileOrganizer(config)
        self.download_stats = download_stats or DownloadStats(keep_history=True)
        
        # Initialize advanced systems
        self._initialize_advanced_systems()
        
        # Track state
        self.current_download_url = None
        self.download_start_time = None
        self._active_downloads = 0
        self._download_lock = threading.RLock()
        self._failed_attempts = {}
        self._failed_lock = threading.RLock()
        
        # Configure retry behavior
        self.max_retries = config.get("max_retries", MAX_RETRIES)
        self.retry_delay = config.get("retry_delay", RETRY_SLEEP_BASE)
        self.exponential_backoff = config.get("exponential_backoff", True)
        
        # Set resource limits
        self.memory_limit = psutil.virtual_memory().total * (MAX_MEMORY_PERCENT / 100)
        
        # Validate FFmpeg
        self.ffmpeg_path = locate_ffmpeg()
        if not self.ffmpeg_path or not validate_ffmpeg_installation():
            logging.warning(ERROR_MSGS["FFMPEG_MISSING"])

        # Plugin system
        self.download_hooks = []
        self.post_processors = []

    def register_download_hook(self, hook: Callable[[str, Dict[str, Any]], None]) -> None:
        """Register a hook to be called during download stages."""
        self.download_hooks.append(hook)

    def register_post_processor(self, processor: Callable[[str, Dict[str, Any]], None]) -> None:
        """Register a post-processor for downloaded files."""
        self.post_processors.append(processor)

    async def get_sessions(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get list of download sessions, optionally filtered by status."""
        return await self.session_manager.list_sessions(status)

    async def cancel_session(self, session_id: str) -> bool:
        """Cancel an active download session."""
        return await self.session_manager.cancel_session(session_id)

    async def batch_update_sessions(self, updates: List[Dict[str, Any]]) -> None:
        """Update multiple sessions in batch."""
        await self.session_manager.batch_update(updates)

    async def get_session_stats(self) -> Dict[str, Any]:
        """Get statistics about download sessions."""
        return self.download_stats.get_statistics()    
    async def download(self, url: str, **kwargs) -> bool:
        """Download media with comprehensive error handling and progress tracking."""
        session_id = None
        try:
            self.current_download_url = url
            self.download_start_time = time.time()

            # Configure format and options
            options = self.get_download_options(**kwargs)
            
            # Register download session
            session_id = await self.session_manager.create_session(url, options)
            
            # Notify hooks of download start
            for hook in self.download_hooks:
                hook(url, options)
                
            # Perform download
            success = await self._perform_download(url, session_id, options)
            
            if success:
                # Run post-processors
                filepath = self._get_output_path(url, options)
                for processor in self.post_processors:
                    processor(filepath, options)
                    
            return success
            
        except asyncio.CancelledError:
            logging.info(f"Download cancelled for {url}")
            if session_id:
                await self.session_manager.update_session(session_id, {"status": "cancelled", "error": "Download was cancelled"})
            return False
            
        except Exception as e:
            logging.error(f"Download failed for {url}: {str(e)}")
            if session_id:
                await self.session_manager.update_session(session_id, {"status": "failed", "error": str(e)})
            return False
            
        finally:
            self.current_download_url = None
            self.download_start_time = None

    async def batch_download(
        self, urls: List[str], max_concurrent: Optional[int] = None, **kwargs
    ) -> List[bool]:
        """Download multiple URLs in parallel."""
        max_workers = max_concurrent or min(32, os.cpu_count() * 2)
        
        async with asyncio.Semaphore(max_workers):
            tasks = [self.download(url, **kwargs) for url in urls]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
        return [isinstance(r, bool) and r for r in results]    
    async def _perform_download(self, url: str, session_id: str, options: Dict[str, Any]) -> bool:
        """Execute the download with progress tracking and error handling."""
        try:
            # Configure yt-dlp options
            ydl_opts = {
                **options,
                "progress_hooks": [self._progress_hook],
                "postprocessor_hooks": [self._post_process_hook],
            }
            
            with self._download_lock:
                self._active_downloads += 1
            
            loop = asyncio.get_event_loop()
            try:
                await loop.run_in_executor(None, lambda: self._do_download(url, ydl_opts))
                error_code = 0
            except asyncio.CancelledError:
                logging.info(f"Download process cancelled for {url}")
                await self.session_manager.update_session(session_id, {"status": "cancelled"})
                return False
            except Exception as e:
                logging.error(f"Download error: {str(e)}")
                error_code = 1
                
            success = error_code == 0
            if success:
                await self.session_manager.update_session(session_id, {"status": "completed"})
            else:
                await self.session_manager.update_session(session_id, {"status": "failed"})
                
            return success
                
        except asyncio.CancelledError:
            logging.info(f"Download task cancelled for {url}")
            await self.session_manager.update_session(session_id, {"status": "cancelled"})
            return False
        except Exception as e:
            logging.error(f"Unexpected error in download process: {str(e)}")
            await self.session_manager.update_session(session_id, {"status": "failed", "error": str(e)})
            return False
        finally:
            with self._download_lock:
                self._active_downloads -= 1

    def _do_download(self, url: str, ydl_opts: Dict[str, Any]) -> None:
        """Perform actual download using yt-dlp."""
        import yt_dlp
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

    def _progress_hook(self, d: Dict[str, Any]) -> None:
        """Handle download progress updates."""
        status = d.get("status")
        
        if status == "downloading":
            self._handle_downloading_status(d)
        elif status == "finished":
            self._handle_finished_status(d)
        elif status == "error":
            self._handle_error_status(d)

    def _handle_downloading_status(self, d: Dict[str, Any]) -> None:
        """Process download progress information."""
        total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
        downloaded = d.get("downloaded_bytes", 0)
        
        if total > 0:
            percent = (downloaded / total) * 100
            
            # Update progress tracking
            if hasattr(self, "download_stats"):
                self.download_stats.update(downloaded=downloaded, total=total)
                
            # Update session progress
            if self.current_download_url:
                self.session_manager.update_session(
                    self.current_download_url, {"progress": percent}
                )

    def _handle_finished_status(self, d: Dict[str, Any]) -> None:
        """Process download completion."""
        filepath = d.get("filename", "")
        if not filepath:
            return
            
        is_fragment = any(
            marker in os.path.basename(filepath)
            for marker in (PART_EXT, ".f", "tmp")
        )
        
        if not is_fragment:
            duration = time.time() - (self.download_start_time or time.time())
            
            # Record statistics
            self.download_stats.add_download(
                success=True,
                size_bytes=os.path.getsize(filepath) if os.path.exists(filepath) else 0,
                duration=duration,
            )

    def _handle_error_status(self, d: Dict[str, Any]) -> None:
        """Process download errors."""
        error_msg = d.get("error", ERROR_MSGS["UNKNOWN_ERROR"])
        logging.error(f"Download error: {error_msg}")
        
        self.download_stats.add_download(success=False, error=error_msg)
        
    def _get_output_path(self, url: str, options: Dict[str, Any]) -> str:
        """Determine output file path based on options."""
        output_dir = (
            self.config["audio_output"]
            if options.get("extract_audio")
            else self.config["video_output"]
        )
        
        filename = options.get("outtmpl", {}).get("default", os.path.basename(url))
        return os.path.join(output_dir, filename)

    def get_download_options(
        self,
        *,
        audio_only: bool = False,
        resolution: Optional[str] = None,
        format_id: Optional[str] = None,
        filename: Optional[str] = None,
        audio_format: str = "opus",
        audio_channels: int = 2,
        video_codec: Optional[str] = None,
        retry_config: Optional[Dict[str, Any]] = None,
        additional_options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Get complete download options configuration.
        
        Args:
            audio_only: Whether to extract audio only
            resolution: Target video resolution (e.g. "1080p", "720p")
            format_id: Specific format ID to download
            filename: Output filename template
            audio_format: Target audio format for extraction
            audio_channels: Number of audio channels (2 for stereo, 8 for 7.1)
            video_codec: Preferred video codec
            retry_config: Custom retry configuration
            additional_options: Additional yt-dlp options
        """
        options = {}
        
        # Base output configuration
        options.update(self._get_base_output_config(audio_only, filename))
        
        # Common options (socket timeout, fragment handling etc)
        options.update(self._get_common_options())
        
        # Format selection
        options.update(
            self._get_format_options(
                format_id=format_id,
                audio_only=audio_only,
                audio_format=audio_format,
                audio_channels=audio_channels,
                resolution=resolution,
                video_codec=video_codec,
            )
        )
        
        # Retry configuration
        retry_opts = retry_config or {"max_retries": self.max_retries}
        options.update(self._get_retry_config(retry_opts))
        
        # Add any additional options
        if additional_options:
            options.update(additional_options)
            
        return options
        
    def _get_base_output_config(
        self, audio_only: bool, filename: Optional[str]
    ) -> Dict[str, Any]:
        """Configure output path and template."""
        output_dir = (
            self.config["audio_output"]
            if audio_only
            else self.config["video_output"]
        )
        
        if filename:
            filename = os.path.splitext(filename)[0]
            filename = re.sub(r'[\\/*?:"<>|]', "_", filename)
            template = f"{filename}.%(ext)s"
        else:
            template = "%(title)s.%(ext)s"
            
        return {
            "outtmpl": {
                "default": os.path.join(output_dir, template)
            },
            "restrictfilenames": True,
        }
        
    def _get_common_options(self) -> Dict[str, Any]:
        """Get common download options."""
        return {
            "ffmpeg_location": self.ffmpeg_path,
            "concurrent_fragment_downloads": min(16, os.cpu_count() or 4),
            "http_chunk_size": 10485760,  # 10MB chunks
            "socket_timeout": 30,
            "extractor_retries": 3,
            "file_access_retries": 3,
            "ignoreerrors": True,
            "skip_unavailable_fragments": True,
            "force_generic_extractor": False,
            "quiet": True,
            "no_warnings": False,
            "extract_flat": False,
        }
        
    def _get_retry_config(self, retry_opts: Dict[str, Any]) -> Dict[str, Any]:
        """Configure download retry behavior."""
        max_retries = retry_opts.get("max_retries", self.max_retries)
        return {
            "retries": max_retries,
            "fragment_retries": max_retries,
            "retry_sleep_functions": {
                "http": self._get_retry_delay
            } if self.exponential_backoff else None,
        }
        
    def _get_retry_delay(self, attempt: int) -> float:
        """Calculate delay between retry attempts."""
        if self.exponential_backoff:
            return self.retry_delay * (2 ** (attempt - 1))
        return self.retry_delay
        
    def _get_format_options(
        self,
        format_id: Optional[str],
        audio_only: bool,
        audio_format: str,
        audio_channels: int,
        resolution: Optional[str],
        video_codec: Optional[str],
    ) -> Dict[str, Any]:
        """Configure format selection and post-processing."""
        if format_id:
            return {"format": format_id}
            
        if audio_only:
            return self._get_audio_format_options(
                audio_format, audio_channels
            )
            
        return self._get_video_format_options(
            resolution, video_codec
        )
        
    def _get_audio_format_options(
        self, audio_format: str, audio_channels: int
    ) -> Dict[str, Any]:
        """Configure audio format options."""        
        options = {
            "format": BESTAUDIO_FORMAT,  # Use the simple version for consistency
            "extract_audio": True,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": audio_format,
                "preferredquality": "0",
                "nopostoverwrites": True
            }]
        }
        
        # Add channel-specific options
        if audio_channels == 8:  # 7.1 surround
            options["postprocessor_args"] = {
                "FFmpegExtractAudio": [
                    "-ac", "8",
                    "-channel_layout", "7.1",
                ]            }
            
        return options
        
    def _get_video_format_options(
        self, resolution: Optional[str], video_codec: Optional[str]
    ) -> Dict[str, Any]:
        """Configure video format options."""
        format_str = "bestvideo+bestaudio/best"
        
        if resolution:
            height = int(resolution.rstrip("p"))
            format_str = f"bestvideo[height<={height}]+bestaudio/best"
            
        if video_codec:
            format_str = f"{format_str}[vcodec={video_codec}]"
            
        return {"format": format_str}
        
    async def check_network_connectivity(self) -> Tuple[bool, str]:
        """Check internet connectivity with better error reporting."""
        return await check_internet_connection()
        
    async def measure_network_speed(self) -> float:
        """Get network speed measurement.
        
        Returns:
            Network speed in Mbps
        """
        result = await run_speedtest(detailed=False)
        return result.download_mbps

# HTTP Protocol and data classes for async functionality
class HTTPClientProtocol(Protocol):
    """Protocol defining HTTP client interface for dependency injection"""
    async def get(self, url: str, **kwargs) -> aiohttp.ClientResponse: ...
    async def head(self, url: str, **kwargs) -> aiohttp.ClientResponse: ...

@dataclass
class DownloadChunk:
    """Represents a chunk of a downloaded file with validation"""
    start: int
    end: int
    data: bytes = field(default=b"")
    sha256: str = ""
    retries: int = 0

class DownloadHooks(ABC):
    """Abstract base class defining hooks for download lifecycle events"""
    @abstractmethod
    async def pre_download(self, url: str, metadata: Dict[str, Any]) -> None:
        """Called before download starts"""
        pass
        
    @abstractmethod
    async def post_chunk(self, chunk: DownloadChunk, sha256: str) -> None:
        """Called after each chunk is downloaded"""
        pass
        
    @abstractmethod
    async def post_download(self, url: str, file_path: str) -> None:
        """Called after download completes"""
        pass

class AsyncDownloadManager:
    """Async download manager with resumable downloads and chunk validation"""
    
    def __init__(self, config: Dict[str, Any],
                 session_manager: SessionManager,
                 download_cache: DownloadCache,
                 http_client: Optional[HTTPClientProtocol] = None,
                 performance_monitor: Optional['PerformanceMonitor'] = None,
                 advanced_scheduler: Optional['AdvancedScheduler'] = None):
        self.config = config
        self.session_manager = session_manager 
        self.download_cache = download_cache
        self._http_client = None  # Will be created in __aenter__
        self.user_provided_client = http_client is not None
        if http_client:
            self._http_client = http_client
        self.hooks: List[DownloadHooks] = []
        self.chunk_size = 1024 * 1024  # 1MB default
        
        # Initialize error handler
        error_log_path = config.get("error_log_path", "logs/snatch_errors.log")
        self.error_handler = EnhancedErrorHandler(log_file=error_log_path)
        
        # Set or initialize advanced components
        self.performance_monitor = performance_monitor
        self.advanced_scheduler = advanced_scheduler
        
        # Initialize advanced systems if not provided
        if not self.performance_monitor or not self.advanced_scheduler:
            self._initialize_advanced_systems()
          # Create audio processor instance
        self.audio_processor = AudioProcessor(config) if 'AudioProcessor' in globals() else None
        
        # Initialize video upscaler
        self.video_upscaler = None
        if config.get("upscaling", {}).get("enabled", False):
            try:
                from .ffmpeg_helper import create_video_upscaler
                self.video_upscaler = create_video_upscaler(config)
                logging.info("Video upscaler initialized successfully")
            except ImportError as e:
                logging.warning(f"Video upscaling not available: {e}")
            except Exception as e:
                logging.error(f"Failed to initialize video upscaler: {e}")
        
        # Initialize P2P manager if enabled
        self.p2p_manager = None
        if config.get("p2p_enabled", False):
            try:
                from .p2p import P2PManager
                self.p2p_manager = P2PManager(config, session_manager)
                logging.info("P2P manager initialized successfully")
            except ImportError as e:
                logging.warning(f"P2P functionality not available: {e}")
            except Exception as e:
                logging.error(f"Failed to initialize P2P manager: {e}")
        
        # Active downloads tracking for P2P coordination
        self.active_downloads: Dict[str, Dict[str, Any]] = {}
        self.download_lock = asyncio.Lock()
        
        # Import dependencies
        self._import_dependencies()
        
    def _import_dependencies(self):
        """Import optional dependencies"""
        # Import yt-dlp for download functionality
        try:
            import yt_dlp
            self.yt_dlp = yt_dlp
            self.yt_dlp_available = True
        except ImportError:
            self.yt_dlp = None
            self.yt_dlp_available = False
            logging.warning("yt-dlp not available, some functionality may be limited")

    @property
    def http_client(self) -> HTTPClientProtocol:
        """Get the HTTP client session, creating it if needed"""
        if not self._http_client:
            self._http_client = aiohttp.ClientSession()
        return self._http_client

    async def __aenter__(self):
        """Async context manager entry"""
        if not self._http_client and not self.user_provided_client:
            self._http_client = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self._http_client and not self.user_provided_client:
            await self._http_client.close()
            self._http_client = None

    async def _calculate_sha256(self, data: bytes) -> str:
        """Calculate SHA256 hash of chunk data"""
        return hashlib.sha256(data).hexdigest()
        
    @backoff.on_exception(
        backoff.expo,
        (aiohttp.ClientError, asyncio.TimeoutError),
        max_tries=5
    )
    async def _download_chunk(self, url: str, chunk: DownloadChunk) -> bool:
        """Download a single chunk with retries and exponential backoff"""
        headers = {"Range": f"bytes={chunk.start}-{chunk.end}"}
        
        try:
            async with self.http_client.get(url, headers=headers) as response:
                if response.status != 206:
                    logging.error(f"Range request failed: got status {response.status}")
                    return False
                    
                chunk.data = await response.read()
                chunk.sha256 = await self._calculate_sha256(chunk.data)
                
                # Notify hooks
                for hook in self.hooks:
                    await hook.post_chunk(chunk, chunk.sha256)
                    
                return True
        except Exception as e:
            logging.error(f"Chunk download error: {str(e)}")
            chunk.retries += 1
            if chunk.retries >= 5:
                logging.error(f"Maximum retries reached for chunk {chunk.start}-{chunk.end}")
                return False
            raise  # Let backoff handle retry
    @handle_errors(ErrorCategory.DOWNLOAD, ErrorSeverity.ERROR)
    async def download(self, url: str, output_path: str, **options) -> str:
        """
        Download file with resume support and chunk validation
        
        Args:
            url: Download URL
            output_path: Where to save the file
            **options: Additional download options
            
        Returns:
            Path to downloaded file
        """
        console = Console()
        
        # Get content info
        try:
            async with self.http_client.head(url) as response:
                if response.status >= 400:
                    raise NetworkError(f"Failed to fetch URL: HTTP {response.status}")
                total_size = int(response.headers.get("Content-Length", 0))
                
            if total_size <= 0:
                raise ResourceError("Unable to determine file size. Content-Length header missing.")
                
        except aiohttp.ClientError as e:
            error_msg = f"Network error during download preparation: {str(e)}"
            logging.error(error_msg)
            self.error_handler.log_error(
                error_msg,
                ErrorCategory.NETWORK,
                ErrorSeverity.ERROR,
                context={"url": url, "error_type": "client_error"}
            )
            raise NetworkError(f"Connection error: {str(e)}") from e
        except Exception as e:
            error_msg = f"Error preparing download: {str(e)}"
            logging.error(error_msg)
            self.error_handler.log_error(
                error_msg,
                ErrorCategory.DOWNLOAD,
                ErrorSeverity.ERROR,
                context={"url": url, "preparation_stage": True}
            )
            raise
            
        # Load resume data if exists
        session_data = self.session_manager.get_session(url)
        resume_from = session_data.get("downloaded_bytes", 0) if session_data else 0
        
        # Calculate chunks
        chunks = []
        for start in range(resume_from, total_size, self.chunk_size):
            end = min(start + self.chunk_size - 1, total_size - 1)
            chunks.append(DownloadChunk(start=start, end=end))
            
        # Notify pre-download hooks
        metadata = {"total_size": total_size, "resume_from": resume_from}
        for hook in self.hooks:
            await hook.pre_download(url, metadata)
            
        # Download chunks
        temp_path = f"{output_path}.part"
        mode = "ab" if resume_from > 0 else "wb"
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]Downloading...", justify="right"),
            BarColumn(bar_width=40),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("•"),
            DownloadColumn(),
            TextColumn("•"),
            TransferSpeedColumn(),
            TextColumn("•"),
            TimeElapsedColumn(),
            console=console
        ) as progress:
            task = progress.add_task(f"Downloading {os.path.basename(output_path)}", total=total_size)
            progress.update(task, completed=resume_from)
            
            try:
                with open(temp_path, mode) as f:
                    for chunk in chunks:
                        success = await self._download_chunk(url, chunk)
                        if not success:
                            raise DownloadError(f"Failed to download chunk {chunk.start}-{chunk.end}")
                            
                        f.write(chunk.data)
                        progress.update(task, advance=len(chunk.data))
                        
                        # Update session
                        downloaded = chunk.end + 1
                        self.session_manager.update_session(url, {"progress": downloaded / total_size * 100})
                  # Rename temp file to final
                os.replace(temp_path, output_path)
            except Exception as e:
                logging.error(f"Download failed: {str(e)}")
                if os.path.exists(temp_path):
                    # Leave partial download for potential future resume
                    logging.info(f"Partial download saved as {temp_path}")
                raise
        
        # Notify post-download hooks
        for hook in self.hooks:
            await hook.post_download(url, output_path)
            
        return output_path    
    @handle_errors(ErrorCategory.DOWNLOAD, ErrorSeverity.ERROR)    
    async def download_with_options(self, urls: List[str], options: Dict[str, Any]) -> List[str]:
        """
        Download media with specified options from a list of URLs
        
        Args:
            urls: List of URLs to download
            options: Dictionary of download options (audio_only, resolution, etc.)
            
        Returns:
            List of paths to downloaded files
        """
        if not urls:
            logging.error("No URLs provided for download")
            return []
        
        # Prepare download environment
        self._prepare_download_environment(options)
        
        # Process downloads
        return await self._process_downloads(urls, options)
    
    def _prepare_download_environment(self, options: Dict[str, Any]) -> None:
        """Prepare the download environment and validate requirements"""
        self._validate_download_requirements(options)
        self._normalize_audio_options(options)
    
    def _normalize_audio_options(self, options: Dict[str, Any]) -> None:
        """Normalize CLI audio option names to processor-expected names"""
        # Map CLI flags to audio processor parameters
        if options.get('upmix_71'):
            options['upmix_audio'] = True
        if options.get('denoise'):
            options['denoise_audio'] = True
        
        # Set enhancement flag if any audio processing is requested
        if any(options.get(key, False) for key in ['upmix_audio', 'denoise_audio', 'normalize_audio']):
            options['process_audio'] = True
    async def _process_downloads(self, urls: List[str], options: Dict[str, Any]) -> List[str]:
        """Process all downloads with advanced scheduling and performance monitoring"""
        # Check if advanced scheduler is available and should be used
        if self.advanced_scheduler and len(urls) > 1:
            return await self._process_downloads_with_scheduler(urls, options)
        else:
            return await self._process_downloads_sequentially(urls, options)
    
    async def _process_downloads_with_scheduler(self, urls: List[str], options: Dict[str, Any]) -> List[str]:
        """Process downloads using the advanced scheduler for optimal performance"""
        console = Console()
        downloaded_files = []
        
        # Add downloads to scheduler queue
        download_tasks = []
        for url in urls:
            task_id = await self.advanced_scheduler.add_download(
                url=url,
                options=options,
                priority=options.get('priority', 5),  # Default priority
                callback=self._download_progress_callback
            )
            download_tasks.append((task_id, url))
            
        console.print(f"[cyan]Added {len(download_tasks)} downloads to scheduler queue[/]")
        
        # Monitor progress
        with console.status("[bold green]Processing downloads with scheduler...") as status:
            completed = 0
            while completed < len(download_tasks):
                # Check scheduler status
                scheduler_status = self.advanced_scheduler.get_status()
                active_downloads = scheduler_status.get('active_downloads', 0)
                queue_size = scheduler_status.get('queue_size', 0)
                
                status.update(f"[bold green]Active: {active_downloads}, Queued: {queue_size}, Completed: {completed}/{len(download_tasks)}[/]")
                
                # Check for completed downloads
                for task_id, url in download_tasks:
                    task_status = await self.advanced_scheduler.get_download_status(task_id)
                    if task_status.get('status') == 'completed' and task_status.get('result'):
                        downloaded_files.append(task_status['result'])
                        completed += 1
                    elif task_status.get('status') == 'failed':
                        console.print(f"[bold red]Failed: {url}[/]")
                        completed += 1
                        
                await asyncio.sleep(0.5)  # Brief pause
                
        self._report_download_results(downloaded_files, console)
        return downloaded_files
    
    async def _process_downloads_sequentially(self, urls: List[str], options: Dict[str, Any]) -> List[str]:
        """Process downloads sequentially (fallback method)"""
        ydl_opts = self._setup_download_options(options)
        downloaded_files = []
        console = Console()
        
        with console.status("[bold green]Downloading...") as _:
            for url in urls:
                try:
                    console.print(f"[cyan]Downloading:[/] {url}")
                    file_path = await self._download_single_file(url, ydl_opts, options, console)
                    
                    if file_path:
                        downloaded_files.append(file_path)
                except Exception as e:
                    console.print(f"[bold red]Error downloading {url}: {str(e)}[/]")
                    logging.error(f"Download error for {url}: {str(e)}")
        
        self._report_download_results(downloaded_files, console)
        return downloaded_files
    
    async def _download_progress_callback(self, task_id: str, progress_data: Dict[str, Any]) -> None:
        """Callback for download progress updates from scheduler"""
        if self.performance_monitor:
            # Update performance metrics
            self.performance_monitor.update_download_metrics(progress_data)
            
            # Check if performance optimization is needed
            metrics = self.performance_monitor.get_current_metrics()
            if metrics.get('cpu_percent', 0) > 90 or metrics.get('memory_percent', 0) > 90:
                await self.optimize_performance()
    def _report_download_results(self, downloaded_files: List[str], console: Console) -> None:
        """Report download results to the user"""
        if not downloaded_files:
            console.print("[bold yellow]No files were successfully downloaded.[/]")
        else:
            console.print(f"[bold green]Successfully downloaded {len(downloaded_files)} files.[/]")
    
    async def _download_single_file(self, url: str, ydl_opts: Dict[str, Any], options: Dict[str, Any], console: Console) -> Optional[str]:
        """Download a single file with all processing options"""
        # Try P2P download first if enabled
        file_path = await self._try_p2p_download(url, options, console)
          # Fall back to traditional download if P2P failed
        if not file_path:
            console.print("[blue]Using traditional download method[/]")
            file_path = await self._download_single_url(url, ydl_opts, console, options)
            
            # Apply audio processing for traditional downloads
            if file_path and self._needs_audio_processing(options):
                console.print(f"[yellow]Processing audio for:[/] {file_path}")
                await self._process_audio_async(file_path, options)
        
        # Handle P2P sharing if requested
        if file_path:
            await self._handle_p2p_sharing(file_path, options, console)
        
        return file_path
    
    async def _try_p2p_download(self, url: str, options: Dict[str, Any], console: Console) -> Optional[str]:
        """Try P2P download if enabled and available"""
        if not options.get('try_p2p', True) or not self.p2p_manager:
            return None
            
        console.print(f"[yellow]Checking P2P availability for:[/] {url}")
        p2p_available = await self.check_p2p_availability(url)
        
        if p2p_available:
            console.print("[green]Content found in P2P network, downloading...[/]")
            output_dir = self.config.get(
                "audio_output" if options.get("audio_only") else "video_output", 
                "downloads"
            )
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, f"p2p_download_{int(time.time())}")
            
            file_path = await self.download_via_p2p(url, output_path, **options)
            if file_path:
                console.print(f"[green]P2P download completed:[/] {file_path}")
                return file_path
        
        return None
    
    async def _handle_p2p_sharing(self, file_path: str, options: Dict[str, Any], console: Console) -> None:
        """Handle P2P file sharing if requested"""
        if options.get('share_p2p', False) and self.p2p_manager:
            console.print("[cyan]Sharing file via P2P network...[/]")
            share_code = await self.share_file_p2p(file_path)
            if share_code:
                console.print(f"[green]File shared! Share code: {share_code}[/]")
    
    def _needs_audio_processing(self, options: Dict[str, Any]) -> bool:
        """Check if audio processing is needed based on options"""
        return any([
            options.get('process_audio', False),
            options.get('upmix_audio', False),
            options.get('enhance_audio', False),
            options.get('denoise_audio', False),
            options.get('normalize_audio', False)
        ])
    
    def _validate_download_requirements(self, options: Dict[str, Any]) -> None:
        """Validate that required tools are available for download options."""
        # Import required modules
        try:
            import yt_dlp
        except ImportError:
            error_msg = "yt-dlp is not installed. Cannot perform downloads."
            logging.error(error_msg)
            raise ResourceError(error_msg)
        
        # Make sure ffmpeg is available for audio conversion if needed
        if options.get("audio_only"):
            try:
                from .ffmpeg_helper import locate_ffmpeg, validate_ffmpeg_installation
                ffmpeg_path = locate_ffmpeg()
                if not ffmpeg_path or not validate_ffmpeg_installation():
                    raise AudioConversionError("FFmpeg is required for audio conversion but not found or not working properly")
            except ImportError:
                logging.warning("FFmpeg helper not available, assuming FFmpeg is installed")
    
    def _setup_download_options(self, options: Dict[str, Any]) -> Dict[str, Any]:
        """Setup yt-dlp download options based on user preferences."""
        # Ensure we have sanitize_filename function
        try:
            from .common_utils import sanitize_filename
        except ImportError:
            # Fall back to local implementation if import fails
            def sanitize_filename(filename: str) -> str:
                """Sanitize filename by removing invalid characters"""
                invalid_chars = r'[<>:"/\\|?*\x00-\x1F]'
                return re.sub(invalid_chars, '_', filename).strip('. ')
        
        ydl_opts = {}
        
        # Set output directory based on audio_only flag
        output_dir = self.config.get(
            "audio_output" if options.get("audio_only") else "video_output", 
            "downloads"
        )
        os.makedirs(output_dir, exist_ok=True)
        
        # Set output template
        if options.get("filename"):
            filename = sanitize_filename(options.get("filename"))
            ydl_opts["outtmpl"] = os.path.join(output_dir, f"{filename}.%(ext)s")
        else:
            ydl_opts["outtmpl"] = os.path.join(output_dir, "%(title)s.%(ext)s")
        
        # Configure format-specific options
        self._configure_format_options(ydl_opts, options)
        
        return ydl_opts
    
    def _configure_format_options(self, ydl_opts: Dict[str, Any], options: Dict[str, Any]) -> None:
        """Configure format-specific download options."""
        # Handle audio-only downloads
        if options.get("audio_only"):
            ydl_opts["format"] = "bestaudio/best"
            ydl_opts["postprocessors"] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': options.get("audio_format", "mp3"),
                'preferredquality': options.get("audio_quality", "192"),
            }]
            logging.info(f"Audio download configured: format={options.get('audio_format', 'mp3')}, quality={options.get('audio_quality', '192')}")        # Handle resolution-specific downloads
        elif options.get("resolution"):
            res = options.get("resolution")
            # Convert resolution to height value
            if isinstance(res, str) and res.endswith("p"):
                res = res[:-1]
            try:
                height = int(res)
                # Use a more compatible format string approach
                # This format string works better with yt-dlp's actual format selection
                format_parts = []
                
                if height >= 2160:  # 4K
                    format_parts.extend([
                        FORMAT_4K,
                        FORMAT_1440P, 
                        FORMAT_1080P,
                        DEFAULT_VIDEO_FORMAT
                    ])
                elif height >= 1440:  # 1440p
                    format_parts.extend([
                        FORMAT_1440P,
                        FORMAT_1080P,
                        DEFAULT_VIDEO_FORMAT
                    ])
                elif height >= 1080:  # 1080p
                    format_parts.extend([
                        FORMAT_1080P,
                        FORMAT_720P,
                        DEFAULT_VIDEO_FORMAT
                    ])
                elif height >= 720:  # 720p
                    format_parts.extend([
                        FORMAT_720P,
                        FORMAT_480P,
                        DEFAULT_VIDEO_FORMAT
                    ])
                else:  # 480p and below
                    format_parts.extend([
                        f"bestvideo[height<={height}]+bestaudio/best[height<={height}]",
                        DEFAULT_VIDEO_FORMAT
                    ])
                
                # Combine format options
                format_string = "/".join(format_parts)
                ydl_opts["format"] = format_string
                logging.info(f"Video download configured: target resolution={height}p with fallbacks")
                logging.debug(f"Generated format string: {format_string}")
                
            except ValueError:
                logging.warning(f"Invalid resolution format: {res}, using default")
                ydl_opts["format"] = DEFAULT_VIDEO_FORMAT
        
        # Handle specific format ID
        elif options.get("format_id"):
            ydl_opts["format"] = options.get("format_id")
            logging.info(f"Using specific format: {options.get('format_id')}")        # Default to best quality
        else:
            ydl_opts["format"] = DEFAULT_VIDEO_FORMAT
    
    async def _download_single_url(self, url: str, ydl_opts: Dict[str, Any], console: Console, options: Dict[str, Any]) -> Optional[str]:
        """Download a single URL with the given options."""
        try:
            import yt_dlp
            
            # Add progress hook
            def progress_hook(d):
                if d['status'] == 'downloading':
                    percent = d.get('_percent_str', 'N/A')
                    speed = d.get('_speed_str', 'N/A')
                    console.print(f"[cyan]Downloading:[/] {percent} at {speed}")
                elif d['status'] == 'finished':
                    console.print(f"[green]Download completed:[/] {d['filename']}")
            
            ydl_opts["progress_hooks"] = [progress_hook]
            
            # Setup error handling
            def error_hook(error_msg):
                self.error_handler.log_error(
                    f"yt-dlp error: {error_msg}",
                    ErrorCategory.DOWNLOAD,
                    ErrorSeverity.ERROR,
                    context={"url": url, "ydl_error": True}
                )
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    # Extract info first to get filename
                    info = ydl.extract_info(url, download=False)
                    if not info:
                        raise DownloadError("Failed to extract video information")
                      # Download the video
                    ydl.download([url])
                    
                    # Get the downloaded filename
                    downloaded_file = ydl.prepare_filename(info)
                    
                    # Check if upscaling is requested and applicable
                    if self._should_upscale_video(options, downloaded_file):
                        upscaled_file = await self._apply_video_upscaling(downloaded_file, options, console)
                        if upscaled_file:
                            return upscaled_file
                    
                    return downloaded_file
                    
                except Exception as e:
                    error_hook(str(e))
                    raise DownloadError(f"Download failed for {url}: {str(e)}") from e
                    
        except Exception as e:
            self.error_handler.log_error(
                f"Failed to download {url}: {str(e)}",
                ErrorCategory.DOWNLOAD,
                ErrorSeverity.ERROR,
                context={"url": url, "download_error": True}
            )
            console.print(f"[red]Error downloading {url}:[/] {str(e)}")
            return None

    async def start_p2p_server(self) -> bool:
        """Start P2P server for peer-to-peer downloads"""
        if not self.p2p_manager:
            logging.warning("P2P manager not initialized")
            return False
        
        try:
            success = await self.p2p_manager.start_server()
            if success:
                logging.info(f"P2P server started on port {self.p2p_manager.port}")
                # Set up progress callbacks
                self.p2p_manager.on_transfer_progress = self._on_p2p_progress
                self.p2p_manager.on_transfer_complete = self._on_p2p_complete
                return True
            return False
        except Exception as e:
            logging.error(f"Failed to start P2P server: {e}")
            return False
    
    async def stop_p2p_server(self) -> None:
        """Stop P2P server"""
        if self.p2p_manager:
            await self.p2p_manager.stop_server()
            logging.info("P2P server stopped")
    
    def _on_p2p_progress(self, progress) -> None:
        """Handle P2P transfer progress updates"""
        # Update session with P2P progress
        if hasattr(progress, 'file_id') and progress.file_id in self.active_downloads:
            download_info = self.active_downloads[progress.file_id]
            download_info['p2p_progress'] = progress.progress_percent
            download_info['speed'] = progress.speed_bps
            download_info['eta'] = progress.eta_seconds
    
    def _on_p2p_complete(self, file_id: str, file_path: str) -> None:
        """Handle P2P transfer completion"""
        if file_id in self.active_downloads:
            download_info = self.active_downloads[file_id]
            download_info['status'] = 'completed'
            download_info['file_path'] = file_path
            logging.info(f"P2P download completed: {file_path}")
    
    async def check_p2p_availability(self, url: str) -> bool:
        """Check if content is available via P2P"""
        if not self.p2p_manager:
            return False
        
        try:
            # Generate content hash for P2P lookup
            content_hash = hashlib.sha256(url.encode()).hexdigest()
            return await self.p2p_manager.is_content_available(content_hash)
        except Exception as e:
            logging.debug(f"P2P availability check failed: {e}")
            return False
    
    async def download_via_p2p(self, url: str, output_path: str, **options) -> Optional[str]:
        """Attempt download via P2P network"""
        if not self.p2p_manager:
            return None
        
        try:
            content_hash = hashlib.sha256(url.encode()).hexdigest()
            file_id = f"download_{int(time.time())}"
            
            # Add to active downloads
            async with self.download_lock:
                self.active_downloads[file_id] = {
                    'url': url,
                    'output_path': output_path,
                    'status': 'starting',
                    'method': 'p2p'
                }
            
            # Attempt P2P download
            success = await self.p2p_manager.download_file(content_hash, output_path)
            
            if success:
                # Apply audio processing if needed
                if options.get('process_audio') and self.audio_processor:
                    await self._process_audio_async(output_path, options)
                
                return output_path
            
            return None
            
        except Exception as e:
            logging.error(f"P2P download failed: {e}")
            return None
        finally:
            # Clean up active downloads
            async with self.download_lock:
                self.active_downloads.pop(file_id, None)
    
    async def _process_audio_async(self, file_path: str, options: Dict[str, Any]) -> bool:
        """Process audio file with enhanced async operations"""
        if not self.audio_processor:
            logging.warning("Audio processor not available")
            return False
        
        try:
            # Check if file is audio
            audio_extensions = {'.mp3', '.wav', '.flac', '.aac', '.ogg', '.opus', '.m4a', '.wma'}
            if not any(file_path.lower().endswith(ext) for ext in audio_extensions):
                return True  # Not an audio file, no processing needed
            
            logging.info(f"Starting audio processing for: {file_path}")
            
            # Apply processing in optimal order
            processing_chain = []
            
            # 1. Denoising first (removes artifacts before other processing)
            if options.get('denoise_audio', False):
                processing_chain.append(('denoise', self.audio_processor.denoise_audio))
            
            # 2. Upmix to 7.1 surround sound if requested
            if options.get('upmix_audio', False):
                processing_chain.append(('upmix_7.1', self.audio_processor.upmix_to_7_1))
            
            # 3. Normalization last (final level adjustment)
            if options.get('normalize_audio', False):
                processing_chain.append(('normalize', self.audio_processor.normalize))
            
            # Execute processing chain
            for process_name, process_func in processing_chain:
                logging.info(f"Applying {process_name} to {file_path}")
                try:
                    success = await process_func(file_path)
                    if not success:
                        logging.warning(f"{process_name} failed for {file_path}")
                    else:
                        logging.info(f"{process_name} completed successfully for {file_path}")
                except Exception as e:
                    logging.error(f"Error during {process_name}: {e}")
            
            # Apply complete enhancement chain if requested
            if options.get('enhance_audio', False):
                logging.info(f"Applying complete audio enhancement chain to {file_path}")
                await self.audio_processor.apply_all_enhancements(file_path)
            
            return True
            
        except Exception as e:
            logging.error(f"Audio processing failed for {file_path}: {e}")
            return False
    
    async def get_p2p_peers(self) -> List[Dict[str, Any]]:
        """Get list of connected P2P peers"""
        if not self.p2p_manager:
            return []
        
        try:
            peers = []
            for peer_id, peer_info in self.p2p_manager.peers.items():
                peers.append({
                    'peer_id': peer_id,
                    'ip': peer_info.ip,
                    'port': peer_info.port,
                    'connected': peer_info.connected,
                    'last_seen': peer_info.last_seen,
                    'nat_type': peer_info.nat_type
                })
            return peers
        except Exception as e:
            logging.error(f"Error getting P2P peers: {e}")
            return []
    
    async def share_file_p2p(self, file_path: str) -> Optional[str]:
        """Share a file via P2P network and return share code"""
        if not self.p2p_manager:
            logging.warning("P2P manager not available")
            return None
        
        try:
            return await self.p2p_manager.share_file(file_path)
        except Exception as e:
            logging.error(f"Failed to share file via P2P: {e}")
            return None    
    def _initialize_advanced_systems(self) -> None:
        """Initialize advanced systems with graceful fallbacks."""
        # Initialize performance monitor if not already provided
        if not self.performance_monitor:
            try:
                from .performance_monitor import PerformanceMonitor
                self.performance_monitor = PerformanceMonitor(self.config)
                logging.info("Performance monitoring system initialized")
            except ImportError:
                logging.warning("Performance monitor not available")
                self.performance_monitor = None
            except Exception as e:
                logging.error(f"Failed to initialize performance monitor: {e}")
                self.performance_monitor = None
            
        # Initialize advanced scheduler if not already provided        if not self.advanced_scheduler:
            try:
                from .advanced_scheduler import AdvancedScheduler
                self.advanced_scheduler = AdvancedScheduler(self.config)
                logging.info("Advanced scheduler system initialized")
            except ImportError:
                logging.warning("Advanced scheduler not available")
                self.advanced_scheduler = None
            except Exception as e:
                logging.error(f"Failed to initialize advanced scheduler: {e}")
                self.advanced_scheduler = None
              # Initialize audio processor if available
        if not hasattr(self, 'audio_processor') or not self.audio_processor:
            try:
                from .audio_processor import EnhancedAudioProcessor
                self.audio_processor = EnhancedAudioProcessor(self.config)
                logging.info("Enhanced audio processor initialized")
            except ImportError:
                logging.warning("Enhanced audio processor not available")
                self.audio_processor = None
            except Exception as e:
                logging.error(f"Failed to initialize audio processor: {e}")
                self.audio_processor = None

    def get_system_status(self) -> Dict[str, Any]:
        """Get current system status and performance metrics."""
        status = {
            "active_downloads": self._active_downloads,
            "failed_attempts": len(self._failed_attempts),
            "cache_size": len(self.download_cache._cache) if self.download_cache else 0,
            "session_count": len(self.session_manager._sessions) if self.session_manager else 0,
        }
        
        # Add performance metrics if available
        if self.performance_monitor:
            metrics = self.performance_monitor.get_current_metrics()
            status.update({
                "cpu_usage": metrics.get("cpu_percent", 0),
                "memory_usage": metrics.get("memory_percent", 0),
                "disk_usage": metrics.get("disk_percent", 0),
                "network_usage": metrics.get("network_mbps", 0),
                "performance_recommendations": self.performance_monitor.get_optimization_recommendations()
            })
            
        # Add scheduler status if available
        if self.advanced_scheduler:
            scheduler_status = self.advanced_scheduler.get_status()
            status.update({
                "queue_size": scheduler_status.get("queue_size", 0),
                "bandwidth_usage": scheduler_status.get("bandwidth_usage", 0),
                "scheduler_active": scheduler_status.get("active", False)
            })
            
        return status

    async def optimize_performance(self) -> Dict[str, Any]:
        """Optimize system performance based on current conditions."""
        if not self.performance_monitor:
            return {"status": "performance_monitor_unavailable"}
            
        metrics = self.performance_monitor.get_current_metrics()
        recommendations = self.performance_monitor.get_optimization_recommendations()
        
        optimizations_applied = []
        
        # Apply CPU optimization
        if metrics.get("cpu_percent", 0) > 80:
            if self.advanced_scheduler:
                current_concurrent = self.config.get("max_concurrent", 3)
                new_concurrent = max(1, current_concurrent - 1)
                self.config["max_concurrent"] = new_concurrent
                optimizations_applied.append(f"Reduced concurrent downloads to {new_concurrent}")
                
        # Apply memory optimization
        if metrics.get("memory_percent", 0) > 85:
            current_chunk = self.config.get("chunk_size", 1048576)
            new_chunk = max(262144, current_chunk // 2)  # Minimum 256KB
            self.config["chunk_size"] = new_chunk
            optimizations_applied.append(f"Reduced chunk size to {new_chunk}")
            
        # Apply disk space optimization
        if metrics.get("disk_percent", 0) > 90:
            # Enable compression for temporary files
            self.config["compress_temp"] = True
            optimizations_applied.append("Enabled temporary file compression")
            return {
            "status": "optimized",
            "metrics": metrics,
            "recommendations": recommendations,
            "optimizations_applied": optimizations_applied
        }
    
    # Alias method for API compatibility
    async def download_async(self, urls: List[str], options: Dict[str, Any]) -> List[str]:
        """Alias for download_with_options for backward compatibility"""
        return await self.download_with_options(urls, options)
    def _should_upscale_video(self, options: Dict[str, Any], file_path: str) -> bool:
        """Check if video should be upscaled based on options and file type"""
        if not self.video_upscaler:
            return False
            
        # Check if upscaling is enabled in options
        if not options.get("upscale_video", False):
            return False
            
        # Check if file is a video file
        video_extensions = {'.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv', '.wmv'}
        file_ext = Path(file_path).suffix.lower()
        if file_ext not in video_extensions:
            return False
            
        # Don't upscale audio-only downloads
        if options.get("audio_only", False):
            return False
            
        return True
    async def _apply_video_upscaling(self, file_path: str, options: Dict[str, Any], console: Console) -> Optional[str]:
        """Apply video upscaling to the downloaded file"""
        try:
            console.print(f"[yellow]Starting video upscaling for:[/] {Path(file_path).name}")
            
            # Prepare upscaling configuration
            upscale_config = self._prepare_upscale_config(options)
            
            # Generate output path for upscaled video
            input_path = Path(file_path)
            output_path = input_path.parent / f"{input_path.stem}_upscaled{input_path.suffix}"
            
            console.print(f"[cyan]Upscaling method:[/] {upscale_config.get('method', 'lanczos')} "
                         f"{upscale_config.get('scale_factor', 2)}x")
            
            # Perform upscaling
            success = await self.video_upscaler.upscale_video(
                str(input_path),
                str(output_path),
                upscale_config
            )
            
            if success and output_path.exists():
                console.print(f"[green]Video upscaling completed:[/] {output_path.name}")
                
                # Optionally remove original file if requested
                if options.get("replace_original", False):
                    try:
                        input_path.unlink()
                        output_path.rename(input_path)
                        console.print("[blue]Replaced original file with upscaled version[/]")
                        return str(input_path)
                    except Exception as e:
                        logging.warning(f"Failed to replace original file: {e}")
                        return str(output_path)
                else:
                    return str(output_path)
            else:
                console.print(f"[red]Video upscaling failed for:[/] {input_path.name}")
                return file_path  # Return original file
                
        except Exception as e:
            console.print(f"[red]Error during video upscaling:[/] {str(e)}")
            logging.error(f"Video upscaling error: {str(e)}")
            return file_path  # Return original file on error
    
    def _prepare_upscale_config(self, options: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare upscaling configuration from options and defaults"""
        # Get default upscaling config
        default_config = self.config.get("upscaling", {})
        
        # Merge with user options
        upscale_config = {
            "method": options.get("upscale_method", default_config.get("method", "lanczos")),
            "scale_factor": options.get("upscale_factor", default_config.get("scale_factor", 2)),
            "quality": options.get("upscale_quality", default_config.get("quality", "high")),
            "preserve_aspect_ratio": default_config.get("preserve_aspect_ratio", True),
            "max_resolution": default_config.get("max_resolution", "4K"),
            "gpu_acceleration": default_config.get("gpu_acceleration", True)
        }
        
        return upscale_config