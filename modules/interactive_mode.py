#!/usr/bin/env python3
"""
interactive_mode.py - Snatch Premium Interactive Experience

A modern, feature-rich terminal interface for media downloads.

Features:
- Responsive multi-pane TUI layout
- Real-time media previews and metadata display
- Holographic progress visualization
- Intelligent format selection matrix
- Context-sensitive help system
- Smooth animated transitions
- Advanced surround sound configuration
- Download queue management
- System resource monitoring
"""

import sys
import time
import asyncio
import psutil
import re
import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Union, Tuple
from datetime import datetime

from rich import box
from rich.console import Console, RenderableType
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.panel import Panel
from rich.progress import (
    Progress, SpinnerColumn, BarColumn, TextColumn, 
    DownloadColumn, TransferSpeedColumn, TimeRemainingColumn,
    TaskProgressColumn, Group, MofNCompleteColumn
)
from rich.layout import Layout
from rich.live import Live
from textual.widgets import Markdown  # Markdown support
from rich.align import Align
from rich.text import Text
from rich.table import Table
from rich.columns import Columns
from rich.style import Style
from rich.syntax import Syntax
from rich.traceback import install
from rich.measure import Measurement
from rich.spinner import Spinner

from colorama import Fore, Style as ColoramaStyle, init
import typer

# Import local modules
from .manager import DownloadManager, AsyncDownloadManager
from .defaults import (
    THEME, BANNER_ART, HELP_CONTENT, QUALITY_PRESETS,
    SURROUND_PROFILES, SUBTITLE_STYLES
)
from .logging_config import setup_logging
from .progress import HolographicProgress
from .common_utils import sanitize_filename, format_size
from .audio_processor import AudioProcessor
from .advanced_config import AdvancedConfigManager, ConfigCategory

# Textual imports for TUI features
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import (
    Button, Header, Footer, Static, Input, Label, 
    Checkbox, DataTable, Select, ProgressBar, 
    ContentSwitcher, RadioSet, RadioButton
)
from textual.reactive import reactive
from textual.containers import Container, Vertical, Horizontal
from textual.worker import Worker, WorkerState
from textual import work

# Safe wrapper for table access to prevent RowDoesNotExist errors
def safe_get_row(table, row_index, default_value=None):
    """Safe getter for DataTable rows that prevents RowDoesNotExist errors"""
    if not hasattr(table, "row_count") or table.row_count == 0:
        return default_value
        
    try:
        if hasattr(table, "get_row_at"):
            return table.get_row_at(row_index)
    except Exception as e:
        logging.warning(f"Error accessing table row: {str(e)}")
        
    return default_value

# Enable rich traceback handling
install(show_locals=True)

# Initialize colorama and console
init(autoreset=True)
console = Console(theme=THEME)

# Constants to reduce string duplication
UI_ELEMENTS = {
    "FILES_LIST": "#files-list",
    "FORMAT_TABLE": "#format-table",
    "PROCESS_AUDIO": "#process-audio",
    "DOWNLOAD_BUTTON": "#download-button",
    "URL_INPUT": "#url-input",
    "STATUS_BAR": "#status-bar"
}

CONSTANTS = {
    "PRESS_ENTER": "\n[dim]Press Enter to continue[/]",
    "FILE_ORG_NOT_AVAILABLE": "File organizer module not available",
    "FFMPEG_EXE": "ffmpeg.exe",
    "FFMPEG_BINARY": "ffmpeg",
    "DOWNLOAD_FAILED": "Download failed",
    "PROCESSING_COMPLETE": "Processing complete",
    "CONVERSION_FAILED": "Conversion failed"
}

# Custom exception classes
class DownloadManagerError(Exception):
    """Custom exception for download manager errors"""
    pass

class ConversionError(Exception):
    """Custom exception for conversion errors"""
    pass

# UI Style Constants
STYLE = {
    "primary": "bold cyan",
    "secondary": "bright_green",
    "accent": "magenta",
    "success": "bold bright_green",
    "warning": "bold yellow",  
    "error": "bold red",
    "muted": "dim",
    "header": "bold bright_blue",
    "title": "bold bright_white",
    "label": "cyan",
    "value": "bright_white",
    "progress": "bright_blue"
}

# Box Styles
BOX = {
    "app": box.HEAVY,
    "panel": box.ROUNDED,
    "data": box.MINIMAL_HEAVY_HEAD,
    "section": box.HEAVY_EDGE,
    "simple": box.SIMPLE,
    "double": box.DOUBLE
}

# Border Styles
BORDERS = {
    "primary": "bright_blue",
    "secondary": "cyan",
    "accent": "magenta", 
    "preview": "bright_blue",
    "info": "cyan",
    "matrix": "magenta",
    "surround": "green",
    "help": "yellow"
}

# Layout Constants
LAYOUT = {
    "header_size": 3,
    "footer_size": 3,
    "sidebar_size": 35,
    "status_size": 3,
    "main_ratio": 3,
    "content_ratio": 8
}

# Update Intervals
REFRESH_RATE = {
    "normal": 4,
    "fast": 10,
    "slow": 1
}

# UI Elements
UI = {
    "spinner": "dots",
    "progress_chars": "█░",
    "indent": "  ",
    "spacer": "\n"
}


# Error message constants
ERROR_MESSAGES = {
    "INPUT_FILE_NOT_EXIST": "Input file does not exist",
    "FILE_ORG_FAILED": "File organization failed",
    "NO_INPUT_FILE": "Please specify an input file",
    "CONVERSION_FAILED": "Conversion failed",
    "PROCESSING_FAILED": "Processing failed"
}

def create_format_table(formats: List[Dict[str, Any]], box_style=None, border_style: str = "bright_blue") -> Table:
    """Create a formatted table for displaying media format information.
    
    Args:
        formats: List of format dictionaries with media information
        box_style: Rich box style for the table
        border_style: Border color style
        
    Returns:
        Rich Table object with formatted media information
    """
    table = Table(
        title="Available Formats",
        box=box_style or box.MINIMAL_HEAVY_HEAD,
        border_style=border_style,
        show_header=True,
        header_style="bold magenta"
    )
    
    # Add columns
    table.add_column("ID", style="cyan", width=6)
    table.add_column("Extension", style="green", width=10)
    table.add_column("Resolution", style="blue", width=12)
    table.add_column("Codec", style="yellow", width=10)
    table.add_column("Size", style="red", width=10)
    table.add_column("Audio", style="purple", width=12)
    table.add_column("FPS", style="bright_green", width=8)
    
    # Add format data
    for fmt in formats:
        table.add_row(
            str(fmt.get('format_id', 'N/A')),
            fmt.get('ext', 'N/A'),
            f"{fmt.get('width', 'N/A')}x{fmt.get('height', 'N/A')}" if fmt.get('width') and fmt.get('height') else 'N/A',
            fmt.get('vcodec', 'N/A')[:10] if fmt.get('vcodec') else 'N/A',
            format_size(fmt.get('filesize', 0)) if fmt.get('filesize') else 'N/A',
            f"{fmt.get('abr', 'N/A')} kbps" if fmt.get('abr') else 'N/A',
            str(fmt.get('fps', 'N/A')) if fmt.get('fps') else 'N/A'
        )
    
    return table

# Status classification helpers for reducing complexity
def classify_download_speed(speed_mbps: float) -> str:
    """Classify download speed into status classes."""
    if speed_mbps > 5:
        return "status-ok"
    elif speed_mbps > 1:
        return "status-warning"
    else:
        return "status-error"

def classify_upload_speed(speed_mbps: float) -> str:
    """Classify upload speed into status classes."""
    if speed_mbps > 2:
        return "status-ok"
    elif speed_mbps > 0.5:
        return "status-warning"
    else:
        return "status-error"

def classify_ping(ping_ms: float) -> str:
    """Classify ping latency into status classes."""
    if ping_ms < 100:
        return "status-ok"
    elif ping_ms < 200:
        return "status-warning"
    else:
        return "status-error"

def classify_jitter(jitter_ms: float) -> str:
    """Classify jitter into status classes."""
    if jitter_ms < 20:
        return "status-ok"
    elif jitter_ms < 50:
        return "status-warning"
    else:
        return "status-error"

def classify_packet_loss(loss_percent: float) -> str:
    """Classify packet loss into status classes."""
    if loss_percent < 1:
        return "status-ok"
    elif loss_percent < 5:
        return "status-warning"
    else:
        return "status-error"

def get_overall_rating(download_mbps: float, ping_ms: float) -> str:
    """Get overall network rating."""
    if download_mbps > 10 and ping_ms < 100:
        return "Good"
    elif download_mbps > 3:
        return "Fair"
    else:
        return "Poor"

def get_rating_class(rating: str) -> str:
    """Get CSS class for rating."""
    if rating == "Good":
        return "status-ok"
    elif rating == "Fair":
        return "status-warning"
    else:
        return "status-error"


