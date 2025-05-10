#!/usr/bin/env python3
"""
interactive_mode.py

Centralizes interactive prompt logic for the Snatch CLI tool.
Features:
  - Interactive selection of media type, codecs, channels, resolution
  - Rich UI with progress bars and spinners
  - Clean error handling and defaults
  - Integration with DownloadManager
"""
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn
from rich import print as rprint
from rich.theme import Theme
from rich.table import Table

from .logging_config import setup_logging
from .utils import sanitize_filename, format_size
from .manager import DownloadManager

# Initialize Rich console with custom theme
theme = Theme({
    "info": "cyan",
    "success": "green",
    "warning": "yellow",
    "error": "red bold",
    "highlight": "magenta"
})
console = Console(theme=theme)

def show_welcome():
    """Display a welcoming message with instructions"""
    welcome_text = """
    Welcome to [info]Snatch Interactive Mode[/info]!
    
    Here you can interactively download media with custom options.
    Use [highlight]Ctrl+C[/highlight] at any time to cancel the current operation.
    """
    console.print(Panel(welcome_text, title="[success]Snatch[/success]", border_style="info"))

def create_progress() -> Progress:
    """Create a Rich progress instance with custom styling"""
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeRemainingColumn(),
        console=console
    )

def select_media_type(non_interactive: bool = False, default: str = "video") -> str:
    """Interactive media type selection with Rich UI"""
    if non_interactive:
        return default
    
    options = {
        "1": ("Video", "video"),
        "2": ("Audio Only", "audio")
    }
    
    table = Table(show_header=False, box=None)
    table.add_column("Key", style="highlight")
    table.add_column("Option", style="info")
    
    for key, (label, _) in options.items():
        table.add_row(f"{key})", label)
    
    console.print("\n[bold]Available Media Types:[/bold]")
    console.print(table)
        
    choice = Prompt.ask(
        "\nSelect media type",
        choices=list(options.keys()),
        default="1"
    )
    return options[choice][1]

def select_audio_codec(available: List[str], non_interactive: bool = False, default: Optional[str] = None) -> str:
    """Interactive audio codec selection with Rich UI"""
    if non_interactive:
        return default or available[-1]
    
    table = Table(show_header=False, box=None)
    table.add_column("Index", style="highlight")
    table.add_column("Codec", style="info")
    
    for i, codec in enumerate(available, 1):
        table.add_row(f"{i})", codec)
    
    console.print("\n[bold]Available Audio Codecs:[/bold]")
    console.print(table)
        
    idx = Prompt.ask(
        "\nChoose codec",
        choices=[str(i) for i in range(1, len(available) + 1)],
        default=str(len(available))
    )
    try:
        return available[int(idx) - 1]
    except (ValueError, IndexError):
        console.print("[warning]Invalid choice, using default codec.[/warning]")
        return available[-1]

def select_audio_channels(non_interactive: bool = False, default: int = 2) -> int:
    """Interactive audio channel selection with Rich UI"""
    opts = [1, 2, 6]
    if non_interactive:
        return default
    
    table = Table(show_header=False, box=None)
    table.add_column("Index", style="highlight")
    table.add_column("Channels", style="info")
    
    for i, channels in enumerate(opts, 1):
        label = "channel" if channels == 1 else "channels"
        table.add_row(f"{i})", f"{channels} {label}")
    
    console.print("\n[bold]Audio Channel Options:[/bold]")
    console.print(table)
        
    idx = Prompt.ask(
        "\nChoose channels",
        choices=[str(i) for i in range(1, len(opts) + 1)],
        default="2"
    )
    try:
        return opts[int(idx) - 1]
    except (ValueError, IndexError):
        console.print("[warning]Invalid choice, using default channels.[/warning]")
        return default

