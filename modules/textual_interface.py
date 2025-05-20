#!/usr/bin/env python3
"""
textual_interface_improved.py - Enhanced Snatch TUI Interface using Textual

A modern, feature-rich terminal user interface for media downloads using Textual framework.
This provides an enhanced user experience with interactive widgets and responsive design.
Works with the unified download manager for optimal performance.

Features:
- Responsive grid layout with dynamic resizing
- Interactive widgets with enhanced styling
- Live download progress tracking with detailed statistics
- Format selection matrix with quality indicators
- Media preview panel with rich metadata display
- Download queue management with priority control
- System resource monitoring dashboard
- Network speed testing and diagnostics
- Dark/light theme support
"""

import os
import sys
import asyncio
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union, Callable
from datetime import datetime, timedelta

from rich.style import Style
from rich.text import Text
from rich import box
from rich.console import RenderableType
from rich.table import Table
from rich.panel import Panel
from rich.progress import BarColumn, Progress
from rich.syntax import Syntax

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Grid, Horizontal, Vertical, VerticalScroll, ScrollableContainer
from textual.screen import Screen, ModalScreen
from textual.widgets import (
    Button, Static, Input, Label, Header, Footer, 
    ProgressBar, ContentSwitcher, RadioSet, RadioButton,
    Checkbox, OptionList, TextLog, DataTable, Rule, 
    Select, ListView, Markdown, Switch
)
from textual.widget import Widget
from textual.reactive import reactive

from .constants import APP_VERSION
from .defaults import BANNER_ART, HELP_CONTENT
from .audio_processor import AudioProcessor
from .common_utils import sanitize_filename, format_size, ensure_dir
from .network import NetworkManager, SpeedTestResult


# Import conditionally to handle non-interactive environments
try:
    from yt_dlp import YoutubeDL
    from yt_dlp.utils import DownloadError
    YTDLP_AVAILABLE = True
except ImportError:
    YTDLP_AVAILABLE = False

# Define color themes
LIGHT_THEME = {
    "primary": "dark_blue",
    "secondary": "blue",
    "accent": "magenta",
    "background": "white",
    "foreground": "black",
    "muted": "gray70",
    "success": "green",
    "warning": "orange3",
    "error": "red",
    "info": "blue"
}

DARK_THEME = {
    "primary": "cyan",
    "secondary": "bright_blue",
    "accent": "bright_magenta",
    "background": "black",
    "foreground": "white",
    "muted": "gray50",
    "success": "bright_green",
    "warning": "yellow",
    "error": "bright_red",
    "info": "bright_blue"
}