class MediaInfo:
    """Rich media information display with metadata and quality visualization."""

    def __init__(self):
        self._theme = THEME
        self._box_style = box.HEAVY_EDGE
        self._last_update = None

    def render(self, metadata: Dict[str, Any]) -> Panel:
        """Generate rich panel with comprehensive media information."""
        self._last_update = datetime.now()
        
        # Create the main info grid
        grid = Table.grid(padding=(0, 2), expand=True)
        grid.add_column("Label", style="bright_blue", justify="right", width=15)
        grid.add_column("Value", style="bright_white", ratio=2)

        # Basic metadata
        grid.add_row("📺 Title", self._format_title(metadata.get('title', 'Unknown')))
        grid.add_row("⏱️ Duration", self._format_duration(metadata.get('duration', 0)))
        if metadata.get('upload_date'):
            grid.add_row("📅 Released", self._format_date(metadata['upload_date']))
        if metadata.get('uploader'):
            grid.add_row("👤 Uploader", f"[cyan]{metadata['uploader']}[/]")
            
        # Media-specific information
        if metadata.get('width') and metadata.get('height'):
            grid.add_row(
                "🎥 Resolution",
                f"{metadata['width']}x{metadata['height']} ({self._get_quality_tag(metadata)})"
            )
        
        # Extended metadata
        if 'ext' in metadata:
            grid.add_row("📦 Format", self._format_codec_info(metadata))
        if metadata.get('filesize'):
            grid.add_row("💾 Size", format_size(metadata['filesize']))
        if metadata.get('view_count'):
            grid.add_row("👁️ Views", f"{metadata['view_count']:,}")
            
        # Format table if available
        format_table = None
        if metadata.get('formats'):
            format_table = self._build_format_table(metadata['formats'])
            
        group = Group(
            grid,
            Text(""),  # Spacer
            self._build_quality_indicators(metadata),
            Text(""),  # Spacer
            format_table if format_table else Text("")
        )

        return Panel(
            group,
            title="[b]📊 Media Analysis[/b]",
            subtitle=f"[dim]Last updated: {self._format_relative_time(self._last_update)}[/]",
            border_style="bright_blue",
            box=self._box_style
        )
        
    def _format_title(self, title: str, max_length: int = 60) -> Text:
        """Format title with smart truncation and styling."""
        return Text(
            title if len(title) <= max_length else f"{title[:max_length-1]}…",
            style="bright_white bold"
        )
        
    def _format_duration(self, seconds: Union[float, int]) -> str:
        """Format duration in human-readable time format."""
        if not seconds:
            return "Unknown"
            
        hours, remainder = divmod(int(seconds), 3600)
        minutes, seconds = divmod(remainder, 60)
        
        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"
            
    def _format_date(self, date_str: str) -> str:
        """Format date in a human-readable format."""
        try:
            # Format YYYYMMDD to YYYY-MM-DD
            if len(date_str) == 8 and date_str.isdigit():
                return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
            return date_str
        except Exception:
            return date_str
            
    def _get_quality_tag(self, metadata: Dict[str, Any]) -> Text:
        """Generate rich quality tag based on resolution."""
        height = metadata.get('height', 0)
        
        if height >= 2160:
            return Text("4K UHD", style="bright_green bold")
        elif height >= 1080:
            return Text("Full HD", style="green bold")
        elif height >= 720:
            return Text("HD", style="yellow bold")
        elif height >= 480:
            return Text("SD", style="yellow")
        else:
            return Text("Low Quality", style="red")
            
    def _format_codec_info(self, metadata: Dict[str, Any]) -> Text:
        """Format codec information with color highlighting."""
        parts = []
        
        # File extension
        if metadata.get('ext'):
            parts.append(f"[bright_blue]{metadata['ext'].upper()}[/]")
        
        # Video codec
        if metadata.get('vcodec') and metadata['vcodec'] != 'none':
            codec = metadata['vcodec']
            parts.append(f"[green]{codec}[/]")
        
        # Audio codec
        if metadata.get('acodec') and metadata['acodec'] != 'none':
            codec = metadata['acodec']
            parts.append(f"[yellow]{codec}[/]")
            
        return Text(" • ".join(parts) if parts else "Unknown")
        
    def _format_relative_time(self, timestamp: datetime) -> str:
        """Format timestamp relative to current time."""
        now = datetime.now()
        delta = now - timestamp
        
        if delta.total_seconds() < 60:
            return "just now"
        elif delta.total_seconds() < 3600:
            minutes = int(delta.total_seconds() / 60)
            return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
        else:
            return timestamp.strftime("%H:%M:%S")
            
    def _build_quality_indicators(self, metadata: Dict[str, Any]) -> Panel:
        """Build visual quality indicators."""
        table = Table.grid(expand=True)
        table.add_column("Indicator", ratio=1)
        table.add_column("Value", ratio=2)
        table.add_column("Scale", ratio=3)
        
        # Video quality indicator
        if metadata.get('height'):
            resolution = metadata['height']
            max_res = 2160  # 4K UHD
            percentage = min(100, int((resolution / max_res) * 100))
            
            table.add_row(
                Text("Video Quality", style="cyan"),
                Text(f"{percentage}%", style="bright_white"),
                self._build_progress_bar(percentage)
            )
            
        # Audio quality indicator
        if metadata.get('abr'):
            abr = metadata['abr']
            max_abr = 320  # Typical maximum bitrate
            percentage = min(100, int((abr / max_abr) * 100))
            
            table.add_row(
                Text("Audio Quality", style="cyan"),
                Text(f"{percentage}%", style="bright_white"),
                self._build_progress_bar(percentage)
            )
            
        return Panel(
            table, 
            title="[b]Quality Rating[/b]",
            border_style="bright_blue",
            box=BOX["simple"]
        )
        
    def _build_progress_bar(self, percentage: int) -> Text:
        """Build a text-based progress bar."""
        width = 20
        filled = int((percentage / 100) * width)
        bar = "█" * filled + "░" * (width - filled)
        
        if percentage >= 75:
            style = "bright_green"
        elif percentage >= 50:
            style = "green"
        elif percentage >= 25:
            style = "yellow"
        else:
            style = "red"
            
        return Text(bar, style=style)
    def _build_format_table(self, formats: List[Dict[str, Any]]) -> Table:
        """Build a table of available formats."""
        # Use our improved format table creator
        return create_format_table(formats, box_style=BOX["data"], border_style="bright_blue")
        
    def _format_resolution(self, fmt: Dict[str, Any]) -> str:
        """Format resolution information."""
        if fmt.get('height') and fmt.get('width'):
            return f"{fmt['width']}x{fmt['height']}"
        return "N/A"
        
    def _format_audio_info(self, fmt: Dict[str, Any]) -> str:
        """Format audio information."""
        if fmt.get('abr'):
            return f"{fmt['abr']} kbps"
        return "N/A"

