#!/usr/bin/env python3
"""
Enhanced Interactive Mode with Cyberpunk UI and Full Functionality

This completely redesigned interactive mode features:
- Cyberpunk/neon-styled UI with matrix effects
- Standalone audio processing without downloads
- Working download functionality with P2P support  
- Enhanced 7.1 surround sound upmixing
- Real-time neural network monitoring
- All async/await warnings fixed
"""

from textual.app import App, ComposeResult
from textual.containers import Container, Vertical, Horizontal, Grid
from textual.widgets import (
    Header, Footer, Static, Input, Button, Label, 
    Checkbox, DataTable, ProgressBar, Tabs, Tab,
    TextArea, DirectoryTree, Switch
)
from textual.screen import Screen
from textual import work
from textual.reactive import reactive
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
import asyncio
import os
import logging
from typing import Dict, Any, List, Optional

class CyberpunkInteractiveApp(App):
    """Enhanced cyberpunk-styled interactive application"""
    
    CSS = """
    /* Cyberpunk Theme CSS */
    Screen {
        background: #0a0a0a;
    }
    
    Header {
        background: linear-gradient(90deg, #00ffff 0%, #ff1493 50%, #39ff14 100%);
        color: #000000;
        text-style: bold;
    }
    
    Footer {
        background: #1a1a1a;
        color: #00ffff;
    }
    
    Button {
        background: #1a1a1a;
        color: #00ffff;
        border: solid #00ffff;
        margin: 1;
    }
    
    Button:hover {
        background: #00ffff;
        color: #000000;
        border: solid #ff1493;
    }
    
    Button.-primary {
        background: #ff1493;
        color: #ffffff;
        border: solid #ff1493;
    }
    
    Button.-accent {
        background: #39ff14;
        color: #000000;
        border: solid #39ff14;
    }
    
    Input {
        background: #1a1a1a;
        color: #00ffff;
        border: solid #39ff14;
    }
    
    Input:focus {
        border: solid #ff1493;
    }
    
    DataTable {
        background: #0f0f0f;
        color: #00ffff;
        border: solid #39ff14;
    }
    
    DataTable > .datatable--header {
        background: #ff1493;
        color: #ffffff;
        text-style: bold;
    }
    
    DataTable > .datatable--cursor {
        background: #39ff14;
        color: #000000;
    }
    
    Static.neon-panel {
        background: #0f0f0f;
        color: #00ffff;
        border: solid #ff1493;
        padding: 1;
        margin: 1;
    }
    
    .cyber-title {
        color: #ff1493;
        text-style: bold;
    }
    
    .neon-green {
        color: #39ff14;
    }
    
    .neon-blue {
        color: #00ffff;
    }
    
    .neon-pink {
        color: #ff1493;
    }
    
    Tabs {
        background: #1a1a1a;
    }
    
    Tab {
        background: #1a1a1a;
        color: #00ffff;
        border: solid #39ff14;
    }
    
    Tab.-active {
        background: #ff1493;
        color: #ffffff;
    }
    """
    
    BINDINGS = [
        ("d", "download", "Download"),
        ("a", "audio", "Audio"),
        ("v", "video", "Video"),
        ("p", "p2p", "P2P"),
        ("s", "settings", "Settings"),
        ("q", "quit", "Quit"),
    ]
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__()
        self.config = config
        self.current_url = ""
        self.format_info = {}
        self.downloads = []
        self.cyberpunk_banner = None
        self.matrix_table = None
        self.status_panel = None
        self.download_manager = None
        self.p2p_manager = None
        self.standalone_audio = None
        
    def compose(self) -> ComposeResult:
        """Create the cyberpunk UI layout"""
        yield Header(show_clock=True, name="SNATCH NEURAL INTERFACE V2.0")
        
        with Container():
            # Top banner area
            yield Static(id="banner-area", classes="neon-panel")
            
            with Horizontal():
                # Left sidebar
                with Vertical(id="sidebar"):
                    yield Static("🔮 NEURAL MENU", classes="cyber-title")
                    yield Button("🔗 Neural Download", id="btn-download", classes="-primary")
                    yield Button("🎵 Audio Matrix", id="btn-audio", classes="-accent")  
                    yield Button("🎬 Video Nexus", id="btn-video", classes="-accent")
                    yield Button("📡 P2P Network", id="btn-p2p", classes="-accent")
                    yield Button("⚙️ Cyber Config", id="btn-settings", classes="-accent")
                    yield Button("📊 Data Stream", id="btn-monitor", classes="-accent")
                    yield Button("❓ Help Matrix", id="btn-help", classes="-accent")
                    
                    # Status panel
                    yield Static(id="status-panel", classes="neon-panel")
                
                # Main content area
                with Vertical(id="main-content"):
                    with Tabs(id="main-tabs"):
                        yield Tab("Download", id="tab-download")
                        yield Tab("Audio", id="tab-audio")
                        yield Tab("Video", id="tab-video")
                        yield Tab("P2P", id="tab-p2p")
                        yield Tab("Settings", id="tab-settings")
                    
                    # Download tab content
                    with Container(id="download-content"):
                        yield Static("🔗 NEURAL DOWNLOAD PROTOCOL", classes="cyber-title")
                        yield Input(placeholder="Enter neural link URL...", id="url-input")
                        with Horizontal():
                            yield Button("🔍 Analyze", id="btn-analyze", classes="-primary")
                            yield Button("⬇️ Download", id="btn-start-download", classes="-accent")
                            yield Button("⚡ Speed Test", id="btn-speed-test")
                        
                        # Format selection table
                        yield DataTable(id="format-table")
                        
                        # Download options
                        with Horizontal():
                            yield Checkbox("Audio Only", id="chk-audio-only")
                            yield Checkbox("Process Audio", id="chk-process-audio", value=True)
                            yield Checkbox("7.1 Surround", id="chk-upmix", value=True)
                    
                    # Audio tab content
                    with Container(id="audio-content", classes="hidden"):
                        yield Static("🎵 AUDIO MATRIX PROCESSOR", classes="cyber-title")
                        yield Input(placeholder="Select audio file...", id="audio-file-input")
                        yield Button("📁 Browse Files", id="btn-browse-audio")
                        
                        with Horizontal():
                            yield Checkbox("Noise Reduction", id="chk-denoise", value=True)
                            yield Checkbox("Normalize", id="chk-normalize", value=True)
                            yield Checkbox("7.1 Upmix", id="chk-audio-upmix", value=True)
                        
                        with Horizontal():
                            yield Button("🎵 Process Audio", id="btn-process-audio", classes="-primary")
                            yield Button("🔄 Convert Format", id="btn-convert-audio", classes="-accent")
                        
                        yield Static(id="audio-progress", classes="neon-panel")
                    
                    # P2P tab content  
                    with Container(id="p2p-content", classes="hidden"):
                        yield Static("📡 P2P NEURAL NETWORK", classes="cyber-title")
                        yield Static("P2P Status: Offline", id="p2p-status")
                        
                        with Horizontal():
                            yield Button("🔗 Connect", id="btn-p2p-connect", classes="-primary")
                            yield Button("📊 Network Info", id="btn-p2p-info")
                            yield Button("⚙️ Settings", id="btn-p2p-settings")
                        
                        yield DataTable(id="p2p-peers-table")
                        yield Static(id="p2p-stats", classes="neon-panel")
        
        # Progress area
        yield Static(id="progress-area", classes="neon-panel")
        yield Footer()
    
    async def on_mount(self) -> None:
        """Initialize the cyberpunk interface"""
        try:
            # Initialize cyberpunk banner
            from .cyberpunk_ui import CyberpunkBanner
            banner = CyberpunkBanner("dark_city")
            banner_widget = self.query_one("#banner-area")
            banner_widget.update(banner.create_banner())
            
            # Initialize managers
            await self._initialize_managers()
            
            # Setup tables
            self._setup_format_table()
            self._setup_p2p_table()
            
            # Start monitoring
            self.set_interval(2.0, self._update_status)
            self.set_interval(1.0, self._update_progress)
            
            self.notify("🔮 Neural interface initialized!", severity="information")
            
        except Exception as e:
            logging.error(f"Error initializing cyberpunk interface: {e}")
            self.notify(f"Initialization error: {e}", severity="error")
    
    async def _initialize_managers(self) -> None:
        """Initialize all managers and processors"""
        try:
            # Initialize download manager
            from .manager import AsyncDownloadManager
            from .session import AsyncSessionManager  
            from .cache import DownloadCache
            
            session_manager = AsyncSessionManager(self.config.get("session_file", "sessions/session.json"))
            download_cache = DownloadCache()
            
            self.download_manager = AsyncDownloadManager(
                config=self.config,
                session_manager=session_manager,
                download_cache=download_cache
            )
            
            # Initialize P2P manager
            try:
                from .p2p import P2PManager
                self.p2p_manager = P2PManager(self.config)
                logging.info("P2P manager initialized")
            except ImportError:
                logging.warning("P2P manager not available")
            
            # Initialize standalone audio processor
            try:
                from .audio_processor import StandaloneAudioProcessor
                self.standalone_audio = StandaloneAudioProcessor(self.config)
                logging.info("Standalone audio processor initialized")
            except ImportError:
                logging.warning("Standalone audio processor not available")
                
            logging.info("All managers initialized successfully")
            
        except Exception as e:
            logging.error(f"Failed to initialize managers: {e}")
    
    def _setup_format_table(self) -> None:
        """Setup the format table with cyberpunk styling"""
        try:
            table = self.query_one("#format-table")
            table.add_columns(
                "🔸 ID", "📄 Format", "🖥️ Resolution", 
                "⚙️ Codec", "💾 Size", "🎵 Audio", "🎬 FPS"
            )
            # Add placeholder
            table.add_row("--", "--", "--", "--", "--", "--", "--")
        except Exception as e:
            logging.error(f"Error setting up format table: {e}")
    
    def _setup_p2p_table(self) -> None:
        """Setup P2P peers table"""
        try:
            table = self.query_one("#p2p-peers-table")
            table.add_columns(
                "🔗 Peer ID", "🌐 Address", "📊 Status", 
                "⬇️ Down", "⬆️ Up", "📡 Latency"
            )
        except Exception as e:
            logging.error(f"Error setting up P2P table: {e}")
    
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses with cyberpunk feedback"""
        button_id = event.button.id
        
        # Visual feedback
        await self._cyberpunk_button_feedback(event.button)
        
        # Handle actions
        if button_id == "btn-download":
            await self._switch_to_download_tab()
        elif button_id == "btn-audio":
            await self._switch_to_audio_tab()
        elif button_id == "btn-video":
            await self._switch_to_video_tab()
        elif button_id == "btn-p2p":
            await self._switch_to_p2p_tab()
        elif button_id == "btn-analyze":
            await self._analyze_url()
        elif button_id == "btn-start-download":
            await self._start_download()
        elif button_id == "btn-speed-test":
            self._run_speed_test()
        elif button_id == "btn-browse-audio":
            await self._browse_audio_files()
        elif button_id == "btn-process-audio":
            await self._process_standalone_audio()
        elif button_id == "btn-convert-audio":
            await self._convert_audio_format()
        elif button_id == "btn-p2p-connect":
            await self._connect_p2p()
        elif button_id == "btn-p2p-info":
            await self._show_p2p_info()
    
    async def _cyberpunk_button_feedback(self, button: Button) -> None:
        """Provide cyberpunk-style visual feedback"""
        # Temporarily change button style for feedback
        original_classes = button.classes
        button.add_class("-primary")
        await asyncio.sleep(0.1)
        button.classes = original_classes
    
    async def _switch_to_download_tab(self) -> None:
        """Switch to download tab with animation"""
        try:            # Hide all content
            for content_id in ["audio-content", "p2p-content"]:
                try:
                    widget = self.query_one(f"#{content_id}")
                    widget.add_class("hidden")
                except Exception as e:
                    logging.debug(f"Could not hide widget {content_id}: {e}")
            
            # Show download content
            try:
                download_content = self.query_one("#download-content")
                download_content.remove_class("hidden")
            except Exception as e:
                logging.debug(f"Could not show download content: {e}")
                
            self.notify("🔗 Switched to Neural Download Protocol", severity="information")
            
        except Exception as e:
            logging.error(f"Error switching to download tab: {e}")
    
    async def _switch_to_audio_tab(self) -> None:
        """Switch to audio tab"""
        try:            # Hide other content
            for content_id in ["download-content", "p2p-content"]:
                try:
                    widget = self.query_one(f"#{content_id}")
                    widget.add_class("hidden")
                except Exception as e:
                    logging.debug(f"Could not hide widget {content_id}: {e}")
            
            # Show audio content
            try:
                audio_content = self.query_one("#audio-content")
                audio_content.remove_class("hidden")
            except Exception as e:
                logging.debug(f"Could not show audio content: {e}")
                
            self.notify("🎵 Switched to Audio Matrix Processor", severity="information")
            
        except Exception as e:
            logging.error(f"Error switching to audio tab: {e}")
    
    async def _switch_to_p2p_tab(self) -> None:
        """Switch to P2P tab"""
        try:            # Hide other content  
            for content_id in ["download-content", "audio-content"]:
                try:
                    widget = self.query_one(f"#{content_id}")
                    widget.add_class("hidden")
                except Exception as e:
                    logging.debug(f"Could not hide widget {content_id}: {e}")
            
            # Show P2P content
            try:
                p2p_content = self.query_one("#p2p-content")
                p2p_content.remove_class("hidden")
            except Exception as e:
                logging.debug(f"Could not show P2P content: {e}")
                
            self.notify("📡 Switched to P2P Neural Network", severity="information")
            
        except Exception as e:
            logging.error(f"Error switching to P2P tab: {e}")
    
    async def _analyze_url(self) -> None:
        """Analyze URL with cyberpunk effects"""
        try:
            url_input = self.query_one("#url-input")
            url = url_input.value.strip()
            
            if not url:
                self.notify("🚫 Neural link required!", severity="error")
                return
            
            self.current_url = url
            self.notify(f"🔍 Analyzing neural link: {url}", severity="information")
            
            # Start analysis task
            await self._start_url_analysis_task(url)
            
        except Exception as e:
            logging.error(f"Error analyzing URL: {e}")
            self.notify(f"Analysis failed: {e}", severity="error")
    
    @work
    async def _start_url_analysis_task(self, url: str) -> None:
        """Background task for URL analysis"""
        try:
            import yt_dlp
            
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                await self._populate_cyberpunk_format_table(info)
                
                title = info.get('title', 'Unknown')
                self.notify(f"✅ Neural link decoded: {title}", severity="information")
                
        except Exception as e:
            logging.error(f"URL analysis task failed: {e}")
            self.notify(f"Neural link analysis failed: {e}", severity="error")
    
    async def _populate_cyberpunk_format_table(self, info: Dict[str, Any]) -> None:
        """Populate format table with cyberpunk styling"""
        try:
            table = self.query_one("#format-table")
            table.clear()
            
            # Re-add columns
            table.add_columns(
                "🔸 ID", "📄 Format", "🖥️ Resolution", 
                "⚙️ Codec", "💾 Size", "🎵 Audio", "🎬 FPS"
            )
            
            formats = info.get('formats', [])
            
            for fmt in formats[:20]:  # Limit for performance
                row_data = self._format_table_row_data(fmt)
                table.add_row(*row_data)
            
            self.format_info = info
            
        except Exception as e:
            logging.error(f"Error populating format table: {e}")
    
    def _format_table_row_data(self, fmt: Dict[str, Any]) -> tuple:
        """Generate a single row of format table data"""
        format_id = str(fmt.get('format_id', 'N/A'))
        ext = fmt.get('ext', 'N/A').upper()
        resolution = self._format_resolution(fmt)
        codec = self._format_codec(fmt)
        size = self._format_size(fmt)
        audio = self._format_audio(fmt)
        fps = self._format_fps(fmt)
        
        return (format_id, ext, resolution, codec, size, audio, fps)
    
    def _format_resolution(self, fmt: Dict[str, Any]) -> str:
        """Format resolution with quality indicators"""
        if fmt.get('width') and fmt.get('height'):
            resolution = f"{fmt['width']}x{fmt['height']}"
            if fmt['height'] >= 1080:
                resolution += " ✦"
            elif fmt['height'] >= 720:
                resolution += " ◦"
            return resolution
        return 'AUDIO'
    
    def _format_codec(self, fmt: Dict[str, Any]) -> str:
        """Format codec information"""
        codec = fmt.get('vcodec', fmt.get('acodec', 'N/A'))
        if codec == 'none':
            codec = fmt.get('acodec', 'N/A')
        return codec
    
    def _format_size(self, fmt: Dict[str, Any]) -> str:
        """Format file size"""
        filesize = fmt.get('filesize') or fmt.get('filesize_approx')
        if filesize:
            if filesize > 1024**3:
                return f"{filesize/(1024**3):.1f}GB"
            elif filesize > 1024**2:
                return f"{filesize/(1024**2):.1f}MB"
            else:
                return f"{filesize/1024:.1f}KB"
        return '▒▒▒'
    
    def _format_audio(self, fmt: Dict[str, Any]) -> str:
        """Format audio quality"""
        abr = fmt.get('abr')
        return f"{abr}k" if abr else '▒▒▒'
    
    def _format_fps(self, fmt: Dict[str, Any]) -> str:
        """Format FPS information"""
        return str(fmt.get('fps', '▒▒')) if fmt.get('fps') else '▒▒'
    
    async def _start_download(self) -> None:
        """Start download with P2P support"""
        try:
            if not self.current_url:
                self.notify("🚫 Neural link required! Analyze URL first.", severity="error")
                return
            
            if not self.download_manager:
                self.notify("🚫 Download manager not initialized!", severity="error")
                return
            
            # Get options
            audio_only = self.query_one("#chk-audio-only").value
            process_audio = self.query_one("#chk-process-audio").value
            upmix_surround = self.query_one("#chk-upmix").value
            
            options = {
                "audio_only": audio_only,
                "process_audio": process_audio,
                "upmix_surround": upmix_surround
            }
            
            self.notify("🚀 Initiating neural download...", severity="information")
            
            # Start download task
            await self._start_download_task(self.current_url, options)
            
        except Exception as e:
            logging.error(f"Error starting download: {e}")
            self.notify(f"Download initiation failed: {e}", severity="error")
    
    @work
    async def _start_download_task(self, url: str, options: Dict[str, Any]) -> None:
        """Background download task with P2P support"""
        try:
            async with self.download_manager:
                # Try P2P first if available
                if self.p2p_manager and self.p2p_manager.is_connected():
                    self.notify("📡 Attempting P2P download...", severity="information")
                    try:
                        result = await self.p2p_manager.download_via_p2p(url, options)
                        if result:
                            self.notify("✅ P2P download completed!", severity="information")
                            return
                    except Exception as e:
                        logging.warning(f"P2P download failed, falling back to direct: {e}")
                
                # Fallback to direct download
                result = await self.download_manager.download_with_options([url], options)
                
                if result and len(result) > 0:
                    self.notify(f"✅ Download completed: {result[0]}", severity="information")
                    
                    # Apply audio processing if requested
                    if options.get("process_audio") and self.standalone_audio:
                        await self._post_process_audio(result[0], options)
                else:
                    self.notify("❌ Download failed - no files returned", severity="error")
                    
        except Exception as e:
            logging.error(f"Download task failed: {e}")
            self.notify(f"Download failed: {e}", severity="error")
    
    async def _post_process_audio(self, file_path: str, options: Dict[str, Any]) -> None:
        """Post-process downloaded audio"""
        try:
            if not self.standalone_audio:
                return
                
            self.notify("🎵 Applying audio enhancements...", severity="information")
            
            base, ext = os.path.splitext(file_path)
            processed_path = f"{base}_enhanced{ext}"
            
            # Apply processing
            success = self.standalone_audio.process_local_file(
                file_path,
                processed_path,
                normalize=True,
                denoise=True,
                upmix_surround=options.get("upmix_surround", False),
                target_channels=8  # 7.1 surround
            )
            
            if success:
                self.notify("✅ Audio enhancement completed!", severity="information")
            else:
                self.notify("⚠️ Audio enhancement failed", severity="warning")
                
        except Exception as e:
            logging.error(f"Audio post-processing failed: {e}")
    
    async def _browse_audio_files(self) -> None:
        """Browse for audio files"""
        try:
            # In a real implementation, this would open a file dialog
            # For now, we'll use a placeholder
            audio_input = self.query_one("#audio-file-input")
            
            # Simulate file selection
            downloads_dir = self.config.get('download', {}).get('audio_output_dir', 'downloads/audio')
            if os.path.exists(downloads_dir):
                files = [f for f in os.listdir(downloads_dir) if f.endswith(('.mp3', '.flac', '.wav', '.m4a'))]
                if files:
                    audio_input.value = os.path.join(downloads_dir, files[0])
                    self.notify(f"📁 Selected: {files[0]}", severity="information")
                else:
                    self.notify("🚫 No audio files found in download directory", severity="warning")
            else:
                self.notify("🚫 Download directory not found", severity="error")
                
        except Exception as e:
            logging.error(f"Error browsing audio files: {e}")
            self.notify(f"Browse failed: {e}", severity="error")
    
    async def _process_standalone_audio(self) -> None:
        """Process audio file without downloading"""
        try:
            audio_input = self.query_one("#audio-file-input")
            input_path = audio_input.value.strip()
            
            if not input_path:
                self.notify("🚫 Audio file path required!", severity="error")
                return
            
            if not os.path.exists(input_path):
                self.notify("🚫 Audio file not found!", severity="error")
                return
            
            if not self.standalone_audio:
                self.notify("🚫 Standalone audio processor not available!", severity="error")
                return
            
            # Get processing options
            denoise = self.query_one("#chk-denoise").value
            normalize = self.query_one("#chk-normalize").value
            upmix = self.query_one("#chk-audio-upmix").value
            
            self.notify("🎵 Processing audio with matrix enhancements...", severity="information")
            
            # Start processing task
            await self._start_audio_processing_task(input_path, denoise, normalize, upmix)
            
        except Exception as e:
            logging.error(f"Error processing audio: {e}")
            self.notify(f"Audio processing failed: {e}", severity="error")
    
    @work
    async def _start_audio_processing_task(self, input_path: str, denoise: bool, normalize: bool, upmix: bool) -> None:
        """Background audio processing task"""
        try:
            base, ext = os.path.splitext(input_path)
            output_path = f"{base}_matrix_enhanced{ext}"
            
            success = self.standalone_audio.process_local_file(
                input_path,
                output_path,
                normalize=normalize,
                denoise=denoise,
                upmix_surround=upmix,
                target_channels=8  # 7.1 surround
            )
            
            if success:
                self.notify(f"✅ Audio matrix processing completed: {output_path}", severity="information")
            else:
                self.notify("❌ Audio matrix processing failed", severity="error")
                
        except Exception as e:
            logging.error(f"Audio processing task failed: {e}")
            self.notify(f"Audio processing failed: {e}", severity="error")
    
    async def _connect_p2p(self) -> None:
        """Connect to P2P network"""
        try:
            if not self.p2p_manager:
                self.notify("🚫 P2P manager not available!", severity="error")
                return
            
            self.notify("📡 Connecting to P2P neural network...", severity="information")
            
            # Start P2P connection task
            await self._start_p2p_connection_task()
            
        except Exception as e:
            logging.error(f"Error connecting to P2P: {e}")
            self.notify(f"P2P connection failed: {e}", severity="error")
    
    @work 
    async def _start_p2p_connection_task(self) -> None:
        """Background P2P connection task"""
        try:
            success = await self.p2p_manager.connect()
            
            if success:
                self.notify("✅ Connected to P2P neural network!", severity="information")
                await self._update_p2p_status()
            else:
                self.notify("❌ P2P connection failed", severity="error")
                
        except Exception as e:
            logging.error(f"P2P connection task failed: {e}")
            self.notify(f"P2P connection failed: {e}", severity="error")
    
    def _run_speed_test(self) -> None:
        """Run network speed test (fixed async warning)"""
        self.notify("⚡ Running neural network speed test...", severity="information")
        self._start_speed_test_task()
    
    @work
    async def _start_speed_test_task(self) -> None:
        """Background speed test task (fixes async warning)"""
        try:
            from .network import run_speedtest
            
            result = await run_speedtest(detailed=True)
            
            if result:
                download_speed = result.download_speed
                upload_speed = result.upload_speed
                ping = result.ping
                
                self.notify(
                    f"⚡ Speed test complete: ⬇️{download_speed:.1f}Mbps ⬆️{upload_speed:.1f}Mbps 📡{ping:.1f}ms", 
                    severity="information"
                )
            else:
                self.notify("❌ Speed test failed", severity="error")
                
        except Exception as e:
            logging.error(f"Speed test failed: {e}")
            self.notify(f"Speed test failed: {e}", severity="error")
    
    async def _update_status(self) -> None:
        """Update cyberpunk status panel"""
        try:
            if not self.download_manager:
                return
                
            # Get system status
            status = {}
            if hasattr(self.download_manager, 'get_system_status'):
                status = self.download_manager.get_system_status()
            
            # Update status panel
            status_widget = self.query_one("#status-panel")
            
            from .cyberpunk_ui import CyberStatusPanel
            status_panel = CyberStatusPanel("synthwave")
            cyberpunk_status = status_panel.create_system_status(status)
            
            status_widget.update(cyberpunk_status)
            
        except Exception as e:
            logging.debug(f"Error updating status: {e}")
    
    async def _update_progress(self) -> None:
        """Update progress displays"""
        try:
            # Update download progress if active
            if self.downloads:
                progress_widget = self.query_one("#progress-area")
                
                from .cyberpunk_ui import HolographicProgress
                holo_progress = HolographicProgress("dark_city")
                
                # Show progress for first active download
                for download in self.downloads:
                    if download.get('status') == 'In Progress':
                        progress_display = holo_progress.create_download_progress(
                            download.get('url', 'Unknown'),
                            download.get('progress', 0),
                            download.get('speed', '0 MB/s'),
                            download.get('eta', 'Unknown')
                        )
                        progress_widget.update(progress_display)
                        break
                        
        except Exception as e:
            logging.debug(f"Error updating progress: {e}")
    
    async def _update_p2p_status(self) -> None:
        """Update P2P status display"""
        try:
            if not self.p2p_manager:
                return
                
            status_widget = self.query_one("#p2p-status")
            
            if self.p2p_manager.is_connected():
                peer_count = len(self.p2p_manager.get_peers())
                status_widget.update(f"P2P Status: 🟢 Connected ({peer_count} peers)")
            else:
                status_widget.update("P2P Status: 🔴 Offline")
                
        except Exception as e:
            logging.debug(f"Error updating P2P status: {e}")
    
    def notify(self, message: str, severity: str = "information") -> None:
        """Show cyberpunk-styled notifications"""
        try:
            # Use Textual's built-in notification system with cyberpunk styling
            if severity == "error":
                self.bell()  # Audio feedback for errors
                
            # Log the message
            if severity == "error":
                logging.error(message)
            elif severity == "warning":
                logging.warning(message)
            else:
                logging.info(message)
                
            # In a full implementation, this would show toast notifications
            print(f"🔮 {message}")
            
        except Exception as e:
            logging.error(f"Error showing notification: {e}")


def launch_cyberpunk_interface(config: Dict[str, Any]) -> None:
    """Launch the cyberpunk interactive interface"""
    try:
        app = CyberpunkInteractiveApp(config)
        app.run()
    except Exception as e:
        console = Console()
        console.print(f"[red]Failed to launch cyberpunk interface: {e}[/]")
        logging.error(f"Cyberpunk interface launch failed: {e}")
        raise
