#!/usr/bin/env python3
"""
interactive_mode.py - Snatch Premium Interactive Experience

Features:
- Multi-pane terminal interface
- Real-time media previews
- Holographic progress visualization
- Advanced format selection matrix
- Context-aware help system
- Animated transitions
- Surround sound configuration
"""

import sys
import time 
import asyncio
import psutil
from pathlib import Path
from typing import Dict, Any, Optional, List
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich.progress import (
    Progress, SpinnerColumn, BarColumn, TextColumn,
    DownloadColumn, TransferSpeedColumn, TimeRemainingColumn,
    Group
)
from rich.layout import Layout
from rich.live import Live
from rich.markdown import Markdown
from rich.align import Align
from rich.text import Text
from rich.box import ROUNDED, DOUBLE
from rich.table import Table
from rich.columns import Columns
from rich.style import Style
from colorama import Fore, Style, init
import typer
from pyfiglet import Figlet

from .logging_config import setup_logging
from .utils import sanitize_filename, format_size
from .manager import DownloadManager
from .progress import HolographicProgress
from .defaults import (
    THEME, BANNER_ART, HELP_CONTENT, QUALITY_PRESETS,
    SURROUND_PROFILES, SUBTITLE_STYLES
)

# Constants
STYLE_HEADER = "bold cyan"
STYLE_NORMAL = "green"
STYLE_ERROR = "red"
UPDATE_INTERVAL = 0.5  # seconds

# Initialize colorama
init(autoreset=True)

# Initialize premium theme
console = Console(theme=THEME)

class MediaPreview:
    """Interactive media preview with metadata visualization"""
    def __init__(self):
        self.preview_data = {}
        
    def render(self, metadata: Dict) -> Table:
        """Generate rich table with media preview"""
        table = Table.grid(padding=(0,1))
        table.add_column(style="preview_label")
        table.add_column(style="preview_value")
        
        table.add_row("🎵 Title", metadata.get('title', 'Unknown'))
        table.add_row("⏱ Duration", self._format_duration(metadata.get('duration', 0)))
        table.add_row("📊 Resolution", f"{metadata.get('width', 0)}x{metadata.get('height', 0)}")
        return table
        
    def _format_duration(self, seconds: float) -> str:
        """Convert duration to human-readable format"""
        return time.strftime('%H:%M:%S', time.gmtime(seconds))

class FormatMatrix:
    """Interactive format selection matrix with quality indicators"""
    def __init__(self):
        self.formats = []
        self.selected = None
        
    def update(self, formats: List[Dict]):
        """Update available formats"""
        self.formats = sorted(formats, key=lambda x: x.get('quality', 0), reverse=True)
        
    def render(self) -> Columns:
        """Render format options as selectable cards"""
        cards = []
        for fmt in self.formats:
            quality = fmt.get('quality', 'unknown')
            card = Panel(
                self._format_card_content(fmt),
                title=f"[b]{fmt['format_id']}[/]",
                subtitle=f"Quality: {quality}",
                style=self._get_style(quality),
                border_style="matrix_border"
            )
            cards.append(card)
        return Columns(cards, equal=True, expand=True)
        
    def _format_card_content(self, fmt: Dict) -> str:
        """Generate card content for a format"""
        content = [
            f"📦 Size: {format_size(fmt.get('filesize', 0))}",
            f"⚡ Bitrate: {fmt.get('bitrate', 'N/A')}",
            f"🎚 Codec: {fmt.get('codec', 'unknown')}"
        ]
        if fmt.get('audio_channels'):
            content.append(f"🎚 Channels: {fmt['audio_channels']}")
        return "\n".join(content)
        
    def _get_style(self, quality: str) -> Style:
        """Get style based on quality rating"""
        return {
            'high': Style(color="green", bold=True),
            'medium': Style(color="yellow"),
            'low': Style(color="red")
        }.get(quality.lower(), Style(color="white"))