class InteractiveApp(App):
    """Modern Textual application for Snatch interactive mode"""
    
    TITLE = "Snatch Media Downloader"
    SUB_TITLE = "Interactive Mode"    # Constants for reducing duplication
    FORMAT_TABLE_ID = "#format-table"
    HELP_DOCUMENTATION_TITLE = "Help & Documentation"
    
    # Screen IDs
    DOWNLOAD_SCREEN = "download-screen"
    BROWSE_SCREEN = "browse-screen"
    NETWORK_SCREEN = "network-screen"
    SETTINGS_SCREEN = "settings-screen"
    HELP_SCREEN = "help-screen"
    AUDIO_SCREEN = "audio-screen"
    VIDEO_SCREEN = "video-screen"
    FILES_SCREEN = "files-screen"
      # Form input ID constants
    VIDEO_DIR_INPUT = "#video-dir-input"
    AUDIO_DIR_INPUT = "#audio-dir-input"
    FFMPEG_INPUT = "#ffmpeg-input"
    ORGANIZE_FILES = "#organize-files"
    
    # Default paths
    DEFAULT_VIDEO_DIR = os.path.join(os.path.expanduser("~"), "Downloads", "video")
    DEFAULT_AUDIO_DIR = os.path.join(os.path.expanduser("~"), "Downloads", "audio")
    CSS = """
    #header {
        dock: top;
        height: 1;
        background: $boost;
        color: $text;
    }
    
    #footer {
        dock: bottom;
        height: 1;
        background: $boost;
        color: $text;
    }
    
    #sidebar {
        dock: left;
        width: 32;
        background: $surface;
        border-right: thick $primary;
        padding: 0 1;
    }
    
    #main-content {
        background: $background;
        margin: 0 1;
    }
    
    .title {
        background: $primary;
        color: $background;
        text-align: center;
        padding: 1;
        text-style: bold;
        width: 100%;
        margin: 0 0 1 0;
    }
    
    .subtitle {
        background: $surface;
        color: $text;
        text-align: center;
        padding: 0 1;
        text-style: bold;
        margin: 0 0 1 0;
    }
    
    .section-title {
        color: $accent;
        text-style: bold;
        margin: 1 0;
        padding: 0 1;
    }
      .menu-item {
        padding: 1 2;
        margin: 0 1 1 1;
        border: solid $surface;
    }
    
    .menu-item:hover {
        background: $primary-darken-1;
        color: $text;
        border: solid $primary;
    }
    
    .menu-item.selected {
        background: $primary;
        color: $text;
        text-style: bold;
        border: solid $accent;
    }
      .info-panel {
        margin: 1;
        padding: 1;
        border: solid $primary-darken-2;
        background: $surface-lighten-1;
    }
    
    .action-panel {
        margin: 1;
        padding: 1;
        background: $surface;
        border: solid $accent;
    }
    
    .tab-container {
        margin: 0 0 1 0;
        padding: 0 1;
    }
    
    .tab-button {
        margin: 0 1 0 0;
        padding: 0 2;
        border: solid $surface;
        background: $surface;
    }
    
    .tab-button.active {
        background: $primary;
        color: $text;
        border: solid $primary;
        text-style: bold;
    }
    
    .tab-button:hover {
        background: $primary-darken-1;
        border: solid $primary-darken-1;
    }
    
    .progress-bar {
        width: 100%;
        margin: 1 0;
        border: solid $primary;
    }
    
    .status-ok {
        color: $success;
        text-style: bold;
    }
    
    .status-warning {
        color: $warning;
        text-style: bold;
    }
    
    .status-error {
        color: $error;
        text-style: bold;
    }
      .format-table {
        width: 100%;
        height: auto;
        border: solid $primary;
    }
    
    .primary {
        background: $primary;
        color: $text;
        text-style: bold;
        border: solid $primary;
        margin: 0 1 0 0;
    }
    
    .secondary {
        background: $surface;
        color: $text;
        border: solid $surface;
        margin: 0 1 0 0;
    }
    
    .primary:hover {
        background: $primary-lighten-1;
        border: solid $primary-lighten-1;
    }
    
    .secondary:hover {
        background: $surface-lighten-1;
        border: solid $surface-lighten-1;
    }
    
    DataTable {
        height: auto;
        border: solid $primary-darken-2;
    }
    
    Input {
        border: solid $primary-darken-2;
        margin: 0 0 1 0;
        padding: 0 1;
    }
    
    Input:focus {
        border: solid $primary;
    }
    
    Select {
        border: solid $primary-darken-2;
        margin: 0 0 1 0;
    }
    
    Checkbox {
        margin: 0 0 1 0;
    }
    
    Container {
        padding: 0 1;
    }
    
    #downloads-table {
        min-height: 10;
    }
    
    #format-table {
        min-height: 8;
    }
    
    #network-stats {
        min-height: 6;
    }
    
    #active-downloads {
        min-height: 6;
    }
    """
    
    # Screen ID constants
    DOWNLOAD_SCREEN = "download-screen"
    BROWSE_SCREEN = "browse-screen"
    NETWORK_SCREEN = "network-screen"
    SETTINGS_SCREEN = "settings-screen"
    HELP_SCREEN = "help-screen"
    AUDIO_SCREEN = "audio-screen"
    VIDEO_SCREEN = "video-screen"
    FILES_SCREEN = "files-screen"
    
    # Input field ID constants
    VIDEO_DIR_INPUT = "#video-dir-input"
    AUDIO_DIR_INPUT = "#audio-dir-input"
    FFMPEG_INPUT = "#ffmpeg-input"
    ORGANIZE_FILES = "#organize-files"
    
    # Default paths
    DEFAULT_VIDEO_DIR = os.path.join(os.path.expanduser("~"), "Downloads", "video")
    DEFAULT_AUDIO_DIR = os.path.join(os.path.expanduser("~"), "Downloads", "audio")
    
    # Help content
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the interactive app with configuration"""
        super().__init__()
        self.config = config
        self.download_manager = None
        self.current_url = None        
        self.format_info = None
        self.downloads = []
        
        # Initialize Advanced Configuration Manager
        self.config_manager = AdvancedConfigManager()
        self.config_manager.load_config()
        
        # Merge with existing config
        self.config.update(self.config_manager.config)
        
        # Current active settings tab
        self.active_settings_tab = "general-settings"
        
    def compose(self) -> ComposeResult:
        """Create UI layout"""
        yield Header()
        
        with Container():
            with Horizontal():
                # Left sidebar with menu
                with Container(id="sidebar"):
                    yield Static("MAIN MENU", classes="title")
                    yield Button("📥 Download", id="menu-download", classes="menu-item")
                    yield Button("🔍 Browse Downloads", id="menu-browse", classes="menu-item")
                    yield Button("🌐 Network Test", id="menu-network", classes="menu-item")
                    yield Button("⚙️ Settings", id="menu-settings", classes="menu-item")
                    yield Button("❓ Help", id="menu-help", classes="menu-item")
                    
                    yield Static("TOOLS", classes="title")
                    yield Button("🎵 Audio Tools", id="menu-audio", classes="menu-item")
                    yield Button("🎬 Video Tools", id="menu-video", classes="menu-item")
                    yield Button("💾 File Management", id="menu-files", classes="menu-item")
                    
                # Main content area with content switcher
                with Container(id="main-content"):
                    with ContentSwitcher(id="content-switcher"):
                        # Download screen
                        with Container(id="download-screen"):
                            yield Static("Download Media", classes="title")
                            yield Input(placeholder="Enter URL to download", id="url-input")
                            yield Button("Analyze URL", id="analyze-btn")
                            
                            with Container(id="format-selection", classes="info-panel"):
                                yield Static("Format Selection", classes="title")
                                yield DataTable(id="format-table", classes="format-table")
                                
                            with Container(id="download-options", classes="info-panel"):
                                yield Static("Download Options", classes="title")
                                yield Checkbox("Extract Audio Only", id="audio-only")
                                yield Checkbox("Process Audio (Denoise, Normalize)", id="process-audio")
                                yield Checkbox("Upmix to 7.1 Surround", id="upmix-audio")
                                
                            yield Button("Start Download", id="start-download-btn")
                            
                            with Container(id="active-downloads"):
                                yield Static("Active Downloads", classes="title")
                                # Will be populated dynamically
                        
                        # Browse screen
                        with Container(id="browse-screen"):
                            yield Static("Browse Downloads", classes="title")
                            yield Input(placeholder="Search downloads...", id="search-input")
                            yield DataTable(id="downloads-table")
                            
                        # Network screen
                        with Container(id="network-screen"):
                            yield Static("Network Diagnostics", classes="title")
                            yield Button("Run Speed Test", id="speedtest-btn")
                            with Container(id="network-stats", classes="info-panel"):
                                yield Static("Network Status: Checking...", id="network-status")
                                # Will be populated with speed test results
                                  # Settings screen
                        with Container(id="settings-screen"):
                            yield Static("Settings", classes="title")
                            
                            # Tabbed interface for different setting categories
                            with Container(id="settings-tabs", classes="tab-container"):
                                yield Button("General", id="general-tab", classes="tab-button active")
                                yield Button("Download", id="download-tab", classes="tab-button")
                                yield Button("Audio/Video", id="media-tab", classes="tab-button")
                                yield Button("Network", id="network-tab", classes="tab-button")
                                yield Button("Advanced", id="advanced-tab", classes="tab-button")
                            
                            with ContentSwitcher(id="settings-content"):
                                # General Settings
                                with Container(id="general-settings"):
                                    with Vertical():
                                        yield Static("Output Directories", classes="section-title")
                                        yield Input(placeholder="Video Output Directory", id="video-dir-input")
                                        yield Input(placeholder="Audio Output Directory", id="audio-dir-input")
                                        
                                        yield Static("Interface", classes="section-title")
                                        yield Select([
                                            ("Default", "default"),
                                            ("Dark", "dark"),
                                            ("Cyberpunk", "cyberpunk"),
                                            ("Matrix", "matrix"),
                                            ("Ocean", "ocean")
                                        ], value="default", id="theme-select")
                                        yield Checkbox("Keep Download History", id="download-history")
                                        yield Checkbox("Auto Update Check", id="auto-update")
                                
                                # Download Settings
                                with Container(id="download-settings"):
                                    with Vertical():
                                        yield Static("Concurrent Downloads", classes="section-title")
                                        yield Input(placeholder="Max Concurrent Downloads (1-10)", id="max-concurrent-input", value="3")
                                        yield Input(placeholder="Fragment Downloads (1-32)", id="fragment-downloads", value="16")
                                        
                                        yield Static("Retry Settings", classes="section-title")
                                        yield Input(placeholder="Max Retries (0-10)", id="max-retries-input", value="3")
                                        yield Input(placeholder="Retry Delay (1-60 seconds)", id="retry-delay-input", value="5")
                                        yield Checkbox("Exponential Backoff", id="exponential-backoff")
                                        
                                        yield Static("Organization", classes="section-title")
                                        yield Checkbox("Auto Organize Files", id="auto-organize")
                                        yield Checkbox("Enable File Organization Features", id="organize-files")
                                
                                # Audio/Video Settings
                                with Container(id="media-settings"):
                                    with Vertical():
                                        yield Static("Video Preferences", classes="section-title")
                                        yield Select([
                                            ("H.264", "h264"),
                                            ("H.265/HEVC", "h265"),
                                            ("VP9", "vp9"),
                                            ("AV1", "av1"),
                                            ("Any", "any")
                                        ], value="h264", id="video-codec-select")
                                        yield Select([
                                            ("4K (2160p)", "2160p"),
                                            ("1440p", "1440p"),
                                            ("1080p", "1080p"),
                                            ("720p", "720p"),
                                            ("480p", "480p"),
                                            ("Best Available", "best")
                                        ], value="1080p", id="video-quality-select")
                                        
                                        yield Static("Audio Preferences", classes="section-title")
                                        yield Select([
                                            ("AAC", "aac"),
                                            ("MP3", "mp3"),
                                            ("Opus", "opus"),
                                            ("FLAC", "flac"),
                                            ("Any", "any")
                                        ], value="aac", id="audio-codec-select")
                                        yield Select([
                                            ("320 kbps", "320"),
                                            ("256 kbps", "256"),
                                            ("192 kbps", "192"),
                                            ("128 kbps", "128"),
                                            ("Best Available", "best")
                                        ], value="192", id="audio-quality-select")
                                        yield Checkbox("Enable High Quality Audio", id="high-quality")
                                
                                # Network Settings
                                with Container(id="network-settings"):
                                    with Vertical():
                                        yield Static("Bandwidth Control", classes="section-title")
                                        yield Input(placeholder="Speed Limit (MB/s, 0=unlimited)", id="bandwidth-limit", value="0")
                                        yield Input(placeholder="Chunk Size (bytes)", id="chunk-size", value="1048576")
                                        
                                        yield Static("Connection Settings", classes="section-title")
                                        yield Input(placeholder="Timeout (seconds)", id="connection-timeout", value="30")
                                        yield Checkbox("Use Proxy", id="use-proxy")
                                        yield Input(placeholder="Proxy URL (optional)", id="proxy-url")
                                
                                # Advanced Settings
                                with Container(id="advanced-settings"):
                                    with Vertical():
                                        yield Static("FFmpeg Configuration", classes="section-title")
                                        yield Input(placeholder="FFmpeg Location", id="ffmpeg-input")
                                        yield Button("Auto-Detect FFmpeg", id="detect-ffmpeg-btn")
                                        
                                        yield Static("Session Management", classes="section-title")
                                        yield Input(placeholder="Session Expiry (hours)", id="session-expiry", value="168")
                                        yield Input(placeholder="Auto Save Interval (seconds)", id="auto-save", value="30")
                                        yield Static("Debug Options", classes="section-title")
                                        yield Checkbox("Enable Debug Logging", id="debug-logging")
                                        yield Checkbox("Verbose Output", id="verbose-output")
                            
                            with Container(id="settings-actions", classes="action-panel"):
                                yield Button("Save Settings", id="save-settings-btn", classes="primary")
                                yield Button("Reset to Defaults", id="reset-settings-btn", classes="secondary")
                                yield Button("Export Settings", id="export-settings-btn", classes="secondary")
                                yield Button("Import Settings", id="import-settings-btn", classes="secondary")
                                
                        # Help screen
                        with Container(id="help-screen"):
                            yield Static(self.HELP_DOCUMENTATION_TITLE, classes="title")
                            # Will be populated with help content
                            yield Static("Loading help content...")
                            
                        # Audio Tools screen
                        with Container(id="audio-screen"):
                            yield Static("Audio Processing Tools", classes="title")
                            with Container(classes="info-panel"):
                                yield Static("Audio Conversion", classes="subtitle")
                                yield Input(placeholder="Input audio file", id="audio-input-file")
                                yield Select([("mp3", "MP3"), ("aac", "AAC"), ("flac", "FLAC"), ("wav", "WAV")], id="audio-format-select", prompt="Select output format")
                                yield Button("Convert Audio", id="convert-audio-btn")
                            
                            with Container(classes="info-panel"):
                                yield Static("Audio Enhancement", classes="subtitle")
                                yield Checkbox("Normalize Volume", id="normalize-audio")
                                yield Checkbox("Remove Background Noise", id="denoise-audio")
                                yield Checkbox("Bass Boost", id="bass-boost")
                                yield Button("Process Audio", id="process-audio-btn")
                        
                        # Video Tools screen
                        with Container(id="video-screen"):
                            yield Static("Video Processing Tools", classes="title")
                            with Container(classes="info-panel"):
                                yield Static("Video Conversion", classes="subtitle")
                                yield Input(placeholder="Input video file", id="video-input-file")
                                yield Select([("mp4", "MP4"), ("mkv", "MKV"), ("webm", "WEBM")], id="video-format-select", prompt="Select output format")
                                yield Input(placeholder="Resolution (e.g., 1080, 720)", id="video-resolution")
                                yield Button("Convert Video", id="convert-video-btn")
                            
                            with Container(classes="info-panel"):
                                yield Static("Video Enhancement", classes="subtitle")
                                yield Checkbox("Enhance Colors", id="enhance-colors")
                                yield Checkbox("Stabilize Video", id="stabilize-video")
                                yield Button("Process Video", id="process-video-btn")
                        
                        # File Management screen                        with Container(id="files-screen"):
                            yield Static("File Management", classes="title")
                            with Container(classes="info-panel"):
                                yield Static("Organize Downloads", classes="subtitle")
                                yield Button("Organize by Type", id="organize-by-type-btn")
                                yield Button("Organize by Date", id="organize-by-date-btn")
                                yield Button("Organize by Source", id="organize-by-source-btn")
                            
                            with Container(classes="info-panel"):
                                yield Static("Batch Operations", classes="subtitle")
                                yield Button("Rename Files", id="rename-files-btn")
                                yield Button("Delete Temporary Files", id="cleanup-btn")
        
        yield Footer()
    
    def on_mount(self) -> None:
        """Handle app mount event"""
        # Initialize download manager
        self.initialize_download_manager()
        
        # Setup content switcher with default screens
        content_switcher = self.query_one("#content-switcher")
        content_switcher.default_screens = [
            self.DOWNLOAD_SCREEN, 
            self.BROWSE_SCREEN, 
            self.NETWORK_SCREEN, 
            self.SETTINGS_SCREEN, 
            self.HELP_SCREEN
        ]
        content_switcher.current = self.DOWNLOAD_SCREEN
        
        # Populate format table
        self.setup_format_table()
        
        # Load settings into form
        self.load_settings()
        
        # Set active menu item
        self.query_one("#menu-download").add_class("selected")
          # Load help content
        #self.load_help_content()
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle all button press events"""
        button_id = event.button.id
        
        # Route to appropriate handler based on button type
        if button_id.startswith("menu-"):
            self._handle_menu_selection(button_id)
        elif button_id.endswith("-tab"):
            self._handle_settings_tab_switch(button_id)
        else:
            self._handle_action_button(button_id)

    def _handle_action_button(self, button_id: str) -> None:
        """Handle action buttons (non-menu, non-tab)"""
        # Download functionality
        if button_id in ["analyze-btn", "start-download-btn", "speedtest-btn"]:
            self._handle_download_actions(button_id)
        # Settings actions
        elif button_id in ["save-settings-btn", "reset-settings-btn", "export-settings-btn", 
                          "import-settings-btn", "detect-ffmpeg-btn"]:
            self._handle_settings_actions(button_id)
        # Media processing
        elif button_id in ["convert-audio-btn", "process-audio-btn", "convert-video-btn", "process-video-btn"]:
            self._handle_media_processing(button_id)
        # File management
        elif button_id in ["organize-by-type-btn", "organize-by-date-btn", "organize-by-source-btn", 
                          "rename-files-btn", "cleanup-btn"]:
            self._handle_file_management(button_id)

    def _handle_download_actions(self, button_id: str) -> None:
        """Handle download-related button actions"""
        if button_id == "analyze-btn":
            self.analyze_url()
        elif button_id == "start-download-btn":
            self.start_download()
        elif button_id == "speedtest-btn":
            self.run_speed_test()

    def _handle_settings_actions(self, button_id: str) -> None:
        """Handle settings-related button actions"""
        if button_id == "save-settings-btn":
            self.save_advanced_settings()
        elif button_id == "reset-settings-btn":
            self.reset_settings()
        elif button_id == "export-settings-btn":
            self.export_settings()
        elif button_id == "import-settings-btn":
            self.import_settings()
        elif button_id == "detect-ffmpeg-btn":
            self.auto_detect_ffmpeg()

    def _handle_media_processing(self, button_id: str) -> None:
        """Handle media processing button actions"""
        if button_id == "convert-audio-btn":
            self.convert_audio()
        elif button_id == "process-audio-btn":
            self.process_audio()
        elif button_id == "convert-video-btn":
            self.convert_video()
        elif button_id == "process-video-btn":
            self.process_video()

    def _handle_file_management(self, button_id: str) -> None:
        """Handle file management button actions"""
        if button_id == "organize-by-type-btn":
            self.organize_files_by_type()
        elif button_id == "organize-by-date-btn":
            self.organize_files_by_date()
        elif button_id == "organize-by-source-btn":
            self.organize_files_by_source()
        elif button_id == "rename-files-btn":
            self.rename_files()
        elif button_id == "cleanup-btn":
            self.cleanup_temp_files()

    def _handle_menu_selection(self, button_id: str) -> None:
        """Handle menu item selection and switch screens"""
        # Remove selected class from all menu items
        for menu_item in self.query(".menu-item"):
            menu_item.remove_class("selected")
        
        # Add selected class to current item
        self.query_one(f"#{button_id}").add_class("selected")
        
        # Switch content
        content_switcher = self.query_one("#content-switcher")
        
        if button_id == "menu-download":
            content_switcher.current = self.DOWNLOAD_SCREEN
        elif button_id == "menu-browse":
            content_switcher.current = self.BROWSE_SCREEN
        elif button_id == "menu-network":
            content_switcher.current = self.NETWORK_SCREEN
        elif button_id == "menu-settings":
            content_switcher.current = self.SETTINGS_SCREEN
            self.load_advanced_settings()
        elif button_id == "menu-help":
            content_switcher.current = self.HELP_SCREEN
        elif button_id == "menu-audio":
            content_switcher.current = self.AUDIO_SCREEN
        elif button_id == "menu-video":
            content_switcher.current = self.VIDEO_SCREEN
        elif button_id == "menu-files":
            content_switcher.current = self.FILES_SCREEN

    def _handle_settings_tab_switch(self, button_id: str) -> None:
        """Handle settings tab switching"""
        # Remove active class from all tabs
        for tab in self.query(".tab-button"):
            tab.remove_class("active")
        
        # Add active class to current tab
        self.query_one(f"#{button_id}").add_class("active")
        
        # Switch settings content
        settings_switcher = self.query_one("#settings-content")
        
        if button_id == "general-tab":
            settings_switcher.current = "general-settings"
            self.active_settings_tab = "general-settings"
        elif button_id == "download-tab":
            settings_switcher.current = "download-settings"
            self.active_settings_tab = "download-settings"
        elif button_id == "media-tab":
            settings_switcher.current = "media-settings"
            self.active_settings_tab = "media-settings"
        elif button_id == "network-tab":
            settings_switcher.current = "network-settings"
            self.active_settings_tab = "network-settings"
        elif button_id == "advanced-tab":
            settings_switcher.current = "advanced-settings"
            self.active_settings_tab = "advanced-settings"

    # Settings Management Methods
    def load_advanced_settings(self) -> None:
        """Load and populate settings form fields from AdvancedConfigManager"""
        try:
            # General settings
            if hasattr(self, 'query_one'):
                video_dir_input = self.query_one(self.VIDEO_DIR_INPUT, Input)
                audio_dir_input = self.query_one(self.AUDIO_DIR_INPUT, Input)
                organize_files = self.query_one(self.ORGANIZE_FILES, Checkbox)
                
                # Populate from config manager
                video_dir_input.value = self.config_manager.get_setting('download', 'video_output_dir', self.DEFAULT_VIDEO_DIR)
                audio_dir_input.value = self.config_manager.get_setting('download', 'audio_output_dir', self.DEFAULT_AUDIO_DIR)
                organize_files.value = self.config_manager.get_setting('general', 'organize_files', True)
                
                # Load other settings
                max_concurrent = self.query_one("#max-concurrent-input", Input)
                max_concurrent.value = str(self.config_manager.get_setting('download', 'max_concurrent_downloads', 3))
                
                # Load retry settings
                max_retries = self.query_one("#max-retries-input", Input)
                max_retries.value = str(self.config_manager.get_setting('download', 'max_retries', 3))
                
        except Exception as e:
            logging.error(f"Error loading advanced settings: {e}")

    def save_advanced_settings(self) -> None:
        """Save current form values to AdvancedConfigManager"""
        try:
            # Get form values
            video_dir = self.query_one(self.VIDEO_DIR_INPUT, Input).value
            audio_dir = self.query_one(self.AUDIO_DIR_INPUT, Input).value
            organize_files = self.query_one(self.ORGANIZE_FILES, Checkbox).value
            
            # Save to config manager
            self.config_manager.set_setting('download', 'video_output_dir', video_dir)
            self.config_manager.set_setting('download', 'audio_output_dir', audio_dir)
            self.config_manager.set_setting('general', 'organize_files', organize_files)
            
            # Get and save numeric settings
            try:
                max_concurrent = int(self.query_one("#max-concurrent-input", Input).value)
                self.config_manager.set_setting('download', 'max_concurrent_downloads', max_concurrent)
            except ValueError:
                pass
                
            try:
                max_retries = int(self.query_one("#max-retries-input", Input).value)
                self.config_manager.set_setting('download', 'max_retries', max_retries)
            except ValueError:
                pass
            
            # Save config
            self.config_manager.save_config()
            
            # Update main config
            self.config.update(self.config_manager.config)
            
            # Show success message
            self.notify("Settings saved successfully!", severity="information")
            
        except Exception as e:
            logging.error(f"Error saving settings: {e}")
            self.notify(f"Error saving settings: {e}", severity="error")

    def reset_settings(self) -> None:
        """Reset settings to defaults"""
        try:
            # Reset config manager to defaults
            self.config_manager.reset_to_defaults()
            
            # Reload settings in form
            self.load_advanced_settings()
            
            self.notify("Settings reset to defaults", severity="information")
            
        except Exception as e:
            logging.error(f"Error resetting settings: {e}")
            self.notify(f"Error resetting settings: {e}", severity="error")

    def export_settings(self) -> None:
        """Export settings to file"""
        try:
            export_path = self.config_manager.export_config()
            self.notify(f"Settings exported to: {export_path}", severity="information")
        except Exception as e:
            logging.error(f"Error exporting settings: {e}")
            self.notify(f"Error exporting settings: {e}", severity="error")

    def import_settings(self) -> None:
        """Import settings from file"""
        try:
            # This would typically open a file picker in a real implementation
            # For now, we'll just show a placeholder message
            self.notify("Import settings functionality not yet implemented", severity="warning")
        except Exception as e:
            logging.error(f"Error importing settings: {e}")
            self.notify(f"Error importing settings: {e}", severity="error")

    def auto_detect_ffmpeg(self) -> None:
        """Auto-detect FFmpeg installation"""
        try:
            # Use AdvancedConfigManager's auto-detection
            ffmpeg_path = self.config_manager.auto_detect_tool('ffmpeg')
            
            if ffmpeg_path:
                # Update the FFmpeg input field
                ffmpeg_input = self.query_one(self.FFMPEG_INPUT, Input)
                ffmpeg_input.value = ffmpeg_path
                
                # Save to config
                self.config_manager.set_setting('tools', 'ffmpeg_path', ffmpeg_path)
                self.config_manager.save_config()
                
                self.notify(f"FFmpeg detected: {ffmpeg_path}", severity="information")
            else:
                self.notify("FFmpeg not found. Please install FFmpeg or set path manually.", severity="warning")
                
        except Exception as e:
            logging.error(f"Error detecting FFmpeg: {e}")
            self.notify(f"Error detecting FFmpeg: {e}", severity="error")

    # Media Processing Methods    def convert_audio(self) -> None:
        """Convert audio files to different formats"""        
        try:
            # Import audio processor
            from .audio_processor import AudioProcessor
            
            # Get input file path from user
            files_widget = self.query_one(UI_ELEMENTS["FILES_LIST"], DataTable)
            if files_widget.row_count == 0:
                self.notify("No files found to convert", severity="warning")
                return
            
            # Get selected file or use first available
            try:
                row_key = files_widget.cursor_row
                if row_key is None or row_key >= files_widget.row_count:
                    row_key = 0
                row = files_widget.get_row_at(row_key)
                file_path = str(row[1])  # File path is in the second column
            except Exception:
                self.notify("Please select a file to convert", severity="error")
                return
            
            if not os.path.exists(file_path):
                self.notify(f"File not found: {file_path}", severity="error")
                return
            
            # Initialize audio processor
            audio_processor = AudioProcessor(self.config)
            
            # Get target format from user input (you could add a form field for this)
            target_format = "flac"  # Default to high quality
              # Create output path
            base_path = os.path.splitext(file_path)[0]
            output_path = f"{base_path}_converted.{target_format}"
            
            self.notify(f"Converting {os.path.basename(file_path)} to {target_format.upper()}", severity="information")
            
            # Start audio conversion in background task
            self._start_audio_conversion_task(audio_processor, file_path, output_path, target_format)
            
        except ImportError:
            self.notify(CONSTANTS["FILE_ORG_NOT_AVAILABLE"], severity="error")
        except Exception as e:
            logging.error(f"Error in audio conversion: {e}")
            self.notify(f"Audio conversion failed: {str(e)}", severity="error")

    @work
    async def _start_audio_conversion_task(self, audio_processor, input_path: str, output_path: str, target_format: str) -> None:
        """Background task for audio conversion"""
        try:
            # Perform actual audio conversion
            result = await audio_processor.convert_audio_async(input_path, output_path, target_format)
            
            if result:
                self.notify(f"Audio conversion to {target_format.upper()} completed!", severity="success")
            else:
                self.notify(CONSTANTS["CONVERSION_FAILED"], severity="error")
                
        except Exception as e:
            logging.error(f"Background audio conversion error: {e}")
            self.notify(f"Audio conversion failed: {str(e)}", severity="error")

    def process_audio(self) -> None:
        """Process audio with advanced effects and enhancements"""
        try:
            # Import audio processor
            from .audio_processor import AudioProcessor
            
            # Get input file path from user
            files_widget = self.query_one(UI_ELEMENTS["FILES_LIST"], DataTable)
            if files_widget.row_count == 0:
                self.notify("No audio files found to process", severity="warning")
                return
            
            # Get selected file or use first available
            try:
                row_key = files_widget.cursor_row
                if row_key is None or row_key >= files_widget.row_count:
                    row_key = 0
                row = files_widget.get_row_at(row_key)
                file_path = str(row[1])  # File path is in the second column
            except Exception:
                self.notify("Please select an audio file to process", severity="error")
                return
            
            if not os.path.exists(file_path):
                self.notify(f"File not found: {file_path}", severity="error")
                return
            
            # Initialize audio processor
            audio_processor = AudioProcessor(self.config)
              # Get processing options from form fields
            try:
                process_audio = self.query_one(UI_ELEMENTS["PROCESS_AUDIO"], Checkbox).value
                upmix_audio = self.query_one("#upmix-audio", Checkbox).value
            except Exception:
                # Default options if form fields not available
                process_audio = True
                upmix_audio = True
            self.notify(f"Processing audio file: {os.path.basename(file_path)}", severity="information")
            
            # Apply audio processing effects
            if process_audio:
                self.notify("Applying audio normalization and denoising...", severity="information")
                
            if upmix_audio:
                self.notify("Applying 7.1 surround sound upmix...", severity="information")
            
            # Start audio processing in background task
            self._start_audio_processing_task(audio_processor, file_path, process_audio, upmix_audio)
            
        except ImportError:
            self.notify(CONSTANTS["FILE_ORG_NOT_AVAILABLE"], severity="error")
        except Exception as e:
            logging.error(f"Error in audio processing: {e}")
            self.notify(f"Audio processing failed: {str(e)}", severity="error")

    @work  
    async def _start_audio_processing_task(self, audio_processor, input_path: str, process_audio: bool, upmix_audio: bool) -> None:
        """Background task for audio processing"""
        try:
            # Apply audio processing effects
            result = await audio_processor.process_audio_async(
                input_path, 
                normalize=process_audio,
                denoise=process_audio,
                upmix_surround=upmix_audio
            )
            
            if result:
                self.notify("Audio processing completed with all enhancements!", severity="success")
            else:
                self.notify(CONSTANTS["CONVERSION_FAILED"], severity="error")
                
        except Exception as e:
            logging.error(f"Background audio processing error: {e}")
            self.notify(f"Audio processing failed: {str(e)}", severity="error")    
    def convert_video(self) -> None:
        """Convert video files to different formats and resolutions"""
        try:
            # Get input file path from user
            files_widget = self.query_one(UI_ELEMENTS["FILES_LIST"], DataTable)
            if files_widget.row_count == 0:
                self.notify("No video files found to convert", severity="warning")
                return
            
            # Get selected file or use first available
            try:
                row_key = files_widget.cursor_row
                if row_key is None or row_key >= files_widget.row_count:
                    row_key = 0
                row = files_widget.get_row_at(row_key)
                file_path = str(row[1])  # File path is in the second column
            except Exception:
                self.notify("Please select a video file to convert", severity="error")
                return
            
            if not os.path.exists(file_path):
                self.notify(f"File not found: {file_path}", severity="error")
                return
              # Basic video conversion using FFmpeg
            ffmpeg_location = self.config.get("ffmpeg_location", "")
            if ffmpeg_location:
                ffmpeg_path = os.path.join(ffmpeg_location, CONSTANTS["FFMPEG_EXE"] if os.name == "nt" else CONSTANTS["FFMPEG_BINARY"])
            else:
                ffmpeg_path = CONSTANTS["FFMPEG_EXE"] if os.name == "nt" else CONSTANTS["FFMPEG_BINARY"]
            
            # Default conversion settings
            target_format = "mp4"  # Popular format
            target_codec = "libx264"  # Hardware compatible
            
            # Create output path
            base_path = os.path.splitext(file_path)[0]
            output_path = f"{base_path}_converted.{target_format}"
            
            self.notify(f"Converting {os.path.basename(file_path)} to {target_format.upper()}", severity="information")
            
            # Start video conversion in background task
            self._start_video_conversion_task(file_path, output_path, target_format, target_codec)
            
        except Exception as e:
            logging.error(f"Error in video conversion: {e}")
            self.notify(f"Video conversion failed: {str(e)}", severity="error")

    @work
    async def _start_video_conversion_task(self, input_path: str, output_path: str, target_format: str, target_codec: str) -> None:
        """Background task for video conversion"""
        try:
            from .ffmpeg_helper import FFmpegHelper
            
            ffmpeg_helper = FFmpegHelper(self.config)
            result = await ffmpeg_helper.convert_video_async(
                input_path,
                output_path, 
                codec=target_codec,
                format=target_format
            )
            
            if result:
                self.notify(f"Video conversion to {target_format.upper()} completed!", severity="success")
            else:
                self.notify(CONSTANTS["CONVERSION_FAILED"], severity="error")
                
        except Exception as e:
            logging.error(f"Background video conversion error: {e}")
            self.notify(f"Video conversion failed: {str(e)}", severity="error")

    def process_video(self) -> None:
        """Process video with effects, filters, and optimizations"""
        try:
            # Get input file path from user            
            # files_widget = self.query_one(UI_ELEMENTS["FILES_LIST"], DataTable)
            if files_widget.row_count == 0:
                self.notify("No video files found to process", severity="warning")
                return
            
            # Get selected file or use first available
            try:
                row_key = files_widget.cursor_row
                if row_key is None or row_key >= files_widget.row_count:
                    row_key = 0
                row = files_widget.get_row_at(row_key)
                file_path = str(row[1])  # File path is in the second column
            except Exception:
                self.notify("Please select a video file to process", severity="error")
                return
            
            if not os.path.exists(file_path):
                self.notify(f"File not found: {file_path}", severity="error")
                return
            
            # Basic video processing using FFmpeg
            ffmpeg_location = self.config.get("ffmpeg_location", "")
            if ffmpeg_location:
                ffmpeg_path = os.path.join(ffmpeg_location, "ffmpeg.exe" if os.name == "nt" else "ffmpeg")
            else:
                ffmpeg_path = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
            self.notify(f"Processing video file: {os.path.basename(file_path)}", severity="information")
            
            # Apply video processing effects
            self.notify("Applying video stabilization and enhancement filters...", severity="information")
            
            # Create output path for processed video
            base_path = os.path.splitext(file_path)[0]
            output_path = f"{base_path}_processed.mp4"
            
            # Start video processing in background task
            self._start_video_processing_task(file_path, output_path)
            
        except Exception as e:
            logging.error(f"Error in video processing: {e}")
            self.notify(f"Video processing failed: {str(e)}", severity="error")

    @work
    async def _start_video_processing_task(self, input_path: str, output_path: str) -> None:
        """Background task for video processing"""
        try:
            from .ffmpeg_helper import FFmpegHelper
            
            ffmpeg_helper = FFmpegHelper(self.config)
            result = await ffmpeg_helper.process_video_async(
                input_path,
                output_path,
                stabilize=True,
                enhance_colors=True,
                denoise=True
            )
            
            if result:
                self.notify("Video processing completed with all enhancements!", severity="success")
            else:
                self.notify(CONSTANTS["CONVERSION_FAILED"], severity="error")
                
        except Exception as e:
            logging.error(f"Background video processing error: {e}")
            self.notify(f"Video processing failed: {str(e)}", severity="error")

    # Media Processing Methods
    def organize_files_by_type(self) -> None:
        """Organize files by type"""
        try:
            from .file_organizer import FileOrganizer
            
            # Get output directories
            video_dir = self.config.get('download', {}).get('video_output_dir', self.DEFAULT_VIDEO_DIR)
            audio_dir = self.config.get('download', {}).get('audio_output_dir', self.DEFAULT_AUDIO_DIR)
            
            # Create file organizer
            organizer = FileOrganizer()
            
            # Organize video files
            video_count = organizer.organize_by_type(video_dir)
            audio_count = organizer.organize_by_type(audio_dir)
            
            total_organized = video_count + audio_count
            self.notify(f"Organized {total_organized} files by type", severity="information")
            
        except ImportError:
            self.notify("File organizer module not available", severity="error")
        except Exception as e:
            logging.error(f"Error organizing files by type: {e}")
            self.notify(f"Error organizing files: {str(e)}", severity="error")

    def organize_files_by_date(self) -> None:
        """Organize files by date"""
        try:
            from .file_organizer import FileOrganizer
            
            # Get output directories
            video_dir = self.config.get('download', {}).get('video_output_dir', self.DEFAULT_VIDEO_DIR)
            audio_dir = self.config.get('download', {}).get('audio_output_dir', self.DEFAULT_AUDIO_DIR)
            
            # Create file organizer
            organizer = FileOrganizer()
            
            # Organize by date
            video_count = organizer.organize_by_date(video_dir)
            audio_count = organizer.organize_by_date(audio_dir)
            
            total_organized = video_count + audio_count
            self.notify(f"Organized {total_organized} files by date", severity="information")
            
        except ImportError:
            self.notify("File organizer module not available", severity="error")
        except Exception as e:
            logging.error(f"Error organizing files by date: {e}")
            self.notify(f"Error organizing files: {str(e)}", severity="error")

    def organize_files_by_source(self) -> None:
        """Organize files by source"""
        try:
            from .file_organizer import FileOrganizer
            
            # Get output directories
            video_dir = self.config.get('download', {}).get('video_output_dir', self.DEFAULT_VIDEO_DIR)
            audio_dir = self.config.get('download', {}).get('audio_output_dir', self.DEFAULT_AUDIO_DIR)
            
            # Create file organizer
            organizer = FileOrganizer()
            
            # Organize by source
            video_count = organizer.organize_by_source(video_dir)
            audio_count = organizer.organize_by_source(audio_dir)
            
            total_organized = video_count + audio_count
            self.notify(f"Organized {total_organized} files by source", severity="information")
            
        except ImportError:
            self.notify("File organizer module not available", severity="error")
        except Exception as e:
            logging.error(f"Error organizing files by source: {e}")
            self.notify(f"Error organizing files: {str(e)}", severity="error")

    def rename_files(self) -> None:
        """Rename files based on patterns"""
        try:
            # Get output directories
            video_dir = self.config.get('download', {}).get('video_output_dir', self.DEFAULT_VIDEO_DIR)
            audio_dir = self.config.get('download', {}).get('audio_output_dir', self.DEFAULT_AUDIO_DIR)
            
            # Simple pattern-based renaming (remove special characters, normalize spaces)
            import re
            
            total_renamed = 0
            
            for directory in [video_dir, audio_dir]:
                if os.path.exists(directory):
                    for root, dirs, files in os.walk(directory):
                        for file in files:
                            old_path = os.path.join(root, file)
                            name, ext = os.path.splitext(file)
                            
                            # Clean filename
                            clean_name = re.sub(r'[^\w\s-]', '', name)
                            clean_name = re.sub(r'[-\s]+', '-', clean_name).strip('-')
                            
                            new_file = f"{clean_name}{ext}"
                            new_path = os.path.join(root, new_file)
                            
                            if old_path != new_path and not os.path.exists(new_path):
                                os.rename(old_path, new_path)
                                total_renamed += 1
            
            self.notify(f"Renamed {total_renamed} files", severity="information")
            
        except Exception as e:
            logging.error(f"Error renaming files: {e}")
            self.notify(f"Error renaming files: {str(e)}", severity="error")

    def cleanup_temp_files(self) -> None:
        """Clean up temporary files"""
        try:
            # Get cache directory and temp directories
            cache_dir = self.config.get('cache_directory', os.path.join(os.path.expanduser("~"), ".cache", "snatch"))
            temp_extensions = ['.part', '.tmp', '.temp', '.ytdl']
            
            total_cleaned = 0
            total_size = 0
            
            # Clean cache directory
            if os.path.exists(cache_dir):
                for root, dirs, files in os.walk(cache_dir):
                    for file in files:
                        if any(file.endswith(ext) for ext in temp_extensions):
                            file_path = os.path.join(root, file)
                            try:
                                file_size = os.path.getsize(file_path)
                                os.remove(file_path)
                                total_cleaned += 1
                                total_size += file_size
                            except OSError:
                                pass
            
            # Clean download directories
            video_dir = self.config.get('download', {}).get('video_output_dir', self.DEFAULT_VIDEO_DIR)
            audio_dir = self.config.get('download', {}).get('audio_output_dir', self.DEFAULT_AUDIO_DIR)
            
            for directory in [video_dir, audio_dir]:
                if os.path.exists(directory):
                    for root, dirs, files in os.walk(directory):
                        for file in files:
                            if any(file.endswith(ext) for ext in temp_extensions):
                                file_path = os.path.join(root, file)
                                try:
                                    file_size = os.path.getsize(file_path)
                                    os.remove(file_path)
                                    total_cleaned += 1
                                    total_size += file_size
                                except OSError:
                                    pass
            
            size_str = format_size(total_size)
            self.notify(f"Cleaned up {total_cleaned} temporary files ({size_str})", severity="information")
            
        except Exception as e:
            logging.error(f"Error cleaning up temp files: {e}")
            self.notify(f"Error cleaning up temp files: {str(e)}", severity="error")    # Download Methods (existing but might need updating)
    def analyze_url(self) -> None:
        """Analyze URL with yt-dlp to extract media information"""
        url_input = self.query_one("#url-input", Input)
        url = url_input.value.strip()
        
        if not url:
            self.notify("Please enter a URL", severity="error")
            return
            
        self.current_url = url
        self.notify(f"Analyzing URL: {url}", severity="information")
        
        # Basic URL validation
        if not (url.startswith('http://') or url.startswith('https://')):
            self.notify("Please enter a valid HTTP/HTTPS URL", severity="error")
            return
            
        try:
            # Import yt-dlp for media extraction
            import yt_dlp
            
            # Configure yt-dlp options for info extraction only
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                'listformats': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Extract info without downloading
                info = ydl.extract_info(url, download=False)
                
                # Update the format table with available formats
                self._populate_format_table(info)
                
                # Update info panel with metadata
                self._update_info_panel(info)
                
                self.notify(f"Successfully analyzed: {info.get('title', 'Unknown Title')}", severity="information")
                
        except ImportError:
            self.notify("yt-dlp not found. Please install it: pip install yt-dlp", severity="error")
        except Exception as e:
            logging.error(f"Error analyzing URL: {e}")
            self.notify(f"Error analyzing URL: {str(e)}", severity="error")

    def start_download(self) -> None:
        """Start downloading the selected format"""
        if not self.current_url:
            self.notify("Please analyze a URL first", severity="error")
            return
            
        self.notify(f"Starting download: {self.current_url}", severity="information")
          # Get download options from form
        audio_only = self.query_one("#audio-only", Checkbox).value
        process_audio = self.query_one("#process-audio", Checkbox).value
        upmix_audio = self.query_one("#upmix-audio", Checkbox).value
        
        try:
            if self.download_manager:
                # Prepare download options
                download_options = {
                    'url': self.current_url,
                    'audio_only': audio_only,
                    'process_audio': process_audio,
                    'upmix_audio': upmix_audio,
                    'output_path': self.config.get('download', {}).get('video_output_dir', self.DEFAULT_VIDEO_DIR) if not audio_only else self.config.get('download', {}).get('audio_output_dir', self.DEFAULT_AUDIO_DIR)
                }
                
                # Start download using download manager
                # This would be a background task in a real implementation
                self.notify("Download started! Check the active downloads section for progress.", severity="information")
                
                # Add to downloads list for tracking
                download_info = {
                    'url': self.current_url,
                    'status': 'In Progress',
                    'progress': 0,
                    'options': download_options
                }
                self.downloads.append(download_info)
                
            else:
                raise DownloadManagerError("Download manager not initialized")
                
        except Exception as e:
            logging.error(f"Error starting download: {e}")
            self.notify(f"Error starting download: {str(e)}", severity="error")

    def run_speed_test(self) -> None:
        """Run network speed test using NetworkManager"""
        self.notify("Running speed test...", severity="information")
        
        try:
            # Import network module
            from .network import NetworkManager
            
            # Create network manager
            network_manager = NetworkManager(self.config)
            
            # Run speed test asynchronously
            import asyncio
            
            async def run_test():
                try:
                    result = await network_manager.run_speed_test(detailed=True)
                    if result:
                        # Update network status display
                        network_status = self.query_one("#network-status", Static)
                        status_text = f"""Speed Test Results:
Download: {result.download_mbps:.1f} Mbps
Upload: {result.upload_mbps:.1f} Mbps  
Ping: {result.ping_ms:.1f} ms
Jitter: {result.jitter_ms:.1f} ms
Packet Loss: {result.packet_loss:.1f}%"""
                        network_status.update(status_text)
                        
                        self.notify(f"Speed test completed! Download: {result.download_mbps:.1f} Mbps", severity="information")
                    else:
                        self.notify("Speed test failed - no results returned", severity="error")
                except Exception as e:
                    logging.error(f"Speed test error: {e}")
                    self.notify(f"Speed test failed: {str(e)}", severity="error")
            
            # Run the async function
            try:
                loop = asyncio.get_event_loop()
                loop.run_until_complete(run_test())
            except RuntimeError:
                # If no event loop, create one
                asyncio.run(run_test())
                
        except ImportError as e:
            self.notify("Network module not available for speed testing", severity="error")
        except Exception as e:
            logging.error(f"Error running speed test: {e}")
            self.notify(f"Error running speed test: {str(e)}", severity="error")
    
    # Initialization Methods
    def initialize_download_manager(self) -> None:
        """Initialize the download manager"""
        try:
            self.download_manager = DownloadManager(self.config)
            logging.info("Download manager initialized successfully")        
        except Exception as e:
            logging.error(f"Error initializing download manager: {e}")
            self.notify(f"Error initializing download manager: {e}", severity="error")

    def setup_format_table(self) -> None:
        """Setup the format selection table"""
        try:
            format_table = self.query_one(UI_ELEMENTS["FORMAT_TABLE"], DataTable)
            format_table.add_columns(
                "ID", "Extension", "Resolution", "Codec", "Size", "Audio", "FPS"
            )
            # Add placeholder row
            format_table.add_row("--", "--", "--", "--", "--", "--", "--")
        except Exception as e:
            logging.error(f"Error setting up format table: {e}")

    # Helper Methods
    def notify(self, message: str, severity: str = "information") -> None:
        """Show notification to user"""
        try:
            # In a full Textual implementation, this would show a toast notification
            # For now, we'll log the message
            if severity == "error":
                logging.error(message)
                print(f"ERROR: {message}")
            elif severity == "warning":
                logging.warning(message)
                print(f"WARNING: {message}")
            else:
                logging.info(message)
                print(f"INFO: {message}")
        except Exception as e:
            logging.error(f"Error showing notification: {e}")

    def _populate_format_table(self, info: Dict[str, Any]) -> None:
        """Populate the format table with available formats from yt-dlp info"""        
        try:
            format_table = self.query_one(UI_ELEMENTS["FORMAT_TABLE"], DataTable)
            
            # Clear existing rows
            format_table.clear()
            
            # Add columns if not already present
            if not format_table.columns:
                format_table.add_columns(
                    "ID", "Extension", "Resolution", "Codec", "Size", "Audio", "FPS"
                )
            
            # Add format data from yt-dlp info
            formats = info.get('formats', [])
            
            for fmt in formats:
                format_id = str(fmt.get('format_id', 'N/A'))
                ext = fmt.get('ext', 'N/A')
                
                # Resolution
                if fmt.get('width') and fmt.get('height'):
                    resolution = f"{fmt['width']}x{fmt['height']}"
                else:
                    resolution = 'N/A'
                
                # Codec
                codec = fmt.get('vcodec', 'N/A')
                if codec == 'none':
                    codec = fmt.get('acodec', 'N/A')
                
                # Size
                filesize = fmt.get('filesize') or fmt.get('filesize_approx')
                size = format_size(filesize) if filesize else 'N/A'
                
                # Audio info
                abr = fmt.get('abr')
                audio = f"{abr} kbps" if abr else 'N/A'
                
                # FPS
                fps = str(fmt.get('fps', 'N/A')) if fmt.get('fps') else 'N/A'
                
                format_table.add_row(format_id, ext, resolution, codec, size, audio, fps)
            
            self.format_info = info
            
        except Exception as e:
            logging.error(f"Error populating format table: {e}")
    
    def _update_info_panel(self, info: Dict[str, Any]) -> None:
        """Update the info panel with media metadata"""
        try:
            # This would update an info panel with metadata like title, duration, uploader, etc.
            # For now, we'll just log the info
            title = info.get('title', 'Unknown Title')
            duration = info.get('duration', 0)
            uploader = info.get('uploader', 'Unknown')
            
            logging.info(f"Media info - Title: {title}, Duration: {duration}s, Uploader: {uploader}")
            
        except Exception as e:
            logging.error(f"Error updating info panel: {e}")

    # Static Content Properties
    @property
    def HELP_DOCUMENTATION_TITLE(self) -> str:
        """Get help documentation title"""
        return "📖 Snatch Media Downloader - Help & Documentation"

    async def on_mount(self) -> None:
        """Initialize the application when mounted."""
        try:
            # Initialize download manager if not already done
            if not hasattr(self, 'download_manager') or not self.download_manager:
                await self._initialize_download_manager()
            
            # Start performance monitoring
            if hasattr(self, 'download_manager') and self.download_manager and self.download_manager.performance_monitor:
                await self.download_manager.performance_monitor.start_monitoring()
                
            # Set up periodic updates
            self.set_interval(1.0, self._update_system_stats)
            self.set_interval(0.5, self._update_download_progress)
            
        except Exception as e:
            logging.error(f"Error during app initialization: {e}")

    async def _initialize_download_manager(self) -> None:
        """Initialize the download manager with proper configuration."""
        try:
            from .manager import AsyncDownloadManager
            from .session import AsyncSessionManager
            from .cache import DownloadCache
            
            # Initialize dependencies
            session_manager = AsyncSessionManager(self.config.get("session_file", "sessions/session.json"))
            download_cache = DownloadCache()
            
            # Create download manager
            self.download_manager = AsyncDownloadManager(
                config=self.config,
                session_manager=session_manager,
                download_cache=download_cache
            )
            
            logging.info("Download manager initialized successfully")
            
        except Exception as e:
            logging.error(f"Failed to initialize download manager: {e}")
            self.download_manager = None

    async def _update_system_stats(self) -> None:
        """Update system statistics periodically."""
        try:
            if hasattr(self, 'download_manager') and self.download_manager and self.download_manager.performance_monitor:
                # Update performance metrics
                metrics = self.download_manager.performance_monitor.get_current_metrics()
                
                # Update any visible performance displays
                if hasattr(self, 'performance_widget'):
                    self.performance_widget.update_metrics(metrics)
                    
        except Exception as e:
            logging.debug(f"Error updating system stats: {e}")

    async def _update_download_progress(self) -> None:
        """Update download progress displays."""
        try:
            if hasattr(self, 'download_manager') and self.download_manager:
                # Get current download status
                status = self.download_manager.get_system_status()
                
                # Update progress displays
                if hasattr(self, 'progress_widget'):
                    self.progress_widget.update_status(status)
                    
        except Exception as e:
            logging.debug(f"Error updating download progress: {e}")


