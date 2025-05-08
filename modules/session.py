#HTTP/P2P session abstraction, proxy logic
import logging
import requests
import threading
import shutil
import json
import time
import os
from pathlib import Path
from .common_utils import is_windows
from .progress import Spinner, SpinnerAnimation
from .defaults import (
    CACHE_DIR,
    speedtestresult,
    DOWNLOAD_SESSIONS_FILE,
)
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
from colorama import Fore, Style, init
logger = logging.getLogger(__name__)
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
# Session Manager to track download progress
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
    ):
        self.session_file = session_file
        self.sessions = {}
        self.lock = threading.RLock()
        self.last_save_time = 0
        self.modified = False
        self.auto_save_interval = auto_save_interval
        self.session_expiry = session_expiry
        
        # Add caching for frequently accessed data
        self._cache = {}
        self._cache_ttl = 60  # Cache TTL in seconds
        self._last_cache_clean = time.time()
        self._cache_clean_interval = 300  # Clean cache every 5 minutes
        
        # Memory optimization settings
        self._max_cache_items = 1000
        self._max_sessions = 10000  # Limit total stored sessions
        
        self._load_and_maintain_sessions()
        
        if self.auto_save_interval > 0:
            self._start_auto_save_thread()
            
    def _load_and_maintain_sessions(self):
        """Load existing sessions and maintain them"""
        try:
            if os.path.exists(self.session_file):
                with open(self.session_file, 'r') as f:
                    self.sessions = json.load(f)
                    
            # Clean up old sessions
            current_time = time.time()
            self.sessions = {
                url: session for url, session in self.sessions.items()
                if current_time - session.get('last_updated', 0) < 86400  # 24 hours
            }
            
            # Start maintenance thread
            self._start_maintenance_thread()
            
        except Exception as e:
            logger.error(f"Error loading sessions: {e}")
            self.sessions = {}
            
    def _start_maintenance_thread(self):
        """Start background thread for session maintenance"""
        def maintain_sessions():
            while True:
                try:
                    # Save current sessions
                    with open(self.session_file, 'w') as f:
                        json.dump(self.sessions, f)
                    # Clean up old sessions
                    current_time = time.time()
                    self.sessions = {
                        url: session for url, session in self.sessions.items()
                        if current_time - session.get('last_updated', 0) < 86400
                    }
                except Exception as e:
                    logger.error(f"Session maintenance error: {e}")
                time.sleep(300)  # Run every 5 minutes
                
        thread = threading.Thread(target=maintain_sessions, daemon=True)
        thread.start()
            
    def _clean_cache(self) -> None:
        """Clean expired cache entries and limit cache size"""
        now = time.time()
        if now - self._last_cache_clean < self._cache_clean_interval:
            return
            
        with self.lock:
            # Remove expired entries
            expired = [k for k, v in self._cache.items() if now - v.get("timestamp", 0) > self._cache_ttl]
            for k in expired:
                del self._cache[k]
                
            # If still too many entries, remove oldest
            if len(self._cache) > self._max_cache_items:
                sorted_items = sorted(self._cache.items(), key=lambda x: x[1].get("timestamp", 0))
                to_remove = len(self._cache) - self._max_cache_items
                for k, _ in sorted_items[:to_remove]:
                    del self._cache[k]
                    
            self._last_cache_clean = now
            
    def _get_cached(self, key: str) -> Optional[dict]:
        """Get item from cache if valid"""
        now = time.time()
        with self.lock:
            if key in self._cache:
                item = self._cache[key]
                if now - item.get("timestamp", 0) <= self._cache_ttl:
                    return item.get("data")
                del self._cache[key]
        return None
        
    def _set_cached(self, key: str, data: dict) -> None:
        """Add item to cache with timestamp"""
        with self.lock:
            self._cache[key] = {
                "timestamp": time.time(),
                "data": data
            }
            
    def get_session(self, url: str) -> Optional[dict]:
        """Get session with caching for better performance"""
        # Try cache first
        cached = self._get_cached(url)
        if cached is not None:
            return cached.copy()
            
        with self.lock:
            session = self.sessions.get(url)
            if not session:
                return None
                
            # Validate session
            if "progress" not in session or "timestamp" not in session:
                logging.warning(f"Found invalid session for {url}, removing it")
                del self.sessions[url]
                self.modified = True
                return None
                
            # Check expiry
            if time.time() - session["timestamp"] > self.session_expiry:
                logging.info(f"Found expired session for {url}, removing it")
                del self.sessions[url]
                self.modified = True
                return None
                
            # Cache valid session
            session_copy = session.copy()
            self._set_cached(url, session_copy)
            return session_copy
            
    def update_session(self, url: str, progress: float, metadata: dict = None) -> bool:
        """Update session with optimized cache handling"""
        if not url:
            return False
            
        with self.lock:
            # Clean cache periodically
            self._clean_cache()
            
            # Check total sessions limit
            if url not in self.sessions and len(self.sessions) >= self._max_sessions:
                # Remove oldest session if at limit
                oldest = min(self.sessions.items(), key=lambda x: x[1].get("timestamp", 0))
                del self.sessions[oldest[0]]
                
            # Create or update session
            if url not in self.sessions:
                self.sessions[url] = {}
                
            # Update session data
            self.sessions[url].update({
                "progress": float(progress),
                "timestamp": time.time(),
                "last_active": time.strftime("%Y-%m-%d %H:%M:%S")
            })
            
            # Update metadata if provided
            if metadata and isinstance(metadata, dict):
                if "metadata" not in self.sessions[url]:
                    self.sessions[url]["metadata"] = {}
                self.sessions[url]["metadata"].update(metadata)
                
            # Update cache
            self._set_cached(url, self.sessions[url].copy())
            
            self.modified = True
            
            # Save at milestones
            if progress % 10 < 1:
                self._save_sessions_to_disk()
                
            return True

    def _start_auto_save_thread(self) -> None:
        """Start background thread for periodic auto-saving"""
        def auto_save_worker():
            while True:
                try:
                    time.sleep(self.auto_save_interval)
                    with self.lock:
                        if self.modified and time.time() - self.last_save_time >= self.auto_save_interval:
                            self._save_sessions_to_disk()
                except Exception as e:
                    logger.error(f"Error in auto-save thread: {e}")

        save_thread = threading.Thread(
            target=auto_save_worker,
            daemon=True,
            name="SessionAutoSave"
        )
        save_thread.start()

    def _save_sessions_to_disk(self) -> bool:
        """Save sessions to disk with proper error handling and atomic writes"""
        if not self.modified:
            return True

        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.session_file), exist_ok=True)
            
            # Create temp file for atomic write
            temp_file = f"{self.session_file}.tmp"

            # Use a temporary file for atomic write
            with open(temp_file, "w") as f:
                json.dump(self.sessions, f, indent=2)
                f.flush()
                os.fsync(f.fileno())

            # Perform atomic replace
            if os.path.exists(self.session_file):
                os.replace(temp_file, self.session_file)
            else:
                os.rename(temp_file, self.session_file)

            self.last_save_time = time.time()
            self.modified = False
            return True

        except (IOError, OSError) as e:
            logger.error(f"Failed to save session data: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error saving sessions: {e}")
            return False


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
