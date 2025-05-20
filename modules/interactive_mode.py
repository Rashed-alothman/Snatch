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
    SUB_TITLE = "Interactive Mode"
    
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
                    with ContentSwitcher(initial="download-screen", id="content-switcher"):
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
                            yield Static("Help & Documentation", classes="title")
                            help_md = "\n\n".join(HELP_CONTENT.values())
                            yield Markdown(help_md)
        
        yield Footer()
    
    def on_mount(self) -> None:
        """Handle app mount event"""
        # Initialize download manager
        self.initialize_download_manager()
        
        # Populate format table
        self.setup_format_table()
        
        # Load settings into form
        self.load_settings()
        
        # Set active menu item
        self.query_one("#menu-download").add_class("selected")
        
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
            
            if self.query_one("#content-switcher").has_screen(target_screen):
                self.query_one("#content-switcher").current = target_screen
        
        # Action buttons
        elif button_id == "analyze-btn":
            self.analyze_url()
        elif button_id == "start-download-btn":
            self.start_download()
        elif button_id == "speedtest-btn":
            self.run_speed_test()
        elif button_id == "save-settings-btn":
            self.save_settings()
    
    @work(exclusive=True)
    async def analyze_url(self) -> None:
        """Analyze the URL and load available formats"""
        url_input = self.query_one("#url-input")
        url = url_input.value.strip()
        
        if not url:
            self.notify("Please enter a valid URL", severity="error")
            return
            
        self.current_url = url
        
        # Show loading indicator
        url_input.placeholder = "Analyzing URL..."
        url_input.disabled = True
        
        try:
            # Get format info (implement this method based on your structure)
            self.format_info = await self.get_format_info(url)
            
            # Populate format table
            self.populate_format_table(self.format_info)
            
            url_input.placeholder = "Enter URL to download"
            url_input.disabled = False
            
            self.notify(f"Successfully analyzed URL: {url}", severity="information")
            
        except Exception as e:
            self.notify(f"Error analyzing URL: {str(e)}", severity="error")
            url_input.placeholder = "Enter URL to download"
            url_input.disabled = False
    
    def populate_format_table(self, format_info: Dict[str, Any]) -> None:
        """Populate the format selection table with available formats"""
        table = self.query_one("#format-table")
        table.clear()
        
        # Add columns
        table.add_columns(
            "Select", "Format", "Quality", "Resolution", "Codec", "Size", "FPS", "Audio"
        )
        
        # Add formats as rows
        for fmt in format_info.get("formats", []):
            table.add_row(
                "○",
                fmt.get("format_id", ""),
                fmt.get("quality", ""),
                fmt.get("resolution", ""),
                fmt.get("vcodec", ""),
                fmt.get("filesize_approx", ""),
                fmt.get("fps", ""),
                fmt.get("acodec", "")
            )
    
    @work
    async def start_download(self) -> None:
        """Start the download process"""
        if not self.current_url:
            self.notify("No URL selected for download", severity="warning")
            return
            
        # Get selected format or use best available
        selected_format = self.get_selected_format()
        
        # Get options
        audio_only = self.query_one("#audio-only").value
        process_audio = self.query_one("#process-audio").value
        upmix_audio = self.query_one("#upmix-audio").value
        
        # Prepare download options
        options = {
            "audio_only": audio_only,
            "format_id": selected_format,
            "process_audio": process_audio,
            "upmix_audio": upmix_audio
        }
        
        self.notify("Starting download...", severity="information")
        
        try:
            # Start download and track progress
            download_id = await self.download_manager.download(self.current_url, **options)
            
            # Add to active downloads
            self.add_active_download(download_id, self.current_url)
            
            self.notify("Download started successfully", severity="success")
            
        except Exception as e:
            self.notify(f"Download failed: {str(e)}", severity="error")
    
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
        status_label = Label(f"Starting download...", id=f"status-{download_id}")
        
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
        while True:
            # Update each active download
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
                        status.update(f"{progress.get('status', 'Downloading...')} - {progress.get('progress', 0):.1f}%")
                        
                        # If completed, update UI
                        if progress.get("status") == "completed":
                            status.add_class("status-ok")
                            
                except Exception as e:
                    logging.error(f"Error updating progress: {e}")
            
            # Wait before next update
            await asyncio.sleep(1)
    
    @work
    async def run_speed_test(self) -> None:
        """Run a network speed test"""
        button = self.query_one("#speedtest-btn")
        status = self.query_one("#network-status")
        
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
                # Create stats display
                container = self.query_one("#network-stats")
                container.remove_children()
                
                # Add result data
                container.mount(Static(f"Download: {result.download_mbps:.2f} Mbps", classes="status-ok"))
                container.mount(Static(f"Upload: {result.upload_mbps:.2f} Mbps", classes="status-ok"))
                container.mount(Static(f"Ping: {result.ping_ms:.0f} ms", classes="status-ok" if result.ping_ms < 100 else "status-warning"))
                
                if result.jitter_ms is not None:
                    container.mount(Static(f"Jitter: {result.jitter_ms:.1f} ms"))
                    
                if result.packet_loss is not None:
                    loss_class = "status-ok" if result.packet_loss < 1 else "status-warning" if result.packet_loss < 5 else "status-error"
                    container.mount(Static(f"Packet Loss: {result.packet_loss:.1f}%", classes=loss_class))
                
                # Overall rating
                quality_rating = result.get_quality_rating()
                rating_text = "Excellent" if quality_rating >= 5 else "Good" if quality_rating >= 4 else "Fair" if quality_rating >= 3 else "Poor" if quality_rating >= 2 else "Very Poor"
                rating_class = "status-ok" if quality_rating >= 4 else "status-warning" if quality_rating >= 2 else "status-error"
                
                container.mount(Static(f"Connection Quality: {rating_text}", classes=rating_class))
                
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
    
    def save_settings(self) -> None:
        """Save user settings"""
        # Get input values
        video_dir = self.query_one("#video-dir-input").value
        audio_dir = self.query_one("#audio-dir-input").value
        ffmpeg_location = self.query_one("#ffmpeg-input").value
        organize_files = self.query_one("#organize-files").value
        high_quality = self.query_one("#high-quality").value
        
        # Update config
        self.config.update({
            "video_output": video_dir,
            "audio_output": audio_dir,
            "ffmpeg_location": ffmpeg_location,
            "organize": organize_files,
            "high_quality_audio": high_quality
        })
        
        # Save to file
        try:
            with open("config.json", "w") as f:
                json.dump(self.config, f, indent=2)
            self.notify("Settings saved successfully", severity="success")
        except Exception as e:
            self.notify(f"Error saving settings: {str(e)}", severity="error")
    
    def load_settings(self) -> None:
        """Load settings into form fields"""
        self.query_one("#video-dir-input").value = self.config.get("video_output", "")
        self.query_one("#audio-dir-input").value = self.config.get("audio_output", "")
        self.query_one("#ffmpeg-input").value = self.config.get("ffmpeg_location", "")
        self.query_one("#organize-files").value = self.config.get("organize", False)
        self.query_one("#high-quality").value = self.config.get("high_quality_audio", True)
    
    def setup_format_table(self) -> None:
        """Set up the format selection table"""
        table = self.query_one("#format-table")
        table.cursor_type = "row"
        table.zebra_stripes = True
        
    def get_selected_format(self) -> Optional[str]:
        """Get the selected format ID"""
        table = self.query_one("#format-table")
        if table.cursor_row is not None:
            return table.get_row_at(table.cursor_row)[1]  # Format ID is in column 1
        return None
    
    def initialize_download_manager(self) -> None:
        """Initialize the download manager"""
        from .manager import DownloadManager
        from .session import SessionManager
        
        session_manager = SessionManager("download_sessions.json")
        self.download_manager = DownloadManager(self.config, session_manager=session_manager)
    
    @work
    async def get_format_info(self, url: str) -> Dict[str, Any]:
        """Get format information for a URL"""
        from yt_dlp import YoutubeDL
        
        # Configure YoutubeDL options
        options = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "listformats": True,
        }
        
        with YoutubeDL(options) as ydl:
            info = await asyncio.to_thread(ydl.extract_info, url, download=False)
            return info

def launch_textual_interface(config: Dict[str, Any]) -> None:
    """Launch the Textual interface for interactive mode
    
    Args:
        config: Configuration dictionary
    """
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

        thread = Thread(target=_run_app_in_thread, daemon=False)
        thread.start()
        thread.join()