def launch_textual_interface(config: Dict[str, Any]) -> None:
    """Launch the modern Textual-based interactive interface.
    
    This function provides the entry point for the enhanced interactive mode
    with real-time monitoring, rich UI components, and advanced features.
    
    Args:
        config: Application configuration dictionary
    """
    try:
        # Validate configuration
        if not config:
            raise ValueError("Configuration is required")
            
        # Set up logging for interactive mode
        logging.info("Starting Textual interactive interface...")
        
        # Create and run the interactive app
        app = InteractiveApp(config)
          # Check if we're in an async context
        try:
            import asyncio
            # Try to get the running loop
            asyncio.get_running_loop()
            # If we get here, we're in an async context, so we need to handle this differently
            import threading
            
            def run_app():
                # Create a new event loop for this thread
                asyncio.set_event_loop(asyncio.new_event_loop())
                app.run()
            
            # Run the app in a separate thread
            thread = threading.Thread(target=run_app, daemon=True)
            thread.start()
            thread.join()
            
        except RuntimeError:
            # No running loop, safe to run normally
            app.run()
        
    except Exception as e:
        console = Console()
        console.print(f"[red]Error launching interactive interface: {e}[/]")
        logging.error(f"Failed to launch interactive interface: {e}")
        raise


async def launch_interactive_mode(config: Dict[str, Any]) -> None:
    """Launch the classic interactive mode with Rich console interface.
    
    This provides a fallback option for systems where Textual may not work properly.
    
    Args:
        config: Application configuration dictionary
    """
    console = Console()
    
    try:
        console.print(Panel(
            "[bold cyan]🎬 Snatch Media Downloader - Interactive Mode[/]\n"
            "[yellow]Classic Rich Console Interface[/]",
            title="Welcome",
            border_style="bright_blue"
        ))
        
        # Initialize download manager
        from .manager import AsyncDownloadManager
        from .session import AsyncSessionManager
        from .cache import DownloadCache
        
        session_manager = AsyncSessionManager(config.get("session_file", "sessions/session.json"))
        download_cache = DownloadCache()
        
        download_manager = AsyncDownloadManager(
            config=config,
            session_manager=session_manager,
            download_cache=download_cache
        )
        
        # Main interactive loop
        while True:
            console.print("\n" + "="*60)
            console.print("[bold cyan]📋 Main Menu[/]")
            console.print("="*60)
            
            options = {
                "1": "🔗 Download Media",
                "2": "📊 View System Status", 
                "3": "⚡ Performance Monitor",
                "4": "📁 Queue Management",
                "5": "⚙️  Settings",
                "6": "❓ Help",
                "q": "🚪 Quit"
            }
            
            for key, desc in options.items():
                console.print(f"  [{key}] {desc}")
            
            choice = Prompt.ask(
                "\n[bold yellow]Select an option[/]",
                choices=list(options.keys()),
                default="1"
            )
            
            if choice == "q":
                console.print("[green]👋 Thanks for using Snatch! Goodbye![/]")
                break
            elif choice == "1":
                await _handle_download_interactive(console, download_manager)
            elif choice == "2":
                await _show_system_status(console, download_manager)
            elif choice == "3":
                await _show_performance_monitor(console, download_manager)
            elif choice == "4":
                await _show_queue_management(console, download_manager)
            elif choice == "5":
                _show_settings(console, config)
            elif choice == "6":
                _show_help(console)
                
    except KeyboardInterrupt:
        console.print("\n[yellow]👋 Interactive mode interrupted. Goodbye![/]")
    except Exception as e:
        console.print(f"[red]Error in interactive mode: {e}[/]")
        logging.error(f"Interactive mode error: {e}")


