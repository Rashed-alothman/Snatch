"""
Enhanced CLI module with Rich interface and preset support.
"""

import asyncio
import logging
import signal
import sys
import time
import os
from pathlib import Path
from typing import List, Optional, Dict, Any, NoReturn
import typer
import yaml
from rich.console import Console
from rich.traceback import install

# Local imports
from .constants import VERSION, EXAMPLES, APP_NAME
from .config import initialize_config_async, check_for_updates
from .defaults import FORMAT_PRESETS
from .manager import AsyncDownloadManager
from .logging_config import setup_logging, CustomHelpFormatter
from .session import AsyncSessionManager, SessionManager
from .network import run_speedtest
from .common_utils import list_supported_sites, display_system_stats
from .cache import DownloadCache

# Enable Rich traceback formatting
install(show_locals=True)

# Initialize console
console = Console()

class EnhancedCLI:
    """Enhanced CLI with Rich interface and preset profiles"""
    
    def __init__(self, config: Dict[str, Any]):
        if not config:
            raise ValueError("Configuration must be provided")
            
        self.config = config
        
        try:
            # Get the session file path from config or use default
            session_file = self.config.get("session_file")
            if not session_file:
                sessions_dir = self.config.get("sessions_dir")
                if not sessions_dir:
                    config_dir = os.path.dirname(os.path.dirname(__file__))
                    sessions_dir = os.path.join(config_dir, "sessions")
                    self.config["sessions_dir"] = sessions_dir
                
                session_file = os.path.join(sessions_dir, "download_sessions.json")
                self.config["session_file"] = session_file
            
            # Create sessions directory if it doesn't exist
            os.makedirs(os.path.dirname(session_file), exist_ok=True)
            
            # Initialize dependencies
            self.session_manager = AsyncSessionManager(session_file)
            self.download_cache = DownloadCache()
            
            # Create download manager with dependencies
            self.download_manager = AsyncDownloadManager(
                config=config,
                session_manager=self.session_manager,
                download_cache=self.download_cache
            )
            
        except Exception as error:
            msg = f"Failed to initialize CLI: {str(error)}"
            logging.error(msg)
            raise RuntimeError(msg) from error

    def get_or_create_event_loop(self):
        """Get the current event loop or create a new one if none exists"""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop

    async def run_download(self, urls: List[str], options: Dict[str, Any], non_interactive: bool = False) -> None:
        """Run download(s) with proper context management"""
        async with self.download_manager:
            await self.download_manager.download_with_options(urls, options, non_interactive)

    def run_async(self, coro: Any) -> Any:
        """Run a coroutine in the event loop"""
        loop = self.get_or_create_event_loop()
        if loop.is_running():
            return asyncio.create_task(coro)
        else:
            return loop.run_until_complete(coro)

    def setup_argparse(self) -> typer.Typer:
        """Set up the Typer CLI app with all commands"""
        app = typer.Typer(
            name=APP_NAME,
            help=f"{APP_NAME} - A powerful media downloader",
            epilog=EXAMPLES
        )
        
        # Download command
        @app.command("download", help="Download media from URLs")
        def download(
            urls: List[str] = typer.Argument(None, help="URLs to download"),
            audio_only: bool = typer.Option(False, "--audio-only", "-a", help="Download audio only"),
            resolution: str = typer.Option(None, "--resolution", "-r", help="Video resolution (e.g., 1080, 720)"),
            format_id: str = typer.Option(None, "--format-id", "-f", help="Specific format ID"),
            output_dir: str = typer.Option(None, "--output-dir", "-o", help="Output directory"),
            filename: str = typer.Option(None, "--filename", help="Custom filename"),
            audio_format: str = typer.Option("mp3", "--audio-format", help="Audio format for --audio-only"),
            audio_quality: str = typer.Option("best", "--audio-quality", help="Audio quality"),
            upmix_71: bool = typer.Option(False, "--upmix-7.1", help="Upmix audio to 7.1 surround"),
            denoise: bool = typer.Option(False, "--denoise", help="Apply noise reduction to audio"),
            batch_file: str = typer.Option(None, "--batch-file", "-b", help="File containing URLs to download"),
            quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress output"),
            verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
        ):
            """Download media from URLs"""
            if not urls and not batch_file:
                console.print("[bold red]No URLs provided and no batch file specified.[/]")
                return 1
                
            # Load URLs from batch file if provided
            if batch_file:
                try:
                    with open(batch_file, 'r') as f:
                        batch_urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]
                        urls.extend(batch_urls)
                except Exception as e:
                    console.print(f"[bold red]Error loading batch file: {str(e)}[/]")
                    return 1
            
            # Configure options
            options = {
                "audio_only": audio_only,
                "resolution": resolution,
                "format_id": format_id,
                "output_dir": output_dir,
                "filename": filename,
                "audio_format": audio_format,
                "audio_quality": audio_quality,
                "upmix_71": upmix_71,
                "denoise": denoise,
                "quiet": quiet,
                "verbose": verbose,
            }
              # Run the download with proper processing for audio flags
            try:
                # If audio processing flags are specified, ensure the manager knows about them
                if audio_only and (upmix_71 or denoise):
                    console.print("[bold cyan]Audio processing:[/] Using enhanced audio pipeline")
                
                self.run_async(self.run_download(urls, options))
                return 0
            except Exception as e:
                console.print(f"[bold red]Download error: {str(e)}[/]")
                return 1
        
        # Interactive mode command
        @app.command("interactive", help="Run in interactive mode")
        def interactive():
            """Run in classic interactive mode"""
            from .interactive_mode import launch_textual_interface
            launch_textual_interface(self.config)
            return 0        # New textual interface command
        @app.command("textual", help="Run with modern Textual interface")
        def textual():
            """Run with modern Textual interface"""
            try:
                # Import at runtime to avoid dependencies if not used
                from .textual_interface import start_textual_interface
                # Pass the current CLI instance to maintain state
                start_textual_interface(self.config)
            except ImportError as e:
                console.print(f"[bold yellow]Textual interface not available: {str(e)}[/]")
                console.print("[yellow]Falling back to classic interactive mode.[/]")
                from .interactive_mode import launch_textual_interface
                launch_textual_interface(self.config)
        
        # List supported sites command
        @app.command("list-sites", help="List all supported sites")
        def list_sites():
            """List all supported sites"""
            list_supported_sites()
            return 0
        
        # Show version command
        @app.command("version", help="Show version information")
        def version():
            """Show version information"""
            console.print(f"[bold cyan]{APP_NAME}[/] [bold green]v{VERSION}[/]")
            return 0
        
        # Run speedtest command
        @app.command("speedtest", help="Run download speed test")
        def speedtest():
            """Run download speed test"""
            run_speedtest()
            return 0
        
        # Show system info command
        @app.command("system-info", help="Show system information")
        def system_info():
            """Show system information"""
            display_system_stats()
            return 0
        
        # Show active downloads command
        @app.command("active", help="Show active downloads")
        def active():
            """Show active downloads"""
            self.run_async(self._show_active_downloads_async())
            return 0
            
        return app
        
    async def _show_active_downloads_async(self) -> None:
        """Show active downloads asynchronously"""
        async with AsyncSessionManager(self.config["session_file"]) as sm:
            sessions = sm.get_active_sessions()
            if sessions:
                self.ui.show_active_downloads(sessions)
            else:
                self.ui.print("No active downloads")
                    
    async def interactive_mode(self) -> None:
        """Rich interactive mode with command history"""
        while True:
            try:
                command = self.ui.get_command()
                if not await self._handle_command_async(command):
                    break
            except KeyboardInterrupt:
                continue
            except Exception as error:
                self.ui.show_error(f"Command error: {str(error)}")
                continue

