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
    HIGH_QUALITY = "#high-quality"
    
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
        width: 30;
        background: $surface;
        border-right: solid $primary;
    }
    
    #main-content {
        background: $background;
    }
    
    .title {
        background: $primary;
        color: $background;
        text-align: center;
        padding: 1;
        text-style: bold;
        width: 100%;
    }
    
    .menu-item {
        padding: 1 2;
        margin: 0 1;
    }
    
    .menu-item:hover {
        background: $primary-darken-1;
        color: $text;
    }
    
    .menu-item.selected {
        background: $primary;
        color: $text;
        text-style: bold;
    }
    
    .progress-bar {
        width: 100%;
        margin: 1 0;
    }
    
    .status-ok {
        color: $success;
    }
    
    .status-warning {
        color: $warning;
    }
    
    .status-error {
        color: $error;
    }
    
    .info-panel {
        margin: 1;
        height: auto;
        border: solid $primary-darken-2;
    }
    
    .format-table {
        width: 100%;
        height: auto;
    }
    
    DataTable {
        height: auto;
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
    
    # Form input ID constants
    VIDEO_DIR_INPUT = "#video-dir-input"
    AUDIO_DIR_INPUT = "#audio-dir-input"
    FFMPEG_INPUT = "#ffmpeg-input"
    ORGANIZE_FILES = "#organize-files"
    HIGH_QUALITY = "#high-quality"
    
    # Default paths
    DEFAULT_VIDEO_DIR = os.path.join(os.path.expanduser("~"), "Downloads", "video")
    DEFAULT_AUDIO_DIR = os.path.join(os.path.expanduser("~"), "Downloads", "audio")
    
    # Help content
    HELP_DOCUMENTATION_TITLE = "Help & Documentation"
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the interactive app with configuration"""
        super().__init__()
        self.config = config
        self.download_manager = None
        self.current_url = None        
        self.format_info = None
        self.downloads = []
        
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
                            with Vertical():
                                yield Static("Output Directories")
                                yield Input(placeholder="Video Output Directory", id="video-dir-input")
                                yield Input(placeholder="Audio Output Directory", id="audio-dir-input")
                                
                                yield Static("FFmpeg Settings")
                                yield Input(placeholder="FFmpeg Location", id="ffmpeg-input")
                                
                                yield Static("Advanced Options")
                                yield Checkbox("Organize Files", id="organize-files")
                                yield Checkbox("Enable High Quality Audio", id="high-quality")
                                
                                yield Button("Save Settings", id="save-settings-btn")
                                
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
                        
                        # File Management screen
                        with Container(id="files-screen"):
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
        self.load_help_content()
    def initialize_download_manager(self) -> None:
        """Initialize the download manager with config"""
        try:
            from .manager import AsyncDownloadManager
            from .session import AsyncSessionManager
            from .cache import DownloadCache
            
            # Create sessions directory if it doesn't exist
            session_file = self.config.get("session_file")
            if session_file:
                os.makedirs(os.path.dirname(session_file), exist_ok=True)
            
            # Create dependencies
            session_manager = AsyncSessionManager(session_file)
            download_cache = DownloadCache()
            
            # Create the download manager
            self.download_manager = AsyncDownloadManager(
                config=self.config,
                session_manager=session_manager,
                download_cache=download_cache
            )
            
            logging.info("Download manager initialized successfully")
        except Exception as e:
            logging.error(f"Failed to initialize download manager: {str(e)}")
            self.notify(f"Failed to initialize download manager: {str(e)}", severity="error")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events"""
        button_id = event.button.id
        
        # Menu navigation
        if button_id.startswith("menu-"):
            # Remove selected class from all menu items
            for item in self.query(".menu-item"):
                item.remove_class("selected")
                
            # Add selected class to clicked item
            event.button.add_class("selected")
            
            # Switch content based on menu selection
            menu_target = button_id.replace("menu-", "")
            target_screen = f"{menu_target}-screen"
            
            # Get the content switcher
            content_switcher = self.query_one("#content-switcher")
            
            # Check if the screen exists in default screens
            if target_screen in content_switcher.default_screens:
                content_switcher.current = target_screen
            else:
                self.notify(f"Screen {target_screen} not available", severity="warning")
        
        # Action buttons
        elif button_id == "analyze-btn":
            self.analyze_url()
        elif button_id == "start-download-btn":
            self.start_download()
        elif button_id == "speedtest-btn":
            self.run_speed_test()
        elif button_id == "save-settings-btn":
            self.save_settings()
    def setup_format_table(self) -> None:
        """Set up the format selection table"""
        table = self.query_one(self.FORMAT_TABLE_ID)
        table.cursor_type = "row"
        
        # Clear existing columns if any
        if hasattr(table, "clear"):
            table.clear()
        
        # Add detailed columns for better format selection
        table.add_columns(
            "ID", "Quality", "Resolution", "Codec", "Size", "Audio", "FPS"
        )
        
        # Make sure we have a download button
        if not self.query_one("#format-selection").query("#start-download-btn"):
            download_button = Button("Start Download", id="start-download-btn", variant="primary")
            self.query_one("#format-selection").mount(download_button)
        
    def load_help_content(self) -> None:
        """Load help content from defaults"""
        try:
            help_screen = self.query_one("#help-screen")
            help_screen.remove_children()
            help_screen.mount(Static("Help & Documentation", classes="title"))
            
            # Try to load help content from defaults
            from .defaults import HELP_CONTENT
            help_text = "\n\n".join(HELP_CONTENT.values())
            help_screen.mount(Static(help_text))
        except Exception as e:
            logging.error(f"Error loading help content: {str(e)}")
            help_screen = self.query_one("#help-screen")
            help_screen.remove_children()
            help_screen.mount(Static("Help & Documentation", classes="title"))
            help_screen.mount(Static("Error loading help content. Please check documentation."))
    def load_settings(self) -> None:
        """Load settings into form fields"""
        try:
            self.query_one(self.VIDEO_DIR_INPUT).value = self.config.get("video_output", self.DEFAULT_VIDEO_DIR)
            self.query_one(self.AUDIO_DIR_INPUT).value = self.config.get("audio_output", self.DEFAULT_AUDIO_DIR)
            self.query_one(self.FFMPEG_INPUT).value = self.config.get("ffmpeg_location", "")
            self.query_one(self.ORGANIZE_FILES).value = self.config.get("organize", False)
            self.query_one(self.HIGH_QUALITY).value = self.config.get("high_quality_audio", True)
        except Exception as e:
            logging.error(f"Error loading settings: {str(e)}")
            self.notify("Error loading settings", severity="error")
    def initialize_download_manager(self) -> None:
        """Initialize the download manager with current settings"""
        try:
            from .manager import AsyncDownloadManager
            self.download_manager = AsyncDownloadManager(self.config)
            logging.info("Download manager initialized successfully")
        except Exception as e:
            logging.error(f"Error initializing download manager: {str(e)}")
            self.notify(f"Error initializing core components: {str(e)}", severity="error")
            
    def save_settings(self) -> None:
        """Save user settings to config file"""
        try:
            # Get input values
            video_dir = self.query_one(self.VIDEO_DIR_INPUT).value
            audio_dir = self.query_one(self.AUDIO_DIR_INPUT).value
            ffmpeg_location = self.query_one(self.FFMPEG_INPUT).value
            organize_files = self.query_one(self.ORGANIZE_FILES).value
            high_quality = self.query_one(self.HIGH_QUALITY).value
            
            # Validate directories
            from .config_helpers import ensure_directory_exists, validate_ffmpeg_path
            
            # Check FFmpeg path
            is_valid_ffmpeg, actual_ffmpeg_path = validate_ffmpeg_path(ffmpeg_location)
            if not is_valid_ffmpeg:
                self.notify("FFmpeg path is invalid. Please check and try again.", severity="error")
                return
                
            # Ensure output directories exist or create them
            video_output = ensure_directory_exists(video_dir) if video_dir else self.DEFAULT_VIDEO_DIR
            audio_output = ensure_directory_exists(audio_dir) if audio_dir else self.DEFAULT_AUDIO_DIR
            
            if not video_output:
                self.notify("Could not create video directory. Using default path.", severity="warning")
                video_output = self.DEFAULT_VIDEO_DIR
                
            if not audio_output:
                self.notify("Could not create audio directory. Using default path.", severity="warning")
                audio_output = self.DEFAULT_AUDIO_DIR
            
            # Update config
            self.config.update({
                "video_output": video_output,
                "audio_output": audio_output,
                "ffmpeg_location": actual_ffmpeg_path or ffmpeg_location,
                "organize": organize_files,
                "high_quality_audio": high_quality
            })
            
            # Save to file
            config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")
            with open(config_path, "w") as f:
                json.dump(self.config, f, indent=2)
            
            self.notify("Settings saved successfully!", severity="success")
            
            # Reinitialize download manager with new settings
            self.initialize_download_manager()
        except Exception as e:
            logging.error(f"Error saving settings: {str(e)}")
            self.notify(f"Error saving settings: {str(e)}", severity="error")
    @work(thread=True)
    async def analyze_url(self) -> None:
        """Analyze URL and show available formats"""
        url_input = self.query_one("#url-input")
        url = url_input.value.strip()
        
        if not url:
            self.notify("Please enter a valid URL", severity="error")
            return
            
        # Update UI to show we're analyzing
        self.notify("Analyzing URL...", severity="info")
        
        try:
            # Clear previous formats
            table = self.query_one(self.FORMAT_TABLE_ID)
            table.clear()
            
            # Set up the table columns
            self.setup_format_table()
            
            # Analyze the URL using download manager
            self.current_url = url
            self.format_info = await self.download_manager.get_formats(url)
            
            if not self.format_info:
                self.notify("No formats found for this URL", severity="error")
                return
                
            # Add formats to the table
            formats = self.format_info.get("formats", [])
            
            # Sort formats by quality (highest first)
            formats.sort(key=lambda f: (
                f.get("height", 0) or 0, 
                f.get("fps", 0) or 0,
                f.get("tbr", 0) or 0
            ), reverse=True)
            
            # Filter out formats without video or audio
            video_formats = [f for f in formats if f.get("vcodec") != "none"]
            audio_formats = [f for f in formats if f.get("acodec") != "none"]
            
            # Add best video+audio formats first
            for fmt in video_formats[:10]:  # Limit to top 10 for better usability
                format_id = fmt.get("format_id", "unknown")
                quality = "HD" if fmt.get("height", 0) >= 720 else "SD"
                resolution = f"{fmt.get('width', '?')}x{fmt.get('height', '?')}"
                codec = fmt.get("vcodec", "unknown")
                filesize = format_size(fmt.get("filesize") or fmt.get("filesize_approx") or 0)
                audio_codec = fmt.get("acodec", "none")
                fps = fmt.get("fps", "N/A")
                
                # Add the row to the table
                table.add_row(
                    format_id, 
                    quality, 
                    resolution, 
                    codec, 
                    filesize,
                    audio_codec if audio_codec != "none" else "No audio",
                    str(fps) if fps else "N/A"
                )
            
            # Add audio-only formats
            for fmt in audio_formats[:5]:  # Limit to top 5 audio formats
                if fmt.get("vcodec") == "none":  # Audio only
                    format_id = fmt.get("format_id", "unknown")
                    quality = fmt.get("format_note", "Audio")
                    resolution = "Audio only"
                    codec = "N/A"
                    filesize = format_size(fmt.get("filesize") or fmt.get("filesize_approx") or 0)
                    audio_codec = fmt.get("acodec", "unknown")
                    
                    # Add the row to the table
                    table.add_row(
                        format_id, 
                        quality, 
                        resolution, 
                        codec, 
                        filesize,
                        audio_codec,
                        "N/A"
                    )
                
            # Select the first row by default
            if table.row_count > 0:
                table.cursor_row = 0
                
            # Show download button
            if not self.query_one("#main-content").query("#start-download-btn"):
                download_btn = Button("Start Download", id="start-download-btn", variant="primary")
                format_selection = self.query_one("#format-selection")
                format_selection.mount(download_btn)
                
            self.notify("URL analyzed successfully", severity="success")
        except asyncio.CancelledError:
            self.notify("URL analysis was cancelled", severity="warning")
        except Exception as e:
            logging.error(f"Error analyzing URL: {str(e)}")
            self.notify(f"Error analyzing URL: {str(e)}", severity="error")
                
            # Add formats to the table
            for fmt in formats:
                format_id = fmt.get("format_id", "N/A")
                quality = fmt.get("quality", "N/A")
                resolution = fmt.get("resolution", "N/A")
                codec = fmt.get("codec", "N/A")
                filesize = format_size(fmt.get("filesize", 0))
                audio_codec = fmt.get("acodec", "none")
                
                table.add_row(
                    format_id, 
                    str(quality), 
                    str(resolution), 
                    codec, 
                    filesize,
                    audio_codec if audio_codec != "none" else "No audio"
                )
                
            # Select the first row by default
            if table.row_count > 0:
                table.cursor_row = 0
                
            self.notify("URL analyzed successfully", severity="success")
        except Exception as e:
            logging.error(f"Error analyzing URL: {str(e)}")
            self.notify(f"Error analyzing URL: {str(e)}", severity="error")
    @work(thread=True)
    async def start_download(self) -> None:
        """Start downloading with selected format"""
        try:
            url_input = self.query_one("#url-input")
            url = url_input.value.strip()
            
            if not url:
                self.notify("Please enter a valid URL", severity="error")
                return
                
            # Get selected format
            format_id = self.get_selected_format()
            
            if not format_id:
                self.notify("No format selected, using best quality", severity="warning")
                format_id = "best"
                
            # Generate a download ID
            import uuid
            download_id = str(uuid.uuid4())
            
            # Add to active downloads
            self.add_active_download(download_id, url)
            
            # Create download options
            options = {
                "format": format_id,
                "audio_only": self.query_one("#audio-only").value if hasattr(self.query_one("#download-options"), "query") and self.query_one("#download-options").query("#audio-only") else False,
                "subtitles": self.query_one("#subtitles").value if hasattr(self.query_one("#download-options"), "query") and self.query_one("#download-options").query("#subtitles") else False,
                "download_id": download_id
            }
            
            # Start download
            self.notify(f"Starting download with format {format_id}...", severity="info")
            success = await self.download_manager.download(url, options)
            
            # Start progress update worker if not already running
            if not hasattr(self, "_progress_worker_running") or not self._progress_worker_running:
                self._progress_worker_running = True
                await self.update_download_progress()
                
            if success:
                self.notify(f"Download started successfully", severity="success")
            else:
                self.notify("Download could not be started", severity="error")
                
        except asyncio.CancelledError:
            self.notify("Download operation was cancelled", severity="warning")
            logging.info("Download operation cancelled by user or system")
        except Exception as e:
            logging.error(f"Error starting download: {str(e)}")
            self.notify(f"Error starting download: {str(e)}", severity="error")
    @work(thread=True)
    async def run_speed_test(self) -> None:
        """Run a network speed test"""
        button = self.query_one("#speedtest-btn")
        status = self.query_one("#network-status")
        stats_container = self.query_one("#network-stats")
        
        # Update UI
        button.disabled = True
        button.label = "Running Test..."
        status.update("Testing network speed...")
        
        try:
            # Create NetworkManager instance
            from .network import NetworkManager
            network_manager = NetworkManager(self.config)
            
            # Run speed test
            result = await network_manager.run_speed_test(detailed=True)
            
            if result:
                # Clear previous results
                stats_container.remove_children()
                stats_container.mount(Static("Network Status: Completed", id="network-status"))
                
                # Add result data
                download_class = "status-ok" if result.download_mbps > 5 else "status-warning" if result.download_mbps > 1 else "status-error"
                stats_container.mount(Static(f"Download: {result.download_mbps:.2f} Mbps", classes=download_class))
                
                upload_class = "status-ok" if result.upload_mbps > 2 else "status-warning" if result.upload_mbps > 0.5 else "status-error"
                stats_container.mount(Static(f"Upload: {result.upload_mbps:.2f} Mbps", classes=upload_class))
                
                ping_class = "status-ok" if result.ping_ms < 100 else "status-warning" if result.ping_ms < 200 else "status-error"
                stats_container.mount(Static(f"Ping: {result.ping_ms:.0f} ms", classes=ping_class))
                
                if hasattr(result, 'jitter_ms') and result.jitter_ms is not None:
                    jitter_class = "status-ok" if result.jitter_ms < 20 else "status-warning" if result.jitter_ms < 50 else "status-error"
                    stats_container.mount(Static(f"Jitter: {result.jitter_ms:.1f} ms", classes=jitter_class))
                    
                if hasattr(result, 'packet_loss') and result.packet_loss is not None:
                    loss_class = "status-ok" if result.packet_loss < 1 else "status-warning" if result.packet_loss < 5 else "status-error"
                    stats_container.mount(Static(f"Packet Loss: {result.packet_loss:.1f}%", classes=loss_class))
                
                # Overall rating
                overall_rating = "Good" if result.download_mbps > 10 and result.ping_ms < 100 else "Fair" if result.download_mbps > 3 else "Poor"
                rating_class = "status-ok" if overall_rating == "Good" else "status-warning" if overall_rating == "Fair" else "status-error"
                stats_container.mount(Static(f"Overall Rating: {overall_rating}", classes=rating_class))
                
                # Recommendations based on speed
                recommendations = []
                if result.download_mbps < 3:
                    recommendations.append("- Consider using lower quality video formats")
                    recommendations.append("- Audio-only downloads recommended")
                elif result.download_mbps < 10:
                    recommendations.append("- 720p video should work well")
                    recommendations.append("- 1080p may buffer occasionally")
                else:
                    recommendations.append("- 1080p or higher should work well")
                    recommendations.append("- 4K may be possible depending on stability")
                
                if recommendations:
                    stats_container.mount(Static("Recommendations:", classes="subtitle"))
                    for rec in recommendations:
                        stats_container.mount(Static(rec))
                
                self.notify("Network speed test completed", severity="success")
            else:
                stats_container.mount(Static("No results returned from speed test", classes="status-error"))
                self.notify("Speed test failed - no results", severity="error")
                
        except Exception as e:
            logging.error(f"Error running speed test: {str(e)}")
            stats_container.remove_children()
            stats_container.mount(Static("Network Status: Error", id="network-status", classes="status-error"))
            stats_container.mount(Static(f"Error: {str(e)}", classes="status-error"))
            self.notify(f"Speed test error: {str(e)}", severity="error")
        finally:
            # Reset button
            button.disabled = False
            button.label = "Run Speed Test"
        
        try:
            # Create NetworkManager instance
            from .network import NetworkManager
            network_manager = NetworkManager(self.config)
            
            # Run speed test
            result = await network_manager.run_speed_test(detailed=True)
            
            if result:
                # Clear previous results
                stats_container.remove_children()
                stats_container.mount(Static("Network Status: Checking...", id="network-status"))
                
                # Add result data
                stats_container.mount(Static(f"Download: {result.download_mbps:.2f} Mbps", classes="status-ok"))
                stats_container.mount(Static(f"Upload: {result.upload_mbps:.2f} Mbps", classes="status-ok"))
                
                ping_class = "status-ok" if result.ping_ms < 100 else "status-warning"
                stats_container.mount(Static(f"Ping: {result.ping_ms:.0f} ms", classes=ping_class))
                
                if hasattr(result, 'jitter_ms') and result.jitter_ms is not None:
                    stats_container.mount(Static(f"Jitter: {result.jitter_ms:.1f} ms"))
                    
                if hasattr(result, 'packet_loss') and result.packet_loss is not None:
                    loss_class = "status-ok" if result.packet_loss < 1 else "status-warning" if result.packet_loss < 5 else "status-error"
                    stats_container.mount(Static(f"Packet Loss: {result.packet_loss:.1f}%", classes=loss_class))
                
                # Overall rating
                if hasattr(result, 'get_quality_rating'):
                    quality_rating = result.get_quality_rating()
                    rating_text = "Excellent" if quality_rating >= 5 else "Good" if quality_rating >= 4 else "Fair" if quality_rating >= 3 else "Poor" if quality_rating >= 2 else "Very Poor"
                    rating_class = "status-ok" if quality_rating >= 4 else "status-warning" if quality_rating >= 2 else "status-error"
                    stats_container.mount(Static(f"Connection Quality: {rating_text}", classes=rating_class))
                
                # Update status
                status.update("Network test completed successfully", classes="status-ok")
            else:
                status.update("Network test failed. Check connection.", classes="status-error")
        
        except Exception as e:
            logging.error(f"Speed test error: {e}")
            status.update(f"Error during network test: {str(e)}", classes="status-error")
        
        finally:
            # Reset button
            button.disabled = False
            button.label = "Run Speed Test"
    
    def load_settings(self) -> None:
        """Load settings into form fields"""
        self.query_one("#video-dir-input").value = self.config.get("video_output", "")        
        self.query_one("#audio-dir-input").value = self.config.get("audio_output", "")
        self.query_one("#ffmpeg-input").value = self.config.get("ffmpeg_location", "")
        self.query_one("#organize-files").value = self.config.get("organize", False)
        self.query_one("#high-quality").value = self.config.get("high_quality_audio", True)
        
    def get_selected_format(self) -> Optional[str]:
        """Get the selected format ID"""
        table = self.query_one("#format-table")
        
        # Check if table has any rows
        if not hasattr(table, 'row_count') or not table.row_count:
            return "best"
        
        # Check if a row is selected
        if hasattr(table, 'cursor_row') and table.cursor_row is not None:
            try:
                # Access the row safely with bounds checking
                if 0 <= table.cursor_row < table.row_count:
                    row_data = table.get_row_at(table.cursor_row)
                    if row_data and len(row_data) > 0:
                        return row_data[0]  # Format ID is in column 0
                    else:
                        logging.warning("Selected row has insufficient data")
                        return "best"
                else:
                    logging.warning(f"Cursor row index {table.cursor_row} is out of bounds")
                    return "best"
            except Exception as e:
                logging.warning(f"Error accessing selected format: {str(e)}")
                return "best"
        
        # Default to best quality if nothing is selected
        return "best"
    
    def add_active_download(self, download_id: str, url: str) -> None:
        """Add a download to the active downloads list"""
        container = self.query_one("#active-downloads")
        
        # Create download progress tracker
        progress_id = f"progress-{download_id}"
        filename = url.split("/")[-1]
        if not filename:
            filename = url
            
        # Create progress container
        progress_container = Container(id=progress_id)
        progress_container.border_title = filename
        
        # Add progress bar
        progress_bar = ProgressBar(total=100, id=f"bar-{download_id}", classes="progress-bar")
          # Add status label
        status_label = Label("Starting download...", id=f"status-{download_id}")
        
        progress_container.mount(progress_bar)
        progress_container.mount(status_label)
        container.mount(progress_container)
        
        # Store for updating
        self.downloads.append({
            "id": download_id,
            "url": url,
            "progress_id": progress_id,
            "bar_id": f"bar-{download_id}",
            "status_id": f"status-{download_id}"
        })
    @work(thread=True)
    async def update_download_progress(self) -> None:
        """Update download progress periodically"""
        try:
            while True:
                # Update each active download
                completed_downloads = []
                
                for download in self.downloads:
                    try:
                        # Get progress info from session manager
                        progress = await self.download_manager.session_manager.get_session(download["id"])
                        
                        if progress:
                            # Update the progress bar
                            bar = self.query_one(f"#{download['bar_id']}")
                            bar.progress = progress.get("progress", 0)
                            
                            # Update status label
                            status = self.query_one(f"#{download['status_id']}")
                            status_text = progress.get("status", "Downloading...")
                            progress_percent = progress.get("progress", 0)
                            
                            # Format status message based on status
                            if status_text == "completed":
                                status.update(f"Completed - 100%")
                                status.add_class("status-ok")
                                completed_downloads.append(download["id"])
                            elif status_text == "cancelled":
                                status.update(f"Cancelled - {progress_percent:.1f}%")
                                status.add_class("status-warning")
                                completed_downloads.append(download["id"])
                            elif status_text == "failed":
                                error_msg = progress.get("error", "Unknown error")
                                status.update(f"Failed: {error_msg}")
                                status.add_class("status-error")
                                completed_downloads.append(download["id"]) 
                            else:
                                status.update(f"{status_text} - {progress_percent:.1f}%")
                                
                    except asyncio.CancelledError:
                        raise  # Re-raise to properly handle task cancellation
                    except Exception as e:
                        logging.error(f"Error updating progress for download {download['id']}: {e}")
                
                # Wait before next update
                await asyncio.sleep(1)
                
        except asyncio.CancelledError:
            logging.info("Download progress monitoring cancelled")
        except Exception as e:
            logging.error(f"Download progress monitoring error: {e}")
        finally:
            self._progress_worker_running = False
def launch_textual_interface(config: Dict[str, Any]) -> None:
    """Launch the Textual interface for interactive mode
    
    Args:
        config: Configuration dictionary
    """
    # Ensure required paths exist
    os.makedirs(config.get("video_output", "downloads"), exist_ok=True)
    os.makedirs(config.get("audio_output", "downloads/audio"), exist_ok=True)
    
    # Initialize required components
    session_file = config.get("session_file", "download_sessions.json")
    session_dir = os.path.dirname(os.path.abspath(session_file))
    os.makedirs(session_dir, exist_ok=True)
    
    from .cache import DownloadCache
    from .session import SessionManager, AsyncSessionManager
    
    # Create the app instance
    app = InteractiveApp(config)
    
    try:
        # Try running in this thread (will fail if the loop is already running)
        app.run()
    except RuntimeError:
        # Fallback: spin up a new thread so it gets its own event loop
        from threading import Thread

        def _run_app_in_thread() -> None:
            # 1) create new loop
            loop = asyncio.new_event_loop()
            # 2) install it as the current loop for this thread
            asyncio.set_event_loop(loop)
            # 3) now call run(), which will pick up our thread‑local loop
            app.run()

        console = Console()
        console.print("[bold green]Starting interactive mode in a new thread...[/]")
        thread = Thread(target=_run_app_in_thread, daemon=False)
        thread.start()
        thread.join()