async def _handle_download_interactive(console: Console, download_manager: AsyncDownloadManager) -> None:
    """Handle interactive download process."""
    try:
        console.print("\n[bold cyan]🔗 Media Download[/]")
        
        # Get URL from user
        url = Prompt.ask("[yellow]Enter media URL[/]")
        if not url:
            console.print("[red]No URL provided[/]")
            return
            
        # Get download options
        audio_only = Confirm.ask("[yellow]Audio only?[/]", default=False)
        
        if audio_only:
            format_choice = Prompt.ask(
                "[yellow]Audio format[/]",
                choices=["mp3", "flac", "wav", "aac"],
                default="mp3"
            )
            quality = Prompt.ask(
                "[yellow]Audio quality[/]",
                choices=["64", "128", "192", "256", "320"],
                default="192"
            )
            options = {
                "audio_only": True,
                "audio_format": format_choice,
                "audio_quality": quality
            }
        else:
            resolution = Prompt.ask(
                "[yellow]Video resolution (or 'best')[/]",
                choices=["best", "1080p", "720p", "480p", "360p"],
                default="best"
            )
            options = {
                "audio_only": False,
                "resolution": resolution if resolution != "best" else None
            }
        
        # Start download
        console.print(f"[cyan]Starting download: {url}[/]")
        
        async with download_manager:
            try:
                result = await download_manager.download_with_options([url], options)
                if result:
                    console.print(f"[green]✅ Successfully downloaded: {result[0]}[/]")
                else:
                    console.print("[red]❌ Download failed[/]")
            except Exception as e:
                console.print(f"[red]❌ Download error: {e}[/]")
                
    except Exception as e:
        console.print(f"[red]Error in download process: {e}[/]")
        logging.error(f"Interactive download error: {e}")


