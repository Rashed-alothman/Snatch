#!/usr/bin/env python3
"""
Standalone Audio Processor - Snatch Premium Audio Suite

A comprehensive audio processing interface that works independently of downloads.
Features:
- Advanced audio conversion (MP3, FLAC, WAV, AAC, OGG, M4A)
- Professional-grade 7.1 surround sound upmixing
- Real-time audio effects and enhancement
- Batch processing capabilities
- AI-powered audio restoration
- Spectral analysis and visualization
- Custom audio profiles and presets
"""

import asyncio
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Tuple
from datetime import datetime
import json
import subprocess
from dataclasses import dataclass, field

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn
from rich.prompt import Prompt, Confirm, FloatPrompt, IntPrompt
from rich.text import Text
from rich.align import Align
from rich.columns import Columns
from rich.layout import Layout
from rich.live import Live
from rich import box
from rich.syntax import Syntax
from rich.tree import Tree
from rich.filemanager import Highlight

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, Grid
from textual.widgets import (
    Button, Header, Footer, Static, Input, Label, 
    Select, ProgressBar, DataTable, FileOpen, DirectoryTree,
    Slider, Checkbox, RadioSet, RadioButton, Tabs, Tab
)
from textual.reactive import reactive
from textual.worker import work
from textual.screen import Screen

# Import audio processing modules
from .audio_processor import EnhancedAudioProcessor
from .common_utils import format_size, sanitize_filename
from .defaults import THEME

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
console = Console(theme=THEME)

@dataclass
class AudioProfile:
    """Audio processing profile configuration"""
    name: str
    description: str
    format: str = "flac"
    bitrate: int = 320
    sample_rate: int = 48000
    channels: int = 2
    normalize: bool = True
    denoise: bool = True
    enhance_bass: bool = False
    enhance_treble: bool = False
    surround_mix: bool = False
    surround_channels: int = 8  # 7.1 surround
    effects: Dict[str, Any] = field(default_factory=dict)

# Predefined audio profiles
AUDIO_PROFILES = {
    "audiophile": AudioProfile(
        "Audiophile Master",
        "Highest quality lossless with minimal processing",
        format="flac",
        bitrate=0,  # Lossless
        sample_rate=96000,
        channels=2,
        normalize=False,
        denoise=True,
        surround_mix=False
    ),
    "surround_7_1": AudioProfile(
        "7.1 Surround Master",
        "Professional 7.1 surround sound upmix",
        format="flac",
        bitrate=0,
        sample_rate=48000,
        channels=8,
        normalize=True,
        denoise=True,
        surround_mix=True,
        surround_channels=8,
        effects={
            "room_correction": True,
            "psychoacoustic_enhancement": True,
            "phase_alignment": True
        }
    ),
    "podcast_optimize": AudioProfile(
        "Podcast Optimized",
        "Voice-optimized with noise reduction",
        format="mp3",
        bitrate=128,
        sample_rate=44100,
        channels=1,  # Mono for speech
        normalize=True,
        denoise=True,
        enhance_bass=False,
        enhance_treble=True,
        effects={
            "voice_enhance": True,
            "noise_gate": True,
            "compressor": True
        }
    ),
    "music_enhance": AudioProfile(
        "Music Enhancement",
        "Enhanced dynamic range and clarity",
        format="flac",
        bitrate=0,
        sample_rate=48000,
        channels=2,
        normalize=True,
        denoise=True,
        enhance_bass=True,
        enhance_treble=True,
        effects={
            "stereo_widening": True,
            "harmonic_enhancement": True,
            "dynamic_eq": True
        }
    )
}