def signal_handler(sig: int, frame: Any) -> NoReturn:
    """Handle Ctrl+C gracefully"""
    console.print("\n[yellow]Interrupted by user[/yellow]")
    sys.exit(0)

async def async_main() -> None:
    """Async main function that handles all async initialization"""
    # Initialize configuration
    config = await initialize_config_async()
    if not config:
        sys.exit(1)

    # Create CLI
    cli = EnhancedCLI(config)
    app = cli.setup_argparse()
    
    # Run the appropriate command based on arguments
    # If no arguments, default to textual interface
    if len(sys.argv) <= 1:
        try:
            # Try to use the modern textual interface first
            from .textual_interface import start_textual_interface
            start_textual_interface(config)
        except ImportError:
            # Fall back to classic interactive mode if textual is not available
            console.print("[yellow]Textual interface not available. Using classic interactive mode.[/]")
            from .interactive_mode import launch_textual_interface
            launch_textual_interface(config)
    else:
        # Otherwise run the Typer app with the arguments
        app()

def main() -> None:
    """Main entry point with enhanced CLI"""
    # Configure logging
    setup_logging()
    
    # Enable Ctrl+C handling
    signal.signal(signal.SIGINT, signal_handler)

    try:
        if asyncio.get_event_loop().is_running():
            loop = asyncio.get_event_loop()
            loop.run_until_complete(async_main())
        else:
            asyncio.run(async_main())
    except Exception:
        console.print_exception()
        sys.exit(1)

if __name__ == "__main__":
    main()