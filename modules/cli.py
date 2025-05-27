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
from .error_handler import EnhancedErrorHandler, handle_errors, ErrorCategory, ErrorSeverity

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
            return self._run_download_safely(urls, options)
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
            upmix_71: bool = typer.Option(False, "--upmix-7.1", help="Upmix audio to 7.1 surround"),
            denoise: bool = typer.Option(False, "--denoise", help="Apply noise reduction to audio"),
            upscale_video: bool = typer.Option(False, "--upscale", "-u", help="Enable video upscaling"),
            upscale_method: str = typer.Option("lanczos", "--upscale-method", help="Upscaling method (realesrgan, lanczos, bicubic)"),
            upscale_factor: int = typer.Option(2, "--upscale-factor", help="Upscaling factor (2x, 4x)"),
            upscale_quality: str = typer.Option("high", "--upscale-quality", help="Upscaling quality (low, medium, high)"),
            replace_original: bool = typer.Option(False, "--replace-original", help="Replace original file with upscaled version"),
            batch_file: str = typer.Option(None, "--batch-file", "-b", help="File containing URLs to download"),
            quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress output"),
            verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
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
                "upscale_video": upscale_video,
                "upscale_method": upscale_method,
                "upscale_factor": upscale_factor,
                "upscale_quality": upscale_quality,
                "replace_original": replace_original,
                "quiet": quiet,
                "verbose": verbose,
            }
            
            # Use the execute_download method to handle all download logic
            return self.execute_download(all_urls, options)        # Interactive mode command
        @app.command("interactive", help="Run in interactive mode")
        def interactive():
            """Run in enhanced interactive mode with cyberpunk interface"""
            from .interactive_mode import launch_enhanced_interactive_mode
            launch_enhanced_interactive_mode(self.config)
            return 0
              # New textual interface command
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
            return 0
          # Run speedtest command
        @app.command("speedtest", help="Run download speed test")
        def speedtest():
            """Run download speed test"""
            self.run_async(run_speedtest())
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
        
        # Advanced system management commands
        @app.command("scheduler", help="Manage download scheduler")
        def scheduler_command(
            action: str = typer.Argument(..., help="Action: status, pause, resume, clear"),
            priority: int = typer.Option(5, "--priority", help="Set priority for queue operations"),
        ):
            """Manage the advanced download scheduler"""
            return self.run_async(self._scheduler_command_async(action, priority))
            
        @app.command("performance", help="Show performance metrics and optimization")
        def performance_command(
            action: str = typer.Argument("status", help="Action: status, optimize, monitor"),
            duration: int = typer.Option(10, "--duration", help="Monitoring duration in seconds"),
        ):
            """Show performance metrics and optimization"""
            return self.run_async(self._performance_command_async(action, duration))
            
        @app.command("queue", help="Manage download queue")
        def queue_command(
            action: str = typer.Argument(..., help="Action: list, add, remove, clear"),
            url: str = typer.Option(None, "--url", help="URL for add operation"),
            priority: int = typer.Option(5, "--priority", help="Priority for add operation (1-10)"),
            task_id: str = typer.Option(None, "--id", help="Task ID for remove operation"),        ):
            """Manage the download queue"""
            return self.run_async(self._queue_command_async(action, url, priority, task_id))
            
        @app.command("monitor", help="Real-time system monitoring")
        def monitor_command(
            interval: int = typer.Option(2, "--interval", help="Update interval in seconds"),
            duration: int = typer.Option(60, "--duration", help="Total monitoring duration"),
        ):
            """Real-time system monitoring dashboard"""
            return self.run_async(self._monitor_command_async(interval, duration))
            
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
            console_obj.print("[yellow]Falling back to simple interactive mode...[/]")
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
                console_obj.print("\n[yellow]Operation interrupted. Type 'exit' to quit.[/]")
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
            console_obj.print(f"[yellow]Unknown command:[/] {command}")
            console_obj.print("[yellow]Type 'help' for available commands[/]")
            
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
    async def _scheduler_command_async(self, action: str, _priority: int) -> int:
        """Handle scheduler command asynchronously"""
        if not self.download_manager.advanced_scheduler:
            console.print("[bold red]Advanced scheduler not available[/]")
            return 1
            
        scheduler = self.download_manager.advanced_scheduler
        
        if action == "status":
            return self._show_scheduler_status(scheduler)
        elif action in ["pause", "resume", "clear"]:
            return await self._handle_scheduler_action(scheduler, action)
        else:
            console.print(f"[bold red]Unknown action: {action}[/]")
            console.print("Available actions: status, pause, resume, clear")
            return 1

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
            console.print("[yellow]Scheduler paused[/]")
        elif action == "resume":
            await scheduler.resume_all()
            console.print("[green]Scheduler resumed[/]")
        elif action == "clear":
            await scheduler.clear_queue()
            console.print("[yellow]Queue cleared[/]")
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
        # Proper event loop handling without deprecation warnings
        try:
            loop = asyncio.get_running_loop()
            # We're in a running loop - this shouldn't happen for CLI entry
            loop.run_until_complete(async_main())
        except RuntimeError:
            # No running loop - this is the normal case for CLI
            asyncio.run(async_main())
    except Exception:
        console.print_exception()
        sys.exit(1)

if __name__ == "__main__":
    main()