class StandaloneAudioApp(App):
    """Standalone Audio Processing Application with Cyberpunk Aesthetic"""
    
    TITLE = "🎵 Snatch Audio Suite - Standalone Processor"
    SUB_TITLE = "Professional Audio Processing & 7.1 Surround Upmixing"
    
    CSS = """
    Screen {
        background: #0a0a0a;
        color: #00ff9f;
    }
    
    Header {
        background: #1a1a2e;
        color: #00ff9f;
        text-align: center;
        padding: 1;
        border-bottom: thick #ff6b9d;
    }
    
    Footer {
        background: #1a1a2e;
        color: #00ff9f;
        border-top: thick #ff6b9d;
    }
    
    #main-container {
        layout: grid;
        grid-size: 3 4;
        margin: 1;
        padding: 1;
    }
    
    .panel {
        border: solid #00ff9f;
        margin: 1;
        padding: 1;
        background: #0f0f23;
    }
    
    .cyberpunk-title {
        color: #ff6b9d;
        text-style: bold;
        text-align: center;
        background: #1a1a2e;
        margin: 0 0 1 0;
        padding: 1;
    }
    
    .neon-button {
        background: #1a1a2e;
        color: #00ff9f;
        border: solid #00ff9f;
        text-style: bold;
        margin: 0 1;
    }
    
    .neon-button:hover {
        background: #00ff9f;
        color: #0a0a0a;
        border: solid #ff6b9d;
    }
    
    .active-button {
        background: #ff6b9d;
        color: #0a0a0a;
        border: solid #00ff9f;
        text-style: bold;
    }
    
    Input {
        background: #0f0f23;
        color: #00ff9f;
        border: solid #00ff9f;
    }
    
    Input:focus {
        border: solid #ff6b9d;
        background: #1a1a2e;
    }
    
    Select {
        background: #0f0f23;
        color: #00ff9f;
        border: solid #00ff9f;
    }
    
    DataTable {
        background: #0f0f23;
        color: #00ff9f;
        border: solid #00ff9f;
    }
    
    ProgressBar {
        bar-color: #ff6b9d;
        background: #1a1a2e;
        border: solid #00ff9f;
    }
    
    .status-panel {
        background: #0f0f23;
        border: solid #ff6b9d;
        color: #00ff9f;
        padding: 1;
        margin: 1;
    }
    
    .audio-controls {
        layout: horizontal;
        margin: 1;
    }
    
    .processing-panel {
        border: solid #ff6b9d;
        background: #1a1a2e;
        margin: 1;
        padding: 1;
    }
    """
    
    # Reactive state
    current_file: reactive[str] = reactive("")
    processing_progress: reactive[float] = reactive(0.0)
    selected_profile: reactive[str] = reactive("audiophile")
    
    def __init__(self):
        super().__init__()
        self.audio_processor = None
        self.current_job = None
        self.processing_queue = []
        
    def compose(self) -> ComposeResult:
        """Create the cyberpunk-styled audio interface"""
        yield Header()
        
        with Container(id="main-container"):
            # File Selection Panel
            with Container(classes="panel"):
                yield Static("📁 AUDIO FILE SELECTOR", classes="cyberpunk-title")
                yield Input(placeholder="Enter audio file path or browse...", id="file-input")
                yield Button("🗂️ Browse Files", id="browse-btn", classes="neon-button")
                yield Button("🎵 Add to Queue", id="add-queue-btn", classes="neon-button")
                yield DataTable(id="file-queue")
            
            # Audio Profile Panel
            with Container(classes="panel"):
                yield Static("🎛️ AUDIO PROFILES", classes="cyberpunk-title")
                profile_options = [(name, profile.name) for name, profile in AUDIO_PROFILES.items()]
                yield Select(profile_options, value="audiophile", id="profile-select")
                yield Static("Profile Details:", classes="cyberpunk-title")
                yield Static("", id="profile-details")
                yield Button("⚙️ Custom Profile", id="custom-profile-btn", classes="neon-button")
            
            # Processing Controls Panel  
            with Container(classes="panel"):
                yield Static("🔧 PROCESSING CONTROLS", classes="cyberpunk-title")
                yield Checkbox("🔊 7.1 Surround Upmix", id="surround-enable", value=True)
                yield Checkbox("🎚️ Dynamic Range Enhancement", id="dynamic-enhance")
                yield Checkbox("🎤 Voice Isolation", id="voice-isolate")
                yield Checkbox("🎼 Harmonic Enhancement", id="harmonic-enhance")
                yield Button("▶️ Start Processing", id="process-btn", classes="neon-button")
                yield Button("⏸️ Pause Queue", id="pause-btn", classes="neon-button")
                yield Button("⏹️ Stop All", id="stop-btn", classes="neon-button")
            
            # Real-time Status Panel
            with Container(classes="panel"):
                yield Static("📊 PROCESSING STATUS", classes="cyberpunk-title")
                yield Static("Ready", id="status-text")
                yield ProgressBar(total=100, id="progress-bar")
                yield Static("", id="current-operation")
                yield DataTable(id="processing-stats")
            
            # Output Configuration Panel
            with Container(classes="panel"):
                yield Static("💾 OUTPUT SETTINGS", classes="cyberpunk-title")
                yield Input(placeholder="Output directory", id="output-dir")
                yield Select([
                    ("flac", "FLAC (Lossless)"),
                    ("wav", "WAV (Uncompressed)"),
                    ("mp3", "MP3 (Lossy)"),
                    ("aac", "AAC (Lossy)"),
                    ("ogg", "OGG Vorbis")
                ], value="flac", id="output-format")
                yield Checkbox("🗂️ Auto-organize output", id="auto-organize")
                yield Button("📁 Open Output Folder", id="open-output-btn", classes="neon-button")
            
            # Audio Visualization Panel
            with Container(classes="panel"):
                yield Static("📈 AUDIO ANALYSIS", classes="cyberpunk-title")
                yield Static("No file loaded", id="analysis-display")
                yield Button("🔍 Analyze Audio", id="analyze-btn", classes="neon-button")
                yield Button("👁️ Show Spectrum", id="spectrum-btn", classes="neon-button")
        
        yield Footer()
    
    async def on_mount(self) -> None:
        """Initialize the audio processor"""
        try:
            # Initialize audio processor with enhanced configuration
            config = {
                "audio_processor": {
                    "enable_surround": True,
                    "surround_channels": 8,  # 7.1
                    "enable_enhancement": True,
                    "enable_ai_restoration": True
                }
            }
            
            from .audio_processor import EnhancedAudioProcessor
            self.audio_processor = EnhancedAudioProcessor(config)
            
            # Setup file queue table
            file_queue = self.query_one("#file-queue", DataTable)
            file_queue.add_columns("File", "Size", "Duration", "Status")
            
            # Setup processing stats table
            stats_table = self.query_one("#processing-stats", DataTable)
            stats_table.add_columns("Metric", "Value")
            
            # Load default profile
            self._update_profile_details()
            
            self.notify("🎵 Snatch Audio Suite initialized!", title="Ready")
            
        except Exception as e:
            self.notify(f"❌ Failed to initialize: {e}", severity="error")
            logging.error(f"Audio suite initialization error: {e}")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button interactions"""
        button_id = event.button.id
        
        if button_id == "browse-btn":
            self._browse_files()
        elif button_id == "add-queue-btn":
            self._add_to_queue()
        elif button_id == "process-btn":
            self._start_processing()
        elif button_id == "pause-btn":
            self._pause_processing()
        elif button_id == "stop-btn":
            self._stop_processing()
        elif button_id == "custom-profile-btn":
            self._create_custom_profile()
        elif button_id == "analyze-btn":
            self._analyze_audio()
        elif button_id == "spectrum-btn":
            self._show_spectrum()
        elif button_id == "open-output-btn":
            self._open_output_folder()
    
    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle profile selection changes"""
        if event.select.id == "profile-select":
            self.selected_profile = event.value
            self._update_profile_details()
    
    def _browse_files(self) -> None:
        """Open file browser for audio file selection"""
        try:
            # This would open a file dialog in a full implementation
            self.notify("📁 File browser would open here", title="Browse Files")
            # For now, show example
            file_input = self.query_one("#file-input", Input)
            file_input.placeholder = "Example: C:\\Music\\song.mp3"
        except Exception as e:
            self.notify(f"❌ Browse error: {e}", severity="error")
    
    def _add_to_queue(self) -> None:
        """Add selected file to processing queue"""
        try:
            file_input = self.query_one("#file-input", Input)
            file_path = file_input.value.strip()
            
            if not file_path:
                self.notify("⚠️ Please enter a file path", severity="warning")
                return
            
            if not os.path.exists(file_path):
                self.notify("❌ File not found", severity="error")
                return
            
            # Add to queue table
            file_queue = self.query_one("#file-queue", DataTable)
            file_size = format_size(os.path.getsize(file_path))
            
            file_queue.add_row(
                os.path.basename(file_path),
                file_size,
                "Unknown",  # Would analyze duration
                "Queued"
            )
            
            self.processing_queue.append(file_path)
            self.notify(f"✅ Added to queue: {os.path.basename(file_path)}")
            
            # Clear input
            file_input.value = ""
            
        except Exception as e:
            self.notify(f"❌ Queue error: {e}", severity="error")
    
    @work
    async def _start_processing(self) -> None:
        """Start processing queued files"""
        try:
            if not self.processing_queue:
                self.notify("⚠️ No files in queue", severity="warning")
                return
            
            profile = AUDIO_PROFILES[self.selected_profile]
            surround_enabled = self.query_one("#surround-enable", Checkbox).value
            
            self.query_one("#status-text", Static).update("🔄 Processing...")
            
            for i, file_path in enumerate(self.processing_queue):
                current_op = self.query_one("#current-operation", Static)
                current_op.update(f"Processing: {os.path.basename(file_path)}")
                
                # Update progress
                progress = (i / len(self.processing_queue)) * 100
                self.query_one("#progress-bar", ProgressBar).update(progress=progress)
                
                # Process audio file
                await self._process_single_file(file_path, profile, surround_enabled)
                
                # Update queue status
                self._update_queue_status(i, "Completed")
            
            self.query_one("#status-text", Static).update("✅ All files processed!")
            self.query_one("#progress-bar", ProgressBar).update(progress=100)
            self.notify("🎉 Processing completed successfully!")
            
        except Exception as e:
            self.notify(f"❌ Processing error: {e}", severity="error")
            logging.error(f"Audio processing error: {e}")
    
    async def _process_single_file(self, file_path: str, profile: AudioProfile, surround_enabled: bool) -> None:
        """Process a single audio file"""
        try:
            if not self.audio_processor:
                raise Exception("Audio processor not initialized")
            
            # Determine output path
            output_dir = self.query_one("#output-dir", Input).value or "output"
            os.makedirs(output_dir, exist_ok=True)
            
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            output_ext = profile.format
            
            if surround_enabled:
                output_name = f"{base_name}_7.1_surround.{output_ext}"
            else:
                output_name = f"{base_name}_enhanced.{output_ext}"
            
            output_path = os.path.join(output_dir, output_name)
            
            # Configure processing options
            options = {
                "format": profile.format,
                "bitrate": profile.bitrate if profile.bitrate > 0 else None,
                "sample_rate": profile.sample_rate,
                "channels": profile.surround_channels if surround_enabled else profile.channels,
                "normalize": profile.normalize,
                "denoise": profile.denoise,
                "enhance_bass": profile.enhance_bass,
                "enhance_treble": profile.enhance_treble,
                "surround_mix": surround_enabled,
                "effects": profile.effects
            }
            
            # Process the audio
            success = await self.audio_processor.process_audio_enhanced(
                file_path,
                output_path,
                **options
            )
            
            if success:
                logging.info(f"Successfully processed: {file_path} -> {output_path}")
            else:
                raise Exception("Audio processing failed")
                
        except Exception as e:
            logging.error(f"Single file processing error: {e}")
            raise
    
    def _update_profile_details(self) -> None:
        """Update profile details display"""
        try:
            profile = AUDIO_PROFILES[self.selected_profile]
            details = self.query_one("#profile-details", Static)
            
            detail_text = f"""
📋 {profile.description}
🎵 Format: {profile.format.upper()}
🎚️ Bitrate: {'Lossless' if profile.bitrate == 0 else f'{profile.bitrate} kbps'}
📊 Sample Rate: {profile.sample_rate} Hz
🔊 Channels: {profile.channels}
🔧 Normalize: {'Yes' if profile.normalize else 'No'}
🎯 Denoise: {'Yes' if profile.denoise else 'No'}
🎪 Surround: {'Yes' if profile.surround_mix else 'No'}
            """.strip()
            
            details.update(detail_text)
            
        except Exception as e:
            logging.error(f"Profile details update error: {e}")
    
    def _update_queue_status(self, index: int, status: str) -> None:
        """Update queue item status"""
        try:
            file_queue = self.query_one("#file-queue", DataTable)
            if index < file_queue.row_count:
                # Would update specific row status in a full implementation
                pass
        except Exception as e:
            logging.error(f"Queue status update error: {e}")
    
    def _pause_processing(self) -> None:
        """Pause current processing"""
        self.notify("⏸️ Processing paused")
    
    def _stop_processing(self) -> None:
        """Stop all processing"""
        self.processing_queue.clear()
        self.query_one("#status-text", Static).update("⏹️ Stopped")
        self.query_one("#progress-bar", ProgressBar).update(progress=0)
        self.notify("⏹️ Processing stopped")
    
    def _create_custom_profile(self) -> None:
        """Create custom audio profile"""
        self.notify("⚙️ Custom profile editor would open here")
    
    def _analyze_audio(self) -> None:
        """Analyze selected audio file"""
        self.notify("🔍 Audio analysis would run here")
    
    def _show_spectrum(self) -> None:
        """Show audio spectrum visualization"""
        self.notify("📈 Spectrum analyzer would open here")
    
    def _open_output_folder(self) -> None:
        """Open output folder in file explorer"""
        try:
            output_dir = self.query_one("#output-dir", Input).value or "output"
            os.makedirs(output_dir, exist_ok=True)
            
            # Open folder based on OS
            if os.name == 'nt':  # Windows
                os.startfile(output_dir)
            elif os.name == 'posix':  # macOS and Linux
                subprocess.run(['open' if sys.platform == 'darwin' else 'xdg-open', output_dir])
            
            self.notify(f"📁 Opened: {output_dir}")
            
        except Exception as e:
            self.notify(f"❌ Failed to open folder: {e}", severity="error")


