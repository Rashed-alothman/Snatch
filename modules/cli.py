"""
Enhanced CLI module with Rich interface and preset support.
"""

import asyncio
import logging
import signal
import sys
import time
import os
import glob
from pathlib import Path
from typing import List, Optional, Dict, Any, NoReturn
import typer
import yaml
from rich.console import Console
from rich.traceback import install
from rich.prompt import Confirm
from rich.live import Live
from rich.table import Table

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
from .error_handler import EnhancedErrorHandler, handle_errors, ErrorCategory, ErrorSeverity
from .config_manager import ConfigurationManager, CacheType
from .customization_manager import CustomizationManager, ThemePreset, ConfigFormat, InterfaceMode, ProgressStyle, NotificationLevel
from .audio_processor import EnhancedAudioProcessor, AudioEnhancementSettings, AUDIO_ENHANCEMENT_PRESETS

# Enable Rich traceback formatting
install(show_locals=True)

# Initialize console
console = Console()

# Constants for duplicate strings
FALLBACK_INTERACTIVE_MSG = "[yellow]Falling back to enhanced interactive mode.[/]"
FALLBACK_SIMPLE_MSG = "[yellow]Falling back to simple interactive mode...[/]"
SKIP_CONFIRMATION_HELP = "Skip confirmation prompt"
SETTING_MODIFY_HELP = "Setting to modify"
NEW_VALUE_HELP = "New value for the setting"
BOTH_SETTING_VALUE_MSG = "[red]Both setting and value required, or use --show[/]"
P2P_SERVICE_FAILED_MSG = "[red]Failed to start P2P service[/]"
P2P_NOT_AVAILABLE_MSG = "[red]P2P functionality not available[/]"
PEER_ID_COLUMN = "Peer ID"
LAST_SEEN_COLUMN = "Last Seen"
P2P_SERVICE_STARTING_MSG = "[yellow]P2P service not running. Starting...[/]"

# Additional duplicate string constants
INTERRUPTED_MSG = "\n[yellow]Operation interrupted. Type 'exit' to quit.[/]"
UNKNOWN_COMMAND_MSG = "[yellow]Unknown command:[/]"
HELP_AVAILABLE_MSG = "[yellow]Type 'help' for available commands[/]"
PROVIDE_URL_MSG = "[yellow]Please provide a URL to download[/]"
QUEUE_CLEARED_MSG = "[yellow]Queue cleared[/]"
SCHEDULER_PAUSED_MSG = "[yellow]Scheduler paused[/]"
MONITORING_STOPPED_MSG = "\n[yellow]Monitoring stopped by user[/]"
PRESS_CTRL_C_MSG = "[yellow]Press Ctrl+C to stop early[/]"
INVALID_ACTION_MSG = "[red]Invalid action:"
LIBRARY_NAME_REQUIRED_MSG = "[red]Library name required for create action[/]"
LIBRARY_FRIEND_REQUIRED_MSG = "[red]Library name and friend ID required for share action[/]"
SEARCH_QUERY_REQUIRED_MSG = "[red]Search query required for search action[/]"
COMING_SOON_MSG = "[yellow]Library {} functionality coming soon[/]"
VALID_ACTIONS_MSG = "[yellow]Valid actions: {}"

