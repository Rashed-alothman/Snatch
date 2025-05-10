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

class SessionManager:
    """
    Manages download sessions with advanced features for resuming interrupted downloads.
    Provides thread-safe operations and automatic session persistence.

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
        session_expiry: int = 7 * 24 * 60 * 60,  # 7 days default expiry
        max_cache_size: int = 1000
    ):
        self.session_file = session_file
        self.sessions = {}
        self.lock = threading.RLock()  # Reentrant lock for thread safety
        self.last_save_time = 0
        self.modified = False
        self.auto_save_interval = auto_save_interval
        self.session_expiry = session_expiry
        self.max_cache_size = max_cache_size
        self._cache = {}

        # Create sessions directory if it doesn't exist
        os.makedirs(os.path.dirname(session_file), exist_ok=True)

        # Load existing sessions and perform maintenance
        self._load_and_maintain_sessions()

        # Start background auto-save thread if interval is positive
        if self.auto_save_interval > 0:
            self._start_auto_save_thread()

    def _load_and_maintain_sessions(self) -> None:
        """Load sessions from disk and remove expired entries."""
        with self.lock:
            self.sessions = self._load_sessions_from_disk()
            current_time = time.time()
            expired_count = 0

            # Remove expired sessions
            for url, session in list(self.sessions.items()):
                if current_time - session.get("timestamp", 0) > self.session_expiry:
                    del self.sessions[url]
                    expired_count += 1

            if expired_count > 0:
                logger.info(f"Removed {expired_count} expired download sessions")
                self.modified = True
                self._save_sessions_to_disk()

    def _load_sessions_from_disk(self) -> Dict[str, Dict[str, Any]]:
        """Load sessions from disk with robust error handling."""
        if not os.path.exists(self.session_file):
            return {}

        try:
            with open(self.session_file, "r") as f:
                sessions = json.load(f)

            if not isinstance(sessions, dict):
                logger.warning(f"Invalid session data format, expected dict but got {type(sessions)}")
                return {}

            return sessions

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse session file: {e}")
            self._backup_corrupted_file()
            return {}
        except (IOError, OSError) as e:
            logger.error(f"Error reading session file: {e}")
            return {}
        except Exception as e:
            logger.error(f"Unexpected error loading sessions: {e}")
            return {}

    def _backup_corrupted_file(self) -> None:
        """Create backup of corrupted session file."""
        try:
            if os.path.exists(self.session_file):
                backup_file = f"{self.session_file}.bak.{int(time.time())}"
                shutil.copy2(self.session_file, backup_file)
                logger.info(f"Created backup of corrupted session file: {backup_file}")
        except Exception as e:
            logger.error(f"Failed to backup corrupted session file: {e}")

    def _save_sessions_to_disk(self) -> bool:
        """Save sessions to disk with proper error handling and atomic writes."""
        if not self.modified:
            return True

        try:
            # Create temp file for atomic write
            temp_file = f"{self.session_file}.tmp"
            
            with open(temp_file, "w") as f:
                json.dump(self.sessions, f, indent=2)
                f.flush()
                os.fsync(f.fileno())

            # Perform atomic replace
            if os.path.exists(self.session_file):
                if is_windows():
                    os.replace(temp_file, self.session_file)
                else:
                    os.rename(temp_file, self.session_file)
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

    def _start_auto_save_thread(self) -> None:
        """Start background thread for periodic auto-saving."""
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

    def update_session(self, url: str, progress: float, metadata: Optional[Dict] = None) -> bool:
        """
        Update or create a session with the current progress and optional metadata.

        Args:
            url: The download URL as unique identifier
            progress: Download progress percentage (0-100)
            metadata: Optional dict with additional session data

        Returns:
            bool: True if session was updated successfully
        """
        if not url:
            return False

        with self.lock:
            if url not in self.sessions:
                self.sessions[url] = {}

            # Update session data
            self.sessions[url].update({
                "progress": float(progress),
                "timestamp": time.time(),
                "last_active": time.strftime("%Y-%m-%d %H:%M:%S")
            })

            # Add metadata if provided
            if metadata and isinstance(metadata, dict):
                if "metadata" not in self.sessions[url]:
                    self.sessions[url]["metadata"] = {}
                self.sessions[url]["metadata"].update(metadata)

            self.modified = True

            # Save immediately if this is a significant progress update
            if progress % 10 < 1:  # Save at each 10% milestone
                self._save_sessions_to_disk()

            return True

    def get_session(self, url: str) -> Optional[Dict]:
        """
        Get session data for a URL if it exists and is valid.

        Args:
            url: The download URL to retrieve

        Returns:
            Optional[Dict]: Session dict or None if not found or expired
        """
        with self.lock:
            session = self.sessions.get(url)
            if not session:
                return None

            # Validate session data
            if "progress" not in session or "timestamp" not in session:
                logger.warning(f"Found invalid session for {url}, removing it")
                del self.sessions[url]
                self.modified = True
                return None

            # Check expiration
            if time.time() - session["timestamp"] > self.session_expiry:
                logger.info(f"Found expired session for {url}, removing it")
                del self.sessions[url]
                self.modified = True
                return None

            return session.copy()

    def remove_session(self, url: str) -> bool:
        """
        Remove a session when download completes or is cancelled.

        Args:
            url: The download URL to remove

        Returns:
            bool: True if session was found and removed
        """
        with self.lock:
            if url in self.sessions:
                del self.sessions[url]
                self.modified = True
                self._save_sessions_to_disk()
                return True
            return False

    def get_all_sessions(self) -> Dict[str, Dict]:
        """Get all active download sessions (thread-safe copy)."""
        with self.lock:
            return {url: session.copy() for url, session in self.sessions.items()}

    def clear_all_sessions(self) -> None:
        """Clear all sessions and save changes to disk."""
        with self.lock:
            self.sessions.clear()
            self.modified = True
            self._save_sessions_to_disk()

    def get_session_count(self) -> int:
        """Get the number of active sessions."""
        with self.lock:
            return len(self.sessions)

    def get_resumable_sessions(self, max_age: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get a list of sessions that can be resumed, sorted by last activity.

        Args:
            max_age: Optional maximum age in seconds (defaults to session_expiry)

        Returns:
            List[Dict[str, Any]]: List of session info including URLs
        """
        with self.lock:
            current_time = time.time()
            max_age = max_age or self.session_expiry

            resumable = []
            for url, session in self.sessions.items():
                age = current_time - session.get("timestamp", 0)
                if age <= max_age and 0 <= session.get("progress", 0) < 100:
                    info = session.copy()
                    info["url"] = url
                    info["age"] = age
                    resumable.append(info)

            # Sort by last activity (most recent first)
            return sorted(resumable, key=lambda x: x["timestamp"], reverse=True)

    def cleanup_expired(self) -> int:
        """
        Remove all expired sessions.

        Returns:
            int: Number of sessions removed
        """
        with self.lock:
            current_time = time.time()
            expired = [url for url, session in self.sessions.items()
                      if current_time - session.get("timestamp", 0) > self.session_expiry]

            for url in expired:
                del self.sessions[url]

            if expired:
                self.modified = True
                self._save_sessions_to_disk()

            return len(expired)

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
            print(f"  • {Fore.RED}4K Video:{Style.RESET_ALL}")