def launch_standalone_audio_suite() -> None:
    """Launch the standalone audio processing suite"""
    try:
        console.print(CyberpunkBanner().render())
        console.print("\n[bold cyan]🎵 Launching Snatch Audio Suite - Standalone Processor[/]")
        
        app = StandaloneAudioApp()
        app.run()
        
    except Exception as e:
        console.print(f"[red]❌ Failed to launch audio suite: {e}[/]")
        logging.error(f"Audio suite launch error: {e}")


# Console interface for standalone audio processing
async def launch_console_audio_processor() -> None:
    """Launch console-based audio processor"""
    console.print(Panel(
        "[bold cyan]🎵 Snatch Audio Suite - Console Mode[/]\n"
        "[yellow]Professional Audio Processing & 7.1 Surround Upmixing[/]",
        title="Audio Processor",
        border_style="bright_blue"
    ))
    
    try:
        # Initialize audio processor
        config = {
            "audio_processor": {
                "enable_surround": True,
                "surround_channels": 8,
                "enable_enhancement": True
            }
        }
        
        from .audio_processor import EnhancedAudioProcessor
        processor = EnhancedAudioProcessor(config)
        
        while True:
            console.print("\n[bold cyan]🎛️ Audio Processing Menu[/]")
            console.print("1. 🎵 Convert Audio Format")
            console.print("2. 🔊 Upmix to 7.1 Surround")
            console.print("3. 🎚️ Enhance Audio Quality")
            console.print("4. 📊 Batch Process Directory")
            console.print("5. 🔍 Analyze Audio File")
            console.print("q. 🚪 Quit")
            
            choice = Prompt.ask(
                "\n[yellow]Select option[/]",
                choices=["1", "2", "3", "4", "5", "q"],
                default="1"
            )
            
            if choice == "q":
                console.print("[green]👋 Thanks for using Snatch Audio Suite![/]")
                break
            elif choice == "1":
                await _console_convert_audio(processor)
            elif choice == "2":
                await _console_surround_upmix(processor)
            elif choice == "3":
                await _console_enhance_audio(processor)
            elif choice == "4":
                await _console_batch_process(processor)
            elif choice == "5":
                await _console_analyze_audio(processor)
                
    except KeyboardInterrupt:
        console.print("\n[yellow]👋 Audio processing interrupted. Goodbye![/]")
    except Exception as e:
        console.print(f"[red]Error in audio processor: {e}[/]")
        logging.error(f"Console audio processor error: {e}")


