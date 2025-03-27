import sys
import os
import yt_dlp
import argparse
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional, List, Dict, Any, Union, Tuple, Callable
import json
import textwrap
import mutagen
from mutagen.mp3 import MP3
from mutagen.flac import FLAC
import subprocess
from tqdm import tqdm
import threading
import time
from colorama import init, Fore, Style
from difflib import get_close_matches
import shutil
import re
import platform
import signal
from functools import lru_cache
import psutil  # Add this import for system resource monitoring
import urllib.parse
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed, wait, FIRST_COMPLETED
from contextlib import contextmanager
from typing import Optional, List, Dict, Any, Union, Tuple, Callable, Generator, Iterator

# Initialize colorama for Windows support with autoreset for cleaner code
init(autoreset=True)

class CustomHelpFormatter(argparse.HelpFormatter):
    def _split_lines(self, text, width):
        return [line for line in textwrap.wrap(text, width)]

# Constants moved to top for better organization and maintainability
CONFIG_FILE = 'config.json'
FLAC_EXT = '.flac'
VERSION = "1.2.0"  # Centralized version definition
LOG_FILE = 'download_log.txt'
SPINNER_CHARS = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
DEFAULT_CONFIG = {
    'ffmpeg_location': '',  # Will be auto-detected
    'video_output': str(Path.home() / 'Videos'),
    'audio_output': str(Path.home() / 'Music'),
    'max_concurrent': 3
}

# Enhanced spinner characters for better visual appearance
SPINNER_CHARS = ['⣾', '⣽', '⣻', '⢿', '⡿', '⣟', '⣯', '⣷']
# Alternative spinners that users can select
SPINNER_STYLES = {
    "dots": ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'],
    "line": ['|', '/', '-', '\\'],
    "grow": ['▏', '▎', '▍', '▌', '▋', '▊', '▉', '█', '▉', '▊', '▋', '▌', '▍', '▎', '▏'],
    "pulse": ['█', '▓', '▒', '░', '▒', '▓'],
    "bounce": ['⠁', '⠂', '⠄', '⠂'],
    "moon": ['🌑', '🌒', '🌓', '🌔', '🌕', '🌖', '🌗', '🌘'],
    "aesthetic": ['⣾', '⣽', '⣻', '⢿', '⡿', '⣟', '⣯', '⣷']
}

# Common file extensions by type for better categorization
AUDIO_EXTENSIONS = {'.mp3', '.flac', '.wav', '.m4a', '.aac', '.ogg', '.opus'}
VIDEO_EXTENSIONS = {'.mp4', '.webm', '.mkv', '.avi', '.mov', '.flv', '.wmv', '.3gp'}

# Create a download cache directory for faster repeated downloads
CACHE_DIR = Path.home() / '.snatch' / 'cache'
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Add system resource constraints to prevent overloading
MAX_MEMORY_PERCENT = 80  # Don't use more than 80% of system memory
DEFAULT_CHUNK_SIZE = 8192  # Optimal for most systems

# Set up a handler for SIGINT to ensure clean exits
def signal_handler(sig, frame):
    print(f"\n{Fore.YELLOW}Operation cancelled by user. Exiting gracefully...{Style.RESET_ALL}")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

# Examples text unchanged
EXAMPLES = """
Examples:
---------
1. Download a video from various platforms:
   python Snatch.py "https://youtube.com/watch?v=example"
   python Snatch.py "https://vimeo.com/123456789"
   python Snatch.py "https://dailymotion.com/video/x7tgd2g"
   python Snatch.py "https://twitch.tv/videos/1234567890"

2. Download audio only (MP3):
   python Snatch.py "https://soundcloud.com/artist/track" --audio-only

3. Download video in specific resolution:
   python Snatch.py "https://youtube.com/watch?v=example" --resolution 1080

4. Download multiple videos:
   python Snatch.py "URL1" "URL2" "URL3"

5. Download with custom filename:
   python Snatch.py "URL" --filename "my_video"

6. Download audio in FLAC format:
   python Snatch.py "URL" --audio-only --audio-format flac

Advanced Usage:
--------------
- Custom output directory:
  python Snatch.py "URL" --output-dir "path/to/directory"

- Specify format ID (for advanced users):
  python Snatch.py "URL" --format-id 137+140

- List all supported sites:
  python Snatch.py --list-sites

Common Issues:
--------------
1. FFMPEG not found: Install FFMPEG and update config.json
2. SSL Error: Update Python and yt-dlp
3. Permission Error: Run with admin privileges
"""

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
            r'C:\ffmpeg\bin',
            r'C:\Program Files\ffmpeg\bin',
            r'C:\ffmpeg\ffmpeg-master-latest-win64-gpl\bin',
            r'.\ffmpeg\bin',  # Relative to script location
        ]
        
        # Check if ffmpeg is in PATH on Windows
        try:
            result = subprocess.run(['where', 'ffmpeg'], capture_output=True, text=True, timeout=3)
            if result.returncode == 0:
                path = result.stdout.strip().split('\n')[0]
                return os.path.dirname(path)
        except (subprocess.SubprocessError, FileNotFoundError):
            pass
    else:
        common_locations = [
            '/usr/bin',
            '/usr/local/bin',
            '/opt/local/bin',
            '/opt/homebrew/bin'
        ]
        
        # Check if ffmpeg is in PATH on Unix-like systems
        try:
            result = subprocess.run(['which', 'ffmpeg'], capture_output=True, text=True, timeout=3)
            if result.returncode == 0:
                path = result.stdout.strip()
                return os.path.dirname(path)
        except (subprocess.SubprocessError, FileNotFoundError):
            pass
    
    # Check common locations for ffmpeg binary
    ffmpeg_exec = 'ffmpeg.exe' if is_windows() else 'ffmpeg'
    for location in common_locations:
        ffmpeg_path = os.path.join(location, ffmpeg_exec)
        if os.path.exists(ffmpeg_path):
            return location
    
    return None

def print_ffmpeg_instructions():
    """Print instructions for installing FFmpeg with platform-specific guidance"""
    print(f"{Fore.YELLOW}FFmpeg not found! Please follow these steps to install FFmpeg:{Style.RESET_ALL}")
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
    print("\nFor detailed instructions, visit: https://www.wikihow.com/Install-FFmpeg-on-Windows")