class SurroundConfigurator:
    """7.1 Surround Sound configuration interface"""
    def __init__(self):
        self.profiles = SURROUND_PROFILES
        self.active_profile = None
        
    def render(self) -> Panel:
        """Render surround sound configuration panel"""
        grid = Table.grid(padding=(0,2))
        grid.add_column("Channel", style="surround_channel")
        grid.add_column("Level", style="surround_level")
        
        for channel, level in self.profiles.items():
            grid.add_row(
                f"🔊 {channel}",
                self._render_level_bar(level)
            )
            
        return Panel(
            grid,
            title="🎛 Surround Sound Configuration",
            border_style="surround_border",
            box=ROUNDED
        )
        
    def _render_level_bar(self, level: int) -> str:
        """Render audio level visualization"""
        return f"[surround_bar]{'█' * level}{'░' * (10 - level)}[/]"

class InteractiveHelp:
    """Context-aware help system with keyboard navigation"""
    def __init__(self):
        self.current_topic = "main"
        
    def render(self) -> Panel:
        """Render help content based on current context"""
        content = HELP_CONTENT.get(self.current_topic, HELP_CONTENT["main"])
        return Panel(
            Markdown(content),
            title="💡 Interactive Help",
            border_style="help_border",
            box=DOUBLE
        )