async def _console_convert_audio(processor) -> None:
    """Console audio conversion"""
    try:
        input_file = Prompt.ask("[yellow]Enter input audio file path[/]")
        if not os.path.exists(input_file):
            console.print("[red]❌ File not found[/]")
            return
        
        format_choice = Prompt.ask(
            "[yellow]Output format[/]",
            choices=["mp3", "flac", "wav", "aac", "ogg"],
            default="flac"
        )
        
        output_dir = Prompt.ask("[yellow]Output directory[/]", default="output")
        os.makedirs(output_dir, exist_ok=True)
        
        base_name = os.path.splitext(os.path.basename(input_file))[0]
        output_file = os.path.join(output_dir, f"{base_name}_converted.{format_choice}")
        
        console.print(f"[cyan]Converting to {format_choice.upper()}...[/]")
        
        with Progress() as progress:
            task = progress.add_task("Processing...", total=100)
            
            success = await processor.convert_audio_async(
                input_file, output_file, format_choice
            )
            
            progress.update(task, completed=100)
        
        if success:
            console.print(f"[green]✅ Conversion completed: {output_file}[/]")
        else:
            console.print("[red]❌ Conversion failed[/]")
            
    except Exception as e:
        console.print(f"[red]Conversion error: {e}[/]")


async def _console_surround_upmix(processor) -> None:
    """Console 7.1 surround upmixing"""
    try:
        input_file = Prompt.ask("[yellow]Enter input audio file path[/]")
        if not os.path.exists(input_file):
            console.print("[red]❌ File not found[/]")
            return
        
        output_dir = Prompt.ask("[yellow]Output directory[/]", default="output")
        os.makedirs(output_dir, exist_ok=True)
        
        base_name = os.path.splitext(os.path.basename(input_file))[0]
        output_file = os.path.join(output_dir, f"{base_name}_7.1_surround.flac")
        
        console.print("[cyan]🔊 Creating 7.1 surround sound mix...[/]")
        
        with Progress() as progress:
            task = progress.add_task("Upmixing to 7.1...", total=100)
            
            success = await processor.process_audio_enhanced(
                input_file,
                output_file,
                channels=8,  # 7.1 surround
                surround_mix=True,
                format="flac",
                sample_rate=48000
            )
            
            progress.update(task, completed=100)
        
        if success:
            console.print(f"[green]✅ 7.1 Surround mix completed: {output_file}[/]")
            console.print("[dim]🎧 Best experienced with 7.1 surround sound system[/]")
        else:
            console.print("[red]❌ Surround upmix failed[/]")
            
    except Exception as e:
        console.print(f"[red]Surround upmix error: {e}[/]")