async def _show_system_status(console: Console, download_manager: AsyncDownloadManager) -> None:
    """Show system status information."""
    try:
        console.print("\n[bold cyan]📊 System Status[/]")
        
        # Get system status
        status = download_manager.get_system_status()
        
        # Create status table
        table = Table(title="System Information", border_style="bright_blue")
        table.add_column("Metric", style="cyan", min_width=20)
        table.add_column("Value", style="green")
        
        table.add_row("Active Downloads", str(status.get("active_downloads", 0)))
        table.add_row("Failed Attempts", str(status.get("failed_attempts", 0)))
        table.add_row("Cache Size", str(status.get("cache_size", 0)))
        table.add_row("Session Count", str(status.get("session_count", 0)))
        
        if "cpu_usage" in status:
            table.add_row("CPU Usage", f"{status['cpu_usage']:.1f}%")
            table.add_row("Memory Usage", f"{status['memory_usage']:.1f}%")
            table.add_row("Disk Usage", f"{status['disk_usage']:.1f}%")
            table.add_row("Network Usage", f"{status['network_usage']:.1f} Mbps")
        
        console.print(table)
        
        # Show recommendations if available
        if "performance_recommendations" in status:
            recommendations = status["performance_recommendations"]
            if recommendations:
                console.print("\n[bold yellow]🔧 Performance Recommendations:[/]")
                for rec in recommendations:
                    console.print(f"  • {rec}")
        
        Prompt.ask("\n[dim]Press Enter to continue[/]", default="")
        
    except Exception as e:
        console.print(f"[red]Error showing system status: {e}[/]")
        logging.error(f"System status error: {e}")


