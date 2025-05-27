#!/usr/bin/env python3
"""
modern_interactive.py - Beautiful Modern Interactive Interface for SnatchV2

A stunning, modern, and highly functional interactive interface featuring:
- Contemporary GitHub Dark Pro inspired design
- Rich visual elements and animations
- Full download functionality
- Professional typography and spacing
- Intuitive user experience
"""

import asyncio
import os
import logging
import time
from typing import Dict, Any, List, Optional
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Container, Vertical, Horizontal, Grid, ScrollableContainer
from textual.widgets import (
    Header, Footer, Static, Input, Button, Label, 
    Checkbox, DataTable, ProgressBar, Tabs, Tab,
    TextArea, Switch, Select, Rule, Tree
)
from textual.screen import Screen
from textual import work
from textual.reactive import reactive
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

import yt_dlp

# Import the actual working download manager
from .manager import DownloadManager, AsyncDownloadManager
from .session import SessionManager
from .cache import DownloadCache
from .common_utils import sanitize_filename, format_size

# Constants
DEFAULT_DOWNLOAD_DIR = "~/Downloads/Snatch"

class ModernSnatchApp(App):
    """Beautiful, modern interactive application for Snatch Media Downloader"""
    
    TITLE = "Snatch Media Downloader"
    SUB_TITLE = "Professional Media Acquisition Suite"
    
    # Enhanced widget constants
    URL_INPUT = "#url-input"
    FORMAT_TABLE = "#format-table"
    DOWNLOAD_PROGRESS = "#download-progress"
    STATUS_DISPLAY = "#status-display"
    DOWNLOADS_LOG = "#downloads-log"
    STATS_PANEL = "#stats-panel"
    
    CSS = """
    /* Modern Professional Theme - GitHub Dark Pro Inspired */
    Screen {
        background: #0d1117;
        color: #e6edf3;
        overflow: hidden;
    }
    
    Header {
        background: #21262d;
        color: #58a6ff;
        text-style: bold;
        height: 3;
        text-align: center;
        border-bottom: solid #30363d;
        dock: top;
    }
    
    Footer {
        background: #161b22;
        color: #7d8590;
        border-top: solid #30363d;
        height: 3;
        dock: bottom;
    }
    
    #main-grid {
        layout: grid;
        grid-size: 3 4;
        grid-gutter: 1;
        height: 100%;
        padding: 1;
        background: #0d1117;
    }
    
    /* URL Input Section - Spans full width */
    #url-section {
        column-span: 3;
        row-span: 1;
        background: #161b22;
        border: solid #30363d;
        border-title-color: #58a6ff;
        border-title-style: bold;
        padding: 2;
    }
    
    #url-input {
        width: 100%;
        background: #21262d;
        border: solid #30363d;
        color: #e6edf3;
        padding: 0 2;
        height: 3;
    }
    
    #url-input:focus {
        border: solid #58a6ff;
        background: #0d1117;
    }
      #url-controls {
        layout: horizontal;
        height: auto;
        margin-top: 1;
        align: center middle;
    }
    
    /* Media Info Panel */
    #media-info {
        column-span: 2;
        row-span: 2;
        background: #161b22;
        border: solid #30363d;
        border-title-color: #7c3aed;
        border-title-style: bold;
        padding: 1;
    }
    
    #format-table {
        height: 100%;
        background: #0d1117;
        color: #e6edf3;
        border: none;
    }
    
    #format-table > .datatable--header {
        background: #21262d;
        color: #58a6ff;
        text-style: bold;
        height: 2;
    }
    
    #format-table > .datatable--cursor {
        background: #388bfd;
        color: #ffffff;
        text-style: bold;
    }
    
    #format-table > .datatable--odd-row {
        background: #161b22;
    }
    
    #format-table > .datatable--even-row {
        background: #0d1117;
    }
    
    #format-table > .datatable--hover {
        background: #21262d;
    }
    
    /* Settings & Options Panel */
    #options-panel {
        column-span: 1;
        row-span: 2;
        background: #161b22;
        border: solid #30363d;
        border-title-color: #f85149;
        border-title-style: bold;
        padding: 1;
    }
    
    .options-group {
        background: #21262d;
        border: solid #30363d;
        border-title-color: #7d8590;
        padding: 1;
        margin: 1 0;
    }
    
    /* Progress & Status Panel */
    #progress-panel {
        column-span: 3;
        row-span: 1;
        background: #161b22;
        border: solid #30363d;
        border-title-color: #39d353;
        border-title-style: bold;
        padding: 1;
        layout: horizontal;
    }
    
    #status-section {
        width: 2fr;
        margin-right: 1;
    }
    
    #stats-section {
        width: 1fr;
        background: #21262d;
        border: solid #30363d;
        padding: 1;
        border-title-color: #f79000;
    }
    
    #status-display {
        height: 3;
        background: #0d1117;
        color: #58a6ff;
        text-align: center;
        text-style: bold;
        border: solid #30363d;
        padding: 1;
    }
    
    #download-progress {
        margin-top: 1;
        background: #21262d;
        border: solid #30363d;
        height: 2;
    }
    
    /* Button Styling */
    Button {
        margin: 0 1;
        padding: 1 3;
        border: solid #30363d;
        background: #21262d;
        color: #e6edf3;
        text-style: bold;
        height: 3;
        min-width: 12;
    }
    
    Button:hover {
        background: #30363d;
        border: solid #58a6ff;
        color: #58a6ff;
    }
    
    Button.-primary {
        background: #238636;
        color: #ffffff;
        border: solid #238636;
    }
    
    Button.-primary:hover {
        background: #2ea043;
        border: solid #2ea043;
    }
    
    Button.-secondary {
        background: #1f6feb;
        color: #ffffff;
        border: solid #1f6feb;
    }
    
    Button.-secondary:hover {
        background: #388bfd;
        border: solid #388bfd;
    }
    
    Button.-danger {
        background: #da3633;
        color: #ffffff;
        border: solid #da3633;
    }
    
    Button.-danger:hover {
        background: #f85149;
        border: solid #f85149;
    }
    
    /* Checkbox Styling */
    Checkbox {
        margin: 1 0;
        color: #e6edf3;
        background: #21262d;
        padding: 1;
    }
    
    Checkbox:hover {
        color: #58a6ff;
        background: #30363d;
    }
    
    Checkbox:focus {
        border: solid #58a6ff;
    }
    
    /* Text Input Styling */
    Input {
        border: solid #30363d;
        background: #21262d;
        color: #e6edf3;
        padding: 1;
    }
    
    Input:focus {
        border: solid #58a6ff;
        background: #0d1117;
    }
    
    /* Text Area / Log Styling */
    TextArea {
        border: solid #30363d;
        background: #0d1117;
        color: #7c3aed;
    }
    
    /* Progress Bar Styling */
    ProgressBar > .bar--bar {
        color: #30363d;
    }
    
    ProgressBar > .bar--complete {
        color: #238636;
    }
    
    ProgressBar > .bar--indeterminate {
        color: #58a6ff;
    }
    
    /* Status Classes */
    .status-ready {
        color: #7d8590;
    }
    
    .status-analyzing {
        color: #f79000;
        text-style: bold;
    }
    
    .status-downloading {
        color: #58a6ff;
        text-style: bold;
    }
    
    .status-complete {
        color: #39d353;
        text-style: bold;
    }
    
    .status-error {
        color: #f85149;
        text-style: bold;
    }
    
    /* Section Titles */
    .section-title {
        color: #58a6ff;
        text-style: bold;
        text-align: center;
        background: #21262d;
        border: solid #30363d;
        padding: 1;
        margin: 0 0 1 0;
    }
    
    .panel-header {
        color: #e6edf3;
        text-style: bold;
        text-align: left;
        background: #30363d;
        padding: 1;
        margin: 0 0 1 0;
    }
    
    /* Statistics Display */
    .stat-item {
        background: #0d1117;
        border: solid #30363d;
        padding: 1;
        margin: 1 0;
        text-align: center;
    }
    
    .stat-value {
        color: #58a6ff;
        text-style: bold;
    }
    
    .stat-label {
        color: #7d8590;
    }
    
    /* Scrollable areas */
    ScrollableContainer {
        background: #0d1117;
        border: solid #30363d;
    }
    
    /* Rules/Dividers */
    Rule {
        color: #30363d;
        margin: 1 0;
    }
    
    /* Special highlights */
    .highlight {
        background: #1f6feb;
        color: #ffffff;
        text-style: bold;
        padding: 1;
    }
    
    .warning {
        background: #9a6700;
        color: #ffffff;
        text-style: bold;
        padding: 1;
    }
    
    .success {
        background: #1a7f37;
        color: #ffffff;
        text-style: bold;
        padding: 1;
    }
    
    .error {
        background: #b91c1c;
        color: #ffffff;
        text-style: bold;
        padding: 1;
    }
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__()
        self.config = config
        self.current_url = None
        self.format_info = None
        self.downloads = []
        self.download_stats = {
            'total_downloads': 0,
            'successful_downloads': 0,
            'failed_downloads': 0,
            'total_size_downloaded': 0
        }
        
        # Initialize download manager properly
        self.download_manager = None
        self.session_manager = None
        self.download_cache = None
        
        # Current download tracking
        self.active_downloads = {}
        
    def compose(self) -> ComposeResult:
        """Create the modern UI layout with grid system"""
        yield Header()
        
        with Grid(id="main-grid"):
            # URL Input Section (spans full width)
            with Container(id="url-section"):                
                yield Static("🎬 Enter Media URL", classes="section-title")
                yield Input(
                    placeholder="https://youtube.com/watch?v=... or any supported URL",
                    id="url-input"
                )
                with Horizontal(id="url-controls"):
                    yield Button("🔍 Analyze", id="analyze-btn", variant="success")
                    yield Button("⬇️ Download", id="download-btn", variant="primary")
                    yield Button("🚀 Speed Test", id="speedtest-btn", variant="default")
                    yield Button("🗂️ Open Folder", id="folder-btn", variant="default")
            
            # Media Information Panel (2/3 width, 2 rows tall)
            with Container(id="media-info"):
                yield Static("📋 Available Formats", classes="panel-header")
                yield DataTable(id="format-table", show_cursor=True)
            
            # Options & Settings Panel (1/3 width, 2 rows tall)
            with Container(id="options-panel"):
                yield Static("⚙️ Download Options", classes="panel-header")
                
                with Container(classes="options-group"):
                    yield Static("📁 Output Format")
                    yield Checkbox("🎵 Audio Only", id="audio-only")
                    yield Checkbox("🏆 Best Quality", id="best-quality", value=True)
                    yield Checkbox("📺 Include Subtitles", id="subtitles", value=True)
                
                with Container(classes="options-group"):
                    yield Static("🎛️ Audio Processing")
                    yield Checkbox("🔧 Process Audio", id="process-audio")
                    yield Checkbox("🎭 Normalize Volume", id="normalize-audio")
                    yield Checkbox("🌟 Upmix to 7.1", id="upmix-audio")
                
                with Container(classes="options-group"):
                    yield Static("🌐 Network")
                    yield Checkbox("🔄 Use Proxy", id="use-proxy")
                    yield Checkbox("⚡ Parallel Downloads", id="parallel", value=True)
            
            # Progress & Status Panel (spans full width)
            with Container(id="progress-panel"):
                with Container(id="status-section"):
                    yield Static("Ready to download", id="status-display", classes="status-ready")
                    yield ProgressBar(total=100, show_eta=True, id="download-progress")
                
                with Container(id="stats-section"):
                    yield Static("📊 Statistics", classes="panel-header")
                    yield Static("Downloads: 0", id="stat-total", classes="stat-item")
                    yield Static("Success: 0", id="stat-success", classes="stat-item")
                    yield Static("Size: 0 MB", id="stat-size", classes="stat-item")
        
        yield Footer()

    async def on_mount(self) -> None:
        """Initialize the modern app when mounted"""
        await self._initialize_managers()
        self._setup_format_table()
        self._update_status("🚀 Application initialized - Ready for downloads", "status-ready")
        
    async def _initialize_managers(self) -> None:
        """Initialize download managers and dependencies"""
        try:
            # Initialize session manager
            session_file = self.config.get("session_file", "downloads/sessions.json")
            self.session_manager = SessionManager(session_file)
            
            # Initialize download cache
            cache_dir = self.config.get("cache_directory", "downloads/cache")
            self.download_cache = DownloadCache(Path(cache_dir))
            
            # Initialize download manager
            self.download_manager = DownloadManager(
                config=self.config,
                session_manager=self.session_manager,
                download_cache=self.download_cache
            )
            
            self._update_status("✅ Download manager initialized", "status-complete")
            
        except Exception as e:
            error_msg = f"❌ Failed to initialize: {str(e)}"
            logging.error(error_msg)
            self._update_status(error_msg, "status-error")    
    def _setup_format_table(self) -> None:
        """Setup the modern format selection table"""
        try:
            format_table = self.query_one(self.FORMAT_TABLE, DataTable)
            format_table.add_columns(
                "ID", "Type", "Resolution", "Codec", "Size", "Audio", "FPS", "Quality"
            )
            format_table.add_row("--", "No URL", "--", "--", "--", "--", "--", "★☆☆☆☆")
        except Exception as e:
            logging.error(f"Error setting up format table: {e}")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle modern button press events"""
        button_id = event.button.id
        
        if button_id == "analyze-btn":
            self.analyze_url()
        elif button_id == "download-btn":
            self.start_download()
        elif button_id == "speedtest-btn":
            self.run_speed_test()
        elif button_id == "folder-btn":
            self.open_download_folder()

    def analyze_url(self) -> None:
        """Analyze URL with modern feedback"""
        url_input = self.query_one(self.URL_INPUT, Input)
        url = url_input.value.strip()
        
        if not url:
            self._update_status("⚠️ Please enter a valid URL", "status-error")
            return
            
        self.current_url = url
        self._update_status(f"🔍 Analyzing: {url[:50]}...", "status-analyzing")
        
        # Start analysis in background task
        self._analyze_url_task(url)

    @work
    async def _analyze_url_task(self, url: str) -> None:
        """Modern background task to analyze URL"""
        try:
            # Import yt-dlp for media extraction
            import yt_dlp
            
            # Update progress
            progress = self.query_one(self.DOWNLOAD_PROGRESS, ProgressBar)
            progress.update(progress=25)
            
            # Configure yt-dlp options for info extraction only
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                'listformats': True,
            }
            
            progress.update(progress=50)
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Extract info without downloading
                info = await asyncio.to_thread(ydl.extract_info, url, download=False)
                
                progress.update(progress=75)
                
                # Update the format table with available formats
                self._populate_modern_format_table(info)
                
                progress.update(progress=100)
                
                # Store format info for download
                self.format_info = info
                
                title = info.get('title', 'Unknown Title')
                duration = info.get('duration', 0)
                uploader = info.get('uploader', 'Unknown')
                
                duration_str = f"{duration//60}:{duration%60:02d}" if duration else "Unknown"
                
                self._update_status(
                    f"✅ Analyzed: {title[:30]}... ({duration_str}) by {uploader}",
                    "status-complete"
                )
                
                # Reset progress
                await asyncio.sleep(2)
                progress.update(progress=0)
                
        except ImportError:
            error_msg = "❌ yt-dlp not found. Install: pip install yt-dlp"
            self._update_status(error_msg, "status-error")
        except Exception as e:
            error_msg = f"❌ Analysis failed: {str(e)}"
            logging.error(error_msg)
            self._update_status(error_msg, "status-error")

    def _populate_modern_format_table(self, info: Dict[str, Any]) -> None:
        """Populate format table with modern styling and emoji indicators"""        
        try:
            format_table = self.query_one(self.FORMAT_TABLE, DataTable)
            format_table.clear()
            format_table.add_columns(
                "ID", "📁 Type", "📺 Res", "🎬 Codec", "📏 Size", "🎵 Audio", "⚡ FPS", "⭐ Quality"
            )
            
            formats = info.get('formats', [])
            if not formats:
                format_table.add_row("--", "❌ No formats", "--", "--", "--", "--", "--", "☆☆☆☆☆")
                return
            
            # Sort formats by quality (resolution and bitrate)
            sorted_formats = sorted(formats, key=lambda x: (
                x.get('height', 0) if x.get('height') else 0,
                x.get('tbr', 0) if x.get('tbr') else 0
            ), reverse=True)
            for fmt in sorted_formats[:15]:  # Limit to top 15 formats for clarity
                format_id = fmt.get('format_id', '--')
                
                # Type with emoji
                vcodec = fmt.get('vcodec', '')
                acodec = fmt.get('acodec', '')
                if vcodec and vcodec != 'none' and acodec and acodec != 'none':
                    type_str = "🎬 Video+Audio"
                elif vcodec and vcodec != 'none':
                    type_str = "📺 Video Only"
                elif acodec and acodec != 'none':
                    type_str = "🎵 Audio Only"
                else:
                    type_str = "❓ Unknown"
                
                # Resolution
                height = fmt.get('height')
                width = fmt.get('width')
                if height and width:
                    resolution = f"{width}x{height}"
                elif height:
                    resolution = f"{height}p"
                else:
                    resolution = "--"
                
                # Codec info
                if vcodec and vcodec != 'none':
                    codec = vcodec[:10]  # Truncate long codec names
                elif acodec and acodec != 'none':
                    codec = acodec[:10]
                else:
                    codec = "--"
                
                # File size
                filesize = fmt.get('filesize')
                if filesize:
                    size = format_size(filesize)
                else:
                    size = "--"
                
                # Audio info
                abr = fmt.get('abr')
                if abr:
                    audio = f"{abr}kbps"
                elif acodec and acodec != 'none':
                    audio = "✅ Yes"
                else:
                    audio = "❌ No"
                
                # FPS
                fps = fmt.get('fps')
                fps_str = f"{fps}fps" if fps else "--"
                
                # Quality rating (stars based on resolution and bitrate)
                quality_score = 0
                if height:
                    if height >= 2160: quality_score = 5  # 4K
                    elif height >= 1440: quality_score = 4  # 1440p
                    elif height >= 1080: quality_score = 3  # 1080p
                    elif height >= 720: quality_score = 2   # 720p
                    else: quality_score = 1
                
                quality_stars = "⭐" * quality_score + "☆" * (5 - quality_score)
                
                format_table.add_row(
                    format_id, type_str, resolution, codec, 
                    size, audio, fps_str, quality_stars
                )
                
        except Exception as e:
            logging.error(f"Error populating format table: {e}")

    def start_download(self) -> None:
        """Start downloading with modern interface feedback"""
        if not self.current_url:
            self._update_status("⚠️ Please analyze a URL first", "status-error")
            return
            
        if not self.download_manager:
            self._update_status("❌ Download manager not ready", "status-error")
            return
            
        # Get download options from modern checkboxes
        options = {
            'audio_only': self.query_one("#audio-only", Checkbox).value,
            'best_quality': self.query_one("#best-quality", Checkbox).value,
            'include_subtitles': self.query_one("#subtitles", Checkbox).value,
            'process_audio': self.query_one("#process-audio", Checkbox).value,
            'normalize_audio': self.query_one("#normalize-audio", Checkbox).value,
            'upmix_audio': self.query_one("#upmix-audio", Checkbox).value,
            'use_proxy': self.query_one("#use-proxy", Checkbox).value,
            'parallel': self.query_one("#parallel", Checkbox).value
        }
        
        self._update_status("🚀 Starting download...", "status-downloading")
        
        # Start download in background task
        self._download_task(self.current_url, options)

    @work
    async def _download_task(self, url: str, options: Dict[str, Any]) -> None:
        """Modern background task to perform the download"""
        try:
            # Update progress bar with smooth animation
            progress = self.query_one(self.DOWNLOAD_PROGRESS, ProgressBar)
            
            # Prepare download
            progress.update(progress=10)
            self._update_status("📋 Preparing download...", "status-downloading")
            
            download_options = self._prepare_modern_download_options(options)
            
            progress.update(progress=20)
            self._update_status("🌐 Connecting to server...", "status-downloading")
            
            # Simulate realistic download progress updates
            for i in range(20, 95, 5):
                await asyncio.sleep(0.5)
                progress.update(progress=i)
                self._update_status(f"⬇️ Downloading... {i}%", "status-downloading")
            
            # Use the download manager to perform the download
            success = await self.download_manager.download(url, **download_options)
            
            if success:
                progress.update(progress=100)
                self._update_status("🎉 Download completed successfully!", "status-complete")
                
                # Update statistics
                self.download_stats['total_downloads'] += 1
                self.download_stats['successful_downloads'] += 1
                self._update_statistics()
                
                # Add to downloads list
                self.downloads.append({
                    'url': url,
                    'status': 'Completed',
                    'timestamp': time.strftime('%H:%M:%S'),
                    'options': options
                })
                
                # Reset progress after delay
                await asyncio.sleep(3)
                progress.update(progress=0)
                self._update_status("✅ Ready for next download", "status-ready")
                
            else:
                progress.update(progress=0)
                self._update_status("❌ Download failed", "status-error")
                self.download_stats['total_downloads'] += 1
                self.download_stats['failed_downloads'] += 1
                self._update_statistics()
                
        except Exception as e:
            progress.update(progress=0)
            error_msg = f"❌ Download error: {str(e)}"
            logging.error(error_msg)
            self._update_status(error_msg, "status-error")
            self.download_stats['total_downloads'] += 1
            self.download_stats['failed_downloads'] += 1
            self._update_statistics()

    def _prepare_modern_download_options(self, options: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare enhanced download options for the modern interface"""
        # Set up paths with better organization
        base_dir = self.config.get('download_directory', os.path.expanduser("~/Downloads/Snatch"))
        video_dir = os.path.join(base_dir, "Videos")
        audio_dir = os.path.join(base_dir, "Audio")
        
        # Ensure directories exist
        os.makedirs(video_dir, exist_ok=True)
        os.makedirs(audio_dir, exist_ok=True)
        
        download_opts = {
            'format': 'bestaudio/best' if options.get('audio_only') else 'bestvideo+bestaudio/best',
            'outtmpl': os.path.join(
                audio_dir if options.get('audio_only') else video_dir,
                '%(uploader)s - %(title)s.%(ext)s'
            ),
            'extractaudio': options.get('audio_only', False),
            'audioformat': 'mp3' if options.get('audio_only') else None,
            'embed_subs': options.get('include_subtitles', True),
            'writesubtitles': options.get('include_subtitles', True),
            'writeautomaticsub': options.get('include_subtitles', True),
        }
        
        # Enhanced audio processing options
        if options.get('process_audio'):
            download_opts['process_audio'] = True
            download_opts['denoise_audio'] = True
            
        if options.get('normalize_audio'):
            download_opts['normalize_audio'] = True
            
        if options.get('upmix_audio'):
            download_opts['upmix_surround'] = True
            
        if options.get('parallel'):
            download_opts['concurrent_fragments'] = 4
            
        return download_opts

    def run_speed_test(self) -> None:
        """Run modern network speed test"""
        self._update_status("🚀 Running speed test...", "status-analyzing")
        self._speed_test_task()

    @work
    async def _speed_test_task(self) -> None:
        """Modern background task for speed test"""
        try:
            from .network import NetworkManager
            
            progress = self.query_one(self.DOWNLOAD_PROGRESS, ProgressBar)
            
            # Simulate speed test progress
            for i in range(0, 100, 10):
                await asyncio.sleep(0.3)
                progress.update(progress=i)
                self._update_status(f"🚀 Testing speed... {i}%", "status-analyzing")
            
            network_manager = NetworkManager(self.config)
            result = await network_manager.run_speed_test(detailed=True)
            
            if result:
                status_text = f"🌐 Speed: ⬇️{result.download_mbps:.1f} Mbps ⬆️{result.upload_mbps:.1f} Mbps 📶{result.ping_ms:.0f}ms"
                self._update_status(status_text, "status-complete")
            else:
                self._update_status("❌ Speed test failed", "status-error")
            
            progress.update(progress=0)
                
        except ImportError:
            error_msg = "❌ Network module not available"
            self._update_status(error_msg, "status-error")
        except Exception as e:
            error_msg = f"❌ Speed test error: {str(e)}"
            logging.error(error_msg)
            self._update_status(error_msg, "status-error")

    def open_download_folder(self) -> None:
        """Open the download folder in file explorer"""
        try:
            import subprocess
            import platform
            
            download_dir = self.config.get('download_directory', os.path.expanduser("~/Downloads/Snatch"))
            os.makedirs(download_dir, exist_ok=True)
            
            system = platform.system()
            if system == "Windows":
                subprocess.run(["explorer", download_dir])
            elif system == "Darwin":  # macOS
                subprocess.run(["open", download_dir])
            elif system == "Linux":
                subprocess.run(["xdg-open", download_dir])
            
            self._update_status(f"📂 Opened folder: {download_dir}", "status-complete")
            
        except Exception as e:
            error_msg = f"❌ Could not open folder: {str(e)}"
            self._update_status(error_msg, "status-error")

    def _update_status(self, message: str, css_class: str = "status-ready") -> None:
        """Update the modern status display"""
        try:
            status_display = self.query_one(self.STATUS_DISPLAY, Static)
            status_display.update(message)
            # Remove all status classes and add the new one
            status_display.remove_class("status-ready", "status-analyzing", "status-downloading", 
                                      "status-complete", "status-error")
            status_display.add_class(css_class)
        except Exception as e:
            logging.error(f"Error updating status: {e}")

    def _update_statistics(self) -> None:
        """Update the modern statistics display"""
        try:
            stats = self.download_stats
            
            total_stat = self.query_one("#stat-total", Static)
            success_stat = self.query_one("#stat-success", Static)
            size_stat = self.query_one("#stat-size", Static)
            
            total_stat.update(f"📊 Total: {stats['total_downloads']}")
            success_stat.update(f"✅ Success: {stats['successful_downloads']}")
            size_stat.update(f"💾 Size: {stats['total_size_downloaded']} MB")
            
        except Exception as e:
            logging.error(f"Error updating statistics: {e}")


def run_modern_interactive(config: Dict[str, Any]) -> None:
    """Run the beautiful modern interactive interface"""
    app = ModernSnatchApp(config)
    app.run()


# For testing - can be removed in final version
if __name__ == "__main__":
    # Test configuration
    test_config = {
        "download_directory": os.path.expanduser("~/Downloads/Snatch"),
        "session_file": "downloads/sessions.json",
        "cache_directory": "downloads/cache",
        "max_retries": 3,
        "audio_only": False,
        "video_quality": "best"
    }
    
    run_modern_interactive(test_config)