class EnhancedCLI:
    """Enhanced CLI with Rich interface and preset profiles"""
    
    def __init__(self, config: Dict[str, Any]):
        if not config:
            raise ValueError("Configuration must be provided")
            
        self.config = config
        self._pending_download = None  # Store pending download for async execution
        
        # Initialize error handler
        error_log_path = config.get("error_log_path", "logs/snatch_errors.log")
        self.error_handler = EnhancedErrorHandler(log_file=error_log_path)
        
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
              # Initialize configuration manager
            config_file = config.get("config_file", "config.json")
            self.config_manager = ConfigurationManager(config_file)
            
            # Initialize customization manager
            customization_file = config.get("customization_file", "customization.yaml")
            self.customization_manager = CustomizationManager(customization_file)
            
            # Create download manager with dependencies
            self.download_manager = AsyncDownloadManager(
                config=config,
                session_manager=self.session_manager,
                download_cache=self.download_cache
            )
            
        except Exception as error:
            self.error_handler.log_error(
                str(error), 
                ErrorCategory.CONFIGURATION, 
                ErrorSeverity.CRITICAL,
                context={"config_keys": list(config.keys()) if config else []}
            )
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
          
    @handle_errors(ErrorCategory.DOWNLOAD, ErrorSeverity.ERROR)
    async def run_download(self, urls: List[str], options: Dict[str, Any], non_interactive: bool = False) -> None:
        """Run download(s) with proper context management"""
        async with self.download_manager:
            try:
                console = Console()
                console.print(f"[bold cyan]Processing {len(urls)} URLs[/]")
                result = await self.download_manager.download_with_options(urls, options)
                if result:
                    console.print(f"[bold green]Successfully downloaded {len(result)} files[/]")
                    self.error_handler.log_error(
                        f"Successfully downloaded {len(result)} files",
                        ErrorCategory.DOWNLOAD,
                        ErrorSeverity.INFO,
                        context={"downloaded_files": len(result), "urls": urls}
                    )
            except asyncio.CancelledError:
                console = Console()
                console.print("[bold yellow]Download was cancelled.[/]")
                self.error_handler.log_error(
                    "Download process was cancelled",
                    ErrorCategory.DOWNLOAD,
                    ErrorSeverity.WARNING,
                    context={"cancellation": True, "urls": urls}
                )
                # Don't re-raise CancelledError to prevent the unhandled exception
            except Exception as e:
                self.error_handler.log_error(
                    f"Download error: {str(e)}",
                    ErrorCategory.DOWNLOAD,
                    ErrorSeverity.ERROR,
                    context={"urls": urls, "options": options}
                )
                console = Console()
                console.print(f"[bold red]Error: {str(e)}[/]")
                raise

    def run_async(self, coro: Any) -> Any:
        """Run a coroutine in the event loop"""
        loop = self.get_or_create_event_loop()
        if loop.is_running():
            return asyncio.create_task(coro)
        else:
            return loop.run_until_complete(coro)
    @handle_errors(ErrorCategory.DOWNLOAD, ErrorSeverity.ERROR)
    def execute_download(self, urls: List[str], options: Dict[str, Any]) -> int:
        """Execute download with proper event loop handling"""
        if not urls:
            self.error_handler.log_error(
                "No URLs provided for download",
                ErrorCategory.USER_INPUT,
                ErrorSeverity.WARNING
            )
            console.print("[bold red]No URLs provided.[/]")
            return 1
        
        # Log useful information
        console.print(f"[bold cyan]Processing {len(urls)} URLs for download[/]")
        self._log_download_mode(options)
          # Handle download with proper event loop management
        try:
            result = self._run_download_safely(urls, options)
            
            # Launch interactive mode if requested and download succeeded
            if result == 0 and options.get("interactive", False):
                console.print("\n[bold cyan]🎮 Launching interactive mode...[/]")
                self._launch_interactive_mode()
            
            return result
        except Exception as e:
            self.error_handler.log_error(
                f"Download execution failed: {str(e)}",
                ErrorCategory.DOWNLOAD,
                ErrorSeverity.ERROR,
                context={"urls": urls, "options": options}            )
            console.print(f"[bold red]Download failed: {str(e)}[/]")
            return 1
    def _log_download_mode(self, options: Dict[str, Any]) -> None:
        """Log download mode information"""
        if options.get("audio_only"):
            console.print(f"[bold cyan]Audio mode:[/] Downloading as {options.get('audio_format', 'mp3')}")
            if options.get("upmix_71"):
                console.print("[bold cyan]Audio processing:[/] Upmixing to 7.1 surround")
            if options.get("denoise"):
                console.print("[bold cyan]Audio processing:[/] Applying noise reduction")
        elif options.get("resolution"):
            resolution = options.get('resolution')
            console.print(f"[bold cyan]Video mode:[/] Setting resolution to {resolution}")
            
        # Log upscaling information
        if options.get("upscale_video"):
            method = options.get("upscale_method", "lanczos")
            factor = options.get("upscale_factor", 2)
            console.print(f"[bold cyan]Video upscaling:[/] {method} {factor}x enhancement enabled")

    @handle_errors(ErrorCategory.DOWNLOAD, ErrorSeverity.WARNING)
    def _run_download_safely(self, urls: List[str], options: Dict[str, Any]) -> int:
        """Run download with safe event loop handling"""
        try:            # Check if we're in an async context already
            try:
                asyncio.get_running_loop()
                # We're in an async context - this means we're called from async code
                # We need to create a new thread to avoid blocking
                console.print("[cyan]Running download in async context...[/]")
                import threading
                import queue
                
                result_queue = queue.Queue()
                
                def run_in_thread():
                    try:
                        # Create a new event loop for this thread
                        new_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(new_loop)
                        new_loop.run_until_complete(self.run_download(urls, options))
                        result_queue.put(0)  # Success
                    except Exception as e:
                        self.error_handler.log_error(
                            f"Thread download error: {str(e)}",
                            ErrorCategory.DOWNLOAD,
                            ErrorSeverity.ERROR,
                            context={"thread_execution": True, "urls": urls}
                        )
                        result_queue.put(1)  # Failure
                    finally:
                        new_loop.close()
                
                # Start the download in a separate thread
                thread = threading.Thread(target=run_in_thread)
                thread.start()
                thread.join()  # Wait for completion
                
                return result_queue.get()
                
            except RuntimeError:
                # No running loop - we can run the download directly
                console.print("[cyan]Starting download...[/]")
                asyncio.run(self.run_download(urls, options))
                return 0
        except Exception as e:
            self.error_handler.log_error(
                f"Failed to start download: {str(e)}",
                ErrorCategory.DOWNLOAD,
                ErrorSeverity.CRITICAL,
                context={"async_context_handling": True, "urls": urls}
            )
            console.print(f"[bold red]Failed to start download: {str(e)}[/]")
            return 1

    async def process_pending_download(self) -> bool:
        """Process any pending download requests"""
        if not self._pending_download:
            return False
            
        urls, options = self._pending_download
        self._pending_download = None  # Clear the pending download
        
        try:
            await self.run_download(urls, options)
            return True
        except Exception as e:
            logging.error(f"Download processing failed: {str(e)}")
            console.print(f"[bold red]Download failed: {str(e)}[/]")
            return False

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
            
            # Existing audio enhancement options
            upmix_71: bool = typer.Option(False, "--upmix-7.1", help="Upmix audio to 7.1 surround"),
            denoise: bool = typer.Option(False, "--denoise", help="Apply noise reduction to audio"),
            
            # New comprehensive audio enhancement options
            enhance_audio: bool = typer.Option(False, "--enhance-audio", help="Enable comprehensive audio enhancement"),
            audio_enhancement_level: str = typer.Option("medium", "--enhancement-level", help="Enhancement level: light, medium, aggressive"),
            audio_enhancement_preset: str = typer.Option(None, "--enhancement-preset", help="Use preset: podcast, music, speech, broadcast, restoration"),
            noise_reduction: bool = typer.Option(False, "--noise-reduction", help="Apply AI-powered noise reduction"),
            noise_reduction_strength: float = typer.Option(0.6, "--noise-strength", help="Noise reduction strength (0.0-1.0)"),
            upscale_sample_rate: bool = typer.Option(False, "--upscale-sample-rate", help="Upscale audio sample rate"),
            target_sample_rate: int = typer.Option(48000, "--target-sample-rate", help="Target sample rate (22050, 44100, 48000, 96000)"),
            frequency_extension: bool = typer.Option(False, "--frequency-extension", help="Extend frequency range for older audio"),
            stereo_widening: bool = typer.Option(False, "--stereo-widening", help="Apply stereo widening enhancement"),
            dynamic_compression: bool = typer.Option(False, "--dynamic-compression", help="Apply intelligent dynamic compression"),
            audio_normalization: bool = typer.Option(True, "--audio-normalization/--no-normalization", help="Apply loudness normalization"),
            target_lufs: float = typer.Option(-16.0, "--target-lufs", help="Target loudness in LUFS (-23.0 for broadcast)"),
            declipping: bool = typer.Option(False, "--declipping", help="Remove audio clipping artifacts"),
            
            # Video upscaling options
            upscale_video: bool = typer.Option(False, "--upscale", "-u", help="Enable video upscaling"),
            upscale_method: str = typer.Option("lanczos", "--upscale-method", help="Upscaling method (realesrgan, lanczos, bicubic)"),
            upscale_factor: int = typer.Option(2, "--upscale-factor", help="Upscaling factor (2x, 4x)"),
            upscale_quality: str = typer.Option("high", "--upscale-quality", help="Upscaling quality (low, medium, high)"),
            replace_original: bool = typer.Option(False, "--replace-original", help="Replace original file with upscaled version"),
            
            # General options
            batch_file: str = typer.Option(None, "--batch-file", "-b", help="File containing URLs to download"),
            quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress output"),
            verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
            interactive: bool = typer.Option(False, "--interactive", "-i", help="Launch interactive mode after processing"),
        ):
            """Download media from URLs"""
            all_urls = []
            
            # Handle URLs from arguments
            if urls:
                all_urls.extend(urls)
                
            # Load URLs from batch file if provided
            if batch_file:
                try:
                    with open(batch_file, 'r') as f:
                        batch_urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]
                        all_urls.extend(batch_urls)
                except Exception as e:
                    console.print(f"[bold red]Error loading batch file: {str(e)}[/]")
                    return 1
            
            # Ensure we have URLs to process
            if not all_urls:
                console.print("[bold red]No URLs provided and no batch file specified.[/]")
                return 1            # Configure options
            options = {
                "audio_only": audio_only,
                "resolution": resolution,
                "format_id": format_id,
                "output_dir": output_dir,
                "filename": filename,
                "audio_format": audio_format,
                "audio_quality": audio_quality,
                
                # Existing audio enhancement
                "upmix_71": upmix_71,
                "denoise": denoise,
                
                # New comprehensive audio enhancement options
                "enhance_audio": enhance_audio,
                "audio_enhancement_level": audio_enhancement_level,
                "audio_enhancement_preset": audio_enhancement_preset,
                "noise_reduction": noise_reduction,
                "noise_reduction_strength": noise_reduction_strength,
                "upscale_sample_rate": upscale_sample_rate,
                "target_sample_rate": target_sample_rate,
                "frequency_extension": frequency_extension,
                "stereo_widening": stereo_widening,
                "dynamic_compression": dynamic_compression,
                "audio_normalization": audio_normalization,
                "target_lufs": target_lufs,
                "declipping": declipping,
                
                # Video upscaling
                "upscale_video": upscale_video,
                "upscale_method": upscale_method,
                "upscale_factor": upscale_factor,
                "upscale_quality": upscale_quality,
                "replace_original": replace_original,
                
                # General options
                "quiet": quiet,
                "verbose": verbose,
                "interactive": interactive,
            }
            
            # Use the execute_download method to handle all download logic
            return self.execute_download(all_urls, options)        # Interactive mode command        
        @app.command("interactive", help="Run in interactive mode")
        def interactive():
            """Run in enhanced interactive mode with cyberpunk interface"""
            from .interactive_mode import launch_enhanced_interactive_mode
            launch_enhanced_interactive_mode(self.config)
            return 0
            
        # Modern interactive interface command        
        @app.command("modern", help="Run with modern interactive interface")
        def modern():
            """Run with modern beautiful interactive interface"""
            try:
                from Theme.modern_interactive import run_modern_interactive
                run_modern_interactive(self.config)
            except ImportError as e:
                console.print(f"[bold red]Modern interface not available: {str(e)}[/]")
                console.print(FALLBACK_INTERACTIVE_MSG)
                from .interactive_mode import launch_enhanced_interactive_mode
                launch_enhanced_interactive_mode(self.config)
            except Exception as e:
                console.print(f"[bold red]Error launching modern interface: {str(e)}[/]")
                console.print(FALLBACK_INTERACTIVE_MSG)
                from .interactive_mode import launch_enhanced_interactive_mode
                launch_enhanced_interactive_mode(self.config)
            return 0
            
        # New textual interface command
        @app.command("textual", help="Run with modern Textual interface")
        def textual():
            """Run with modern Textual interface"""
            try:
                # Import at runtime to avoid dependencies if not used
                from Theme.textual_interface import start_textual_interface
                # Pass the current CLI instance to maintain state
                start_textual_interface(self.config)
            except ImportError as e:
                console.print(f"[bold yellow]Textual interface not available: {str(e)}[/]")
                console.print("[yellow]Falling back to enhanced interactive mode.[/]")
                from .interactive_mode import launch_enhanced_interactive_mode
                launch_enhanced_interactive_mode(self.config)
        
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
            return 0        # Run speedtest command
        @app.command("speedtest", help="Run enhanced network speed test with detailed analysis")
        def speedtest():
            """Run enhanced network speed test with comprehensive metrics and recommendations"""
            console.print("[bold cyan]🌐 Starting Enhanced Network Speed Test...[/]")
            self.run_async(run_speedtest(detailed=True, use_cache=False, console=console))
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
        
        # Audio Enhancement Commands Sub-application
        audio_app = typer.Typer(help="Audio enhancement and processing commands")
        app.add_typer(audio_app, name="audio")
        
        @audio_app.command("enhance", help="Enhance local audio files")
        def audio_enhance(
            input_file: str = typer.Argument(..., help="Input audio file path"),
            output_file: str = typer.Option(None, "--output", "-o", help="Output file path"),
            preset: str = typer.Option(None, "--preset", "-p", help="Enhancement preset: podcast, music, speech, broadcast, restoration"),
            level: str = typer.Option("medium", "--level", "-l", help="Enhancement level: light, medium, aggressive"),
            noise_reduction: bool = typer.Option(True, "--noise-reduction/--no-noise-reduction", help="Apply noise reduction"),
            noise_strength: float = typer.Option(0.6, "--noise-strength", help="Noise reduction strength (0.0-1.0)"),
            upscale_sample_rate: bool = typer.Option(False, "--upscale-sample-rate", help="Upscale sample rate"),
            target_sample_rate: int = typer.Option(48000, "--target-sample-rate", help="Target sample rate"),
            stereo_widening: bool = typer.Option(False, "--stereo-widening", help="Apply stereo widening"),
            normalization: bool = typer.Option(True, "--normalization/--no-normalization", help="Apply normalization"),
            target_lufs: float = typer.Option(-16.0, "--target-lufs", help="Target loudness in LUFS"),
        ):
            """Enhance local audio files with comprehensive processing"""
            return self._audio_enhance_command(
                input_file, output_file, preset, level, noise_reduction, noise_strength,
                upscale_sample_rate, target_sample_rate, stereo_widening, normalization, target_lufs
            )
        
        @audio_app.command("presets", help="List available enhancement presets")
        def audio_presets(
            detailed: bool = typer.Option(False, "--detailed", "-d", help="Show detailed preset information"),
        ):
            """List available audio enhancement presets"""
            return self._audio_presets_command(detailed)
        
        @audio_app.command("analyze", help="Analyze audio file quality")
        def audio_analyze(
            input_file: str = typer.Argument(..., help="Input audio file path"),
            recommend: bool = typer.Option(False, "--recommend", "-r", help="Recommend best preset"),
        ):
            """Analyze audio file and get quality metrics"""
            return self._audio_analyze_command(input_file, recommend)
        
        @audio_app.command("batch", help="Batch process multiple audio files")
        def audio_batch(
            input_dir: str = typer.Argument(..., help="Input directory containing audio files"),
            output_dir: str = typer.Option(None, "--output-dir", "-o", help="Output directory"),
            preset: str = typer.Option("music", "--preset", "-p", help="Enhancement preset to apply"),
            pattern: str = typer.Option("*.{mp3,wav,flac,m4a}", "--pattern", help="File pattern to match"),
            recursive: bool = typer.Option(False, "--recursive", "-r", help="Search recursively"),
        ):
            """Batch process multiple audio files"""
            return self._audio_batch_command(input_dir, output_dir, preset, pattern, recursive)
        
        @audio_app.command("create-preset", help="Create custom enhancement preset")
        def audio_create_preset(
            name: str = typer.Argument(..., help="Preset name"),
            description: str = typer.Option("Custom preset", "--description", "-d", help="Preset description"),
            level: str = typer.Option("medium", "--level", help="Enhancement level"),
            noise_reduction: bool = typer.Option(True, "--noise-reduction/--no-noise-reduction", help="Apply noise reduction"),
            noise_strength: float = typer.Option(0.6, "--noise-strength", help="Noise reduction strength"),
            normalization: bool = typer.Option(True, "--normalization/--no-normalization", help="Apply normalization"),
            target_lufs: float = typer.Option(-16.0, "--target-lufs", help="Target loudness in LUFS"),
        ):
            """Create a custom enhancement preset"""
            return self._audio_create_preset_command(name, description, level, noise_reduction, noise_strength, normalization, target_lufs)
        
        # Advanced system management commands        
        @app.command("scheduler", help="Manage download scheduler")
        def scheduler_command(
            action: str = typer.Argument(..., help="Action: status, pause, resume, clear"),
            priority: int = typer.Option(5, "--priority", help="Set priority for queue operations"),
            interactive: bool = typer.Option(False, "--interactive", "-i", help="Launch interactive mode after processing"),
        ):
            """Manage the advanced download scheduler"""
            return self.run_async(self._scheduler_command_async(action, priority, interactive))
            
        @app.command("performance", help="Show performance metrics and optimization")
        def performance_command(
            action: str = typer.Argument("status", help="Action: status, optimize, monitor"),
            duration: int = typer.Option(10, "--duration", help="Monitoring duration in seconds"),        ):
            """Show performance metrics and optimization"""
            return self.run_async(self._performance_command_async(action, duration))
            
        @app.command("queue", help="Manage download queue")
        def queue_command(
            action: str = typer.Argument(..., help="Action: list, add, remove, clear"),
            url: str = typer.Option(None, "--url", help="URL for add operation"),
            priority: int = typer.Option(5, "--priority", help="Priority for add operation (1-10)"),
            task_id: str = typer.Option(None, "--id", help="Task ID for remove operation"),
        ):
            """Manage the download queue"""
            return self.run_async(self._queue_command_async(action, url, priority, task_id))
            
        @app.command("monitor", help="Real-time system monitoring")
        def monitor_command(
            interval: int = typer.Option(2, "--interval", help="Update interval in seconds"),
            duration: int = typer.Option(60, "--duration", help="Total monitoring duration"),
        ):
            """Real-time system monitoring dashboard"""
            return self.run_async(self._monitor_command_async(interval, duration))
        
        # Configuration management commands
        @app.command("clear-cache", help="Clear cache data")
        def clear_cache_command(
            cache_type: str = typer.Option("all", "--type", help="Cache type to clear (all, metadata, downloads, sessions, thumbnails, temp)"),
            dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be deleted without actually deleting"),
            no_confirm: bool = typer.Option(False, "--yes", "-y", help=SKIP_CONFIRMATION_HELP),
        ):
            """Clear cached data with safety checks"""
            return self._clear_cache_command(cache_type, dry_run, not no_confirm)
        
        # Config subcommands using a group
        config_app = typer.Typer(help="Configuration management commands")
        app.add_typer(config_app, name="config")
        
        @config_app.command("edit", help="Edit configuration file")
        def config_edit(
            editor: str = typer.Option(None, "--editor", help="Editor to use (auto-detect if not specified)"),
            no_backup: bool = typer.Option(False, "--no-backup", help="Skip creating backup before editing"),
        ):
            """Open configuration file in editor with validation and backup"""
            return self._config_edit_command(editor, not no_backup)
        
        @config_app.command("show", help="Display current configuration")
        def config_show(
            format_type: str = typer.Option("table", "--format", "-f", help="Output format (table, json, yaml)"),
            category: str = typer.Option(None, "--category", "-c", help="Filter by category (download, video, audio, network, interface, advanced)"),
            non_default: bool = typer.Option(False, "--non-default", help="Only show non-default values"),
            output: str = typer.Option(None, "--output", "-o", help="Save to file instead of displaying"),
        ):
            """Display current configuration settings"""
            return self._config_show_command(format_type, category, non_default, output)
        
        @config_app.command("backup", help="Manage configuration backups")
        def config_backup(
            action: str = typer.Argument("list", help="Action: list, create, restore"),
            backup_name: str = typer.Option(None, "--name", help="Backup name for restore action"),
        ):
            """Manage configuration backups"""
            return self._config_backup_command(action, backup_name)
        @config_app.command("reset", help="Reset configuration to defaults")
        def config_reset(
            category: str = typer.Option(None, "--category", help="Reset only specific category"),no_confirm: bool = typer.Option(False, "--yes", "-y", help=SKIP_CONFIRMATION_HELP),
        ):
            """Reset configuration to default values"""
            return self._config_reset_command(category, not no_confirm)
            
        # Customization subcommands using a group
        customize_app = typer.Typer(help="Customization and theming commands")
        app.add_typer(customize_app, name="customize")
        
        @customize_app.command("theme", help="Manage themes")
        def customize_theme(
            action: str = typer.Argument("show", help="Action: show, set, list, create"),
            theme_name: str = typer.Option(None, "--theme", help="Theme name for set action"),
            colors: str = typer.Option(None, "--colors", help="Custom colors in JSON format"),
        ):
            """Manage application themes"""
            return self._customize_theme_command(action, theme_name, colors)
        
        @customize_app.command("performance", help="Configure performance settings")
        def customize_performance(
            setting: str = typer.Option(None, "--setting", help=SETTING_MODIFY_HELP),
            value: str = typer.Option(None, "--value", help=NEW_VALUE_HELP),
            show_all: bool = typer.Option(False, "--show", help="Show all performance settings"),
        ):
            """Configure performance settings"""
            return self._customize_performance_command(setting, value, show_all)
        
        @customize_app.command("interface", help="Configure interface preferences")
        def customize_interface(
            setting: str = typer.Option(None, "--setting", help=SETTING_MODIFY_HELP),
            value: str = typer.Option(None, "--value", help=NEW_VALUE_HELP),
            show_all: bool = typer.Option(False, "--show", help="Show all interface settings"),
        ):
            """Configure interface preferences"""
            return self._customize_interface_command(setting, value, show_all)
        
        @customize_app.command("behavior", help="Configure behavior preferences")
        def customize_behavior(
            setting: str = typer.Option(None, "--setting", help=SETTING_MODIFY_HELP),
            value: str = typer.Option(None, "--value", help=NEW_VALUE_HELP),
            show_all: bool = typer.Option(False, "--show", help="Show all behavior settings"),
        ):
            """Configure behavior preferences"""
            return self._customize_behavior_command(setting, value, show_all)
        
        @customize_app.command("alias", help="Manage command aliases")
        def customize_alias(
            action: str = typer.Argument("list", help="Action: list, add, remove"),
            alias: str = typer.Option(None, "--alias", help="Alias name"),
            command: str = typer.Option(None, "--command", help="Command for alias"),
        ):
            """Manage command aliases"""
            return self._customize_alias_command(action, alias, command)
        
        @customize_app.command("profile", help="Manage configuration profiles")
        def customize_profile(
            action: str = typer.Argument("list", help="Action: list, create, load, delete"),
            profile_name: str = typer.Option(None, "--name", help="Profile name"),
        ):
            """Manage configuration profiles"""
            return self._customize_profile_command(action, profile_name)
        
        @customize_app.command("export", help="Export customization settings")
        def customize_export(
            output_file: str = typer.Argument(..., help="Output file path"),
            format_type: str = typer.Option("yaml", "--format", help="Export format (yaml, json, toml)"),
        ):
            """Export customization settings to file"""
            return self._customize_export_command(output_file, format_type)
        
        @customize_app.command("import", help="Import customization settings")
        def customize_import(
            input_file: str = typer.Argument(..., help="Input file path"),
        ):
            """Import customization settings from file"""
            return self._customize_import_command(input_file)
        
        @customize_app.command("reset", help="Reset customization to defaults")
        def customize_reset(
            no_confirm: bool = typer.Option(False, "--yes", "-y", help=SKIP_CONFIRMATION_HELP),
        ):
            """Reset all customization settings to defaults"""
            return self._customize_reset_command(not no_confirm)
            
        # P2P (Peer-to-Peer) file sharing commands
        p2p_app = typer.Typer(help="Peer-to-peer file sharing commands")
        app.add_typer(p2p_app, name="p2p")
        
        @p2p_app.command("start", help="Start P2P service")
        def p2p_start():
            """Start P2P service for file sharing"""
            return self.run_async(self._p2p_start_command())
            
        @p2p_app.command("stop", help="Stop P2P service")
        def p2p_stop():
            """Stop P2P service"""
            return self.run_async(self._p2p_stop_command())
            
        @p2p_app.command("status", help="Show P2P service status")
        def p2p_status():
            """Show P2P service status and peer information"""
            return self.run_async(self._p2p_status_command())
            
        @p2p_app.command("share", help="Share a file via P2P network")
        def p2p_share(
            file_path: str = typer.Argument(..., help="Path to file to share"),
            max_peers: int = typer.Option(10, "--max-peers", help="Maximum number of peers to serve"),
            encryption: bool = typer.Option(True, "--encryption/--no-encryption", help="Enable encryption"),
        ):
            """Share a file via P2P network and get share code"""
            return self.run_async(self._p2p_share_command(file_path, max_peers, encryption))
            
        @p2p_app.command("fetch", help="Download file using share code")
        def p2p_fetch(
            share_code: str = typer.Argument(..., help="Share code from file sharer"),
            output_dir: str = typer.Option(".", "--output-dir", "-o", help="Directory to save downloaded file"),
        ):
            """Download file using share code"""
            return self.run_async(self._p2p_fetch_command(share_code, output_dir))
            
        @p2p_app.command("discover", help="Discover available peers")
        def p2p_discover(
            query: str = typer.Option(None, "--query", "-q", help="Search query for content discovery"),
            timeout: int = typer.Option(30, "--timeout", "-t", help="Discovery timeout in seconds"),
        ):
            """Discover peers on the P2P network"""
            return self.run_async(self._p2p_discover_command(query, timeout))
            
        @p2p_app.command("peers", help="List connected peers")
        def p2p_peers():
            """List all connected P2P peers"""
            return self.run_async(self._p2p_peers_command())
            
        @p2p_app.command("library", help="Manage P2P libraries")
        def p2p_library(
            action: str = typer.Argument(..., help="Action: create, list, share, search"),
            library_name: str = typer.Option(None, "--name", help="Library name"),
            directory: str = typer.Option(None, "--directory", "-d", help="Directory to add to library"),
            friend_id: str = typer.Option(None, "--friend", help="Friend peer ID to share with"),
            query: str = typer.Option(None, "--query", "-q", help="Search query"),
        ):
            """Manage P2P libraries for organized sharing"""
            return self.run_async(self._p2p_library_command(action, library_name, directory, friend_id, query))
            
        return app
    
    async def _show_active_downloads_async(self) -> None:
        """Show active downloads asynchronously"""
        async with AsyncSessionManager(self.config["session_file"]) as sm:
            sessions = sm.get_active_sessions()
            console_obj = Console()
            if sessions:
                console_obj.print("[bold green]Active downloads:[/]")
                for session in sessions:
                    console_obj.print(f"- {session.get('url', 'Unknown URL')}")
            else:
                console_obj.print("[bold yellow]No active downloads[/]")
                
    async def interactive_mode(self) -> None:
        """Rich interactive mode with command history"""
        console_obj = Console()
        console_obj.print("[bold cyan]Starting interactive mode[/]")
        
        # Try textual interface first, fallback to simple mode
        if await self._try_textual_interface(console_obj):
            return
            
        # Run simple interactive mode
        await self._run_simple_interactive_mode(console_obj)
    async def _try_textual_interface(self, console_obj: Console) -> bool:
        """Try to launch enhanced interactive interface, return True if successful"""
        try:
            from .interactive_mode import launch_enhanced_interactive_mode
            launch_enhanced_interactive_mode(self.config)
            return True
        except ImportError as e:
            console_obj.print(f"[yellow]Could not load enhanced interface: {str(e)}[/]")
            console_obj.print(FALLBACK_SIMPLE_MSG)
            return False
    
    async def _run_simple_interactive_mode(self, console_obj: Console) -> None:
        """Run simple fallback interactive mode"""
        while True:
            try:
                command = console_obj.input("[bold cyan]Enter command (or 'help', 'exit'):[/] ")
                command = command.strip().lower()
                
                if await self._handle_command(command, console_obj):
                    break  # Exit was requested
                    
            except KeyboardInterrupt:
                console_obj.print(INTERRUPTED_MSG)
                continue
            except Exception as error:
                console_obj.print(f"[bold red]Command error:[/] {str(error)}")
                continue
    
    async def _handle_command(self, command: str, console_obj: Console) -> bool:
        """Handle interactive command. Returns True if exit was requested."""
        if command in ['exit', 'quit']:
            console_obj.print("[bold cyan]Exiting interactive mode[/]")
            return True
            
        elif command == 'help':
            self._show_help(console_obj)
            
        elif command.startswith('download '):
            await self._handle_download_command(command, console_obj)
        elif command:
            console_obj.print(f"{UNKNOWN_COMMAND_MSG} {command}")
            console_obj.print(HELP_AVAILABLE_MSG)
            
        return False
    
    def _show_help(self, console_obj: Console) -> None:
        """Show help text for interactive mode"""
        console_obj.print("[bold cyan]Available commands:[/]")
        console_obj.print("  [green]download [URL][/] - Download media from URL")
        console_obj.print("  [green]help[/] - Show this help")
        console_obj.print("  [green]exit[/] or [green]quit[/] - Exit interactive mode")
    
    async def _handle_download_command(self, command: str, console_obj: Console) -> None:
        """Handle download command in interactive mode"""
        url = command[9:].strip()
        if not url:
            console_obj.print("[yellow]Please provide a URL to download[/]")
            return
            
        console_obj.print(f"[cyan]Starting download of:[/] {url}")
        try:
            options = {}  # Default options
            await self.download_manager.download(url, **options)            
            console_obj.print(f"[bold green]Download complete:[/] {url}")
        except Exception as e:
            console_obj.print(f"[bold red]Download error:[/] {str(e)}")
    
    async def _scheduler_command_async(self, action: str, _priority: int, interactive: bool = False) -> int:
        """Handle scheduler command asynchronously"""
        if not self.download_manager.advanced_scheduler:
            console.print("[bold red]Advanced scheduler not available[/]")
            return 1
            
        scheduler = self.download_manager.advanced_scheduler
        
        result = 0
        if action == "status":
            result = self._show_scheduler_status(scheduler)
        elif action in ["pause", "resume", "clear"]:
            result = await self._handle_scheduler_action(scheduler, action)
        else:
            console.print(f"[bold red]Unknown action: {action}[/]")
            console.print("Available actions: status, pause, resume, clear")
            result = 1
            
        # Launch interactive mode if requested and command succeeded
        if result == 0 and interactive:
            console.print("\n[bold cyan]🎮 Launching interactive mode...[/]")
            self._launch_interactive_mode()
            
        return result

    def _show_scheduler_status(self, scheduler) -> int:
        """Show scheduler status"""
        status = scheduler.get_status()
        console.print("[bold cyan]Scheduler Status:[/]")
        console.print(f"  Active: {status.get('active', False)}")
        console.print(f"  Queue Size: {status.get('queue_size', 0)}")
        console.print(f"  Active Downloads: {status.get('active_downloads', 0)}")
        console.print(f"  Bandwidth Usage: {status.get('bandwidth_usage', 0):.2f} MB/s")
        return 0
        
    async def _handle_scheduler_action(self, scheduler, action: str) -> int:
        """Handle scheduler actions"""
        if action == "pause":
            await scheduler.pause_all()
            console.print(SCHEDULER_PAUSED_MSG)        
        elif action == "resume":
            await scheduler.resume_all()
            console.print("[green]Scheduler resumed[/]")
        elif action == "clear":
            await scheduler.clear_queue()
            console.print(QUEUE_CLEARED_MSG)
        return 0
    async def _performance_command_async(self, action: str, duration: int) -> int:
        """Handle performance command asynchronously"""
        if not self.download_manager.performance_monitor:
            console.print("[bold red]Performance monitor not available[/]")
            return 1
            
        monitor = self.download_manager.performance_monitor
        
        if action == "status":
            metrics = monitor.get_current_metrics()
            recommendations = monitor.get_optimization_recommendations()
            
            console.print("[bold cyan]System Performance:[/]")
            console.print(f"  CPU Usage: {metrics.get('cpu_percent', 0):.1f}%")
            console.print(f"  Memory Usage: {metrics.get('memory_percent', 0):.1f}%")
            console.print(f"  Disk Usage: {metrics.get('disk_percent', 0):.1f}%")
            console.print(f"  Network: {metrics.get('network_mbps', 0):.2f} MB/s")
            
            if recommendations:
                console.print("\n[bold yellow]Recommendations:[/]")
                for rec in recommendations:
                    console.print(f"  • {rec}")
                    
        elif action == "optimize":
            result = await self.download_manager.optimize_performance()
            console.print("[bold cyan]Performance Optimization:[/]")
            console.print(f"  Status: {result.get('status', 'unknown')}")
            
            optimizations = result.get('optimizations_applied', [])
            if optimizations:
                console.print("  Applied optimizations:")
                for opt in optimizations:
                    console.print(f"    • {opt}")
            else:
                console.print("  No optimizations needed")
                
        elif action == "monitor":
            console.print(f"[cyan]Monitoring performance for {duration} seconds...[/]")
            
            import time
            start_time = time.time()
            while time.time() - start_time < duration:
                metrics = monitor.get_current_metrics()
                console.print(f"\rCPU: {metrics.get('cpu_percent', 0):.1f}% | "
                            f"Memory: {metrics.get('memory_percent', 0):.1f}% | "
                            f"Network: {metrics.get('network_mbps', 0):.2f} MB/s", end="")
                await asyncio.sleep(1)
            console.print("\n[green]Monitoring complete[/]")
            
        else:
            console.print(f"[bold red]Unknown action: {action}[/]")
            console.print("Available actions: status, optimize, monitor")
            return 1
            
        return 0

    async def _queue_command_async(self, action: str, url: str, priority: int, task_id: str) -> int:
        """Handle queue command asynchronously"""
        if not self.download_manager.advanced_scheduler:
            console.print("[bold red]Advanced scheduler not available[/]")
            return 1
            
        scheduler = self.download_manager.advanced_scheduler
        
        if action == "list":
            queue_info = scheduler.get_queue_info()
            console.print("[bold cyan]Download Queue:[/]")
            
            if not queue_info:
                console.print("  Queue is empty")
            else:
                for item in queue_info:
                    console.print(f"  ID: {item.get('id', 'N/A')} | "
                                f"URL: {item.get('url', 'N/A')[:50]}... | "
                                f"Priority: {item.get('priority', 0)} | "
                                f"Status: {item.get('status', 'unknown')}")
                                
        elif action == "add":
            if not url:
                console.print("[bold red]URL required for add operation[/]")
                return 1
                
            task_id = await scheduler.add_download(
                url=url,
                options={},
                priority=priority
            )
            console.print(f"[green]Added download to queue with ID: {task_id}[/]")
            
        elif action == "remove":
            if not task_id:
                console.print("[bold red]Task ID required for remove operation[/]")
                return 1
                
            success = await scheduler.cancel_download(task_id)
            if success:
                console.print(f"[green]Removed task {task_id} from queue[/]")
            else:
                console.print(f"[red]Failed to remove task {task_id}[/]")
                
        elif action == "clear":
            await scheduler.clear_queue()
            console.print("[yellow]Queue cleared[/]")
            
        else:
            console.print(f"[bold red]Unknown action: {action}[/]")
            console.print("Available actions: list, add, remove, clear")
            return 1
            
        return 0

    async def _monitor_command_async(self, interval: int, duration: int) -> int:
        """Handle real-time monitoring command"""
        if not self.download_manager.performance_monitor:
            console.print("[bold red]Performance monitor not available[/]")
            return 1
            
        from rich.live import Live
        from rich.table import Table
        from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn
        
        monitor = self.download_manager.performance_monitor
        
        def create_monitor_table():
            table = Table(title="System Performance Monitor")
            table.add_column("Metric", style="cyan")
            table.add_column("Current", style="green")
            table.add_column("Status", style="yellow")
            
            metrics = monitor.get_current_metrics()
            
            # CPU
            cpu_percent = metrics.get('cpu_percent', 0)
            cpu_status = "HIGH" if cpu_percent > 80 else "NORMAL"
            table.add_row("CPU Usage", f"{cpu_percent:.1f}%", cpu_status)
            
            # Memory
            mem_percent = metrics.get('memory_percent', 0)
            mem_status = "HIGH" if mem_percent > 80 else "NORMAL"
            table.add_row("Memory Usage", f"{mem_percent:.1f}%", mem_status)
            
            # Network
            network_mbps = metrics.get('network_mbps', 0)
            table.add_row("Network", f"{network_mbps:.2f} MB/s", "ACTIVE" if network_mbps > 0.1 else "IDLE")
            
            # Downloads
            if self.download_manager.advanced_scheduler:
                status = self.download_manager.advanced_scheduler.get_status()
                active_downloads = status.get('active_downloads', 0)
                queue_size = status.get('queue_size', 0)
                table.add_row("Active Downloads", str(active_downloads), "BUSY" if active_downloads > 0 else "IDLE")
                table.add_row("Queue Size", str(queue_size), "QUEUED" if queue_size > 0 else "EMPTY")
            
            return table
        console.print(f"[cyan]Starting real-time monitoring for {duration} seconds...[/]")
        console.print("[yellow]Press Ctrl+C to stop early[/]")
        
        import time
        start_time = time.time()
        
        try:
            with Live(create_monitor_table(), refresh_per_second=1/interval) as live:
                while time.time() - start_time < duration:
                    await asyncio.sleep(interval)
                    live.update(create_monitor_table())
        except KeyboardInterrupt:
            console.print("\n[yellow]Monitoring stopped by user[/]")
        
        console.print("[green]Monitoring complete[/]")
        return 0

    # Configuration management command implementations
    
    def _clear_cache_command(self, cache_type: str, dry_run: bool, confirm: bool) -> int:
        """Implementation for clear-cache command"""
        try:
            # Convert string to CacheType enum
            if cache_type.lower() == "all":
                cache_types = [CacheType.ALL]
            else:
                try:
                    cache_types = [CacheType(cache_type.lower())]
                except ValueError:
                    console.print(f"[red]Invalid cache type: {cache_type}[/]")
                    console.print("[yellow]Valid types: all, metadata, downloads, sessions, thumbnails, temp[/]")
                    return 1
            
            # Execute cache clearing
            result = self.config_manager.clear_cache(
                cache_types=cache_types,
                confirm=confirm,
                dry_run=dry_run
            )
            
            return 0 if result["success"] else 1
            
        except Exception as e:
            console.print(f"[red]Error clearing cache: {str(e)}[/]")
            return 1    
    def _config_edit_command(self, editor: str, create_backup: bool) -> int:
        """Implementation for config edit command"""
        try:
            result = self.config_manager.edit_config(
                editor=editor,
                create_backup=create_backup
            )
            
            return 0 if result["success"] else 1
            
        except Exception as e:
            console.print(f"[red]Error editing configuration: {str(e)}[/]")
            return 1
    def _config_show_command(self, format_type: str, category: str, non_default: bool, output: str) -> int:
        """Implementation for config show command"""
        try:
            result = self.config_manager.show_config(
                format_type=format_type,
                filter_category=category,
                filter_non_default=non_default,
                output_file=output
            )
            
            return 0 if result else 1
            
        except Exception as e:
            console.print(f"[red]Error displaying configuration: {str(e)}[/]")
            return 1
    def _config_backup_command(self, action: str, backup_name: str) -> int:
        """Implementation for config backup command"""
        try:
            if action == "list":
                backups = self.config_manager.list_backups_simple()
                if backups:
                    console.print("[bold cyan]Available configuration backups:[/]")
                    for backup in backups:
                        console.print(f"  - {backup}")
                else:
                    console.print("[yellow]No configuration backups found[/]")
                return 0
                
            elif action == "create":
                result = self.config_manager.create_backup()
                if result["success"]:
                    console.print(f"[green]Backup created: {result['backup_file']}[/]")
                else:
                    console.print(f"[red]Failed to create backup: {result.get('error', 'Unknown error')}[/]")
                return 0 if result["success"] else 1
                
            elif action == "restore":
                if not backup_name:
                    console.print("[red]Backup name required for restore action[/]")
                    return 1
                    
                result = self.config_manager.restore_backup(backup_name)
                if result["success"]:
                    console.print(f"[green]Configuration restored from: {backup_name}[/]")
                else:
                    console.print(f"[red]Failed to restore backup: {result.get('error', 'Unknown error')}[/]")
                return 0 if result["success"] else 1
                
            else:
                console.print(f"[red]Invalid action: {action}[/]")
                console.print("[yellow]Valid actions: list, create, restore[/]")
                return 1
                
        except Exception as e:
            console.print(f"[red]Error managing backups: {str(e)}[/]")
            return 1

    def _config_reset_command(self, category: str, confirm: bool) -> int:
        """Implementation for config reset command"""
        try:
            if confirm:
                if category:
                    message = f"reset the '{category}' configuration category to defaults"
                else:
                    message = "reset ALL configuration to defaults"
                    
                if not Confirm.ask(f"Are you sure you want to {message}?"):
                    console.print("[yellow]Reset cancelled by user[/]")
                    return 0
            
            result = self.config_manager.reset_config(category=category)
            
            if result["success"]:
                if category:
                    console.print(f"[green]Configuration category '{category}' reset to defaults[/]")
                else:
                    console.print("[green]All configuration reset to defaults[/]")
            else:
                console.print(f"[red]Failed to reset configuration: {result.get('error', 'Unknown error')}[/]")
                
            return 0 if result["success"] else 1
        except Exception as e:
            console.print(f"[red]Error resetting configuration: {str(e)}[/]")
            return 1

    # Customization command implementations
    def _customize_theme_command(self, action: str, theme_name: str, colors: str) -> int:
        """Implementation for customize theme command"""
        try:
            if action == "show":
                config = self.customization_manager.load_config()
                console.print(f"[cyan]Current theme:[/] {config.theme_preset.value}")
                if config.custom_theme_colors:
                    console.print("[cyan]Custom colors are active[/]")
                return 0
                
            elif action == "list":
                console.print("[cyan]Available themes:[/]")
                for theme in ThemePreset:
                    console.print(f"  - {theme.value}")
                return 0
                
            elif action == "set":
                if not theme_name:
                    console.print("[red]Theme name required for set action[/]")
                    return 1
                    
                try:
                    theme_preset = ThemePreset(theme_name)
                    success = self.customization_manager.update_theme(theme_preset=theme_preset)
                    if success:
                        console.print(f"[green]Theme set to: {theme_name}[/]")
                    else:
                        console.print(f"[red]Failed to set theme: {theme_name}[/]")
                    return 0 if success else 1
                except ValueError:
                    console.print(f"[red]Unknown theme: {theme_name}[/]")
                    console.print("[yellow]Use 'customize theme list' to see available themes[/]")
                    return 1
                    
            elif action == "create":
                if not colors:
                    console.print("[red]Colors JSON required for create action[/]")
                    console.print("[yellow]Example: --colors '{\"primary\": \"#ff0000\", \"secondary\": \"#00ff00\"}'[/]")
                    return 1
                    
                try:
                    import json
                    color_dict = json.loads(colors)
                    from .customization_manager import ThemeColors
                    custom_colors = ThemeColors(**color_dict)
                    success = self.customization_manager.update_theme(custom_colors=custom_colors)
                    if success:
                        console.print("[green]Custom theme created and applied[/]")
                    else:
                        console.print("[red]Failed to create custom theme[/]")
                    return 0 if success else 1
                except (json.JSONDecodeError, TypeError) as e:
                    console.print(f"[red]Invalid colors JSON: {e}[/]")
                    return 1
                    
            else:
                console.print(f"[red]Invalid action: {action}[/]")
                console.print("[yellow]Valid actions: show, list, set, create[/]")
                return 1
                
        except Exception as e:
            console.print(f"[red]Error managing themes: {str(e)}[/]")
            return 1

    def _customize_performance_command(self, setting: str, value: str, show_all: bool) -> int:
        """Implementation for customize performance command"""
        try:
            if show_all or (not setting and not value):
                config = self.customization_manager.load_config()
                console.print("[cyan]Performance Settings:[/]")
                
                table = Table()
                table.add_column("Setting", style="cyan")
                table.add_column("Value", style="green")
                table.add_column("Description", style="dim")
                
                perf = config.performance
                table.add_row("max_concurrent_downloads", str(perf.max_concurrent_downloads), "Maximum simultaneous downloads")
                table.add_row("concurrent_fragment_downloads", str(perf.concurrent_fragment_downloads), "Fragments per download")
                table.add_row("chunk_size", str(perf.chunk_size), "Download chunk size (bytes)")
                table.add_row("connection_timeout", str(perf.connection_timeout), "Connection timeout (seconds)")
                table.add_row("max_retries", str(perf.max_retries), "Maximum retry attempts")
                table.add_row("global_bandwidth_limit", str(perf.global_bandwidth_limit), "Global bandwidth limit (0=unlimited)")
                table.add_row("max_memory_usage_mb", str(perf.max_memory_usage_mb), "Memory limit (MB)")
                
                console.print(table)
                return 0
                
            if setting and value:
                # Convert value to appropriate type
                try:
                    if setting in ["max_concurrent_downloads", "concurrent_fragment_downloads", "chunk_size", 
                                   "max_retries", "global_bandwidth_limit", "per_download_bandwidth_limit", 
                                   "max_memory_usage_mb", "cache_size_mb", "temp_cleanup_interval"]:
                        value = int(value)
                    elif setting in ["connection_timeout", "read_timeout", "retry_delay"]:
                        value = float(value)
                    elif setting in ["exponential_backoff"]:
                        value = value.lower() in ["true", "1", "yes", "on"]
                    
                    success = self.customization_manager.update_performance(**{setting: value})
                    if success:
                        console.print(f"[green]Performance setting updated: {setting} = {value}[/]")
                    else:
                        console.print(f"[red]Failed to update setting: {setting}[/]")
                    return 0 if success else 1
                    
                except ValueError:
                    console.print(f"[red]Invalid value for {setting}: {value}[/]")
                    return 1
            else:
                console.print(BOTH_SETTING_VALUE_MSG)
                return 1
                
        except Exception as e:
            console.print(f"[red]Error configuring performance: {str(e)}[/]")
            return 1

    def _customize_interface_command(self, setting: str, value: str, show_all: bool) -> int:
        """Implementation for customize interface command"""
        try:
            if show_all or (not setting and not value):
                config = self.customization_manager.load_config()
                console.print("[cyan]Interface Settings:[/]")
                
                table = Table()
                table.add_column("Setting", style="cyan")
                table.add_column("Value", style="green")
                table.add_column("Description", style="dim")
                
                interface = config.interface
                table.add_row("interface_mode", interface.interface_mode.value, "Display mode")
                table.add_row("enable_keyboard_shortcuts", str(interface.enable_keyboard_shortcuts), "Enable shortcuts")
                table.add_row("auto_complete", str(interface.auto_complete), "Auto-completion")
                table.add_row("show_progress_bars", str(interface.show_progress_bars), "Show progress bars")
                table.add_row("show_status_bar", str(interface.show_status_bar), "Show status bar")
                table.add_row("animate_progress", str(interface.animate_progress), "Animate progress")
                table.add_row("sidebar_width", str(interface.sidebar_width), "Sidebar width")
                table.add_row("max_display_items", str(interface.max_display_items), "Max items to display")
                
                console.print(table)
                return 0
                
            if setting and value:
                # Convert value to appropriate type
                try:
                    if setting == "interface_mode":
                        value = InterfaceMode(value)
                    elif setting in ["enable_keyboard_shortcuts", "auto_complete", "show_progress_bars", 
                                     "show_status_bar", "show_menu_bar", "animate_progress", 
                                     "high_contrast_mode", "large_text_mode", "screen_reader_mode"]:
                        value = value.lower() in ["true", "1", "yes", "on"]
                    elif setting in ["sidebar_width", "content_width", "max_display_items", "history_size"]:
                        value = int(value)
                    
                    success = self.customization_manager.update_interface(**{setting: value})
                    if success:
                        console.print(f"[green]Interface setting updated: {setting} = {value}[/]")
                    else:
                        console.print(f"[red]Failed to update setting: {setting}[/]")
                    return 0 if success else 1
                    
                except ValueError:
                    console.print(f"[red]Invalid value for {setting}: {value}[/]")
                    return 1
            else:
                console.print(BOTH_SETTING_VALUE_MSG)
                return 1
                
        except Exception as e:
            console.print(f"[red]Error configuring interface: {str(e)}[/]")
            return 1

    def _customize_behavior_command(self, setting: str, value: str, show_all: bool) -> int:
        """Implementation for customize behavior command"""
        try:
            if show_all or (not setting and not value):
                config = self.customization_manager.load_config()
                console.print("[cyan]Behavior Settings:[/]")
                
                table = Table()
                table.add_column("Setting", style="cyan")
                table.add_column("Value", style="green")
                table.add_column("Description", style="dim")
                
                behavior = config.behavior
                table.add_row("confirm_file_overwrite", str(behavior.confirm_file_overwrite), "Confirm before overwriting files")
                table.add_row("confirm_large_downloads", str(behavior.confirm_large_downloads), "Confirm large downloads")
                table.add_row("confirm_cache_clear", str(behavior.confirm_cache_clear), "Confirm cache clearing")
                table.add_row("auto_organize_downloads", str(behavior.auto_organize_downloads), "Auto-organize downloads")
                table.add_row("auto_update_metadata", str(behavior.auto_update_metadata), "Auto-update metadata")
                table.add_row("auto_generate_thumbnails", str(behavior.auto_generate_thumbnails), "Auto-generate thumbnails")
                table.add_row("resume_incomplete_downloads", str(behavior.resume_incomplete_downloads), "Resume incomplete downloads")
                table.add_row("continue_on_error", str(behavior.continue_on_error), "Continue on errors")
                table.add_row("auto_save_sessions", str(behavior.auto_save_sessions), "Auto-save sessions")
                
                console.print(table)
                return 0
                
            if setting and value:
                # Convert value to appropriate type
                try:
                    if setting in ["large_download_threshold_mb", "session_auto_save_interval", "max_session_history"]:
                        value = int(value)
                    else:
                        value = value.lower() in ["true", "1", "yes", "on"]
                    
                    success = self.customization_manager.update_behavior(**{setting: value})
                    if success:
                        console.print(f"[green]Behavior setting updated: {setting} = {value}[/]")
                    else:
                        console.print(f"[red]Failed to update setting: {setting}[/]")
                    return 0 if success else 1
                    
                except ValueError:
                    console.print(f"[red]Invalid value for {setting}: {value}[/]")
                    return 1
            else:
                console.print(BOTH_SETTING_VALUE_MSG)
                return 1
                
        except Exception as e:
            console.print(f"[red]Error configuring behavior: {str(e)}[/]")
            return 1

    def _customize_alias_command(self, action: str, alias: str, command: str) -> int:
        """Implementation for customize alias command"""
        try:
            if action == "list":
                aliases = self.customization_manager.get_aliases()
                if aliases:
                    console.print("[cyan]Command Aliases:[/]")
                    table = Table()
                    table.add_column("Alias", style="cyan")
                    table.add_column("Command", style="green")
                    
                    for alias_name, cmd in aliases.items():
                        table.add_row(alias_name, cmd)
                    
                    console.print(table)
                else:
                    console.print("[yellow]No aliases configured[/]")
                return 0
                
            elif action == "add":
                if not alias or not command:
                    console.print("[red]Both alias and command required for add action[/]")
                    return 1
                    
                success = self.customization_manager.add_alias(alias, command)
                if success:
                    console.print(f"[green]Alias added: {alias} -> {command}[/]")
                else:
                    console.print(f"[red]Failed to add alias: {alias}[/]")
                return 0 if success else 1
                
            elif action == "remove":
                if not alias:
                    console.print("[red]Alias name required for remove action[/]")
                    return 1
                    
                success = self.customization_manager.remove_alias(alias)
                if success:
                    console.print(f"[green]Alias removed: {alias}[/]")
                else:
                    console.print(f"[red]Alias not found: {alias}[/]")
                return 0 if success else 1
                
            else:
                console.print(f"[red]Invalid action: {action}[/]")
                console.print("[yellow]Valid actions: list, add, remove[/]")
                return 1
                
        except Exception as e:
            console.print(f"[red]Error managing aliases: {str(e)}[/]")
            return 1

    def _customize_profile_command(self, action: str, profile_name: str) -> int:
        """Implementation for customize profile command"""
        try:
            if action == "list":
                profiles = self.customization_manager.list_profiles()
                if profiles:
                    console.print("[cyan]Available Profiles:[/]")
                    for profile in profiles:
                        console.print(f"  - {profile}")
                else:
                    console.print("[yellow]No profiles found[/]")
                return 0
                
            elif action == "create":
                if not profile_name:
                    console.print("[red]Profile name required for create action[/]")
                    return 1
                    
                success = self.customization_manager.create_profile(profile_name)
                if success:
                    console.print(f"[green]Profile created: {profile_name}[/]")
                else:
                    console.print(f"[red]Failed to create profile: {profile_name}[/]")
                return 0 if success else 1
                
            elif action == "load":
                if not profile_name:
                    console.print("[red]Profile name required for load action[/]")
                    return 1
                    
                success = self.customization_manager.load_profile(profile_name)
                if success:
                    console.print(f"[green]Profile loaded: {profile_name}[/]")
                else:
                    console.print(f"[red]Failed to load profile: {profile_name}[/]")
                return 0 if success else 1
                
            elif action == "delete":
                if not profile_name:
                    console.print("[red]Profile name required for delete action[/]")
                    return 1
                    
                # This would need to be implemented in CustomizationManager
                console.print("[yellow]Profile deletion not yet implemented[/]")
                return 1
                
            else:
                console.print(f"[red]Invalid action: {action}[/]")
                console.print("[yellow]Valid actions: list, create, load, delete[/]")
                return 1
                
        except Exception as e:
            console.print(f"[red]Error managing profiles: {str(e)}[/]")
            return 1

    def _customize_export_command(self, output_file: str, format_type: str) -> int:
        """Implementation for customize export command"""
        try:
            try:
                config_format = ConfigFormat(format_type)
            except ValueError:
                console.print(f"[red]Invalid format: {format_type}[/]")
                console.print("[yellow]Valid formats: yaml, json, toml[/]")
                return 1
                
            success = self.customization_manager.export_config(output_file, config_format)
            if success:
                console.print(f"[green]Customization settings exported to: {output_file}[/]")
            else:
                console.print(f"[red]Failed to export settings to: {output_file}[/]")
            return 0 if success else 1
            
        except Exception as e:
            console.print(f"[red]Error exporting settings: {str(e)}[/]")
            return 1

    def _customize_import_command(self, input_file: str) -> int:
        """Implementation for customize import command"""
        try:
            success = self.customization_manager.import_config(input_file)
            if success:
                console.print(f"[green]Customization settings imported from: {input_file}[/]")
            else:
                console.print(f"[red]Failed to import settings from: {input_file}[/]")
            return 0 if success else 1
            
        except Exception as e:
            console.print(f"[red]Error importing settings: {str(e)}[/]")
            return 1

    def _customize_reset_command(self, confirm: bool) -> int:
        """Implementation for customize reset command"""
        try:
            if confirm:
                if not Confirm.ask("Are you sure you want to reset ALL customization settings to defaults?"):
                    console.print("[yellow]Reset cancelled by user[/]")
                    return 0
            
            success = self.customization_manager.reset_to_defaults()
            if success:
                console.print("[green]Customization settings reset to defaults[/]")
            else:
                console.print("[red]Failed to reset customization settings[/]")
            return 0 if success else 1        
        except Exception as e:
            console.print(f"[red]Error resetting customization: {str(e)}[/]")
            return 1
            
    # Audio Enhancement Command Implementations
    
    def _audio_enhance_command(self, input_file: str, output_file: str, preset: str, 
                              level: str, noise_reduction: bool, noise_strength: float,
                              upscale_sample_rate: bool, target_sample_rate: int,
                              stereo_widening: bool, normalization: bool, target_lufs: float) -> int:
        """Implementation for audio enhance command"""
        try:
            # Validate input file
            if not os.path.exists(input_file):
                console.print(f"[red]Input file not found: {input_file}[/]")
                return 1
            
            # Generate output filename if not provided
            if not output_file:
                input_path = Path(input_file)
                output_file = str(input_path.parent / f"{input_path.stem}_enhanced{input_path.suffix}")
            
            # Initialize audio processor
            processor = EnhancedAudioProcessor(self.config)
            
            # Create enhancement settings
            if preset:
                if preset.lower() not in AUDIO_ENHANCEMENT_PRESETS:
                    console.print(f"[red]Unknown preset: {preset}[/]")
                    console.print(f"[yellow]Available presets: {', '.join(AUDIO_ENHANCEMENT_PRESETS.keys())}[/]")
                    return 1
                
                settings = AUDIO_ENHANCEMENT_PRESETS[preset.lower()].settings
                console.print(f"[cyan]Using preset: {preset} - {AUDIO_ENHANCEMENT_PRESETS[preset.lower()].description}[/]")
            else:
                # Create custom settings
                settings = AudioEnhancementSettings(
                    level=level,
                    noise_reduction=noise_reduction,
                    noise_reduction_strength=noise_strength,
                    upscale_sample_rate=upscale_sample_rate,
                    target_sample_rate=target_sample_rate,
                    stereo_widening=stereo_widening,
                    normalization=normalization,
                    target_lufs=target_lufs
                )
            
            # Progress callback for status updates
            def progress_callback(stage: str, progress: int):
                console.print(f"[cyan]{stage}... ({progress}%)[/]")
            
            # Run enhancement
            console.print(f"[bold cyan]Enhancing audio file: {input_file}[/]")
            result = self.run_async(processor.enhance_audio_comprehensive(
                input_file, output_file, settings, progress_callback
            ))
            
            if result:
                console.print(f"[green]✅ Audio enhancement completed: {output_file}[/]")
                return 0
            else:
                console.print("[red]❌ Audio enhancement failed[/]")
                return 1
                
        except Exception as e:
            console.print(f"[red]Error enhancing audio: {str(e)}[/]")
            return 1
    
    def _audio_presets_command(self, detailed: bool) -> int:
        """Implementation for audio presets command"""
        try:
            console.print("[bold cyan]Available Audio Enhancement Presets:[/]")
            
            if detailed:
                for preset_name, preset in AUDIO_ENHANCEMENT_PRESETS.items():
                    console.print(f"\n[bold yellow]{preset.name}[/]")
                    console.print(f"  [dim]{preset.description}[/]")
                    settings = preset.settings
                    console.print(f"  Level: {settings.level}")
                    console.print(f"  Noise Reduction: {settings.noise_reduction} (strength: {settings.noise_reduction_strength})")
                    console.print(f"  Sample Rate Upscaling: {settings.upscale_sample_rate} (target: {settings.target_sample_rate})")
                    console.print(f"  Stereo Widening: {settings.stereo_widening}")
                    console.print(f"  Normalization: {settings.normalization} (target: {settings.target_lufs} LUFS)")
                    console.print(f"  Dynamic Compression: {settings.dynamic_compression}")
                    console.print(f"  Frequency Extension: {settings.frequency_extension}")
            else:
                table = Table()
                table.add_column("Preset", style="yellow")
                table.add_column("Description", style="dim")
                
                for preset_name, preset in AUDIO_ENHANCEMENT_PRESETS.items():
                    table.add_row(preset.name, preset.description)
                
                console.print(table)
            
            return 0
            
        except Exception as e:
            console.print(f"[red]Error listing presets: {str(e)}[/]")
            return 1
    
    def _audio_analyze_command(self, input_file: str, recommend: bool) -> int:
        """Implementation for audio analyze command"""
        try:
            # Validate input file
            if not os.path.exists(input_file):
                console.print(f"[red]Input file not found: {input_file}[/]")
                return 1
            
            # Initialize audio processor
            processor = EnhancedAudioProcessor(self.config)
            
            console.print(f"[cyan]Analyzing audio file: {input_file}[/]")
            
            # Get audio statistics
            stats = self.run_async(processor.get_audio_stats(input_file))
            if stats:
                console.print("\n[bold cyan]Audio File Statistics:[/]")
                console.print(f"  Duration: {stats.duration:.2f} seconds")
                console.print(f"  Sample Rate: {stats.sample_rate} Hz")
                console.print(f"  Channels: {stats.channels}")
                console.print(f"  Bit Rate: {stats.bitrate} kbps")
                console.print(f"  Format: {stats.format}")
            
            # Analyze quality
            quality = self.run_async(processor.analyze_audio_quality(input_file))
            if quality:
                console.print("\n[bold cyan]Quality Analysis:[/]")
                console.print(f"  Noise Level: {quality.noise_level:.2%}")
                console.print(f"  Dynamic Range: {quality.dynamics:.2f}")
                console.print(f"  Clipping: {quality.clipping:.2%}")
                console.print(f"  Peak Level: {quality.peak_level:.2f} dB")
                console.print(f"  RMS Level: {quality.rms_level:.2f} dB")
                console.print(f"  Frequency Range: {quality.frequency_range:.0f} Hz")
            
            # Recommend preset if requested
            if recommend:
                recommended = self.run_async(processor.recommend_preset(input_file))
                if recommended:
                    preset_info = AUDIO_ENHANCEMENT_PRESETS.get(recommended)
                    if preset_info:
                        console.print(f"\n[bold green]Recommended Preset: {preset_info.name}[/]")
                        console.print(f"  {preset_info.description}")
                        console.print(f"  [dim]Use: snatch audio enhance \"{input_file}\" --preset {recommended}[/]")
            
            return 0
            
        except Exception as e:
            console.print(f"[red]Error analyzing audio: {str(e)}[/]")
            return 1
    def _audio_batch_command(self, input_dir: str, output_dir: str, preset: str, 
                            pattern: str, recursive: bool) -> int:
        """Implementation for audio batch command"""
        try:
            # Validate input directory
            if not os.path.exists(input_dir):
                console.print(f"[red]Input directory not found: {input_dir}[/]")
                return 1
            
            # Set output directory
            if not output_dir:
                output_dir = os.path.join(input_dir, "enhanced")
            
            # Create output directory if needed
            os.makedirs(output_dir, exist_ok=True)
            
            # Find audio files
            search_pattern = os.path.join(input_dir, "**" if recursive else "", pattern)
            files = glob.glob(search_pattern, recursive=recursive)
            
            if not files:
                console.print(f"[yellow]No audio files found matching pattern: {pattern}[/]")
                return 0
            
            # Validate preset
            if preset.lower() not in AUDIO_ENHANCEMENT_PRESETS:
                console.print(f"[red]Unknown preset: {preset}[/]")
                console.print(f"[yellow]Available presets: {', '.join(AUDIO_ENHANCEMENT_PRESETS.keys())}[/]")
                return 1
            
            # Initialize processor
            processor = EnhancedAudioProcessor(self.config)
            settings = AUDIO_ENHANCEMENT_PRESETS[preset.lower()].settings
            
            console.print(f"[cyan]Found {len(files)} audio files to process[/]")
            console.print(f"[cyan]Using preset: {preset}[/]")
            
            processed = 0
            failed = 0
            
            for i, input_file in enumerate(files, 1):
                try:
                    # Generate output filename
                    input_path = Path(input_file)
                    output_file = os.path.join(output_dir, f"{input_path.stem}_enhanced{input_path.suffix}")
                    
                    console.print(f"[cyan]Processing {i}/{len(files)}: {input_path.name}[/]")
                    
                    # Progress callback
                    def progress_callback(stage: str, progress: int):
                        console.print(f"  [dim]{stage}... ({progress}%)[/]")
                    
                    # Process file
                    result = self.run_async(processor.enhance_audio_comprehensive(
                        input_file, output_file, settings, progress_callback
                    ))
                    if result:
                        processed += 1
                        console.print(f"  [green]✅ Completed: {output_file}[/]")
                    else:
                        failed += 1
                        console.print("  [red]❌ Failed to process[/]")
                        
                except Exception as e:
                    failed += 1
                    console.print(f"  [red]❌ Error: {str(e)}[/]")
            
            console.print("\n[bold cyan]Batch Processing Complete:[/]")
            console.print(f"  Processed: {processed}")
            console.print(f"  Failed: {failed}")
            console.print(f"  Total: {len(files)}")
            
            return 0 if failed == 0 else 1
            
        except Exception as e:
            console.print(f"[red]Error in batch processing: {str(e)}[/]")
            return 1
    
    def _audio_create_preset_command(self, name: str, description: str, level: str,
                                   noise_reduction: bool, noise_strength: float,
                                   normalization: bool, target_lufs: float) -> int:
        """Implementation for audio create-preset command"""
        try:
            # Validate preset name
            if name.lower() in AUDIO_ENHANCEMENT_PRESETS:
                console.print(f"[red]Preset '{name}' already exists[/]")
                return 1
            
            # Create custom settings
            settings = AudioEnhancementSettings(
                level=level,
                noise_reduction=noise_reduction,
                noise_reduction_strength=noise_strength,
                normalization=normalization,
                target_lufs=target_lufs
            )
            
            # Initialize processor and create preset
            processor = EnhancedAudioProcessor(self.config)
            result = self.run_async(processor.create_custom_preset(name, description, settings))
            
            if result:
                console.print(f"[green]✅ Custom preset created: {name}[/]")
                console.print(f"  Description: {description}")
                console.print(f"  [dim]Use: snatch audio enhance <file> --preset {name.lower()}[/]")
                return 0
            else:
                console.print(f"[red]❌ Failed to create preset: {name}[/]")
                return 1
                
        except Exception as e:
            console.print(f"[red]Error creating preset: {str(e)}[/]")
            return 1
            
    def _launch_interactive_mode(self) -> None:
        """Launch interactive mode with fallback to available interfaces"""
        try:
            # Try modern interface first
            import sys
            import os
            
            # Add parent directory to path for Theme import
            parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if parent_dir not in sys.path:
                sys.path.insert(0, parent_dir)
            
            from Theme.modern_interactive import run_modern_interactive
            console.print("[bold green]🚀 Starting modern interactive interface...[/]")
            run_modern_interactive(self.config)
        except ImportError as import_err:
            console.print(f"[yellow]Modern interface not available ({import_err}), trying enhanced mode...[/]")
            try:
                from .interactive_mode import launch_enhanced_interactive_mode
                console.print("[bold green]🚀 Starting enhanced interactive mode...[/]")
                launch_enhanced_interactive_mode(self.config)
            except ImportError:
                console.print("[red]Interactive mode not available. Please check your installation.[/]")
        except Exception as e:
            console.print(f"[red]Error launching interactive mode: {str(e)}[/]")
            console.print("[yellow]Falling back to enhanced interactive mode...[/]")
            try:
                from .interactive_mode import launch_enhanced_interactive_mode
                launch_enhanced_interactive_mode(self.config)
            except Exception as fallback_error:
                console.print(f"[red]Fallback also failed: {str(fallback_error)}[/")
    
    # P2P Command Implementations
    async def _p2p_start_command(self) -> int:
        """Start P2P service"""
        try:
            if not self.download_manager.p2p_manager:
                console.print("[red]P2P functionality not available. Check configuration.[/]")
                return 1
                
            console.print("[cyan]Starting P2P service...[/]")
            success = await self.download_manager.start_p2p_server()
            
            if success:
                peer_info = self.download_manager.p2p_manager.get_peer_info()
                console.print("[green]P2P service started successfully![/]")
                console.print(f"[cyan]Peer ID:[/] {peer_info.get('peer_id', 'Unknown')}")
                console.print(f"[cyan]Listening on:[/] {peer_info.get('ip', 'Unknown')}:{peer_info.get('port', 'Unknown')}")
                if peer_info.get('external_ip'):
                    console.print(f"[cyan]External address:[/] {peer_info['external_ip']}:{peer_info.get('external_port', peer_info.get('port'))}")
                return 0
            else:
                console.print(P2P_SERVICE_FAILED_MSG)
                return 1
                
        except Exception as e:
            console.print(f"[red]Error starting P2P service: {str(e)}[/]")
            return 1
    
    async def _p2p_stop_command(self) -> int:
        """Stop P2P service"""
        try:
            if not self.download_manager.p2p_manager:
                console.print(P2P_NOT_AVAILABLE_MSG)
                return 1
                
            console.print("[cyan]Stopping P2P service...[/]")
            await self.download_manager.stop_p2p_server()
            console.print("[green]P2P service stopped[/]")
            return 0
            
        except Exception as e:
            console.print(f"[red]Error stopping P2P service: {str(e)}[/]")
            return 1
    
    async def _p2p_status_command(self) -> int:
        """Show P2P service status"""
        try:
            if not self.download_manager.p2p_manager:
                console.print(P2P_NOT_AVAILABLE_MSG)
                return 1
            
            p2p_manager = self.download_manager.p2p_manager
            
            # Service status
            status = "Running" if p2p_manager.listening else "Stopped"
            console.print(f"[cyan]P2P Service Status:[/] {status}")
            
            if p2p_manager.listening:
                peer_info = p2p_manager.get_peer_info()
                console.print(f"[cyan]Peer ID:[/] {peer_info.get('peer_id', 'Unknown')}")
                console.print(f"[cyan]Local address:[/] {peer_info.get('ip', 'Unknown')}:{peer_info.get('port', 'Unknown')}")
                
                if peer_info.get('external_ip'):
                    console.print(f"[cyan]External address:[/] {peer_info['external_ip']}:{peer_info.get('external_port', peer_info.get('port'))}")
                    
                console.print(f"[cyan]NAT Type:[/] {peer_info.get('nat_type', 'Unknown')}")
                
                # Show connected peers
                peers = await self.download_manager.get_p2p_peers()
                console.print(f"[cyan]Connected Peers:[/] {len(peers)}")
                
                if peers:
                    table = Table()
                    table.add_column(PEER_ID_COLUMN, style="cyan")
                    table.add_column("Address", style="green")
                    table.add_column("Status", style="yellow")
                    table.add_column(LAST_SEEN_COLUMN, style="dim")
                    
                    for peer in peers:
                        last_seen = time.strftime('%H:%M:%S', time.localtime(peer.get('last_seen', 0)))
                        status = "Connected" if peer.get('connected') else "Disconnected"
                        table.add_row(
                            peer.get('peer_id', 'Unknown')[:12] + "...",
                            f"{peer.get('ip', 'Unknown')}:{peer.get('port', 'Unknown')}",
                            status,
                            last_seen
                        )
                    
                    console.print(table)
                
                # Show shared files
                shared_count = len(p2p_manager.shared_files) if hasattr(p2p_manager, 'shared_files') else 0
                console.print(f"[cyan]Shared Files:[/] {shared_count}")
                
            return 0
            
        except Exception as e:
            console.print(f"[red]Error getting P2P status: {str(e)}[/]")
            return 1
    
    async def _p2p_share_command(self, file_path: str, max_peers: int, encryption: bool) -> int:
        """Share a file via P2P network"""
        try:
            if not self.download_manager.p2p_manager:
                console.print(P2P_NOT_AVAILABLE_MSG)
                return 1
                
            if not os.path.exists(file_path):
                console.print(f"[red]File not found: {file_path}[/]")
                return 1
                
            # Ensure P2P service is running
            if not self.download_manager.p2p_manager.listening:
                console.print(P2P_SERVICE_STARTING_MSG)
                if not await self.download_manager.start_p2p_server():
                    console.print(P2P_SERVICE_FAILED_MSG)
                    return 1
            
            console.print(f"[cyan]Sharing file:[/] {file_path}")
            console.print(f"[cyan]Max peers:[/] {max_peers}")
            console.print(f"[cyan]Encryption:[/] {'Enabled' if encryption else 'Disabled'}")
            
            share_code = await self.download_manager.share_file_p2p(file_path)
            
            if share_code:
                console.print("[green]File shared successfully![/]")
                console.print(f"[bold cyan]Share Code:[/] [bold green]{share_code}[/]")
                console.print("[yellow]Share this code with others to let them download the file[/]")
                return 0
            else:
                console.print("[red]Failed to share file[/]")
                return 1
                
        except Exception as e:
            console.print(f"[red]Error sharing file: {str(e)}[/]")
            return 1
    
    async def _p2p_fetch_command(self, share_code: str, output_dir: str) -> int:
        """Download file using share code"""
        try:
            if not self.download_manager.p2p_manager:
                console.print(P2P_NOT_AVAILABLE_MSG)
                return 1
                
            if not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)
                
            # Ensure P2P service is running
            if not self.download_manager.p2p_manager.listening:
                console.print(P2P_SERVICE_STARTING_MSG)
                if not await self.download_manager.start_p2p_server():
                    console.print(P2P_SERVICE_FAILED_MSG)
                    return 1
            
            console.print(f"[cyan]Downloading file with share code:[/] {share_code}")
            console.print(f"[cyan]Output directory:[/] {output_dir}")
            
            success = await self.download_manager.p2p_manager.fetch_file(share_code, output_dir)
            
            if success:
                console.print("[green]File downloaded successfully![/]")
                console.print(f"[cyan]Saved to:[/] {output_dir}")
                return 0
            else:
                console.print("[red]Failed to download file[/]")
                console.print("[yellow]Check the share code and network connectivity[/]")
                return 1
                
        except Exception as e:
            console.print(f"[red]Error downloading file: {str(e)}[/]")
            return 1
    
    async def _p2p_discover_command(self, query: str, timeout: int) -> int:
        """Discover peers on P2P network"""
        try:
            if not self.download_manager.p2p_manager:
                console.print(P2P_NOT_AVAILABLE_MSG)
                return 1
                
            # Ensure P2P service is running
            if not self.download_manager.p2p_manager.listening:
                console.print(P2P_SERVICE_STARTING_MSG)
                if not await self.download_manager.start_p2p_server():
                    console.print(P2P_SERVICE_FAILED_MSG)
                    return 1
            
            console.print("[cyan]Discovering peers on P2P network...[/]")
            if query:
                console.print(f"[cyan]Search query:[/] {query}")
            console.print(f"[cyan]Timeout:[/] {timeout} seconds")
            
            # Start discovery with timeout
            discovered_peers = await asyncio.wait_for(
                self.download_manager.p2p_manager.discover_peers(query),
                timeout=timeout
            )
            
            if discovered_peers:
                console.print(f"[green]Discovered {len(discovered_peers)} peers:[/]")
                
                table = Table()
                table.add_column(PEER_ID_COLUMN, style="cyan")
                table.add_column("Address", style="green")
                table.add_column("NAT Type", style="yellow")
                table.add_column(LAST_SEEN_COLUMN, style="dim")
                
                for peer in discovered_peers:
                    last_seen = time.strftime('%H:%M:%S', time.localtime(peer.last_seen)) if peer.last_seen else "Unknown"
                    table.add_row(
                        peer.peer_id[:12] + "...",
                        f"{peer.ip}:{peer.port}",
                        peer.nat_type or "Unknown",
                        last_seen
                    )
                
                console.print(table)
                
                # Optionally, return the list of discovered peers
                # return [peer.peer_id for peer in discovered_peers]
                
            else:
                console.print("[yellow]No peers discovered[/]")
                return 0
                
        except asyncio.TimeoutError:
            console.print(f"[yellow]Discovery timed out after {timeout} seconds[/]")
            return 0
        except Exception as e:
            console.print(f"[red]Error during peer discovery: {str(e)}[/]")
            return 1
    
    async def _p2p_peers_command(self) -> int:
        """List connected P2P peers"""
        try:
            if not self.download_manager.p2p_manager:
                console.print(P2P_NOT_AVAILABLE_MSG)
                return 1
            
            peers = await self.download_manager.get_p2p_peers()
            
            if peers:
                console.print(f"[green]Connected Peers ({len(peers)}):[/]")
                
                table = Table()
                table.add_column(PEER_ID_COLUMN, style="cyan")
                table.add_column("Address", style="green")
                table.add_column("Status", style="yellow")
                table.add_column("NAT Type", style="dim")
                table.add_column(LAST_SEEN_COLUMN, style="dim")
                
                for peer in peers:
                    last_seen = time.strftime('%H:%M:%S', time.localtime(peer.get('last_seen', 0)))
                    status = "Connected" if peer.get('connected') else "Disconnected"
                    table.add_row(
                        peer.get('peer_id', 'Unknown')[:12] + "...",
                        f"{peer.get('ip', 'Unknown')}:{peer.get('port', 'Unknown')}",
                        status,
                        peer.get('nat_type', 'Unknown'),
                        last_seen
                    )
                
                console.print(table)
                return 0
            else:
                console.print("[yellow]No connected peers[/]")
                return 0
                
        except Exception as e:
            console.print(f"[red]Error getting peer list: {str(e)}[/]")
            return 1
    
    async def _p2p_library_command(self, action: str, library_name: str, directory: str, friend_id: str, query: str) -> int:
        """Manage P2P libraries"""
        try:
            if not self.download_manager.p2p_manager:
                console.print(P2P_NOT_AVAILABLE_MSG)
                return 1            
            if action == "create":
                if not library_name:
                    console.print("[red]Library name required for create action[/]")
                    return 1
                    
                console.print(f"[cyan]Creating library:[/] {library_name}")
                if directory:
                    console.print(f"[cyan]Directory to add:[/] {directory}")
                # Implementation would depend on P2P manager library methods
                console.print("[yellow]Library creation functionality coming soon[/]")
                return 0
                
            elif action == "list":
                console.print("[cyan]Available Libraries:[/]")
                # Show libraries if implemented
                console.print("[yellow]Library listing functionality coming soon[/]")
                return 0
                
            elif action == "share":
                if not library_name or not friend_id:
                    console.print("[red]Library name and friend ID required for share action[/]")
                    return 1
                    
                console.print(f"[cyan]Sharing library '{library_name}' with friend:[/] {friend_id}")
                console.print("[yellow]Library sharing functionality coming soon[/]")
                return 0
                
            elif action == "search":
                if not query:
                    console.print("[red]Search query required for search action[/]")
                    return 1
                    
                console.print(f"[cyan]Searching libraries for:[/] {query}")
                console.print("[yellow]Library search functionality coming soon[/]")
                return 0
                
            else:
                console.print(f"[red]Invalid action: {action}[/]")
                console.print("[yellow]Valid actions: create, list, share, search[/]")
                return 1
                
        except Exception as e:
            console.print(f"[red]Error managing P2P library: {str(e)}[/]")
            return 1


def main():
    """Main entry point for the CLI application"""
    try:
        # Initialize configuration
        config = asyncio.run(initialize_config_async())
        
        # Create CLI instance  
        cli = EnhancedCLI(config)
        
        # Setup and run the Typer app
        app = cli.setup_argparse()
        app()
        
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user[/]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Fatal error: {str(e)}[/]")
        sys.exit(1)


if __name__ == "__main__":
    main()