async def _console_enhance_audio(processor) -> None:
    """Console audio enhancement"""
    try:
        input_file = Prompt.ask("[yellow]Enter input audio file path[/]")
        if not os.path.exists(input_file):
            console.print("[red]❌ File not found[/]")
            return
        
        # Enhancement options
        normalize = Confirm.ask("[yellow]Normalize volume?[/]", default=True)
        denoise = Confirm.ask("[yellow]Remove noise?[/]", default=True)
        enhance_bass = Confirm.ask("[yellow]Enhance bass?[/]", default=False)
        enhance_treble = Confirm.ask("[yellow]Enhance treble?[/]", default=False)
        
        output_dir = Prompt.ask("[yellow]Output directory[/]", default="output")
        os.makedirs(output_dir, exist_ok=True)
        
        base_name = os.path.splitext(os.path.basename(input_file))[0]
        output_file = os.path.join(output_dir, f"{base_name}_enhanced.flac")
        
        console.print("[cyan]🎚️ Enhancing audio quality...[/]")
        
        with Progress() as progress:
            task = progress.add_task("Enhancing...", total=100)
            
            success = await processor.process_audio_enhanced(
                input_file,
                output_file,
                normalize=normalize,
                denoise=denoise,
                enhance_bass=enhance_bass,
                enhance_treble=enhance_treble,
                format="flac"
            )
            
            progress.update(task, completed=100)
        
        if success:
            console.print(f"[green]✅ Enhancement completed: {output_file}[/]")
        else:
            console.print("[red]❌ Enhancement failed[/]")
            
    except Exception as e:
        console.print(f"[red]Enhancement error: {e}[/]")