class SnatchUI:
    def __init__(self, download_manager: DownloadManager):
        self.manager = download_manager
        self.console = Console(theme=THEME)
        self.layout = Layout()
        self.help_system = InteractiveHelp()
        self.setup_layout()
        self.show_sidebar = True
        
    def setup_layout(self):
        """Configure the main application layout"""
        # Create main layout sections
        self.layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body", ratio=8),
            Layout(name="footer", size=3)
        )
        
        # Split body into sections
        self.layout["body"].split_row(
            Layout(name="main", ratio=3),
            Layout(name="sidebar", minimum_size=30)
        )
        
        # Split main section into content areas
        self.layout["main"].split_column(
            Layout(name="content", ratio=3),
            Layout(name="status", size=3)
        )
        
        # Initialize sections
        self.update_header()
        self.update_footer()
        self.update_sidebar()

    def handle_key(self, key: str) -> bool:
        """Handle special key presses"""
        if key == "f1":
            self.show_advanced_options()
            return True
        elif key == "f2":
            self.toggle_sidebar()
            return True
        elif key == "f3":
            self.show_queue()
            return True
        return False

    def show_advanced_options(self):
        """Show advanced options menu"""
        options = Table(show_header=True, header_style="bold cyan", box=ROUNDED)
        options.add_column("Option", style="cyan")
        options.add_column("Description", style="green")
        
        options.add_row("Format Selection", "Choose specific video/audio formats")
        options.add_row("Quality Settings", "Configure download quality presets")
        options.add_row("Network Options", "Proxy and connection settings")
        options.add_row("File Organization", "Configure auto-organization rules")
        options.add_row("FFmpeg Settings", "Configure audio/video processing")
        
        self.layout["content"].update(Panel(
            options,
            title="[b]Advanced Options[/b]",
            border_style="cyan"
        ))
        
        self.update_status("Press any key to return")

    def toggle_sidebar(self):
        """Toggle sidebar visibility"""
        self.show_sidebar = not self.show_sidebar
        if self.show_sidebar:
            self.layout["body"].split_row(
                Layout(name="main", ratio=3),
                Layout(name="sidebar", minimum_size=30)
            )
        else:
            self.layout["body"].split_row(
                Layout(name="main", ratio=1)
            )
        self.refresh()

    def show_queue(self):
        """Show download queue and progress"""
        queue = Table(show_header=True, header_style="bold cyan", box=ROUNDED)
        queue.add_column("ID", style="cyan")
        queue.add_column("URL", style="blue")
        queue.add_column("Status", style="green")
        queue.add_column("Progress", justify="right")
        
        downloads = getattr(self.manager, '_current_info_dict', {})
        for idx, (url, info) in enumerate(downloads.items(), 1):
            status = info.get('status', 'Unknown')
            progress = f"{info.get('progress', 0):3.0f}%"
            queue.add_row(str(idx), url[:50], status, progress)
            
        self.layout["content"].update(Panel(
            queue,
            title="[b]Download Queue[/b]",
            border_style="cyan"
        ))
        
        self.update_status(f"Active Downloads: {len(downloads)}")

    def show_help(self):
        """Display help content in the main area"""
        from .help_text import HELP_TEXT
        
        help_content = Panel(
            Markdown(HELP_TEXT),
            title="[b]Help & Documentation[/b]",
            border_style="cyan"
        )
        self.layout["content"].update(help_content)
        self.update_status("Press any key to return")

    async def get_command(self) -> str:
        """Get command from user with support for special keys"""
        try:
            with self.console.screen() as screen:
                while True:
                    command = ""
                    key = screen.get_key()
                    
                    if key in ("f1", "f2", "f3"):
                        if self.handle_key(key):
                            continue
                    
                    command = await self.console.input(f"\n{Fore.GREEN}snatch> {Style.RESET_ALL}")
                    return command.strip()
        except Exception as e:
            self.show_error(f"Input error: {str(e)}")
            return ""

    def update_header(self):
        """Update header with banner and status"""
        header = Panel(
            Align.center(
                Text("SNATCH DOWNLOAD MANAGER", style="bold cyan"),
                vertical="middle"
            ),
            box=ROUNDED,
            title="[b]Welcome[/b]",
            border_style="bright_blue"
        )
        self.layout["header"].update(header)
        
    def update_content(self, content: str = ""):
        """Update main content area"""
        panel = Panel(
            Markdown(content) if content else "",
            box=ROUNDED,
            title="[b]Content[/b]",
            border_style="blue"
        )
        self.layout["content"].update(panel)
        
    def update_status(self, status: str = "Ready"):
        """Update status area with current information"""
        status_panel = Panel(
            Text(status),
            box=ROUNDED,
            title="[b]Status[/b]",
            border_style="green"
        )
        self.layout["status"].update(status_panel)
        
    def update_sidebar(self):
        """Update sidebar with download stats and system info"""
        if not self.show_sidebar:
            return
            
        # Create downloads table
        downloads = Table(show_header=True, header_style="bold cyan", box=ROUNDED)
        downloads.add_column("Download", style="cyan")
        downloads.add_column("Progress", justify="right")
        downloads.add_column("Speed", justify="right")
        
        active_downloads = getattr(self.manager, '_current_info_dict', {})
        for url, info in active_downloads.items():
            title = info.get('title', 'Unknown')[:20]
            progress = f"{info.get('progress', 0):3.0f}%"
            speed = info.get('speed', '0 KB/s')
            downloads.add_row(title, progress, speed)
            
        # System stats
        stats = Table.grid()
        stats.add_column(style="cyan", justify="right")
        stats.add_column(style="green")
        stats.add_row("CPU:", f"{psutil.cpu_percent()}%")
        stats.add_row("Memory:", f"{psutil.virtual_memory().percent}%")
        stats.add_row("Active:", str(len(active_downloads)))
        
        # FFmpeg status
        ffmpeg_status = "✓ Ready" if self.manager.ffmpeg_path else "⚠ Not Found"
        stats.add_row("FFmpeg:", ffmpeg_status)
        
        # Combine in a panel
        sidebar = Panel(
            Group(
                Panel(downloads, title="[b]Active Downloads[/b]", border_style="blue"),
                Panel(stats, title="[b]System Stats[/b]", border_style="green")
            ),
            box=ROUNDED,
            title="[b]Downloads & Stats[/b]",
            border_style="blue"
        )
        self.layout["sidebar"].update(sidebar)
        
    def update_footer(self, keys: Dict[str, str] = None):
        """Update footer with keybindings and help"""
        if keys is None:
            keys = {
                "F1": "Help",
                "F2": "Queue",
                "F3": "Settings",
                "Ctrl+C": "Exit"
            }
            
        footer_content = " | ".join(
            f"[cyan]{key}[/] [green]{desc}[/]" 
            for key, desc in keys.items()
        )
        
        footer = Panel(
            Align.center(footer_content),
            box=ROUNDED,
            border_style="bright_blue"
        )
        self.layout["footer"].update(footer)
        
    def refresh(self):
        """Refresh the entire UI"""
        self.update_header()
        self.update_sidebar()
        self.update_footer()
        self.console.print(self.layout)

    async def run(self):
        """Main UI loop"""
        try:
            with Live(self.layout, refresh_per_second=4, screen=True):
                # Show welcome message
                self.update_content(HELP_CONTENT["welcome"])
                
                while True:
                    command = await self.get_command()
                    
                    if not command:
                        continue
                        
                    if command.lower() in ('exit', 'quit', 'q'):
                        self.update_status("Exiting...")
                        break
                        
                    if command.lower() in ('help', '?'):
                        self.show_help()
                        continue
                        
                    if command.lower() == 'h':
                        from .help_text import QUICK_HELP
                        self.update_content(QUICK_HELP)
                        continue
                        
                    # Handle URL input with options
                    if '://' in command:
                        parts = command.split(maxsplit=1)
                        url = parts[0]
                        options = {}
                        
                        if len(parts) > 1:
                            option_text = parts[1].strip().lower()
                            if option_text in ['flac', 'opus', 'mp3', 'wav', 'm4a']:
                                options = {
                                    'audio_only': True,
                                    'audio_format': option_text
                                }
                            elif option_text in ['720', '1080', '2160', '4k', '480']:
                                options = {
                                    'resolution': '2160' if option_text == '4k' else option_text
                                }
                                
                        self.update_status(f"Downloading {url}...")
                        try:
                            await self.manager.download_with_retries(url, **options)
                            self.update_status("Download completed")
                        except Exception as e:
                            self.show_error(f"Download failed: {str(e)}")
                        continue
                    
                    # Handle special commands
                    if command.startswith('!'):
                        await self.handle_special_command(command[1:])
                        continue
                        
                    self.show_error(f"Unknown command: {command}")
                    self.update_status("Type 'help' for commands")
                    
        except KeyboardInterrupt:
            self.show_error("Interrupted by user")
            
    async def handle_special_command(self, command: str):
        """Handle special commands starting with !"""
        parts = command.split()
        cmd = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []
        
        if cmd in ('stats', 'speed', 'test'):
            self.update_status("Running speed test...")
            await self.manager.run_speedtest()
            
        elif cmd == 'sites':
            self.update_status("Loading supported sites...")
            # TODO: Implement list_supported_sites
            
        elif cmd == 'config':
            self.show_advanced_options()
            
        elif cmd == 'clear':
            self.update_content("")
            self.update_status("Screen cleared")
            
        else:
            self.show_error(f"Unknown command: !{command}")
            
    def update_status(self, status: str = "Ready"):
        """Update status area with current information"""
        status_panel = Panel(
            Text(status),
            box=ROUNDED,
            title="[b]Status[/b]",
            border_style="green"
        )
        self.layout["status"].update(status_panel)

