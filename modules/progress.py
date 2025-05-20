#progress/spinner interface, UI abstraction
from colorama import Fore, Style, init
from typing import Optional, Dict, List, Any, Union
import asyncio
from rich.progress import (
    Progress, SpinnerColumn, TimeRemainingColumn,
    TextColumn, BarColumn, DownloadColumn,
    TransferSpeedColumn, TaskProgressColumn
)
from rich.live import Live
from rich.panel import Panel
from rich.console import Console
from rich.table import Table
from rich.layout import Layout
from rich.text import Text
from rich import box
from .defaults import SPINNER_STYLES, THEME
import threading
import platform
import logging
import shutil
import tqdm
import time
import os
import math
import sys
import json

# Rich console setup
console = Console(theme=THEME)
logger = logging.getLogger(__name__)

# Progress Dashboard Constants
STYLE = {
    "progress": {
        "bar": {
            "complete": "bright_cyan",
            "finished": "bright_green",
            "pulse": "bright_cyan"
        },
        "speed": "bright_yellow",
        "elapsed": "bright_black",
        "remaining": "bright_black",
        "description": "bright_white"
    },
    "status": {
        "success": "bright_green",
        "error": "bright_red",
        "warning": "bright_yellow",
        "info": "bright_blue"
    }
}

BOX = {
    "main": box.HEAVY,
    "progress": box.ROUNDED,
    "stats": box.MINIMAL_HEAVY_HEAD,
    "info": box.SIMPLE
}

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
class HolographicProgress(DetailedProgressDisplay):
    """Premium progress display with holographic effects and enhanced visuals"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.holo_colors = ["#00ffff", "#ff00ff", "#9400d3"]  # Cyan, Magenta, Purple
        self.shimmer_phase = 0
        self.border_style = "bold cyan"
        self.box = "round"
        
    def _get_progress_bar(self, percent: float) -> str:
        """Generate holographic progress bar with light effects"""
        bar_width = min(self.bar_size, max(10, self.max_width - 30))
        filled_width = int(bar_width * percent / 100)
        
        # Create gradient effect
        gradient_bar = []
        for i in range(filled_width):
            color_idx = int((i / filled_width) * (len(self.holo_colors)-1))
            gradient_bar.append(f"[{self.holo_colors[color_idx]}]█[/]")
        
        # Add shimmer effect
        if self.shimmer_phase % 3 == 0 and filled_width > 3:
            gradient_bar[-2] = "[white]▓[/]"
        self.shimmer_phase += 1
        
        # Remaining space
        remaining = "[bright_black]░[/]" * (bar_width - filled_width)
        
        return (
            f"[{self.border_style}]╭[/]" + 
            "".join(gradient_bar) + 
            remaining +
            f"[{self.border_style}]╮[/]\n" +
            f"[{self.border_style}]╰[/] {percent:5.1f}% [bright_black]◀[/]"
        )

    def _format_title(self) -> str:
        """Create shimmering title effect"""
        title = f"🌀 {self.title}"
        shimmer_text = ""
        for i, char in enumerate(title):
            phase = (self.shimmer_phase + i) % len(self.holo_colors)
            shimmer_text += f"[{self.holo_colors[phase]}]{char}[/]"
        return shimmer_text

    def display(self) -> None:
        """Overridden display with holographic effects"""
        # Add border padding
        self.max_width -= 4  # Account for border characters
        super().display()
        self.max_width += 4

    def _format_display_header(self) -> None:
        """Holographic header formatting"""
        print(f"\n[{self.border_style}]╔{'═' * (self.term_width-2)}╗[/]")
        title_line = self._format_title().center(self.term_width-4)
        print(f"[{self.border_style}]║[/] {title_line} [{self.border_style}]║[/]")
        print(f"[{self.border_style}]╚{'═' * (self.term_width-2)}╝[/]\n")

    def _format_speed(self, speed: float) -> str:
        """Animated speed display"""
        if speed > 1e6:  # MB/s range
            return f"[blink]⚡[/] [cyan]{super()._format_speed(speed)}[/]"
        return f"[cyan]{super()._format_speed(speed)}[/]"

    def finish(self, success: bool = True) -> None:
        """Add special effects on completion"""
        if success:
            end_msg = "[blink]✅ Download Complete![/]"
            self.holo_colors = ["#00ff00", "#00ffff", "#00ff00"]  # Green shimmer
        else:
            end_msg = "[blink]❌ Download Failed![/]"
            self.holo_colors = ["#ff0000", "#ff4500", "#ff0000"]  # Red shimmer
        
        super().finish(success)
        print(f"\n[end_msg]", end="")
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

class RichProgressDashboard:
    """Modern progress dashboard with real-time stats, adaptive layout, and holographic effects.
    
    Features:
    - Multi-column progress bars with ETA and speed
    - Real-time transfer statistics with peak/average speeds
    - System resource monitoring
    - File information panel
    - Rich styling and animations
    - Responsive layout
    """
    
    def __init__(self, total_size: int = 0, title: str = "Download"):
        self.total_size = total_size
        self.title = title
        self.started = False
        self.download_task_id = None
        self._lock = threading.Lock()
        
        # Stats tracking
        self.stats = {
            "downloaded": 0,
            "current_speed": 0,
            "peak_speed": 0,
            "avg_speed": 0,
            "start_time": 0,
            "speeds": [],
            "max_samples": 50
        }
        
        # Setup Rich components
        self.progress = Progress(
            SpinnerColumn(style=STYLE["progress"]["description"]),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(
                complete_style=STYLE["progress"]["bar"]["complete"],
                finished_style=STYLE["progress"]["bar"]["finished"],
                pulse_style=STYLE["progress"]["bar"]["pulse"]
            ),
            TaskProgressColumn(),
            DownloadColumn(binary_units=True),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
            expand=True
        )
        
        # Create layout
        self.layout = Layout()
        self._setup_layout()

    def _setup_layout(self):
        """Configure the dashboard layout"""
        self.layout.split(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=3)
        )
        
        self.layout["body"].split_row(
            Layout(name="main", ratio=2),
            Layout(name="sidebar", ratio=1)
        )
        
        self.layout["main"].split(
            Layout(name="progress"),
            Layout(name="stats")
        )

    def _render_header(self) -> Panel:
        """Render the header panel with title and status"""
        return Panel(
            Text(self.title, style="bold bright_cyan"),
            box=BOX["main"],
            border_style="bright_blue",
            title="Snatch Download Manager"
        )

    def _render_progress(self) -> Panel:
        """Render the progress panel"""
        return Panel(
            self.progress,
            box=BOX["progress"],
            border_style="bright_cyan",
            title="Progress"
        )

    def _render_stats(self) -> Panel:
        """Render download statistics"""
        stats_table = Table.grid(expand=True, padding=(0, 2))
        stats_table.add_column(style="bright_blue")
        stats_table.add_column(justify="right")
        
        avg_speed = self._format_speed(self.stats["avg_speed"])
        peak_speed = self._format_speed(self.stats["peak_speed"])
        elapsed = time.time() - self.stats["start_time"] if self.stats["start_time"] else 0
        
        stats_table.add_row("Average Speed:", avg_speed)
        stats_table.add_row("Peak Speed:", peak_speed)
        stats_table.add_row("Time Elapsed:", self._format_time(elapsed))
        
        return Panel(
            stats_table,
            box=BOX["stats"],
            border_style="bright_blue",
            title="Statistics"
        )

    def _render_sidebar(self) -> Panel:
        """Render system info and file details"""
        info_table = Table.grid(expand=True, padding=(0, 2))
        info_table.add_column(style="bright_blue")
        info_table.add_column(justify="right")
        
        info_table.add_row(
            "File Size:",
            self._format_size(self.total_size) if self.total_size else "Unknown"
        )
        info_table.add_row(
            "Downloaded:",
            self._format_size(self.stats["downloaded"])
        )
        
        # Add system stats if psutil is available
        try:
            import psutil
            info_table.add_row("CPU Usage:", f"{psutil.cpu_percent()}%")
            info_table.add_row("Memory Usage:", f"{psutil.virtual_memory().percent}%")
        except ImportError:
            pass
        
        return Panel(
            info_table,
            box=BOX["info"],
            border_style="bright_cyan",
            title="Information"
        )

    def _format_size(self, size: int) -> str:
        """Format size in human-readable format"""
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"

    def _format_speed(self, speed: float) -> str:
        """Format speed with units"""
        return f"{self._format_size(speed)}/s" if speed else "0 B/s"

    def _format_time(self, seconds: float) -> str:
        """Format time duration"""
        if seconds < 60:
            return f"{seconds:.1f}s"
        minutes = int(seconds / 60)
        seconds = seconds % 60
        if minutes < 60:
            return f"{minutes}m {seconds:.0f}s"
        hours = int(minutes / 60)
        minutes = minutes % 60
        return f"{hours}h {minutes}m"

    def _update_speed_stats(self, bytes_downloaded: int, elapsed: float):
        """Update speed statistics"""
        if elapsed > 0:
            current_speed = bytes_downloaded / elapsed
            self.stats["current_speed"] = current_speed
            self.stats["peak_speed"] = max(self.stats["peak_speed"], current_speed)
            
            # Update speed samples
            self.stats["speeds"].append(current_speed)
            if len(self.stats["speeds"]) > self.stats["max_samples"]:
                self.stats["speeds"].pop(0)
            
            # Calculate average speed
            self.stats["avg_speed"] = sum(self.stats["speeds"]) / len(self.stats["speeds"])

    def start(self):
        """Start the progress dashboard"""
        if not self.started:
            self.stats["start_time"] = time.time()
            self.last_update_time = 0
            self.download_task_id = self.progress.add_task(
                "[cyan]Downloading...", 
                total=self.total_size or 100
            )
            self.started = True

    def update(self, bytes_increment: int):
        """Update progress with new bytes downloaded"""
        with self._lock:
            if not self.started:
                self.start()
            
            self.stats["downloaded"] += bytes_increment
            elapsed = time.time() - self.stats["start_time"]
            self._update_speed_stats(bytes_increment, elapsed)
            
            # Update progress bar
            self.progress.update(
                self.download_task_id,
                advance=bytes_increment,
                refresh=True
            )

    def refresh(self):
        """Refresh the entire dashboard"""
        self.layout["header"].update(self._render_header())
        self.layout["progress"].update(self._render_progress())
        self.layout["stats"].update(self._render_stats())
        self.layout["sidebar"].update(self._render_sidebar())

    async def run(self):
        """Run the dashboard in an async context"""
        with Live(self.layout, refresh_per_second=4, screen=True):
            while True:
                self.refresh()
                await asyncio.sleep(0.25)
    
    def run_sync(self):
        """Run the dashboard synchronously"""
        with Live(self.layout, refresh_per_second=4, screen=True):
            try:
                while True:
                    self.refresh()
                    time.sleep(0.25)
            except KeyboardInterrupt:
                self.stop()

    def stop(self):
        """Stop the progress dashboard"""
        if self.started:
            self.progress.remove_task(self.download_task_id)
            self.started = False

class HolographicDownloadDashboard:
    """Premium interactive download dashboard with holographic effects and real-time monitoring.
    
    Features:
    - Real-time speed and progress visualization
    - System resource monitoring
    - Detailed format information
    - Network speed monitoring
    - Smart retry handling
    - File integrity tracking
    """
    
    def __init__(
        self,
        manager: 'DownloadManager',
        console: Optional[Console] = None,
        theme: Optional[Dict[str, str]] = None
    ):
        self.manager = manager
        self.console = console or Console()
        self.layout = Layout()
        self._setup_layout()
        
        # Progress tracking
        self.progress = Progress(
            TextColumn("[progress.description]{task.description}"),
            SpinnerColumn("dots", style="progress"),
            BarColumn(
                complete_style="progress.bar.complete",
                finished_style="progress.bar.finished",
                pulse_style="progress.bar.pulse"
            ),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            DownloadColumn(binary_units=True),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
            expand=True
        )
        
        # Stats tracking
        self.current_task = None
        self.stats = {
            "start_time": None,
            "downloaded_bytes": 0,
            "total_bytes": 0,
            "current_speed": 0,
            "peak_speed": 0,
            "speeds": [],  # Rolling window of speed samples
            "retries": 0,
            "max_retries": 3
        }
        
        # Holographic effects
        self.holographic_colors = ["#00ffff", "#ff00ff", "#9400d3"]  # Cyan, Magenta, Purple
        self.shimmer_phase = 0
        
    def _setup_layout(self):
        """Configure the dashboard layout"""
        # Main layout structure
        self.layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main", ratio=8),
            Layout(name="footer", size=3),
        )
        
        # Main content area with progress and info
        self.layout["main"].split_row(
            Layout(name="body", ratio=2),
            Layout(name="sidebar", ratio=1, minimum_size=30),
        )
        
        # Body section with progress and details
        self.layout["body"].split(
            Layout(name="progress"),
            Layout(name="details"),
        )
        
    def _render_header(self) -> Panel:
        """Render holographic header with download info"""
        # Create shimmering title
        title = "🌀 Snatch Download Manager"
        shimmer_text = ""
        for i, char in enumerate(title):
            phase = (self.shimmer_phase + i) % len(self.holographic_colors)
            shimmer_text += f"[{self.holographic_colors[phase]}]{char}[/]"
        
        # Add download status
        if self.stats["start_time"]:
            elapsed = time.time() - self.stats["start_time"]
            speed = self.stats["current_speed"]
            status = f"⏱️ {self._format_time(elapsed)} | ⚡ {self._format_speed(speed)}"
        else:
            status = "Initializing..."
            
        content = Table.grid(padding=(0, 1))
        content.add_row(Text(shimmer_text, justify="center"))
        content.add_row(Text(status, justify="center", style="bright_blue"))
        
        return Panel(
            content,
            box=BOX["main"],
            border_style="bright_blue",
            padding=(1, 2)
        )
    
    def _render_progress(self) -> Panel:
        """Render main download progress section"""
        return Panel(
            self.progress,
            title=self._get_progress_title(),
            border_style="bright_cyan",
            box=BOX["progress"]
        )
    
    def _render_details(self) -> Panel:
        """Render download details and statistics"""
        stats_table = Table.grid(expand=True)
        stats_table.add_column(style="bright_blue")
        stats_table.add_column(justify="right")
        
        # Download stats
        downloaded = self.stats["downloaded_bytes"]
        total = self.stats["total_bytes"]
        peak = self.stats["peak_speed"]
        
        stats_table.add_row("Downloaded:", self._format_size(downloaded))
        stats_table.add_row("Total Size:", self._format_size(total))
        stats_table.add_row("Peak Speed:", self._format_speed(peak))
        
        if self.stats["retries"] > 0:
            stats_table.add_row(
                "Retries:",
                f"{self.stats['retries']}/{self.stats['max_retries']}"
            )
        
        return Panel(
            stats_table,
            title="📊 Statistics",
            border_style="bright_blue",
            box=BOX["stats"]
        )
    
    def _render_sidebar(self) -> Panel:
        """Render system info and download queue"""
        try:
            import psutil
            cpu = psutil.cpu_percent()
            mem = psutil.virtual_memory().percent
            
            sys_table = Table.grid(expand=True)
            sys_table.add_column(style="bright_blue")
            sys_table.add_column(justify="right")
            
            sys_table.add_row("CPU Usage:", f"{cpu}%")
            sys_table.add_row("Memory:", f"{mem}%")
            sys_table.add_row("Active Downloads:", str(len(self.manager.current_downloads)))
            
            return Panel(
                sys_table,
                title="💻 System",
                border_style="bright_cyan",
                box=BOX["info"]
            )
            
        except ImportError:
            return Panel(
                "System monitoring unavailable",
                border_style="bright_cyan",
                box=BOX["info"]
            )
    
    def _get_progress_title(self) -> str:
        """Get the progress panel title with holographic effect"""
        phase = int(time.time() * 2) % len(self.holographic_colors)
        color = self.holographic_colors[phase]
        return f"[{color}]⬇️ Download Progress[/]"
    
    def _format_size(self, size: int) -> str:
        """Format size with color-coded units"""
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024:
                return f"[cyan]{size:.1f}[/] [bright_black]{unit}[/]"
            size /= 1024
        return f"[cyan]{size:.1f}[/] [bright_black]PB[/]"
    
    def _format_speed(self, speed: float) -> str:
        """Format speed with color-coded units"""
        if speed == 0:
            return "[bright_black]0 B/s[/]"
        
        formatted = self._format_size(speed)
        return f"{formatted}/s"
    
    def _format_time(self, seconds: float) -> str:
        """Format time with color coding"""
        if seconds < 60:
            return f"[cyan]{seconds:.1f}[/][bright_black]s[/]"
        
        minutes = int(seconds / 60)
        seconds = seconds % 60
        if minutes < 60:
            return f"[cyan]{minutes}[/][bright_black]m [/][cyan]{seconds:.0f}[/][bright_black]s[/]"
        
        hours = int(minutes / 60)
        minutes = minutes % 60
        return f"[cyan]{hours}[/][bright_black]h [/][cyan]{minutes}[/][bright_black]m[/]"
    
    def start(self, title: str = "Downloading...", total: Optional[int] = None):
        """Start a new download task"""
        self.stats.update({
            "start_time": time.time(),
            "downloaded_bytes": 0,
            "total_bytes": total or 0,
            "current_speed": 0,
            "peak_speed": 0,
            "speeds": [],
            "retries": 0
        })
        
        self.current_task = self.progress.add_task(title, total=100)
    
    def update(self, n: int, total: Optional[int] = None, speed: Optional[float] = None):
        """Update download progress"""
        if not self.current_task:
            self.start()
        
        self.stats["downloaded_bytes"] += n
        if total is not None:
            self.stats["total_bytes"] = total
        
        if speed is not None:
            self.stats["current_speed"] = speed
            self.stats["peak_speed"] = max(self.stats["peak_speed"], speed)
            
            # Update speed samples
            self.stats["speeds"].append(speed)
            if len(self.stats["speeds"]) > 50:  # Keep last 50 samples
                self.stats["speeds"].pop(0)
        
        # Update progress percentage
        if self.stats["total_bytes"] > 0:
            percentage = (self.stats["downloaded_bytes"] / self.stats["total_bytes"]) * 100
            self.progress.update(self.current_task, completed=percentage)
    
    def retry(self, reason: str):
        """Handle a retry event"""
        self.stats["retries"] += 1
        self.progress.update(
            self.current_task,
            description=f"[yellow]Retrying ({reason})[/]"
        )
    
    def finish(self, success: bool = True):
        """Complete the download task"""
        if success:
            self.progress.update(
                self.current_task,
                completed=100,
                description="[green]Download Complete![/]"
            )
        else:
            self.progress.update(
                self.current_task,
                description="[red]Download Failed[/]"
            )
    
    def refresh(self):
        """Refresh the entire dashboard"""
        self.shimmer_phase += 1  # Update holographic effect
        
        # Update layout sections
        self.layout["header"].update(self._render_header())
        self.layout["progress"].update(self._render_progress())
        self.layout["details"].update(self._render_details())
        self.layout["sidebar"].update(self._render_sidebar())
        
        # Live update
        self.console.print(self.layout)
    
    async def run(self):
        """Run the dashboard asynchronously"""
        with Live(self.layout, console=self.console, refresh_per_second=4) as live:
            while True:
                self.refresh()
                await asyncio.sleep(0.25)  # 4 times per second
                
    def run_sync(self):
        """Run the dashboard synchronously"""
        with Live(self.layout, console=self.console, refresh_per_second=4) as live:
            try:
                while True:
                    self.refresh()
                    time.sleep(0.25)
            except KeyboardInterrupt:
                pass