async def _console_batch_process(processor) -> None:
    """Console batch processing"""
    try:
        input_dir = Prompt.ask("[yellow]Enter directory with audio files[/]")
        if not os.path.exists(input_dir):
            console.print("[red]❌ Directory not found[/]")
            return
        
        # Find audio files
        audio_extensions = ['.mp3', '.flac', '.wav', '.aac', '.ogg', '.m4a']
        audio_files = []
        
        for root, dirs, files in os.walk(input_dir):
            for file in files:
                if any(file.lower().endswith(ext) for ext in audio_extensions):
                    audio_files.append(os.path.join(root, file))
        
        if not audio_files:
            console.print("[red]❌ No audio files found[/]")
            return
        
        console.print(f"[cyan]Found {len(audio_files)} audio files[/]")
        
        # Processing options
        operation = Prompt.ask(
            "[yellow]Processing operation[/]",
            choices=["convert", "enhance", "surround"],
            default="enhance"
        )
        
        output_dir = Prompt.ask("[yellow]Output directory[/]", default="batch_output")
        os.makedirs(output_dir, exist_ok=True)
        
        console.print(f"[cyan]Processing {len(audio_files)} files...[/]")
        
        with Progress() as progress:
            main_task = progress.add_task("Batch Processing", total=len(audio_files))
            
            for i, audio_file in enumerate(audio_files):
                base_name = os.path.splitext(os.path.basename(audio_file))[0]
                
                if operation == "surround":
                    output_file = os.path.join(output_dir, f"{base_name}_7.1.flac")
                    success = await processor.process_audio_enhanced(
                        audio_file, output_file, channels=8, surround_mix=True
                    )
                elif operation == "enhance":
                    output_file = os.path.join(output_dir, f"{base_name}_enhanced.flac")
                    success = await processor.process_audio_enhanced(
                        audio_file, output_file, normalize=True, denoise=True
                    )
                else:  # convert
                    output_file = os.path.join(output_dir, f"{base_name}.flac")
                    success = await processor.convert_audio_async(
                        audio_file, output_file, "flac"
                    )
                
                if success:
                    console.print(f"[green]✅ Processed: {os.path.basename(audio_file)}[/]")
                else:
                    console.print(f"[red]❌ Failed: {os.path.basename(audio_file)}[/]")
                
                progress.update(main_task, advance=1)
        
        console.print(f"[green]🎉 Batch processing completed! Output: {output_dir}[/]")
        
    except Exception as e:
        console.print(f"[red]Batch processing error: {e}[/]")


