#progress/spinner interface, UI abstraction
from colorama import Fore, Style, init
from typing import Optional 
from .defaults import SPINNER_STYLES
import threading
import platform
import logging
import shutil
import tqdm
import time
import re
import os
import sys

logger = logging.getLogger(__name__)
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

        # Create proper tqdm instance
        self.progress = tqdm.tqdm(
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

class SpinnerAnimation:
    """Enhanced progress spinner with customizable styles and error recovery"""
    
    def __init__(self, message: str = "", style: str = "dots", color: str = "cyan"):
        self.message = message
        self.running = False
        self.thread = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._lock = threading.Lock()
        self._last_status = ""
        
        # Get spinner style from SPINNER_STYLES or fallback to default
        self.frames = SPINNER_STYLES.get(style, SPINNER_STYLES["aesthetic"])
        
        # Map color names to Fore colors
        self.color = getattr(Fore, color.upper(), Fore.CYAN)
        
        # Keep track of terminal width for dynamic resizing
        try:
            self.term_width = shutil.get_terminal_size().columns
        except:
            self.term_width = 80
            
    def start(self):
        """Start the spinner animation in a separate thread"""
        if self.running:
            return
            
        self.running = True
        self._stop_event.clear()
        self._pause_event.clear()
        
        def spin():
            index = 0
            while not self._stop_event.is_set():
                if not self._pause_event.is_set():
                    try:
                        # Get current terminal width for proper wrapping
                        self.term_width = shutil.get_terminal_size().columns
                    except:
                        pass
                        
                    status = f"\r{self.color}{self.frames[index]}{Style.RESET_ALL} {self.message}"
                    
                    # Handle status that's too long for terminal
                    if len(status) > self.term_width:
                        status = status[:self.term_width-3] + "..."
                        
                    # Only update if status changed to reduce flicker
                    if status != self._last_status:
                        sys.stdout.write(status)
                        sys.stdout.flush()
                        self._last_status = status
                        
                    index = (index + 1) % len(self.frames)
                    
                time.sleep(0.1)
                
        self.thread = threading.Thread(target=spin, daemon=True)
        self.thread.start()
        
    def stop(self, clear: bool = True, success: bool = True):
        """Stop the spinner animation"""
        if not self.running:
            return
            
        self._stop_event.set()
        if self.thread:
            self.thread.join()
            
        self.running = False
        
        if clear:
            sys.stdout.write('\r' + ' ' * (len(self._last_status) + 1) + '\r')
        else:
            # Show final status with success/failure indicator
            icon = f"{Fore.GREEN}✓{Style.RESET_ALL}" if success else f"{Fore.RED}✗{Style.RESET_ALL}"
            final_status = f"\r{icon} {self.message}\n"
            sys.stdout.write(final_status)
            
        sys.stdout.flush()
        
    def update_status(self, message: str):
        """Update the spinner message thread-safely"""
        with self._lock:
            self.message = message
            # Force status update on next spin
            self._last_status = ""
            
    def pause(self):
        """Pause the spinner animation"""
        self._pause_event.set()
        
    def resume(self):
        """Resume the spinner animation"""
        self._pause_event.clear()
        
    def __enter__(self):
        """Support for use as context manager"""
        self.start()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Ensure spinner is stopped when context exits"""
        success = exc_type is None
        self.stop(success=success)

class Spinner:
    """Simple spinner for basic loading states"""
    def __init__(self, message: str = "Processing"):
        self.message = message
        self.running = False
        self.thread = None
        self.frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self._lock = threading.Lock()

    def spin(self):
        """Display spinner animation"""
        i = 0
        while self.running:
            frame = self.frames[i % len(self.frames)]
            sys.stdout.write(f"\r{frame} {self.message}")
            sys.stdout.flush()
            time.sleep(0.1)
            i += 1

    def start(self):
        """Start spinner animation"""
        with self._lock:
            if not self.running:
                self.running = True
                self.thread = threading.Thread(target=self.spin)
                self.thread.daemon = True
                self.thread.start()

    def stop(self):
        """Stop spinner animation"""
        with self._lock:
            self.running = False
        if self.thread:
            self.thread.join()
        sys.stdout.write("\r" + " " * (len(self.message) + 2) + "\r")
        sys.stdout.flush()