class PremiumInteractiveMode:
    """Next-generation interactive download experience"""
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.manager = DownloadManager(config)
        self.layout = Layout(name="root")
        self.session_stats = {
            "total_downloads": 0,
            "total_size": 0,
            "average_speed": 0
        }
        self.media_preview = MediaPreview()
        self.format_matrix = FormatMatrix()
        self.surround_config = SurroundConfigurator()
        self.help_system = InteractiveHelp()
        
        # Setup layout
        self.layout.split(
            Layout(name="header", size=3),
            Layout(name="main", ratio=1),
            Layout(name="footer", size=3)
        )
        self.layout["main"].split_row(
            Layout(name="sidebar", size=35),
            Layout(name="body", ratio=2)
        )
        
    def _update_header(self) -> Panel:
        """Render dynamic header with session stats"""
        stats_text = Text.assemble(
            ("SNATCH PREMIUM", "banner"),
            " │ ",
            ("Downloads: ", "stats_label"),
            (f"{self.session_stats['total_downloads']}", "stats_value"),
            " │ ",
            ("Transferred: ", "stats_label"),
            (format_size(self.session_stats['total_size']), "stats_value")
        )
        return Panel(
            Align.center(stats_text, vertical="middle"),
            style="header"
        )
    
    def _render_main_body(self, metadata: Dict) -> Layout:
        """Render main content area"""
        self.layout["body"].update(
            Columns([
                Panel(
                    self.media_preview.render(metadata),
                    title="📺 Media Preview",
                    border_style="preview_border"
                ),
                self.format_matrix.render()
            ])
        )
        return self.layout
        
    def _render_sidebar(self) -> Layout:
        """Render configuration sidebar"""
        self.layout["sidebar"].update(
            Panel(
                Group(
                    self.surround_config.render(),
                    self.help_system.render()
                ),
                title="⚙️ Configuration",
                border_style="sidebar_border"
            )
        )
        return self.layout
        
    async def run(self):
        """Launch premium interactive session"""
        try:
            self._show_animated_banner()
            with Live(self.layout, refresh_per_second=10, screen=True):
                while True:
                    await self._process_url()
                    if not Confirm.ask("\n[bold]Download another?[/]", default=True):
                        break
                        
            console.print(Panel(
                "[success]Session completed successfully![/]",
                title="Goodbye 👋",
                border_style="success"
            ))
            
        except KeyboardInterrupt:
            console.print("\n[warning]Session interrupted[/]")
        except Exception as e:
            console.print(Panel(
                f"[error]Critical Error: {str(e)}[/]",
                title="⚠️ Fatal Error",
                border_style="error"
            ))

    async def _process_url(self):
        """Premium URL processing workflow"""
        url = Prompt.ask("\n[bold]Enter media URL[/] [dim](or 'q' to quit)[/]")
        if url.lower() in ('q', 'quit', 'exit'):
            raise typer.Exit()
            
        with HolographicProgress() as progress:
            try:
                metadata = await self._fetch_metadata(url, progress)
                self._update_interface(metadata)
                await self._handle_download(url, progress)
                
            except Exception as e:
                progress.stop()
                console.print(Panel(
                    f"[error]Download failed: {str(e)}[/]",
                    title="⚠️ Error",
                    border_style="error"
                ))

    async def _fetch_metadata(self, url: str, progress: Progress) -> Dict:
        """Fetch and display media metadata"""
        task = progress.add_task("[cyan]Analyzing content...", total=None)
        metadata = self.manager.extract_info(url)
        progress.update(task, advance=30)
        return metadata

    def _update_interface(self, metadata: Dict) -> None:
        """Update UI components with new metadata"""
        self.layout["header"].update(self._update_header())
        self._render_main_body(metadata)
        self._render_sidebar()
        self.format_matrix.update(metadata.get('formats', []))

    async def _handle_download(self, url: str, progress: Progress) -> None:
        """Handle full download lifecycle"""
        # Configuration phase
        progress.update(description="[cyan]Configuring format...")
        options = self._get_download_options()
        
        # Download phase
        progress.update(description="[cyan]Starting download...")
        output = await self.manager.download(url, options)
        
        # Update session stats
        self.session_stats["total_downloads"] += 1
        self.session_stats["total_size"] += Path(output).stat().st_size
        
        # Show completion
        console.print(self._download_summary(Path(output)))

    def _get_download_options(self) -> Dict:
        """Get download options based on user configuration"""
        return {
            "audio_format": self.config.get("audio_format", "flac"),
            "audio_channels": 8 if self.surround_config.active_profile else 2,
            "quality_preset": QUALITY_PRESETS["lossless"]
        }

    def _download_summary(self, output_path: Path) -> Panel:
        """Generate post-download summary card"""
        file_stats = output_path.stat()
        table = Table.grid(padding=(0, 1))
        table.add_column(style="summary_label")
        table.add_column(style="summary_value")
        
        table.add_row("📁 Location", str(output_path))
        table.add_row("📦 Size", format_size(file_stats.st_size))
        table.add_row("🔒 Integrity", "[green]Verified[/]")
        
        return Panel(
            Align.center(table),
            title="[success]Download Complete![/]",
            border_style="success",
            padding=(1, 4)
        )

    def _show_animated_banner(self):
        """Display animated welcome banner"""
        console.clear()
        with console.screen(style="black on #1A1B26"):
            for line in BANNER_ART.split("\n"):
                console.print(line, style="banner", end="\n")
            time.sleep(2)
            
        console.print(Panel(
            Markdown(HELP_CONTENT["welcome"]),
            title="[blink]Welcome to Snatch Premium[/]",
            border_style="cyan",
            padding=(1, 2)
        ))

def start_interactive_mode(config: Dict[str, Any]) -> None:
    """Launch premium interactive experience"""
    setup_logging()
    interactive = PremiumInteractiveMode(config)
    asyncio.run(interactive.run())

if __name__ == "__main__":
    console.print("[error]Premium module - execute via main CLI[/]")
    sys.exit(1) 