class MediaPreviewWidget(Static):
    """Media preview widget with metadata display and thumbnail."""
    
    def __init__(self, name: str = None):
        super().__init__(name=name)
        self.metadata = {}
        
    def update_metadata(self, metadata: Dict[str, Any]) -> None:
        """Update metadata and refresh the widget."""
        self.metadata = metadata
        self.refresh()
        
    def clear_metadata(self) -> None:
        """Clear metadata and refresh widget."""
        self.metadata = {}
        self.refresh()
        
    def render(self) -> RenderableType:
        """Render the media preview with metadata."""
        if not self.metadata:
            return Text("No media loaded. Enter a URL to begin.", style="dim")
            
        # Format title
        title = self.metadata.get('title', 'Unknown')
        
        # Base table structure
        grid = Table.grid(padding=(0, 2), expand=True)
        grid.add_column("Label", style="bright_blue", justify="right", width=15)
        grid.add_column("Value", style="bright_white", ratio=2)

        # Basic metadata
        grid.add_row("📺 Title", Text(title[:60] + "..." if len(title) > 60 else title, style="bright_white bold"))
        
        if self.metadata.get('duration'):
            duration = self._format_duration(self.metadata['duration'])
            grid.add_row("⏱️ Duration", duration)
            
        if self.metadata.get('upload_date'):
            grid.add_row("📅 Released", self._format_date(self.metadata['upload_date']))
            
        if self.metadata.get('uploader'):
            grid.add_row("👤 Uploader", Text(self.metadata['uploader'], style="cyan"))
            
        # Media-specific information
        if self.metadata.get('width') and self.metadata.get('height'):
            resolution = f"{self.metadata['width']}x{self.metadata['height']}"
            grid.add_row("🎥 Resolution", resolution)
        
        # Format info
        if self.metadata.get('ext'):
            grid.add_row("📦 Format", self._format_format_info(self.metadata))
            
        if self.metadata.get('filesize'):
            grid.add_row("💾 Size", format_size(self.metadata['filesize']))
            
        if self.metadata.get('view_count'):
            grid.add_row("👁️ Views", f"{self.metadata['view_count']:,}")
            
        # Add links section
        if self.metadata.get('webpage_url'):
            grid.add_row("🔗 Source", Text(self.metadata['webpage_url'], style="underline cyan"))
            
        # Add thumbnail URL if available
        if self.metadata.get('thumbnail'):
            grid.add_row("🖼️ Thumbnail", Text("Available", style="green"))
            
        # Wrap in a panel
        return Panel(
            grid,
            title="Media Information",
            border_style="bright_blue",
            box=box.ROUNDED
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
            
    def _format_format_info(self, metadata: Dict[str, Any]) -> str:
        """Format codec information with color highlighting."""
        parts = []
        
        # File extension
        if metadata.get('ext'):
            parts.append(f"{metadata['ext'].upper()}")
        
        # Video codec
        if metadata.get('vcodec') and metadata['vcodec'] != 'none':
            parts.append(f"{metadata['vcodec']}")
        
        # Audio codec
        if metadata.get('acodec') and metadata['acodec'] != 'none':
            parts.append(f"{metadata['acodec']}")
            
        return " • ".join(parts) if parts else "Unknown"

class FormatSelectionWidget(Static):
    """Widget for selecting download formats with enhanced visualization."""
    
    def __init__(self, 
                 name: str = None, 
                 on_format_select: Optional[Callable[[str], None]] = None):
        super().__init__(name=name)
        self.formats = []
        self.selected_format_id = None
        self.on_format_select = on_format_select
        
    def update_formats(self, formats: List[Dict[str, Any]]) -> None:
        """Update available formats and refresh widget."""
        if formats:
            # Group formats by type (audio, video, video+audio)
            video_formats = []
            audio_formats = []
            combined_formats = []
            
            for fmt in formats:
                if fmt.get('vcodec', 'none') != 'none' and fmt.get('acodec', 'none') != 'none':
                    combined_formats.append(fmt)
                elif fmt.get('vcodec', 'none') != 'none':
                    video_formats.append(fmt)
                elif fmt.get('acodec', 'none') != 'none':
                    audio_formats.append(fmt)
            
            # Sort formats by quality
            video_formats.sort(key=lambda x: (x.get('height', 0) or 0, x.get('fps', 0) or 0, x.get('tbr', 0) or 0), reverse=True)
            audio_formats.sort(key=lambda x: (x.get('abr', 0) or 0), reverse=True)
            combined_formats.sort(key=lambda x: (x.get('height', 0) or 0, x.get('tbr', 0) or 0), reverse=True)
            
            # Create final format list
            self.formats = []
            
            # Add a "Best quality" automatic option
            self.formats.append({
                "format_id": "best",
                "format_note": "Best Quality (Automatic)",
                "ext": "auto",
                "resolution": "auto",
                "is_auto": True
            })
            
            # Add combined formats
            self.formats.extend(combined_formats)
            
            # Add video-only formats
            self.formats.extend(video_formats)
            
            # Add audio-only formats
            self.formats.extend(audio_formats)
            
            # Select best format by default
            if self.formats:
                self.selected_format_id = self.formats[0]['format_id']
        else:
            self.formats = []
            self.selected_format_id = None
            
        self.refresh()
        
    def on_click(self, event) -> None:
        """Handle click events on the format table."""
        # Extract format ID from the clicked row
        try:
            # Try to get the format ID from the clicked position
            meta = event.style.meta
            if meta and "format_id" in meta:
                format_id = meta["format_id"]
                self.selected_format_id = format_id
                self.refresh()
                
                if self.on_format_select:
                    self.on_format_select(format_id)
        except Exception:
            pass
            
    def render(self) -> RenderableType:
        """Render the format selection table."""
        if not self.formats:
            return Text("No formats available", style="dim")
            
        table = Table(
            box=box.SIMPLE,
            expand=True,
            show_header=True,
            header_style="bold bright_blue"
        )
        
        # Define columns
        table.add_column("Format", style="cyan")
        table.add_column("Resolution", justify="center")
        table.add_column("Extension", justify="center")
        table.add_column("FPS", justify="right")
        table.add_column("Size", justify="right")
        table.add_column("Bitrate", justify="right")
        table.add_column("Codec", style="green")
        
        # Add rows for each format
        for fmt in self.formats:
            # Format ID and note
            format_text = f"{fmt.get('format_id', 'unknown')}"
            if fmt.get('format_note'):
                format_text += f" ({fmt['format_note']})"
                
            # Resolution
            if fmt.get('is_auto', False):
                resolution = "Auto"
            elif fmt.get('height', 0) > 0 and fmt.get('width', 0) > 0:
                resolution = f"{fmt['width']}x{fmt['height']}"
            else:
                resolution = "audio only" if fmt.get('acodec', 'none') != 'none' else "N/A"
                
            # File extension
            extension = fmt.get('ext', 'N/A')
            
            # FPS
            fps = f"{fmt['fps']}" if fmt.get('fps') else "N/A"
            
            # Filesize
            if fmt.get('filesize'):
                size = format_size(fmt['filesize'])
            elif fmt.get('filesize_approx'):
                size = f"~{format_size(fmt['filesize_approx'])}"
            else:
                size = "N/A"
                
            # Bitrate
            if fmt.get('tbr'):
                bitrate = f"{fmt['tbr']:.1f} kbps"
            elif fmt.get('abr'):
                bitrate = f"{fmt['abr']:.1f} kbps"
            else:
                bitrate = "N/A"
                
            # Codec info
            codecs = []
            if fmt.get('vcodec') and fmt.get('vcodec') != 'none':
                codecs.append(f"V:{fmt['vcodec']}")
            if fmt.get('acodec') and fmt.get('acodec') != 'none':
                codecs.append(f"A:{fmt['acodec']}")
            codec_text = ", ".join(codecs) if codecs else "N/A"
            
            # Style for selected row
            row_style = "bold reverse" if fmt.get('format_id') == self.selected_format_id else ""
            
            # Add meta information for click handler
            meta = {"format_id": fmt.get('format_id', 'unknown')}
            
            table.add_row(
                format_text,
                resolution,
                extension,
                fps,
                size,
                bitrate,
                codec_text,
                style=row_style,
                end_section=(fmt == self.formats[-1] or 
                             (fmt.get('acodec', 'none') == 'none' and self.formats[self.formats.index(fmt)+1].get('acodec', 'none') != 'none') or
                             (fmt.get('vcodec', 'none') == 'none' and self.formats[self.formats.index(fmt)+1].get('vcodec', 'none') != 'none')),
                meta=meta
            )
        
        return Panel(
            table,
            title="Available Formats [click to select]",
            border_style="bright_blue",
            box=box.ROUNDED
        )

class DownloadProgressWidget(Static):
    """Enhanced widget for displaying download progress."""
    
    def __init__(self, name: str = None):
        super().__init__(name=name)
        self.progress_data = {
            "status": "idle",
            "filename": None,
            "title": None,
            "percent": 0,
            "speed": None,
            "eta": None,
            "size": None,
            "message": "Ready to download",
            "start_time": None,
            "end_time": None
        }
        
    def update_progress(self, data: Dict[str, Any]) -> None:
        """Update progress information."""
        # Update only provided fields
        self.progress_data.update(data)
        
        # Set start time if downloading just began
        if data.get('status') == 'downloading' and not self.progress_data.get('start_time'):
            self.progress_data['start_time'] = time.time()
            
        # Set end time if download just completed
        if data.get('status') in ('completed', 'error') and not self.progress_data.get('end_time'):
            self.progress_data['end_time'] = time.time()
            
        self.refresh()
        
    def reset(self) -> None:
        """Reset progress to initial state."""
        self.progress_data = {
            "status": "idle",
            "filename": None,
            "title": None,
            "percent": 0,
            "speed": None,
            "eta": None,
            "size": None,
            "message": "Ready to download",
            "start_time": None,
            "end_time": None
        }
        self.refresh()
        
    def render(self) -> RenderableType:
        """Render the progress display."""
        status = self.progress_data['status']
        
        # Create base grid
        grid = Table.grid(padding=(0, 2), expand=True)
        grid.add_column("Label", width=12, style="bright_blue")
        grid.add_column("Value", ratio=2)
        
        # Add title if available
        if self.progress_data.get('title'):
            title_text = Text(self.progress_data['title'], style="bold")
            grid.add_row("Title", title_text)
            
        # Add filename if available
        if self.progress_data.get('filename'):
            filename = os.path.basename(self.progress_data['filename'])
            grid.add_row("Filename", filename)
        
        # Create progress bar
        if status in ('downloading', 'processing'):
            percent = min(100, max(0, self.progress_data.get('percent', 0)))
            
            progress_bar = Progress(
                "[progress.description]{task.description}",
                BarColumn(bar_width=40),
                "[progress.percentage]{task.percentage:>3.0f}%",
                expand=True
            )
            
            # Add task
            task_id = progress_bar.add_task("", total=100, completed=percent)
            
            # Add progress row
            grid.add_row("Progress", progress_bar)
            
            # Add speed and ETA if available
            if self.progress_data.get('speed'):
                grid.add_row("Speed", f"{self.progress_data['speed']}")
                
            if self.progress_data.get('eta'):
                grid.add_row("ETA", f"{self.progress_data['eta']}")
                
            if self.progress_data.get('size'):
                grid.add_row("Size", f"{self.progress_data['size']}")
                
        # Add elapsed time if download is in progress or completed
        if status in ('downloading', 'processing', 'completed', 'error'):
            if self.progress_data.get('start_time'):
                end_time = self.progress_data.get('end_time') or time.time()
                elapsed = end_time - self.progress_data['start_time']
                elapsed_str = self._format_time(elapsed)
                grid.add_row("Elapsed", elapsed_str)
                
        # Add status message
        status_style = {
            'idle': "dim",
            'downloading': "bright_blue",
            'processing': "bright_magenta",
            'completed': "bright_green",
            'error': "bright_red"
        }.get(status, "white")
        
        message = self.progress_data.get('message') or f"Status: {status}"
        grid.add_row("Status", Text(message, style=status_style))
        
        # Wrap in a panel
        panel_title = {
            'idle': "Download Ready",
            'downloading': "⬇️ Downloading",
            'processing': "🔄 Processing",
            'completed': "✅ Download Complete",
            'error': "❌ Download Error"
        }.get(status, "Download Progress")
        
        panel_style = {
            'idle': "blue",
            'downloading': "cyan",
            'processing': "magenta",
            'completed': "green",
            'error': "red"
        }.get(status, "blue")
        
        return Panel(
            grid,
            title=panel_title,
            border_style=panel_style,
            box=box.ROUNDED
        )
        
    def _format_time(self, seconds: float) -> str:
        """Format time in seconds to human-readable format."""
        hours, remainder = divmod(int(seconds), 3600)
        minutes, seconds = divmod(remainder, 60)
        
        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"

class NetworkInfoWidget(Static):
    """Widget for displaying network information and speed test results."""
    
    def __init__(self, network_manager: NetworkManager, name: str = None):
        super().__init__(name=name)
        self.network_manager = network_manager
        self.connection_status = False
        self.speed_test_result = None
        
    @work
    async def update_connection_status(self) -> None:
        """Update connection status asynchronously."""
        self.connection_status = await self.network_manager.check_connection()
        self.refresh()
        
    @work
    async def run_speed_test(self) -> None:
        """Run a network speed test asynchronously."""
        self.speed_test_result = await self.network_manager.run_speed_test()
        self.refresh()
        
    def render(self) -> RenderableType:
        """Render network information."""
        grid = Table.grid(padding=(0, 2), expand=True)
        grid.add_column("Label", style="bright_blue", justify="right", width=15)
        grid.add_column("Value", style="white", ratio=2)
        
        # Connection status
        status_text = "Connected" if self.connection_status else "Disconnected"
        status_style = "green bold" if self.connection_status else "red bold"
        grid.add_row("Status", Text(status_text, style=status_style))
        
        # Speed test results
        if self.speed_test_result:
            grid.add_row("Download", Text(f"{self.speed_test_result.download_mbps:.2f} Mbps", style="green"))
            grid.add_row("Upload", Text(f"{self.speed_test_result.upload_mbps:.2f} Mbps", style="cyan"))
            grid.add_row("Ping", Text(f"{self.speed_test_result.ping_ms:.0f} ms", style="yellow"))
            test_time = datetime.fromtimestamp(self.speed_test_result.timestamp).strftime("%H:%M:%S")
            grid.add_row("Last Test", test_time)
        else:
            grid.add_row("Speed Test", Text("Not run yet", style="dim"))
        
        return Panel(
            grid,
            title="Network Information",
            border_style="blue",
            box=box.ROUNDED
        )

class ConfigScreen(ModalScreen):
    """Configuration screen for download settings."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__()
        self.config = config
        
    def compose(self) -> ComposeResult:
        """Create child widgets."""
        with Container(id="config-container"):
            yield Label("Download Configuration", id="config-title", classes="title")
            yield Rule()
            
            with Grid(id="config-grid"):
                # Media settings
                yield Label("Media Type:")
                with Horizontal():
                    yield RadioButton("Video + Audio", value=not self.config.get("audio_only", False), id="media-type-video")
                    yield RadioButton("Audio Only", value=self.config.get("audio_only", False), id="media-type-audio")
                
                # Video quality settings
                yield Label("Video Quality:")
                with Horizontal():
                    yield Select(
                        [(res, res) for res in ["Best", "1080p", "720p", "480p", "360p"]], 
                        value=self.config.get("video_quality", "Best"),
                        id="video-quality"
                    )
                
                # Audio quality settings
                yield Label("Audio Format:")
                with Horizontal():
                    yield Select(
                        [(fmt, fmt) for fmt in ["opus", "mp3", "aac", "flac", "wav"]],
                        value=self.config.get("audio_format", "opus"),
                        id="audio-format"
                    )
                
                # Audio processing options
                yield Label("Audio Processing:")
                with Grid(id="audio-options-grid"):
                    yield Checkbox("Normalize Audio", value=self.config.get("normalize_audio", False), id="normalize-audio")
                    yield Checkbox("Denoise Audio", value=self.config.get("denoise_audio", False), id="denoise-audio")
                    yield Checkbox("Upmix to 7.1 Surround", value=self.config.get("upmix_surround", False), id="upmix-surround")
                
            yield Rule()
            
            with Horizontal(id="config-buttons"):
                yield Button("Save", variant="primary", id="save-config")
                yield Button("Cancel", id="cancel-config")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        if event.button.id == "save-config":
            # Save configuration
            self.config["audio_only"] = self.query_one("#media-type-audio").value
            self.config["video_quality"] = self.query_one("#video-quality").value
            self.config["audio_format"] = self.query_one("#audio-format").value
            self.config["normalize_audio"] = self.query_one("#normalize-audio").value
            self.config["denoise_audio"] = self.query_one("#denoise-audio").value
            self.config["upmix_surround"] = self.query_one("#upmix-surround").value
            
            # Dismiss the modal
            self.dismiss(self.config)
        elif event.button.id == "cancel-config":
            # Dismiss without saving
            self.dismiss()

class SnatchTextualApp(App):
    """Main Textual app for Snatch."""
    
    CSS_PATH = "textual.css"  # Optional custom CSS
    BINDINGS = [
        Binding("d", "download", "Download"),
        Binding("q", "quit", "Quit"),
        Binding("c", "show_config", "Config"),
        Binding("h", "show_help", "Help"),
        Binding("t", "test_network", "Test Network"),
    ]
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the app with configuration."""
        super().__init__()
        self.config = config
        self.metadata = {}
        self.selected_format = None
        self.download_manager = None  # Will be initialized later
        self.network_manager = NetworkManager(config)
        self.audio_processor = AudioProcessor(config)
        self.download_path = config.get("download_directory", os.path.expanduser("~/Downloads"))
        
        # Ensure download directory exists
        ensure_dir(self.download_path)
        
    def on_mount(self) -> None:
        """Handle app mounting."""
        # Initialize async components
        self.network_info = self.query_one("#network-info", NetworkInfoWidget)
        self.network_info.update_connection_status()
        
    def compose(self) -> ComposeResult:
        """Create child widgets."""
        # App header
        yield Header(show_clock=True)
        
        # Main layout grid
        with Grid(id="main-grid"):
            # URL input and controls
            with Container(id="url-container"):
                yield Label("Enter URL:", id="url-label")
                yield Input(placeholder="Enter media URL...", id="url-input")
                
                with Horizontal(id="url-buttons"):
                    yield Button("Fetch Info", variant="primary", id="fetch-button")
                    yield Button("Download", variant="success", id="download-button")
                    yield Button("Configure", id="config-button")
            
            # Media preview
            yield MediaPreviewWidget(name="media-preview", id="media-preview")
            
            # Format selection
            with Container(id="format-container"):
                yield FormatSelectionWidget(name="format-selection", id="format-selection")
            
            # Download progress
            yield DownloadProgressWidget(name="progress-widget", id="progress-widget")
            
            # Network info
            yield NetworkInfoWidget(self.network_manager, name="network-info", id="network-info")
        
        # App footer
        yield Footer()
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        button_id = event.button.id
        
        if button_id == "fetch-button":
            url = self.query_one("#url-input").value
            if url:
                self.fetch_media_info(url)
        
        elif button_id == "download-button":
            url = self.query_one("#url-input").value
            if url and self.metadata:
                self.start_download(url)
        
        elif button_id == "config-button":
            self.action_show_config()
        
    def action_download(self) -> None:
        """Handle download action."""
        url = self.query_one("#url-input").value
        if url and self.metadata:
            self.start_download(url)
        elif url:
            self.fetch_media_info(url)
    
    def action_show_config(self) -> None:
        """Show configuration screen."""
        def handle_config_update(config):
            if config:
                self.config.update(config)
        
        config_screen = ConfigScreen(self.config.copy())
        self.push_screen(config_screen, handle_config_update)
    
    def action_test_network(self) -> None:
        """Run network speed test."""
        self.notify("Running network speed test...")
        self.network_info.run_speed_test()
    
    def action_show_help(self) -> None:
        """Show help information."""
        self.push_screen(
            ModalScreen(
                Container(
                    Markdown(HELP_CONTENT),
                    Button("Close", variant="primary", id="close-help"),
                    id="help-container"
                )
            )
        )
    
    def action_quit(self) -> None:
        """Quit the application."""
        self.exit()
    
    @work
    async def fetch_media_info(self, url: str) -> None:
        """Fetch media information asynchronously."""
        progress_widget = self.query_one("#progress-widget", DownloadProgressWidget)
        media_preview = self.query_one("#media-preview", MediaPreviewWidget)
        format_selection = self.query_one("#format-selection", FormatSelectionWidget)
        
        progress_widget.update_progress({
            "status": "processing",
            "message": "Fetching media information..."
        })
        
        try:
            # Check if URL is valid
            if not await self.network_manager.check_url_availability(url):
                self.notify("Invalid or unavailable URL", severity="error")
                progress_widget.update_progress({
                    "status": "error",
                    "message": "Invalid or unavailable URL"
                })
                return
                
            # Extract info using yt-dlp
            if YTDLP_AVAILABLE:
                ydl_opts = {
                    'quiet': True,
                    'no_warnings': True,
                    'skip_download': True,
                }
                
                with YoutubeDL(ydl_opts) as ydl:
                    info = await asyncio.to_thread(ydl.extract_info, url, download=False)
                    
                    if info:
                        self.metadata = info
                        media_preview.update_metadata(info)
                        
                        # Update format selection
                        if 'formats' in info:
                            format_selection.update_formats(info['formats'])
                        
                        progress_widget.update_progress({
                            "status": "idle",
                            "title": info.get('title', 'Unknown'),
                            "message": "Ready to download"
                        })
                        
                        self.notify("Media information fetched successfully", severity="success")
                    else:
                        self.notify("Failed to fetch media information", severity="error")
                        progress_widget.update_progress({
                            "status": "error",
                            "message": "Failed to fetch media information"
                        })
            else:
                self.notify("yt-dlp is not available. Please install it.", severity="error")
                progress_widget.update_progress({
                    "status": "error",
                    "message": "yt-dlp is not available"
                })
                
        except Exception as e:
            self.notify(f"Error: {str(e)}", severity="error")
            progress_widget.update_progress({
                "status": "error",
                "message": f"Error: {str(e)}"
            })
    
    @work
    async def start_download(self, url: str) -> None:
        """Start the download process asynchronously."""
        progress_widget = self.query_one("#progress-widget", DownloadProgressWidget)
        format_selection = self.query_one("#format-selection", FormatSelectionWidget)
        
        progress_widget.update_progress({
            "status": "downloading",
            "title": self.metadata.get('title', 'Unknown'),
            "message": "Starting download...",
            "percent": 0
        })
        
        try:
            # Create download configuration
            title = self.metadata.get('title', 'Unknown')
            sanitized_title = sanitize_filename(title)
            output_path = os.path.join(self.download_path, sanitized_title)
            
            # Select format based on configuration
            selected_format = format_selection.selected_format_id
            
            # Build yt-dlp options
            ydl_opts = {
                'outtmpl': f'{output_path}.%(ext)s',
                'progress_hooks': [self._progress_hook],
                'quiet': True,
            }
            
            # Handle audio-only downloads
            if self.config.get("audio_only", False):
                ydl_opts.update({
                    'format': 'bestaudio/best',
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': self.config.get("audio_format", "mp3"),
                        'preferredquality': '192',
                    }],
                })
            else:
                # For video formats
                if selected_format and selected_format != "best":
                    ydl_opts.update({'format': selected_format})
                else:
                    # Quality-based format selector
                    quality_map = {
                        'Best': 'bestvideo+bestaudio/best',
                        '1080p': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]',
                        '720p': 'bestvideo[height<=720]+bestaudio/best[height<=720]',
                        '480p': 'bestvideo[height<=480]+bestaudio/best[height<=480]',
                        '360p': 'bestvideo[height<=360]+bestaudio/best[height<=360]',
                    }
                    
                    ydl_opts.update({
                        'format': quality_map.get(self.config.get("video_quality", "Best"), 'bestvideo+bestaudio/best'),
                    })
            
            # Start download
            with YoutubeDL(ydl_opts) as ydl:
                info = await asyncio.to_thread(ydl.extract_info, url, download=True)
                filename = ydl.prepare_filename(info)
                
                # Update progress to completed
                progress_widget.update_progress({
                    "status": "completed",
                    "filename": filename,
                    "title": info.get('title', 'Unknown'),
                    "percent": 100,
                    "message": "Download completed!"
                })
                
                self.notify("Download completed successfully!", severity="success")
                
                # Apply audio processing if needed
                if self.config.get("audio_only", False) and (
                    self.config.get("upmix_surround", False) or 
                    self.config.get("denoise_audio", False) or
                    self.config.get("normalize_audio", False)
                ):
                    await self._apply_audio_processing(filename)
                
        except Exception as e:
            progress_widget.update_progress({
                "status": "error",
                "message": f"Error: {str(e)}"
            })
            self.notify(f"Download error: {str(e)}", severity="error")
    
    def _progress_hook(self, d: Dict[str, Any]) -> None:
        """Progress hook for yt-dlp."""
        progress_widget = self.query_one("#progress-widget", DownloadProgressWidget)
        
        if d['status'] == 'downloading':
            # Extract progress info
            try:
                total = float(d.get('total_bytes', 0)) or float(d.get('total_bytes_estimate', 0))
                downloaded = float(d.get('downloaded_bytes', 0))
                
                if total > 0:
                    percent = (downloaded / total) * 100
                    speed = d.get('speed', 0)
                    eta = d.get('eta', 0)
                    
                    progress_widget.update_progress({
                        "status": "downloading",
                        "filename": d.get('filename'),
                        "title": self.metadata.get('title', 'Unknown'),
                        "percent": percent,
                        "speed": f"{speed / 1024:.1f} KB/s" if speed else "N/A",
                        "eta": f"{eta // 60}:{eta % 60:02d}" if eta else "N/A",
                        "size": f"{downloaded / 1024 / 1024:.1f} MB of {total / 1024 / 1024:.1f} MB"
                    })
            except Exception:
                pass
        
        elif d['status'] == 'finished':
            # Download finished, prepare for post-processing
            progress_widget.update_progress({
                "status": "processing",
                "filename": d.get('filename'),
                "message": "Processing media...",
                "percent": 100
            })
    
    async def _apply_audio_processing(self, audio_file: str) -> None:
        """Apply audio processing options."""
        progress_widget = self.query_one("#progress-widget", DownloadProgressWidget)
        
        # Apply audio normalization if selected
        if self.config.get("normalize_audio", False):
            progress_widget.update_progress({
                "status": "processing",
                "message": "Normalizing audio levels..."
            })
            
            success = await self.audio_processor.normalize_audio(audio_file)
            if not success:
                self.notify("Warning: Audio normalization process failed", severity="warning")
        
        # Apply 7.1 upmix if selected
        if self.config.get("upmix_surround", False):
            progress_widget.update_progress({
                "status": "processing",
                "message": "Applying 7.1 surround sound upmix..."
            })
            
            success = await self.audio_processor.upmix_to_7_1(audio_file)
            if not success:
                self.notify("Warning: 7.1 upmix process failed", severity="warning")
        
        # Apply denoise if selected
        if self.config.get("denoise_audio", False):
            progress_widget.update_progress({
                "status": "processing",
                "message": "Applying audio denoise filter..."
            })
            
            success = await self.audio_processor.denoise_audio(audio_file)
            if not success:
                self.notify("Warning: Audio denoise process failed", severity="warning")
        
        # Update progress to completed
        progress_widget.update_progress({
            "status": "completed",
            "message": "Audio processing completed!"
        })
        
        self.notify("Audio processing completed!", severity="success")

async def run_textual_interface(config: Dict[str, Any]) -> None:
    """Run the Textual interface."""
    app = SnatchTextualApp(config)
    await app.run_async()

def start_textual_interface(config: Dict[str, Any]) -> None:
    """Start the Textual interface."""
    try:
        asyncio.run(run_textual_interface(config))
    except KeyboardInterrupt:
        print("\nTextual interface terminated by user.")
    except Exception as e:
        print(f"Error in Textual interface: {str(e)}")
        import traceback
        traceback.print_exc()