def select_video_format(formats: List[Dict[str, Any]], non_interactive: bool = False, default: Optional[str] = None) -> str:
    """Interactive video format selection with Rich UI"""
    res_list = sorted({f.get("resolution") for f in formats if f.get("resolution")})
    if not res_list:
        raise ValueError("[error]No video resolutions available[/error]")
    
    if non_interactive:
        return default or res_list[-1]
    
    table = Table(show_header=False, box=None)
    table.add_column("Index", style="highlight")
    table.add_column("Resolution", style="info")
    
    for i, resolution in enumerate(res_list, 1):
        table.add_row(f"{i})", resolution)
    
    console.print("\n[bold]Available Resolutions:[/bold]")
    console.print(table)
        
    idx = Prompt.ask(
        "\nChoose resolution",
        choices=[str(i) for i in range(1, len(res_list) + 1)],
        default=str(len(res_list))
    )
    try:
        return res_list[int(idx) - 1]
    except (ValueError, IndexError):
        console.print("[warning]Invalid choice, using highest resolution.[/warning]")
        return res_list[-1]

class InteractiveMode:
    """Main class for handling interactive download mode"""
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.manager = DownloadManager(config)
    
    def run(self):
        """Start the interactive download mode"""
        try:
            show_welcome()
            while True:
                url = Prompt.ask("\n[bold cyan]Enter URL to download[/bold cyan] (or 'q' to quit)")
                if url.lower() in ('q', 'quit', 'exit'):
                    break
                    
                self._process_url(url)
                
                if not Confirm.ask("\nDownload another?", default=True):
                    break
                    
            console.print("\n[success]Thank you for using Snatch![/success]")
            
        except KeyboardInterrupt:
            console.print("\n\n[warning]Interactive mode cancelled.[/warning]")
        except Exception as e:
            console.print(f"\n[error]Error in interactive mode: {str(e)}[/error]")
            
    def _process_url(self, url: str) -> bool:
        """Process a single URL download with progress indication"""
        with create_progress() as progress:
            try:
                # Start metadata extraction
                task = progress.add_task("Analyzing URL...", total=None)
                info = self.manager.extract_info(url)
                
                if not info or "formats" not in info:
                    console.print("[error]Error: Could not retrieve format information.[/error]")
                    return False
                
                # Update progress
                progress.update(task, total=100, completed=30)
                
                # Get user preferences
                chosen_media = select_media_type(
                    non_interactive=self.config.get('non_interactive', False),
                    default="audio" if self.config.get('audio_only', False) else "video"
                )
                progress.update(task, description="Configuring options...", completed=50)
                
                # Configure format string based on media type
                if chosen_media == "audio":
                    acodecs = sorted({f["acodec"] for f in info["formats"] if f.get("acodec")})
                    codec = select_audio_codec(acodecs)
                    channels = select_audio_channels()
                    format_str = f"bestaudio[acodec={codec}][channels={channels}]"
                else:
                    resolution = select_video_format(info["formats"])
                    format_str = f"bestvideo[resolution={resolution}] + bestaudio"
                
                # Start download with progress tracking
                progress.update(task, description="[cyan]Starting download...[/cyan]", completed=60)
                options = {
                    "format": format_str,
                    "progress_hooks": [
                        lambda d: progress.update(
                            task,
                            description=f"[cyan]Downloading: {d.get('_percent_str', '0.0%')}[/cyan]",
                            completed=60 + int(float(d.get('_percent_str', '0.0%').replace('%', '')) * 0.4)
                        )
                    ]
                }
                
                output = self.manager.download(url, options)
                
                progress.update(task, description="[success]Download complete![/success]", completed=100)
                console.print(f"\n[success]Successfully downloaded to: {output}[/success]")
                return True
                
            except Exception as e:
                console.print(f"[error]Error processing {url}: {str(e)}[/error]")
                return False

def start_interactive_mode(config: Dict[str, Any]) -> None:
    """Launch interactive mode with the provided configuration"""
    setup_logging()  # Ensure logging is configured
    interactive = InteractiveMode(config)
    interactive.run()

if __name__ == "__main__":
    console.print("[error]This module should not be run directly.[/error]")
    sys.exit(1)