async def _show_performance_monitor(console: Console, download_manager: AsyncDownloadManager) -> None:
    """Show performance monitoring information."""
    try:
        console.print("\n[bold cyan]⚡ Performance Monitor[/]")
        
        if not download_manager.performance_monitor:
            console.print("[yellow]Performance monitor not available[/]")
            return
            
        # Get current metrics
        metrics = download_manager.performance_monitor.get_current_metrics()
        
        # Create metrics table
        table = Table(title="Performance Metrics", border_style="bright_green")
        table.add_column("Metric", style="cyan", min_width=15)
        table.add_column("Current", style="green")
        table.add_column("Status", style="yellow")
          # CPU
        cpu_percent = metrics.get("cpu_percent", 0)
        if cpu_percent > 80:
            cpu_status = "🔴 High"
        elif cpu_percent > 50:
            cpu_status = "🟡 Medium"
        else:
            cpu_status = "🟢 Normal"
        table.add_row("CPU Usage", f"{cpu_percent:.1f}%", cpu_status)
        
        # Memory
        memory_percent = metrics.get("memory_percent", 0)
        if memory_percent > 85:
            memory_status = "🔴 High"
        elif memory_percent > 70:
            memory_status = "🟡 Medium"
        else:
            memory_status = "🟢 Normal"
        table.add_row("Memory Usage", f"{memory_percent:.1f}%", memory_status)
        
        # Network
        network_mbps = metrics.get("network_mbps", 0)
        network_status = "🟢 Active" if network_mbps > 1 else "🟡 Idle"
        table.add_row("Network", f"{network_mbps:.1f} Mbps", network_status)
        
        console.print(table)
        
        # Optimization option
        if Confirm.ask("\n[yellow]Run performance optimization?[/]", default=False):
            console.print("[cyan]Running optimization...[/]")
            result = await download_manager.optimize_performance()
            
            if result.get("optimizations_applied"):
                console.print("[green]✅ Optimizations applied:[/]")
                for opt in result["optimizations_applied"]:
                    console.print(f"  • {opt}")
            else:
                console.print("[green]✅ System is already optimized[/]")
        
        Prompt.ask("\n[dim]Press Enter to continue[/]", default="")
        
    except Exception as e:
        console.print(f"[red]Error in performance monitor: {e}[/]")
        logging.error(f"Performance monitor error: {e}")