class ColorProgressBar:
    """Enhanced progress bar with color support and performance optimizations"""
    def __init__(self, total: int, desc: str = "Processing", unit: str = "%", color_scheme: str = "gradient"):
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
            "simple": [Fore.CYAN]
        }
        
        # Set scheme and prepare variables - use get() with default for safety
        self.colors = self.color_schemes.get(color_scheme, self.color_schemes["gradient"])
        self.current_color_idx = 0
        self.last_update = 0
        self.color_scheme = color_scheme
        self.completed = False
        self.last_percent = 0  # Track last percentage to avoid redundant updates
        
        # Create the tqdm progress bar
        self.progress = tqdm(
            total=total,
            desc=f"{Fore.CYAN}{desc}{Style.RESET_ALL}",
            bar_format="{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]",
            ncols=bar_width,
            unit=unit,
            dynamic_ncols=True,  # Allow resizing with terminal
            smoothing=0.3        # Add smoothing for more stable rate calculation
        )

    def update(self, n: int = 1) -> None:
        """Update the progress bar with optimized color handling and error tolerance"""
        try:
            current_progress = self.progress.n + n
            
            # Calculate percentage once for efficiency
            percent_complete = min(100, int((current_progress / self.progress.total) * 100))
            
            # Skip update if percentage hasn't changed (optimization)
            if percent_complete == self.last_percent and self.color_scheme != "rotating":
                self.progress.update(n)  # Still update the counter without changing colors
                return
                
            self.last_percent = percent_complete
            current_time = time.time()
            
            # Optimized color update logic
            if self.color_scheme == "gradient":
                # Color based on percentage complete - optimize calculation
                color_idx = min(len(self.colors) - 1, percent_complete * len(self.colors) // 100)
                current_color = self.colors[color_idx]
            elif current_time - self.last_update > 0.2:  # Limit updates for rotating scheme (performance)
                # Rotating colors
                self.current_color_idx = (self.current_color_idx + 1) % len(self.colors)
                current_color = self.colors[self.current_color_idx]
                self.last_update = current_time
            else:
                current_color = self.colors[self.current_color_idx]
                
            # Update the bar format with the selected color
            self.progress.bar_format = (
                "{desc}: {percentage:3.0f}%|"
                f"{current_color}"
                "{bar}"
                f"{Style.RESET_ALL}"
                "| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]"
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
                
        except Exception as e:
            # Fallback to normal update in case of issues with color or formatting
            try:
                self.progress.update(n)
            except:
                pass  # Last resort if everything fails

    def close(self, message: Optional[str] = None) -> None:
        """Close the progress bar with optional completion message"""
        if hasattr(self, 'progress') and not self.progress.disable:
            try:
                self.progress.close()
                if message:
                    print(f"\n{Fore.GREEN}✓ {message}{Style.RESET_ALL}")
                elif not self.completed:  # Don't print twice if already completed
                    print(f"\n{Fore.GREEN}✓ Complete!{Style.RESET_ALL}")
            except:
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
║     {Fore.GREEN}■ {Fore.WHITE}Version: {Fore.YELLOW}1.2.0{Fore.WHITE}                                   {Fore.CYAN}  ║
║     {Fore.GREEN}■ {Fore.WHITE}Author : {Fore.YELLOW}Rashed Alothman{Fore.WHITE}                           {Fore.CYAN}║
║     {Fore.GREEN}■ {Fore.WHITE}GitHub : {Fore.YELLOW}github.com/Rashed-alothman/Snatch{Fore.WHITE}        {Fore.CYAN} ║
╠{'═' * 58}╣
║  {Fore.YELLOW}Type {Fore.GREEN}help{Fore.YELLOW} or {Fore.GREEN}?{Fore.YELLOW} for commands  {Fore.WHITE}|  {Fore.YELLOW}Press {Fore.GREEN}Ctrl+C{Fore.YELLOW} to cancel  {Fore.CYAN}║
╚{'═' * 58}╝{Style.RESET_ALL}"""

    # Calculate padding for centering
    lines = banner.split('\n')
    max_content_width = max((len(re.sub(r'\x1b\[[0-9;]+m', '', line)) for line in lines if line), default=0)
    padding = max(0, (terminal_width - max_content_width) // 2)
    
    # Print banner with padding
    print('\n' * 2)  # Add some space above banner
    for line in banner.split('\n'):
        if line:
            print(' ' * padding + line)
    print('\n')  # Add space below banner

class SpinnerAnimation:
    """Animated spinner for loading states with resource cleanup improvements"""
    def __init__(self, message: str = "Processing"):
        self.spinner = SPINNER_CHARS
        self.message = message
        self.running = False
        self.thread = None
        self._lock = threading.Lock()  # Thread safety

    def spin(self):
        """Spin animation with reduced CPU usage"""
        while self.running:
            for char in self.spinner:
                if not self.running:
                    break
                with self._lock:
                    print(f"\r{Fore.CYAN}{char} {self.message}...{Style.RESET_ALL}", end='', flush=True)
                time.sleep(0.1)  # Reduced CPU usage

    def start(self):
        """Start spinner animation safely"""
        with self._lock:
            if not self.running:
                self.running = True
                self.thread = threading.Thread(target=self.spin, daemon=True)  # Make thread daemon
                self.thread.start()

    def stop(self):
        """Stop spinner animation with proper resource cleanup"""
        with self._lock:
            self.running = False
        
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)  # Timeout to prevent hanging
            
        # Clear the spinner line
        print('\r' + ' ' * (len(self.message) + 20) + '\r', end='')

@lru_cache(maxsize=100)
def fuzzy_match_command(input_cmd: str, valid_commands: tuple) -> Optional[str]:
    """Find the closest matching command with caching for performance"""
    matches = get_close_matches(input_cmd.lower(), valid_commands, n=1, cutoff=0.6)
    return matches[0] if matches else None

@contextmanager
def timer(name: str = "Operation", silent: bool = False) -> Generator:
    """Context manager to time operations for performance tracking"""
    start_time = time.time()
    try:
        yield
    finally:
        elapsed = time.time() - start_time
        if not silent:
            print(f"{Fore.CYAN}⏱️ {name} completed in {elapsed:.2f} seconds{Style.RESET_ALL}")

def get_available_memory() -> int:
    """Get available system memory in bytes"""
    return psutil.virtual_memory().available

def is_memory_sufficient() -> bool:
    """Check if system has sufficient memory"""
    vm = psutil.virtual_memory()
    return vm.percent < MAX_MEMORY_PERCENT

def estimate_download_size(info: Dict[str, Any]) -> int:
    """Estimate download size in bytes from media info"""
    if 'filesize' in info and info['filesize']:
        return info['filesize']
    elif 'filesize_approx' in info and info['filesize_approx']:
        return info['filesize_approx']
    else:
        # Estimate based on duration and format
        duration = info.get('duration', 0)
        if 'formats' in info:
            for fmt in info['formats']:
                if fmt.get('filesize'):
                    return fmt['filesize']
        
        # Return a conservative estimate based on duration (3MB per minute)
        return int(duration * 50000)  # ~3MB/minute

class EnhancedSpinnerAnimation:
    """Advanced animated spinner with customization and message updates"""
    def __init__(self, message: str = "Processing", style: str = "aesthetic", 
                 color: str = "cyan", delay: float = 0.08):
        self.style = style.lower()
        self.spinner = SPINNER_STYLES.get(self.style, SPINNER_STYLES["aesthetic"])
        self.message = message
        self.color_name = color.lower()
        self.color = getattr(Fore, color.upper(), Fore.CYAN)
        self.delay = delay
        self.running = False
        self.thread = None
        self._lock = threading.Lock()
        self._paused = False
        self._last_terminal_width = shutil.get_terminal_size().columns
        self._status_text = ""
        self._start_time = None
        
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
            self.spinner = SPINNER_STYLES.get(self.style, SPINNER_STYLES["aesthetic"])

    def spin(self) -> None:
        """Spin animation with adaptive terminal width handling"""
        self._start_time = time.time()
        
        while self.running:
            try:
                # Check if terminal size changed
                current_width = shutil.get_terminal_size().columns
                if current_width != self._last_terminal_width:
                    self._last_terminal_width = current_width
                
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
                    if len(formatted_msg) + 5 > self._last_terminal_width:
                        # Truncate with ellipsis if needed
                        max_len = self._last_terminal_width - 5
                        formatted_msg = formatted_msg[:max_len-3] + "..."
                    
                    # Print the spinner frame
                    print(f"\r{self.color}{char} {formatted_msg}{Style.RESET_ALL}", end='', flush=True)
                    time.sleep(self.delay)
            
            except Exception:
                # Prevent spinner from crashing the main program
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
            self.thread.join(timeout=0.5)
        
        if clear:
            # Clear the spinner line completely
            print('\r' + ' ' * (self._last_terminal_width - 1) + '\r', end='')
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
    """Cache for optimizing repeated downloads"""
    def __init__(self, cache_dir: Path = CACHE_DIR, max_size_mb: int = 100):
        self.cache_dir = cache_dir
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._cleanup_if_needed()
        
    def _get_cache_key(self, url: str) -> str:
        """Generate a unique key for a URL"""
        return hashlib.md5(url.encode('utf-8')).hexdigest()
    
    def get_info(self, url: str) -> Optional[Dict]:
        """Get cached info for a URL"""
        key = self._get_cache_key(url)
        info_path = self.cache_dir / f"{key}.info.json"
        
        if info_path.exists() and time.time() - info_path.stat().st_mtime < 3600:  # 1 hour cache
            try:
                with open(info_path, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return None
        return None
        
    def save_info(self, url: str, info: Dict) -> None:
        """Save info for a URL"""
        key = self._get_cache_key(url)
        info_path = self.cache_dir / f"{key}.info.json"
        
        try:
            with open(info_path, 'w') as f:
                json.dump(info, f)
        except IOError:
            pass
            
    def _cleanup_if_needed(self) -> None:
        """Clean up cache if it exceeds size limit"""
        try:
            cache_size = sum(f.stat().st_size for f in self.cache_dir.glob('*') if f.is_file())
            
            if cache_size > self.max_size_bytes:
                # Delete oldest files first
                files = [(f, f.stat().st_mtime) for f in self.cache_dir.glob('*') if f.is_file()]
                files.sort(key=lambda x: x[1])  # Sort by modification time
                
                # Delete files until we're under the size limit
                for file, _ in files:
                    file.unlink(missing_ok=True)
                    cache_size = sum(f.stat().st_size for f in self.cache_dir.glob('*') if f.is_file())
                    if cache_size < self.max_size_bytes * 0.8:  # Clean up to 80% of max
                        break
        except Exception:
            # Ignore cleanup errors
            pass

class DownloadManager:
    """Enhanced download manager with improved performance and resource management"""
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # Initialize the download cache
        self.download_cache = DownloadCache()
        
        # FFmpeg validation with better error handling
        if not self.config.get('ffmpeg_location'):
            ffmpeg_path = find_ffmpeg()
            if ffmpeg_path:
                self.config['ffmpeg_location'] = ffmpeg_path
            else:
                print_ffmpeg_instructions()
                raise FileNotFoundError("FFmpeg is required but not found. Please install FFmpeg and try again.")
        
        self.setup_logging()
        self.verify_paths()
        self.last_percentage = 0
        
        # Convert to tuple for better performance with lru_cache
        self.valid_commands = (
            'download', 'dl', 'audio', 'video', 'help', '?', 'exit', 'quit', 'q',
            'flac', 'mp3', 'wav', 'm4a', 'list', 'sites', 'clear', 'cls'
        )
        
        # Cached format descriptions for performance
        self._format_descriptions = {
            'mp3': 'High quality MP3 (320kbps)',
            'flac': 'Lossless audio (best quality)',
            'wav': 'Uncompressed audio',
            'm4a': 'AAC audio (good quality)'
        }
        
        # Track active downloads for better resource management
        self._active_downloads = set()
        self._download_lock = threading.RLock()

    def setup_logging(self):
        """Set up logging with rotation and improved error handling"""
        try:
            log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            
            # File handler with error handling
            try:
                file_handler = logging.FileHandler(LOG_FILE)
                file_handler.setFormatter(log_formatter)
            except (PermissionError, OSError) as e:
                print(f"{Fore.YELLOW}Warning: Could not create log file: {str(e)}{Style.RESET_ALL}")
                file_handler = None
                
            # Console handler (always works)
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(log_formatter)
            
            # Set up root logger
            root_logger = logging.getLogger()
            root_logger.setLevel(logging.INFO)
            
            # Remove any existing handlers
            for handler in root_logger.handlers[:]:
                root_logger.removeHandler(handler)
                
            # Add handlers
            if file_handler:
                root_logger.addHandler(file_handler)
            root_logger.addHandler(console_handler)
            
        except Exception as e:
            print(f"{Fore.YELLOW}Warning: Logger setup failed: {str(e)}. Using basic logging.{Style.RESET_ALL}")
            logging.basicConfig(level=logging.INFO)

    def verify_paths(self):
        """Verify and create necessary paths with improved error handling"""
        # Verify FFmpeg location
        if not os.path.exists(self.config['ffmpeg_location']):
            # Try to find FFmpeg as a last resort
            ffmpeg_path = find_ffmpeg()
            if ffmpeg_path:
                self.config['ffmpeg_location'] = ffmpeg_path
            else:
                raise FileNotFoundError(f"FFMPEG not found at {self.config['ffmpeg_location']}")
        
        # Create output directories with error handling
        for key in ['video_output', 'audio_output']:
            try:
                os.makedirs(self.config[key], exist_ok=True)
            except (PermissionError, OSError) as e:
                # Try to use home directory as fallback
                fallback_dir = str(Path.home() / ('Videos' if key == 'video_output' else 'Music'))
                print(f"{Fore.YELLOW}Warning: Could not create {key}: {str(e)}. Using {fallback_dir}{Style.RESET_ALL}")
                try:
                    os.makedirs(fallback_dir, exist_ok=True)
                    self.config[key] = fallback_dir
                except OSError:
                    raise RuntimeError(f"Cannot create any output directory for {key}")

    def progress_hook(self, d: Dict[str, Any]) -> None:
        """Optimized progress hook for downloads"""
        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            downloaded = d.get('downloaded_bytes', 0)
            
            # Initialize progress bar if not exists
            if not hasattr(self, 'pbar'):
                self.pbar = ColorProgressBar(100, desc="Downloading")
                self.last_percentage = 0  # Reset percentage
            
            # Only update when there's meaningful progress
            if total > 0:
                percentage = min(int((downloaded / total) * 100), 100)
                # Update only when percentage changes (optimization)
                if percentage > self.last_percentage:
                    self.pbar.update(percentage - self.last_percentage)
                    self.last_percentage = percentage
                
        elif d['status'] == 'finished':
            if hasattr(self, 'pbar'):
                self.pbar.close()
                delattr(self, 'pbar')
            self.last_percentage = 0  # Reset last_percentage
            print(f"{Fore.GREEN}✓ Download Complete!{Style.RESET_ALL}")

    # FLAC verification methods with performance improvements
    def _verify_flac_properties(self, audio):
        """Verify FLAC format-specific properties with optimized checks"""
        bit_depth = getattr(audio.info, 'bits_per_sample', 0)
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

    def _verify_flac_quality(self, audio):
        """Verify FLAC quality and metadata with early returns for performance"""
        # Additional quality checks
        minimum_bitrate = 400000  # 400kbps minimum for FLAC
        if audio.info.bits_per_sample * audio.info.sample_rate * audio.info.channels < minimum_bitrate:
            logging.error("FLAC quality too low")
            return False

        # Check STREAMINFO block
        if not audio.info.total_samples or not audio.info.length:
            logging.error("Invalid FLAC stream info")
            return False

    def verify_audio_file(self, filepath: str) -> bool:
        """Enhanced audio file verification with faster checks and better error handling"""
        if not os.path.exists(filepath):
            logging.error(f"File not found: {filepath}")
            return False
            
        # Fast check - skip verification for non-FLAC files
        if not filepath.lower().endswith(FLAC_EXT):
            return True
        
        try:
            # Load FLAC file once and reuse for all checks
            audio = FLAC(filepath)
            
            # Basic verification
            if not audio or not audio.info:
                logging.error("Invalid FLAC file (no audio info)")
                return False
                
            # Complete verification using existing methods
            if not self._verify_flac_properties(audio) or not self._verify_flac_quality(audio):
                return False

            # Verify FLAC stream markers
            with open(filepath, 'rb') as f:
                header = f.read(4)
                if header != b'fLaC':
                    logging.error("Invalid FLAC signature")
                    return False

            return True

        except Exception as e:
            logging.error(f"FLAC verification error: {str(e)}")
            return False

    def _prepare_ffmpeg_command(self, input_file: str, output_file: str) -> list:
        """Prepare FFmpeg command with improved option handling"""
        return [
            os.path.join(self.config['ffmpeg_location'], 'ffmpeg'),
            '-i', input_file,
            '-c:a', 'flac',
            '-compression_level', '12',
            '-sample_fmt', 's32',
            '-ar', '48000',
            '-progress', 'pipe:1',
            output_file
        ]

    def _monitor_conversion_progress(self, process, duration, pbar):
        """Monitor conversion progress with enhanced error handling"""
        last_progress = 0
        while process.poll() is None:
            line = process.stdout.readline()
            if not line:
                continue
            
            if 'out_time_ms=' in line:
                try:
                    time_ms = int(line.split('=')[1])
                    progress = min(int((time_ms / 1000) / duration * 100), 100)
                    if progress > last_progress:
                        pbar.update(progress - last_progress)
                        last_progress = progress
                except (ValueError, AttributeError):
                    pass
        return process.returncode

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
                universal_newlines=True
            )

            # Monitor conversion progress
            returncode = self._monitor_conversion_progress(
                process, 
                original_audio.info.length, 
                pbar
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

    def get_download_options(self, url: str, audio_only: bool, resolution: Optional[str] = None,
                           format_id: Optional[str] = None, filename: Optional[str] = None,
                           audio_format: str = 'mp3') -> Dict[str, Any]:
        """Get download options with improved sanitization and fallbacks"""
        # Determine output path with fallback
        try:
            output_path = self.config['audio_output'] if audio_only else self.config['video_output']
            if not os.path.exists(output_path):
                os.makedirs(output_path, exist_ok=True)
        except OSError:
            # Fallback to home directory
            output_path = str(Path.home() / ('Music' if audio_only else 'Videos'))
            os.makedirs(output_path, exist_ok=True)
        
        # Sanitize filename for better OS compatibility
        if filename:
            # Remove problematic characters
            filename = re.sub(r'[\\/*?:"<>|]', '_', filename)
        
        # Base options with retry improvements
        options = {
            'outtmpl': os.path.join(output_path, f"{filename or '%(title)s'}.%(ext)s"),
            'ffmpeg_location': self.config['ffmpeg_location'],
            'progress_hooks': [self.progress_hook],
            'ignoreerrors': True,
            'continue': True,
            'postprocessor_hooks': [self.post_process_hook],
            'concurrent_fragment_downloads': min(10, os.cpu_count() or 4),  # Dynamic based on CPU
            'no_url_cleanup': True,
            'clean_infojson': False,
            'prefer_insecure': True,
            'retries': 5,             # Retry failed downloads
            'fragment_retries': 10,   # Retry failed fragments more aggressively
            'retry_sleep': lambda n: 5 * (2 ** (n - 1)),  # Exponential backoff
            'socket_timeout': 60,     # Increased timeout
            'http_chunk_size': 10485760,  # Larger chunks (10MB) for better performance
        }

        if audio_only:
            options['format'] = 'bestaudio/best'
            options['extract_audio'] = True
            
            # Process different audio formats
            if audio_format == 'flac':
                # Enhanced FLAC conversion with more error handling
                temp_format = '%(title)s.temp.wav'
                options['postprocessors'] = [
                    {
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'wav',  # First convert to WAV
                        'preferredquality': '0',
                    },
                    {
                        'key': 'FFmpegMetadata',
                        'add_metadata': True,
                    },
                    # Convert WAV to high-quality FLAC
                    {
                        'key': 'ExecAfterDownload',
                        'exec_cmd': (
                            f'"{os.path.join(self.config["ffmpeg_location"], "ffmpeg")}" -i "{{}}" '
                            '-c:a flac -compression_level 12 -sample_fmt s32p '
                            '-ar 96000 -bits_per_raw_sample 24 -vn '
                            '-af "aresample=resampler=soxr:precision=28:dither_method=triangular" '
                            '-metadata encoded_by="Snatch" '
                            '"{{}}".flac && del "{{}}"'
                        )
                    }
                ]
                options['postprocessor_args'] = [
                    '-acodec', 'pcm_s32le',  # 32-bit WAV
                    '-ar', '96000',          # 96kHz sampling
                    '-bits_per_raw_sample', '32'
                ]
            else:
                # Configure standard audio format with quality settings
                options['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': audio_format,
                    'preferredquality': '320' if audio_format == 'mp3' else '0',
                }]
                
        elif resolution:
            # Enhanced resolution handling
            options['format'] = f'bestvideo[height<={resolution}]+bestaudio/best[height<={resolution}]/best'
        
        return options

    def post_process_hook(self, d: Dict[str, Any]) -> None:
        """Improved post-processing with better file handling"""
        if d['status'] == 'started':
            filename = d.get('filename', '')
            
            # Only process FLAC files
            if filename.lower().endswith(FLAC_EXT):
                print(f"\n{Fore.CYAN}Verifying FLAC conversion...{Style.RESET_ALL}")
                try:
                    if not os.path.exists(filename):
                        print(f"{Fore.RED}File not found: {filename}{Style.RESET_ALL}")
                        return
                        
                    if self.verify_audio_file(filename):
                        audio = FLAC(filename)
                        filesize = os.path.getsize(filename)
                        bitrate = (filesize * 8) / (audio.info.length * 1000)  # kbps
                        
                        # Show file details
                        print(f"\n{Fore.GREEN}✓ FLAC conversion successful:{Style.RESET_ALL}")
                        print(f"   - Sample Rate: {audio.info.sample_rate} Hz")
                        print(f"   - Bit Depth: {audio.info.bits_per_sample} bit")
                        print(f"   - Channels: {audio.info.channels}")
                        print(f"   - Duration: {int(audio.info.length // 60)}:{int(audio.info.length % 60):02d}")
                        print(f"   - Average Bitrate: {int(bitrate)} kbps")
                        print(f"   - File Size: {filesize // 1024 // 1024} MB")
                        print("   - Compression Level: Maximum (12)")
                    else:
                        # Try to recover by reconverting
                        temp_wav = filename.replace('.flac', '.temp.wav')
                        if os.path.exists(temp_wav):
                            print(f"{Fore.YELLOW}Attempting recovery of FLAC file...{Style.RESET_ALL}")
                            self.convert_to_flac(temp_wav, filename)
                except Exception as e:
                    print(f"{Fore.RED}✗ Error during FLAC verification: {str(e)}{Style.RESET_ALL}")

    def download(self, url: str, **kwargs) -> bool:
        """Download media with improved caching, error handling and resource management"""
        # Check URL validity early
        try:
            parsed = urllib.parse.urlparse(url)
            if not all([parsed.scheme, parsed.netloc]):
                print(f"{Fore.RED}Invalid URL: {url}{Style.RESET_ALL}")
                return False
        except Exception:
            print(f"{Fore.RED}Invalid URL format: {url}{Style.RESET_ALL}")
            return False

        # Use enhanced spinner for better user feedback
        info_spinner = EnhancedSpinnerAnimation("Analyzing media", style="aesthetic")
        try:
            # First check cache for info
            cached_info = self.download_cache.get_info(url)
            if cached_info:
                info_spinner.update_message("Using cached media information")
                info_spinner.start()
                time.sleep(0.5)  # Brief pause to show the cached info message
                info = cached_info
            else:
                info_spinner.start()
                
                # Prepare options with smart defaults based on content
                ydl_opts = self.get_download_options(
                    url, 
                    kwargs.get('audio_only', False),
                    kwargs.get('resolution'),
                    kwargs.get('format_id'),
                    kwargs.get('filename'),
                    kwargs.get('audio_format', 'mp3')
                )
                ydl_opts['quiet'] = True  # Silence yt-dlp output during info extraction

                # Extract info with timeout and caching
                with timer("Media info extraction", silent=True):
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        try:
                            # First try quick extraction 
                            info = ydl.extract_info(url, download=False, process=False)
                            
                            # If it's a single video, get full info
                            if info and not info.get('_type') == 'playlist':
                                info_spinner.update_status("Getting detailed info")
                                info = ydl.extract_info(url, download=False)
                                
                                # Cache successful info for future use
                                self.download_cache.save_info(url, info)
                        except Exception as e:
                            info_spinner.stop(clear=False, success=False)
                            print(f"{Fore.RED}Error fetching media info: {str(e)}{Style.RESET_ALL}")
                            return False
            
            # Stop the spinner with success indicator
            info_spinner.stop(clear=True)
            
            if not info:
                print(f"{Fore.RED}Could not fetch media information for: {url}{Style.RESET_ALL}")
                return False
                
            # Show media information
            self._display_media_info(info)
            
            # Check for playlists and handle accordingly
            if info.get('_type') == 'playlist':
                return self._handle_playlist(url, info, **kwargs)
                
            # Check system resources before large downloads
            est_size = estimate_download_size(info)
            if est_size > 500 * 1024 * 1024 and not is_memory_sufficient():  # > 500MB
                print(f"{Fore.YELLOW}⚠️ Warning: System memory is low. Download may be slow or fail.{Style.RESET_ALL}")
                proceed = input(f"{Fore.CYAN}Continue anyway? (y/n): {Style.RESET_ALL}").lower().startswith('y')
                if not proceed:
                    return False
                    
            # Prepare download options with dynamic chunk size
            ydl_opts = self.get_download_options(
                url, 
                kwargs.get('audio_only', False),
                kwargs.get('resolution'),
                kwargs.get('format_id'),
                kwargs.get('filename'),
                kwargs.get('audio_format', 'mp3')
            )
            # Set optimal chunk size based on system memory
            ydl_opts['http_chunk_size'] = self._adaptive_chunk_size()
            
            # Register this download as active for resource management
            with self._download_lock:
                self._active_downloads.add(url)
            
            # Perform the actual download with robust error handling
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
                    return True
            except KeyboardInterrupt:
                print(f"\n{Fore.YELLOW}Download cancelled by user{Style.RESET_ALL}")
                return False
            except yt_dlp.utils.DownloadError as e:
                error_msg = str(e)
                print(f"{Fore.RED}Download Error: {error_msg}{Style.RESET_ALL}")
                
                # Show helpful error explanations and recovery suggestions
                if "unavailable" in error_msg.lower():
                    print(f"{Fore.YELLOW}This media may have been removed or is private.{Style.RESET_ALL}")
                elif "ffmpeg" in error_msg.lower():
                    print(f"{Fore.YELLOW}FFmpeg error. Try running 'python setup_ffmpeg.py' to fix.{Style.RESET_ALL}")
                elif any(net_err in error_msg.lower() for net_err in ["timeout", "connection", "network"]):
                    print(f"{Fore.YELLOW}Network error. Check your internet connection and try again.{Style.RESET_ALL}")
                return False
            finally:
                # Unregister from active downloads
                with self._download_lock:
                    self._active_downloads.discard(url)
                
        except Exception as e:
            info_spinner.stop(clear=False, success=False)
            print(f"{Fore.RED}Unexpected error: {str(e)}{Style.RESET_ALL}")
            return False

    def _display_media_info(self, info: Dict[str, Any]) -> None:
        """Display detailed and well-formatted media information"""
        # Extract commonly used info
        title = info.get('title', 'Unknown Title')
        uploader = info.get('uploader', info.get('channel', 'Unknown Uploader'))
        duration = info.get('duration', 0)
        
        # Calculate formatted duration
        if duration:
            mins, secs = divmod(int(duration), 60)
            hours, mins = divmod(mins, 60)
            duration_str = f"{hours}:{mins:02d}:{secs:02d}" if hours else f"{mins}:{secs:02d}"
        else:
            duration_str = "Unknown duration"
        
        # Get video quality if available
        height = info.get('height', 0)
        width = info.get('width', 0)
        quality = ""
        if width and height:
            if height >= 2160:
                quality = "4K"
            elif height >= 1080:
                quality = "Full HD"
            elif height >= 720:
                quality = "HD"
                
        # Determine file size
        filesize = info.get('filesize', info.get('filesize_approx', 0))
        if filesize:
            if filesize > 1024 * 1024 * 1024:
                filesize_str = f"{filesize / (1024 * 1024 * 1024):.2f} GB"
            else:
                filesize_str = f"{filesize / (1024 * 1024):.2f} MB"
        else:
            filesize_str = "Unknown"
            
        # Display info with colors and formatting
        print(f"\n{Fore.CYAN}{'='*40}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}Title:{Style.RESET_ALL} {title}")
        print(f"{Fore.GREEN}Channel/Uploader:{Style.RESET_ALL} {uploader}")
        print(f"{Fore.GREEN}Duration:{Style.RESET_ALL} {duration_str}")
        
        if quality:
            print(f"{Fore.GREEN}Quality:{Style.RESET_ALL} {quality} ({width}x{height})")
            
        print(f"{Fore.GREEN}Estimated Size:{Style.RESET_ALL} {filesize_str}")
        
        # Show additional metadata if available
        if info.get('upload_date'):
            try:
                date_str = info['upload_date']
                formatted_date = f"{date_str[0:4]}-{date_str[4:6]}-{date_str[6:8]}"
                print(f"{Fore.GREEN}Upload Date:{Style.RESET_ALL} {formatted_date}")
            except (IndexError, ValueError):
                pass
                
        if info.get('view_count'):
            view_count = info['view_count']
            # Format view count with commas
            view_str = f"{view_count:,}"
            print(f"{Fore.GREEN}Views:{Style.RESET_ALL} {view_str}")
            
        print(f"{Fore.CYAN}{'='*40}{Style.RESET_ALL}\n")

    def _handle_playlist(self, url: str, info: Dict[str, Any], **kwargs) -> bool:
        """Handle playlist downloads with better UX and resource management"""
        entries = info.get('entries', [])
        entry_count = len(list(entries))
        
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
        
        if choice == '1':
            return self._download_entire_playlist(url, **kwargs)
        elif choice == '2':
            try:
                count = int(input(f"{Fore.GREEN}How many videos to download: {Style.RESET_ALL}"))
                return self._download_partial_playlist(url, count, **kwargs)
            except ValueError:
                print(f"{Fore.RED}Invalid number{Style.RESET_ALL}")
                return False
        elif choice == '3':
            return self._download_selected_playlist_items(info, **kwargs)
        else:
            print(f"{Fore.YELLOW}Download cancelled{Style.RESET_ALL}")
            return False

    def _download_entire_playlist(self, url: str, **kwargs) -> bool:
        """Download an entire playlist"""
        ydl_opts = self.get_download_options(
            url, 
            kwargs.get('audio_only', False),
            kwargs.get('resolution'),
            kwargs.get('format_id'),
            kwargs.get('filename'),
            kwargs.get('audio_format', 'mp3')
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
            kwargs.get('audio_only', False),
            kwargs.get('resolution'),
            kwargs.get('format_id'),
            kwargs.get('filename'),
            kwargs.get('audio_format', 'mp3')
        )
        
        # Add playlist item limit (1-based indexing for yt-dlp)
        ydl_opts['playliststart'] = 1
        ydl_opts['playlistend'] = count
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            return True
        except Exception as e:
            print(f"{Fore.RED}Error downloading playlist items: {str(e)}{Style.RESET_ALL}")
            return False

    def _download_selected_playlist_items(self, info: Dict[str, Any], **kwargs) -> bool:
        """Download specific videos selected by the user"""
        entries = list(info.get('entries', []))
        
        if not entries:
            print(f"{Fore.YELLOW}No videos found in playlist{Style.RESET_ALL}")
            return False
            
        # Display videos with numbers
        print(f"\n{Fore.CYAN}Available Videos:{Style.RESET_ALL}")
        for i, entry in enumerate(entries, 1):
            title = entry.get('title', f'Video {i}')
            duration = entry.get('duration', 0)
            duration_str = f"{int(duration // 60)}:{int(duration % 60):02d}" if duration else "??:??"
            print(f"{i}. {title} [{duration_str}]")
            
        # Get user selection
        try:
            selection = input(f"\n{Fore.GREEN}Enter video numbers to download (e.g. 1,3,5-7): {Style.RESET_ALL}")
            selected_indices = []
            
            # Parse the selection string
            for part in selection.split(','):
                if '-' in part:
                    start, end = map(int, part.split('-'))
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
                url = entry.get('webpage_url', entry.get('url', None))
                
                if not url:
                    print(f"{Fore.YELLOW}Could not get URL for video #{idx}{Style.RESET_ALL}")
                    continue
                    
                print(f"\n{Fore.CYAN}Downloading #{idx}: {entry.get('title', 'Unknown')}{Style.RESET_ALL}")
                if self.download(url, **kwargs):
                    success_count += 1
                    
            print(f"\n{Fore.GREEN}Downloaded {success_count} of {len(selected_indices)} selected videos{Style.RESET_ALL}")
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
            
        print(f"{Fore.CYAN}Starting batch download of {total} items...{Style.RESET_ALL}")
        
        # Determine optimal concurrency based on system resources
        available_memory = get_available_memory()
        memory_based_limit = max(1, int(available_memory / (500 * 1024 * 1024)))  # ~500MB per download
        
        # Balance between config, memory limitations and CPU cores
        max_workers = min(
            self.config.get('max_concurrent', 3),  # From config
            memory_based_limit,                    # Based on available memory
            os.cpu_count() or 4,                   # Based on CPU cores
            total
        )

        # Use ThreadPoolExecutor for parallel downloads
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_url = {executor.submit(self.download, url, **kwargs): url for url in urls}
            
            for future in as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    print(f"{Fore.RED}Error downloading {url}: {str(e)}{Style.RESET_ALL}")
                    results.append(False)
        
        print(f"\n{Fore.GREEN}Batch download complete. {sum(results)} of {total} items downloaded successfully.{Style.RESET_ALL}")
        return results

    def interactive_mode(self) -> None:
        """Interactive mode for user-friendly operation"""
        print_banner()
        print(f"{Fore.CYAN}Welcome to Snatch Interactive Mode!{Style.RESET_ALL}")
        
        while True:
            try:
                command = input(f"\n{Fore.GREEN}snatch> {Style.RESET_ALL}").strip().lower()
                
                if not command:
                    continue
                
                if command in ('exit', 'quit', 'q'):
                    print(f"{Fore.CYAN}Exiting Snatch. Goodbye!{Style.RESET_ALL}")
                    break
                
                if command in ('help', '?'):
                    print(EXAMPLES)
                    continue
                
                # Fuzzy match for common commands
                matched_command = fuzzy_match_command(command, self.valid_commands)
                if matched_command:
                    command = matched_command
                
                if command.startswith('download') or command.startswith('dl'):
                    url = input(f"{Fore.GREEN}Enter URL: {Style.RESET_ALL}").strip()
                    self.download(url)
                elif command.startswith('audio'):
                    url = input(f"{Fore.GREEN}Enter URL: {Style.RESET_ALL}").strip()
                    self.download(url, audio_only=True)
                elif command.startswith('video'):
                    url = input(f"{Fore.GREEN}Enter URL: {Style.RESET_ALL}").strip()
                    resolution = input(f"{Fore.GREEN}Enter resolution (e.g., 1080): {Style.RESET_ALL}").strip()
                    self.download(url, resolution=resolution)
                elif command.startswith('flac'):
                    url = input(f"{Fore.GREEN}Enter URL: {Style.RESET_ALL}").strip()
                    self.download(url, audio_only=True, audio_format='flac')
                elif command.startswith('mp3'):
                    url = input(f"{Fore.GREEN}Enter URL: {Style.RESET_ALL}").strip()
                    self.download(url, audio_only=True, audio_format='mp3')
                elif command.startswith('wav'):
                    url = input(f"{Fore.GREEN}Enter URL: {Style.RESET_ALL}").strip()
                    self.download(url, audio_only=True, audio_format='wav')
                elif command.startswith('m4a'):
                    url = input(f"{Fore.GREEN}Enter URL: {Style.RESET_ALL}").strip()
                    self.download(url, audio_only=True, audio_format='m4a')
                elif command.startswith('list') or command.startswith('sites'):
                    list_supported_sites()
                elif command.startswith('clear') or command.startswith('cls'):
                    os.system('cls' if is_windows() else 'clear')
                else:
                    print(f"{Fore.RED}Unknown command: {command}{Style.RESET_ALL}")
                    print(f"{Fore.YELLOW}Type 'help' or '?' for a list of commands.{Style.RESET_ALL}")
            
            except KeyboardInterrupt:
                print(f"\n{Fore.YELLOW}Operation cancelled by user. Exiting interactive mode...{Style.RESET_ALL}")
                break
            except Exception as e:
                print(f"{Fore.RED}An error occurred: {str(e)}{Style.RESET_ALL}")

    def _adaptive_chunk_size(self) -> int:
        """Dynamically determine optimal chunk size based on available memory"""
        available_memory = get_available_memory()
        
        # Use larger chunks when more memory is available
        if available_memory > 4 * 1024 * 1024 * 1024:  # > 4GB free
            return 10485760  # 10MB chunks
        elif available_memory > 2 * 1024 * 1024 * 1024:  # > 2GB free
            return 5242880   # 5MB chunks
        elif available_memory > 1 * 1024 * 1024 * 1024:  # > 1GB free
            return 2097152   # 2MB chunks
        else:
            return 1048576   # 1MB chunks for low memory situations

def load_config() -> Dict[str, Any]:
    """Load configuration from file with defaults and error handling"""
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        config = DEFAULT_CONFIG.copy()
    
    # Ensure all default keys are present
    for key, value in DEFAULT_CONFIG.items():
        config.setdefault(key, value)
    
    return config

def list_supported_sites() -> bool:
    """List supported sites from the Supported-sites.txt file"""
    try:
        sites_file = Path("Supported-sites.txt")
        if not sites_file.exists():
            print(f"{Fore.RED}Supported-sites.txt not found. Cannot list supported sites.{Style.RESET_ALL}")
            return False
        
        with open(sites_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        print(f"\n{Fore.CYAN}{'=' * 40}")
        print(f"{Fore.GREEN}SUPPORTED SITES{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'=' * 40}{Style.RESET_ALL}\n")
        
        # Skip the header lines if present
        lines = content.split('\n')
        start_idx = 0
        for i, line in enumerate(lines):
            if line.strip().startswith("Below is a list"):
                start_idx = i + 1
                break
                
        # Track categories for better organization
        current_category = "General"
        site_count = 0
        
        # Print each site (skipping empty lines)
        for line in lines[start_idx:]:
            line = line.strip()
            if line and not line.startswith('"'):
                parts = line.split(':', 1)
                site_name = parts[0].strip()
                if site_name:
                    site_count += 1
                    # Print with nice formatting
                    if len(parts) > 1:  # This is likely a category entry
                        current_category = site_name
                        print(f"\n{Fore.YELLOW}{current_category.upper()}{Style.RESET_ALL}")
                    else:
                        print(f"{Fore.GREEN} • {site_name}{Style.RESET_ALL}")
        
        print(f"\n{Fore.CYAN}Total supported sites: {site_count}{Style.RESET_ALL}\n")
        return True
    
    except Exception as e:
        print(f"{Fore.RED}Error reading supported sites: {str(e)}{Style.RESET_ALL}")
        return False

def test_functionality() -> bool:
    """Run basic tests to verify functionality"""
    print(f"{Fore.CYAN}Running basic tests...{Style.RESET_ALL}")
    try:
        # Test FFmpeg detection
        ffmpeg_path = find_ffmpeg()
        if not ffmpeg_path:
            print(f"{Fore.RED}FFmpeg not found!{Style.RESET_ALL}")
            return False
        print(f"{Fore.GREEN}FFmpeg found at: {ffmpeg_path}{Style.RESET_ALL}")
        
        # Test yt-dlp
        with yt_dlp.YoutubeDL() as ydl:
            version = ydl._version
            print(f"{Fore.GREEN}yt-dlp version: {version}{Style.RESET_ALL}")
        
        # Test download manager
        config = load_config()
        manager = DownloadManager(config)
        print(f"{Fore.GREEN}Download manager initialized successfully{Style.RESET_ALL}")
        
        return True
    except Exception as e:
        print(f"{Fore.RED}Test failed: {str(e)}{Style.RESET_ALL}")
        return False

def main() -> None:
    """Enhanced main function with better argument handling and error management"""
    # Optimized early handling of special args
    if '--version' in sys.argv:
        print(f'Snatch v{VERSION}')
        sys.exit(0)
    
    if '--test' in sys.argv:
        print(f"\n{Fore.CYAN}╔{'═' * 40}╗")
        print("║          Snatch Test Suite              ║")
        print(f"╚{'═' * 40}╝{Style.RESET_ALL}")
        sys.exit(0 if test_functionality() else 1)
        
    if len(sys.argv) == 2 and sys.argv[1] == '--list-sites':
        list_supported_sites()
        sys.exit(0)
        
    # FIXED: Special handling for interactive mode without parsing other args
    if "--interactive" in sys.argv or "-i" in sys.argv:
        try:
            config = load_config()
            manager = DownloadManager(config)
            manager.interactive_mode()
            sys.exit(0)
        except Exception as e:
            print(f"{Fore.RED}Error starting interactive mode: {str(e)}{Style.RESET_ALL}")
            sys.exit(1)

    # Simplified path for no arguments (also runs interactive mode)
    if len(sys.argv) == 1:
        try:
            config = load_config()
            manager = DownloadManager(config)
            manager.interactive_mode()
            sys.exit(0)
        except Exception as e:
            print(f"{Fore.RED}Error starting interactive mode: {str(e)}{Style.RESET_ALL}")
            sys.exit(1)

    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Snatch - Download Anything!",
        formatter_class=CustomHelpFormatter,
        epilog=EXAMPLES
    )
    parser.add_argument('urls', nargs='*', help='URLs to download')
    parser.add_argument('--audio-only', action='store_true', help='Download audio only')
    parser.add_argument('--resolution', type=str, help='Specify video resolution (e.g., 1080)')
    parser.add_argument('--format-id', type=str, help='Specify format ID')
    parser.add_argument('--filename', type=str, help='Specify custom filename')
    parser.add_argument('--audio-format', type=str, choices=['mp3', 'flac', 'wav', 'm4a'], default='mp3', help='Specify audio format')
    parser.add_argument('--output-dir', type=str, help='Specify custom output directory')
    parser.add_argument('--list-sites', action='store_true', help='List all supported sites')
    parser.add_argument('--version', action='store_true', help='Show version information')
    parser.add_argument('--test', action='store_true', help='Run basic tests to verify functionality')
    parser.add_argument('--interactive', '-i', action='store_true', help='Run in interactive mode')
    
    args = parser.parse_args()
    
    # Handle special args
    if args.version:
        print(f'Snatch v{VERSION}')
        sys.exit(0)
    
    if args.test:
        print(f"\n{Fore.CYAN}╔{'═' * 40}╗")
        print("║          Snatch Test Suite              ║")
        print(f"╚{'═' * 40}╝{Style.RESET_ALL}")
        sys.exit(0 if test_functionality() else 1)
        
    if args.list_sites:
        list_supported_sites()
        sys.exit(0)
    
    # Load configuration
    config = load_config()
    
    # Override output directories if specified
    if args.output_dir:
        if args.audio_only:
            config['audio_output'] = args.output_dir
        else:
            config['video_output'] = args.output_dir
    
    # Initialize download manager
    manager = DownloadManager(config)
    
    # Handle interactive mode
    if args.interactive:
        manager.interactive_mode()
        sys.exit(0)
    
    # Handle batch download
    if args.urls:
        manager.batch_download(
            args.urls,
            audio_only=args.audio_only,
            resolution=args.resolution,
            format_id=args.format_id,
            filename=args.filename,
            audio_format=args.audio_format
        )
    else:
        print(f"{Fore.RED}No URLs provided. Use --interactive for interactive mode.{Style.RESET_ALL}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"{Fore.RED}An unexpected error occurred: {str(e)}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Try running with --interactive flag for easier usage.{Style.RESET_ALL}")
        sys.exit(1)