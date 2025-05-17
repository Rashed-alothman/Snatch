"""
Enhanced session management system for Snatch.
Provides persistent session tracking for HTTP and P2P file transfers.
"""

import asyncio
import json
import logging
import os
import shutil
import threading
import time
import requests
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Set, TypeVar, Type, cast
from urllib.parse import urlparse

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TimeElapsedColumn
from rich.panel import Panel
from colorama import Fore, Style, init
from .progress import SpinnerAnimation
from .common_utils import is_windows, ensure_dir
from .defaults import DOWNLOAD_SESSIONS_FILE,CACHE_DIR,speedtestresult
from .logging_config import setup_logging
from .p2p import (
    P2PManager,
    ShareConfig,
    P2PError,
)
from .progress import HolographicProgress

# Configure logging
setup_logging()
logger = logging.getLogger(__name__)
console = Console()

# Type variable for generic session handling
T = TypeVar('T', bound='TransferSession')

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
    except Exception as e:
        # If any error occurs with cache, just run a new test
        logger.debug(f"Cache read error: {e}")

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
@dataclass
class TransferSession:
    """Base class for transfer sessions"""
    id: str
    start_time: datetime
    file_path: str
    total_size: int
    error: Optional[str] = None
    status: str = "pending"
    transferred: int = 0
    
    def is_active(self) -> bool:
        """Check if session is active"""
        return self.status not in ("completed", "error", "cancelled", "stopped")
    
    def is_finished(self) -> bool:
        """Check if session has finished"""
        return self.status in ("completed", "error", "cancelled", "stopped")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary for storage"""
        return {
            **asdict(self),
            "start_time": self.start_time.isoformat(),
            "type": self.__class__.__name__
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TransferSession":
        """Create session from dictionary"""
        data = data.copy()
        data["start_time"] = datetime.fromisoformat(data["start_time"])
        return cls(**data)

@dataclass
class P2PShareSession(TransferSession):
    """P2P file sharing session with encryption and DHT support."""
    share_code: Optional[str] = None
    encryption: bool = True
    dht_enabled: bool = True
    connections: List[Dict[str, Any]] = None
    chunk_size: int = 1024 * 1024  # 1MB chunks

    def __post_init__(self):
        """Initialize and validate P2P share session."""
        super().__post_init__()
        self.connections = self.connections or []
        self._validate_share_settings()

    def _validate_share_settings(self) -> None:
        """Validate P2P sharing settings."""
        if not Path(self.file_path).is_file():
            raise FileNotFoundError(f"Share file not found: {self.file_path}")
        if self.chunk_size <= 0:
            raise ValueError("Chunk size must be positive")

    def add_connection(self, peer_info: Dict[str, Any]) -> None:
        """Add a new peer connection with validation."""
        required_fields = {'id', 'address', 'port'}
        if not all(field in peer_info for field in required_fields):
            raise ValueError(f"Peer info missing required fields: {required_fields}")
        if peer_info not in self.connections:
            self.connections.append(peer_info)
            logger.info(f"New peer connected: {peer_info['address']}:{peer_info['port']}")

    def remove_connection(self, peer_info: Dict[str, Any]) -> None:
        """Remove a peer connection."""
        if peer_info in self.connections:
            self.connections.remove(peer_info)
            logger.info(f"Peer disconnected: {peer_info['address']}:{peer_info['port']}")

    def get_active_connections(self) -> List[Dict[str, Any]]:
        """Get list of active peer connections."""
        return [conn for conn in self.connections if conn.get('active', False)]

@dataclass(kw_only=True)
class P2PFetchSession(TransferSession):
    """P2P file fetching session with integrity verification."""
    share_code: str
    source_hash: str
    verify: bool = True
    peer_info: Optional[Dict[str, Any]] = None
    resume_position: int = 0
    temp_path: Optional[str] = None

    def __post_init__(self):
        """Initialize and validate P2P fetch session."""
        super().__post_init__()
        self._validate_fetch_settings()
        if not self.temp_path:
            self.temp_path = str(Path(self.file_path).with_suffix('.part'))

    def _validate_fetch_settings(self) -> None:
        """Validate fetch settings."""
        if not self.share_code:
            raise ValueError("Share code is required")
        if self.verify and not self.source_hash:
            raise ValueError("Source hash is required when verify=True")
        if self.resume_position < 0:
            raise ValueError("Resume position cannot be negative")
        
    def validate_hash(self, computed_hash: str) -> bool:
        """Validate file integrity using source hash."""
        if not self.verify:
            logger.warning("Hash verification disabled")
            return True
        if not self.source_hash:
            logger.error("Source hash not available for verification")
            return False
        matches = self.source_hash == computed_hash
        if not matches:
            logger.error(f"Hash mismatch. Expected: {self.source_hash}, Got: {computed_hash}")
        return matches

    def cleanup(self) -> None:
        """Clean up temporary files."""
        if self.temp_path and Path(self.temp_path).exists():
            try:
                Path(self.temp_path).unlink()
                logger.debug(f"Cleaned up temporary file: {self.temp_path}")
            except Exception as e:
                logger.error(f"Failed to clean up temporary file: {e}")

    def can_resume(self) -> bool:
        """Check if download can be resumed."""
        return (
            self.resume_position > 0 and
            self.resume_position < self.total_size and
            Path(self.temp_path).exists()
        )
@dataclass
class SessionManager:
    """Enhanced session management system."""
    
    def __init__(self, session_file: str = DOWNLOAD_SESSIONS_FILE, auto_save_interval: int = 30,
        session_expiry: int = 7 * 24 * 60 * 60,  # 7 days default expiry
        max_cache_size: int = 1000):
        """Initialize session manager."""
        self.session_file = os.path.abspath(session_file) # Absolute path to session file
        self.sessions: Dict[str, Dict] = {} # Dictionary to store session data
        self.lock = threading.RLock()  # Reentrant lock for thread safety
        self.last_save_time = 0 # Last save time for auto-save
        self._active_transfers: Set[str] = set() # Set of active transfer session IDs 
        self.auto_save_interval = auto_save_interval # Auto-save interval in seconds
        self._shutdown = False # Flag to indicate shutdown
        self.session_expiry = session_expiry # Session expiry in seconds
        self.modified = False # Flag to track if sessions have been modified
        self.session_expiry = session_expiry # Session expiry in seconds
        self.max_cache_size = max_cache_size # Maximum cache size
        self._cache = {} # Cache for session data
        self._executor = ThreadPoolExecutor(max_workers=4) # Thread pool executor for async tasks
        self._load_sessions() # Load existing sessions from disk
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
    async def _handle_fetch_session(self, session: P2PFetchSession) -> None:
        """Handle a P2P fetch session with progress tracking."""
        if not isinstance(session, P2PFetchSession) or not session.id:
            raise ValueError("Invalid fetch session")
            
        config = ShareConfig()
        p2p = P2PManager(config)
        output_file = None
        
        try:
            session.status = "connecting"
            self._save_session(session)
            
            # Setup progress tracking with rich holographic display
            with Progress(
                SpinnerColumn(),
                *Progress.get_default_columns(),
                TimeElapsedColumn(),
                console=console,
                transient=False
            ) as progress:
                # Add download task
                task_id = progress.add_task(
                    description=self._format_progress_message(session),
                    total=session.total_size or 100
                )
                
                # Start download with progress updates
                session.status = "downloading"
                self._active_transfers.add(session.id)
                
                def update_progress(bytes_received: int) -> None:
                    progress.update(task_id, completed=bytes_received)
                
                output_file = await p2p.fetch_file(
                    session.share_code,
                    session.file_path,
                    progress_callback=update_progress,
                )
                
                if output_file and output_file.exists():
                    # Update session info
                    session.total_size = output_file.stat().st_size
                    session.transferred = session.total_size
                    session.status = "completed"
                    logger.info(f"Download completed: {session.id}")
                    
        except P2PError as e:
            session.status = "error"
            session.error = str(e)
            if output_file and output_file.exists():
                output_file.unlink()
            logger.error(f"Download error in session {session.id}: {e}")
            raise
            
        except asyncio.CancelledError:
            session.status = "cancelled"
            session.error = "Download cancelled by user"
            if output_file and output_file.exists():
                output_file.unlink()
            logger.info(f"Download cancelled: {session.id}")
            
        finally:
            self._active_transfers.discard(session.id)
            self._save_session(session)
            
    def get_session(self, session_id: str) -> Optional[TransferSession]:
        """Get session by ID."""
        return self.sessions.get(session_id)
        
    def get_session_info(self, session_id: str) -> Dict[str, Any]:
        """Get detailed session info."""
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")
            
        return {
            "id": session.id,
            "type": "share" if isinstance(session, P2PShareSession) else "fetch",
            "status": session.status,
            "error": session.error,
            "progress": session.get_progress(),
            "start_time": session.start_time.isoformat(),
            "file_path": session.file_path,
            "total_size": session.total_size,
            "transferred": session.transferred
        }
        
    def _save_session(self, session: TransferSession) -> None:
        """Save session state."""
        if session and session.id:
            self.sessions[session.id] = session
            # Persist to disk
            self._save_sessions_to_disk()
            
    def _clean_share_code(self, code: str) -> str:
        """Clean and validate share code."""
        clean = code.strip()
        if not clean.startswith("snatch://"):
            raise ValueError("Invalid share code format")
        return clean

    def shutdown(self) -> None:
        """Shutdown session manager gracefully."""
        try:
            # Signal shutdown
            self._shutdown = True
            
            # Cancel active transfers
            for session_id in list(self._active_transfers):
                try:
                    self.cancel_session(session_id)
                except Exception as e:
                    logger.error(f"Error cancelling session {session_id}: {e}")
                    
            # Save final state
            self._save_sessions_to_disk()
            
            # Cleanup resources
            if self._executor:
                self._executor.shutdown(wait=True)
                
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
        finally:
            logger.info("Session manager shutdown complete")
            
    def cleanup_sessions(self, max_age: int = 24 * 60 * 60) -> int:
        """Clean up old sessions."""
        now = datetime.now()
        expired = []
        
        for session_id, session in list(self.sessions.items()):
            # Skip active transfers
            if session_id in self._active_transfers:
                continue
                
            # Check age
            age = (now - session.start_time).total_seconds()
            if age > max_age:
                expired.append(session_id)
                
            # Clean up completed/failed sessions
            elif session.status in ("completed", "error", "cancelled"):
                if isinstance(session, P2PFetchSession):
                    session.cleanup()  # Clean temp files
                expired.append(session_id)
                
        # Remove expired sessions
        for session_id in expired:
            del self.sessions[session_id]
            
        # Save changes
        if expired:
            self._save_sessions_to_disk()
            
        return len(expired)
    
    def _save_sessions_to_disk(self) -> None:
        """Persist sessions to disk."""
        try:
            # Convert sessions to dict
            data = {}
            for sid, session in self.sessions.items():
                if isinstance(session, TransferSession):
                    data[sid] = asdict(session)
                else:  # Handle legacy sessions
                    data[sid] = dict(session)
            # Save to file
            temp_path = Path(self.session_file).with_suffix('.tmp')
            
            with temp_path.open('w') as f:
                json.dump(self._serialize_sessions(), f, indent=2)
            temp_path.replace(self.session_file)

                
        except Exception as e:
            logger.error(f"Failed to save sessions: {e}")
            temp_path.unlink(missing_ok=True)

    def _serialize_sessions(self) -> Dict:
        return {
            sid: (session.to_dict() if isinstance(session, TransferSession)
                  else session)
            for sid, session in self.sessions.items()
        }

    def _load_sessions(self) -> None:
        """Load sessions from disk."""
        try:
            load_path = Path(DOWNLOAD_SESSIONS_FILE)
            if not load_path.exists():
                return
                
            with load_path.open('r', encoding='utf-8') as f:
                data = json.load(f)
                
            # Restore sessions
            for sid, session_data in data.items():
                try:
                    if session_data.get('type') == 'share':
                        session = P2PShareSession(**session_data)
                    else:
                        session = P2PFetchSession(**session_data)
                    self.sessions[sid] = session
                except Exception as e:
                    logger.error(f"Failed to restore session {sid}: {e}")
                    
        except Exception as e:
            logger.error(f"Failed to load sessions: {e}")
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

    def __enter__(self) -> 'SessionManager':
        """Context manager enter."""
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit with cleanup."""
        self.shutdown()