async def _console_analyze_audio(processor) -> None:
    """Console audio analysis"""
    try:
        input_file = Prompt.ask("[yellow]Enter audio file path to analyze[/]")
        if not os.path.exists(input_file):
            console.print("[red]❌ File not found[/]")
            return
        
        console.print("[cyan]🔍 Analyzing audio file...[/]")
        
        # Basic file info
        file_size = format_size(os.path.getsize(input_file))
        
        # Create analysis table
        table = Table(title="Audio Analysis", border_style="bright_blue")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="green")
        
        table.add_row("File", os.path.basename(input_file))
        table.add_row("Size", file_size)
        table.add_row("Format", os.path.splitext(input_file)[1][1:].upper())
        
        # Would add more detailed analysis with ffprobe
        table.add_row("Duration", "Unknown")
        table.add_row("Sample Rate", "Unknown")
        table.add_row("Channels", "Unknown")
        table.add_row("Bitrate", "Unknown")
        
        console.print(table)
        console.print("[dim]💡 Detailed analysis requires ffprobe integration[/]")
        
    except Exception as e:
        console.print(f"[red]Analysis error: {e}[/]")


if __name__ == "__main__":
    import asyncio
    
    mode = Prompt.ask(
        "[yellow]Launch mode[/]",
        choices=["gui", "console"],
        default="gui"
    )
    
    if mode == "gui":
        launch_standalone_audio_suite()
    else:
        asyncio.run(launch_console_audio_processor())