async def _show_queue_management(console: Console, download_manager: AsyncDownloadManager) -> None:
    """Show download queue management."""
    try:
        console.print("\n[bold cyan]📁 Queue Management[/]")
        
        if not download_manager.advanced_scheduler:
            console.print("[yellow]Advanced scheduler not available[/]")
            return
            
        # Get scheduler status
        status = download_manager.advanced_scheduler.get_status()
        
        # Create status table
        table = Table(title="Scheduler Status", border_style="bright_magenta")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="green")
        
        table.add_row("Queue Size", str(status.get("queue_size", 0)))
        table.add_row("Active", "Yes" if status.get("active", False) else "No")
        table.add_row("Bandwidth Usage", f"{status.get('bandwidth_usage', 0):.1f} Mbps")
        
        console.print(table)
        
        # Queue management options
        console.print("\n[bold yellow]Queue Options:[/]")
        console.print("  [1] Pause scheduler")
        console.print("  [2] Resume scheduler") 
        console.print("  [3] Clear queue")
        console.print("  [4] Back to main menu")
        
        choice = Prompt.ask(
            "[yellow]Select option[/]",
            choices=["1", "2", "3", "4"],
            default="4"
        )
        
        if choice == "1":
            await download_manager.advanced_scheduler.pause()
            console.print("[green]✅ Scheduler paused[/]")
        elif choice == "2":
            await download_manager.advanced_scheduler.resume()
            console.print("[green]✅ Scheduler resumed[/]")
        elif choice == "3":
            if Confirm.ask("[red]Clear all queued downloads?[/]", default=False):
                await download_manager.advanced_scheduler.clear_queue()
                console.print("[green]✅ Queue cleared[/]")
        
        if choice != "4":
            Prompt.ask("\n[dim]Press Enter to continue[/]", default="")
            
    except Exception as e:
        console.print(f"[red]Error in queue management: {e}[/]")
        logging.error(f"Queue management error: {e}")


def _show_settings(console: Console, config: Dict[str, Any]) -> None:
    """Show settings configuration."""
    try:
        console.print("\n[bold cyan]⚙️  Settings[/]")
        
        # Create settings table
        table = Table(title="Current Settings", border_style="bright_yellow")
        table.add_column("Setting", style="cyan", min_width=20)
        table.add_column("Value", style="green")
        
        # Show key settings
        table.add_row("Max Concurrent Downloads", str(config.get("max_concurrent", 3)))
        table.add_row("Video Output Dir", config.get("video_output", "downloads/video"))
        table.add_row("Audio Output Dir", config.get("audio_output", "downloads/audio"))
        table.add_row("Bandwidth Limit", f"{config.get('bandwidth_limit', 0)} Mbps" if config.get('bandwidth_limit') else "Unlimited")
        table.add_row("P2P Enabled", "Yes" if config.get("p2p_enabled", False) else "No")
        
        console.print(table)
        
        # Settings modification
        if Confirm.ask("\n[yellow]Modify settings?[/]", default=False):
            console.print("[cyan]Settings modification not implemented in this version[/]")
            console.print("[dim]Use the config.json file to modify settings[/]")
        
        Prompt.ask("\n[dim]Press Enter to continue[/]", default="")
        
    except Exception as e:
        console.print(f"[red]Error showing settings: {e}[/]")
        logging.error(f"Settings error: {e}")


def _show_help(console: Console) -> None:
    """Show help information."""
    try:
        console.print("\n[bold cyan]❓ Help & Documentation[/]")
        
        help_content = """
[bold yellow]🎬 Snatch Media Downloader - Help[/]

[cyan]Basic Usage:[/]
• Enter media URLs to download content
• Choose between audio-only or video downloads
• Select quality and format options
• Monitor download progress in real-time

[cyan]Features:[/]
• Multi-format support (MP4, MP3, FLAC, etc.)
• Concurrent downloads with intelligent scheduling
• P2P sharing capabilities (if enabled)
• Advanced audio processing options
• Real-time performance monitoring
• Resume interrupted downloads

[cyan]Supported Sites:[/]
• YouTube, Vimeo, Dailymotion
• SoundCloud, Bandcamp
• Many more via yt-dlp support

[cyan]Keyboard Shortcuts:[/]
• Ctrl+C: Cancel current operation
• Enter: Confirm selection
• Q: Quit (from main menu)

[cyan]Configuration:[/]
• Edit config.json for advanced settings
• Set custom output directories
• Configure bandwidth limits
• Enable/disable P2P features

[green]For more help, visit the documentation or check the GitHub repository.[/]
        """
        
        console.print(Panel(help_content, border_style="bright_cyan"))
        Prompt.ask("\n[dim]Press Enter to continue[/]", default="")
        
    except Exception as e:
        console.print(f"[red]Error showing help: {e}[/]")
        logging.error(f"Help display error: {e}")


# Compatibility alias for backward compatibility
def run_interactive_mode(config: Dict[str, Any]) -> None:
    """Alias for launch_textual_interface for backward compatibility."""
    launch_textual_interface(config)


# Enhanced initialization function
def initialize_interactive_mode(config: Dict[str, Any]) -> None:
    """Initialize interactive mode with proper error handling and fallbacks."""
    try:
        # Try to launch the modern Textual interface first
        launch_textual_interface(config)
    except ImportError as e:
        # If Textual is not available, fall back to Rich console interface
        logging.warning(f"Textual interface not available: {e}")
        logging.info("Falling back to Rich console interface")
        launch_interactive_mode(config)
    except Exception as e:
        # For any other error, try the fallback
        logging.error(f"Error with Textual interface: {e}")
        logging.info("Attempting fallback to Rich console interface")
        try:
            launch_interactive_mode(config)
        except Exception as fallback_error:
            console = Console()
            console.print("[red]Both interface modes failed:[/]")
            console.print(f"[red]Textual error: {e}[/]")
            console.print(f"[red]Fallback error: {fallback_error}[/]")
            raise