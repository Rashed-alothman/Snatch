from typing import List, Optional
from .config import test_functionality, initialize_config_async, check_for_updates
from .logging_config import setup_logging, CustomHelpFormatter
from .common_utils import list_supported_sites, display_system_stats
from .manager import DownloadManager, DownloadStats
from .defaults import VERSION, EXAMPLES
from colorama import Fore, Style, init
from .session import run_speedtest
import typer
import logging
import signal
import time
import sys
import rich
import asyncio
from pathlib import Path

# Initialize typer app with better help formatting
app = typer.Typer(
    help="Snatch - Download Anything!",
    add_completion=True,
    rich_markup_mode="rich",
    context_settings={"help_option_names": ["-h", "--help"]}
)

def version_callback(value: bool):
    """Handle version display"""
    if value:
        rich.print(f"[cyan]Snatch[/cyan] version [green]{VERSION}[/green]")
        raise typer.Exit()

def signal_handler(sig, frame):
    """Handle graceful exit on CTRL+C"""
    rich.print("\n[yellow]Operation cancelled by user. Exiting gracefully...[/yellow]")
    sys.exit(0)

# Setup signal handler
signal.signal(signal.SIGINT, signal_handler)

def ensure_context(ctx: typer.Context) -> dict:
    """Ensure context object exists and is initialized"""
    if ctx.obj is None:
        ctx.obj = {}
    return ctx.obj

@app.callback()
def app_callback(
    ctx: typer.Context,
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose debug logging"),
    json_log: bool = typer.Option(False, "--log-format-json", help="Enable JSON format logging"),
):
    """Initialize shared context and configure logging"""
    obj = ensure_context(ctx)
    obj["verbose"] = verbose
    
    # Configure logging
    level = logging.DEBUG if verbose else logging.INFO
    setup_logging(json_format=json_log, level=level)

@app.callback(invoke_without_command=True)
def callback(
    ctx: typer.Context,
    version: bool = typer.Option(None, "--version", "-V", callback=version_callback, help="Show version information"),
):
    """
    Snatch - A versatile downloader for videos and audio from various sources
    """
    # Show help if no command specified
    if ctx.invoked_subcommand is None:
        rich.print(ctx.get_help())
        raise typer.Exit()

@app.command()
def download(
    ctx: typer.Context,
    urls: List[str] = typer.Argument(None, help="URLs to download"),
    audio_only: bool = typer.Option(False, "--audio-only", "-a", help="Download audio only"),
    resolution: str = typer.Option(None, "--resolution", "-r", help="Specify video resolution (e.g., 1080)"),
    format_id: str = typer.Option(None, "--format-id", "-f", help="Select specific format IDs"),
    filename: str = typer.Option(None, "--filename", help="Specify custom filename"),
    audio_format: str = typer.Option("opus", "--audio-format", help="Specify audio format [opus|mp3|flac|wav|m4a]"),
    output_dir: str = typer.Option(None, "--output-dir", "-o", help="Specify custom output directory"),
    resume: bool = typer.Option(False, "--resume", help="Resume interrupted downloads"),
    no_cache: bool = typer.Option(False, "--no-cache", help="Skip using cached info"),
    no_retry: bool = typer.Option(False, "--no-retry", help="Do not retry failed downloads"),
    throttle: str = typer.Option(None, "--throttle", help="Limit download speed (e.g., 500KB/s)"),
    aria2c: bool = typer.Option(False, "--aria2c", help="Use aria2c for downloading"),
    detailed_progress: bool = typer.Option(False, "--detailed-progress", "-d", help="Show detailed progress"),
    organize: bool = typer.Option(None, "--organize/--no-organize", help="Enable/disable file organization"),
    org_template: str = typer.Option(None, "--org-template", help='Custom organization template (e.g. "{uploader}/{year}/{title}")'),
    audio_channels: int = typer.Option(2, "--audio-channels", help="Audio channels: 2 (stereo) or 8 (7.1 surround)"),
    non_interactive: bool = typer.Option(False, "--non-interactive", help="Disable interactive prompts"),
    test_formats: bool = typer.Option(False, "--test-formats", help="Test all available formats"),
    fast: bool = typer.Option(True, "--fast/--no-fast", help="Use fast format selection"),
):
    """
    Download content from specified URLs with various options
    """
    if not urls:
        rich.print("[red]No URLs provided. Use --help for usage information.[/red]")
        raise typer.Exit(1)

    try:
        # Initialize configuration
        config = initialize_config_async()
        if config is None:
            rich.print("[red]Failed to initialize configuration.[/red]")
            raise typer.Exit(1)
            
        # Get context object with defaults
        ctx_obj = ensure_context(ctx)
        
        # Update config with CLI options
        config.update({
            "verbose": ctx_obj.get("verbose", False),
            "detailed_progress": detailed_progress,
            "organize": organize if organize is not None else config.get("organize", False),
        })

        if output_dir:
            if audio_only:
                config["audio_output"] = output_dir
            else:
                config["video_output"] = output_dir

        if org_template:
            content_type = "audio" if audio_only else "video"
            config["organization_templates"][content_type] = org_template

        # Initialize download manager
        manager = DownloadManager(config)
        stats = DownloadStats()

        # Prepare download options
        options = {
            "audio_only": audio_only,
            "resolution": resolution,
            "format_id": format_id,
            "filename": filename,
            "audio_format": audio_format,
            "resume": resume,
            "no_cache": no_cache,
            "no_retry": no_retry,
            "throttle": throttle,
            "use_aria2c": aria2c,
            "audio_channels": audio_channels,
            "non_interactive": non_interactive,
            "test_all_formats": test_formats,
            "fast_mode": fast,
        }

        # Start downloads
        start_time = time.time()
        results = asyncio.run(manager.batch_download(urls, **options))

        # Update statistics
        success_count = sum(1 for r in results if r)
        stats.add_download(True, success_count)
        stats.add_download(False, len(results) - success_count)
        stats.total_time = time.time() - start_time

        # Show final statistics
        stats.display(detailed=detailed_progress)

    except Exception as e:
        rich.print(f"[red]Error during download: {str(e)}[/red]")
        raise typer.Exit(1)

@app.command()
def speedtest():
    """Run network speed test to optimize download settings"""
    run_speedtest()

@app.command()
def list_sites():
    """List all supported download sites"""
    list_supported_sites()

@app.command()
def system_info():
    """Display system resource statistics"""
    display_system_stats()

@app.command()
def interactive(
    audio_only: bool = typer.Option(False, "--audio-only", "-a", help="Start in audio-only mode"),
    output_dir: str = typer.Option(None, "--output-dir", "-o", help="Default output directory"),
    audio_format: str = typer.Option("opus", "--audio-format", help="Default audio format [opus|mp3|flac|wav|m4a]"),
    detailed_progress: bool = typer.Option(True, "--detailed-progress/--no-progress", help="Show detailed download progress"),
    organize: bool = typer.Option(None, "--organize/--no-organize", help="Enable/disable file organization"),
    non_interactive: bool = typer.Option(False, "--non-interactive", help="Disable interactive prompts"),
    audio_channels: int = typer.Option(2, "--audio-channels", help="Audio channels: 2 (stereo) or 8 (7.1 surround)"),
    org_template: str = typer.Option(None, "--org-template", help='Custom organization template (e.g. "{uploader}/{year}/{title}")'),
    resume: bool = typer.Option(False, "--resume", help="Resume interrupted downloads"),
    no_cache: bool = typer.Option(False, "--no-cache", help="Skip using cached info"),
    no_retry: bool = typer.Option(False, "--no-retry", help="Do not retry failed downloads"),
    throttle: str = typer.Option(None, "--throttle", help="Limit download speed (e.g., 500KB/s)"),
    aria2c: bool = typer.Option(False, "--aria2c", help="Use aria2c for downloading"),
):
    """Start interactive download mode with a rich UI"""
    try:
        # Initialize configuration with CLI options
        config = initialize_config_async()
        if config is None:
            rich.print("[red]Failed to initialize configuration.[/red]")
            raise typer.Exit(1)
            
        # Update config with interactive-specific options
        config.update({
            "audio_only": audio_only,
            "audio_format": audio_format,
            "detailed_progress": detailed_progress,
            "organize": organize if organize is not None else config.get("organize", False),
            "non_interactive": non_interactive,
            "audio_channels": audio_channels,
            "resume": resume,
            "no_cache": no_cache,
            "no_retry": no_retry,
            "throttle": throttle,
            "use_aria2c": aria2c,
        })
        
        # Handle output directory
        if output_dir:
            if audio_only:
                config["audio_output"] = output_dir
            else:
                config["video_output"] = output_dir
                
        # Handle organization template
        if org_template:
            content_type = "audio" if audio_only else "video"
            config["organization_templates"][content_type] = org_template
                
        # Start interactive mode
        from .interactive_mode import start_interactive_mode
        start_interactive_mode(config)
        
    except KeyboardInterrupt:
        rich.print("\n[yellow]Interactive mode cancelled.[/yellow]")
        raise typer.Exit(0)
    except Exception as e:
        rich.print(f"[red]Error in interactive mode: {str(e)}[/red]")
        raise typer.Exit(1)

@app.command()
def test():
    """Run basic functionality tests"""
    rich.print(f"\n[cyan]╔{'═' * 40}╗[/cyan]")
    rich.print("[cyan]║          Snatch Test Suite              ║[/cyan]")
    rich.print(f"[cyan]╚{'═' * 40}╝[/cyan]")
    
    success = test_functionality()
    if not success:
        raise typer.Exit(1)

@app.command()
def share(
    file: Path = typer.Argument(..., help="File to share via P2P"),
    encrypt: bool = typer.Option(True, "--encrypt/--no-encrypt", "-e", help="Enable/disable encryption"),
    dht: bool = typer.Option(True, "--dht/--no-dht", "-d", help="Enable/disable DHT"),
):
    """Share a file via P2P with encryption and DHT support."""
    try:
        from .p2p import share_file_cmd, P2PError
        code = share_file_cmd(str(file))
        rich.print(f"\n[cyan]Share code:[/cyan] [green]{code}[/green]")
        rich.print("\n[yellow]File is now being shared. Press Ctrl+C to stop sharing.[/yellow]\n")
        
        # Show sharing info
        info_panel = rich.panel.Panel(
            "\n".join([
                "[cyan]🔒 Encryption:[/cyan] " + ("[green]Enabled[/green]" if encrypt else "[yellow]Disabled[/yellow]"),
                "[cyan]🌐 DHT:[/cyan] " + ("[green]Enabled[/green]" if dht else "[yellow]Disabled[/yellow]"),
                "\n[dim]Waiting for incoming connections...[/dim]"
            ]),
            title="[bold]Share Info",
            border_style="cyan"
        )
        rich.print(info_panel)
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            rich.print("\n[yellow]Sharing stopped.[/yellow]")
    except P2PError as e:
        rich.print(f"[red]P2P Error: {str(e)}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        rich.print(f"[red]Error sharing file: {str(e)}[/red]")
        raise typer.Exit(1)

@app.command()
def fetch(
    code: str = typer.Argument(..., help="Share code to fetch file from"),
    out: Path = typer.Option(Path("."), "--output-dir", "-o", help="Output directory"),
    no_verify: bool = typer.Option(False, "--no-verify", help="Skip integrity verification")
):
    """Fetch a file using a share code with progress tracking."""
    try:
        from .p2p import fetch_file_cmd, PeerRefusedError, IntegrityError, P2PError
        
        # Create output directory if it doesn't exist
        out.mkdir(parents=True, exist_ok=True)
        
        try:
            output_file = fetch_file_cmd(code, str(out))
            rich.print(f"\n[green]✓ Download complete![/green]")
            rich.print(f"[cyan]File saved to:[/cyan] {output_file}")
        except PeerRefusedError:
            rich.print("\n[red]❌ Peer refused the request[/red]")
            rich.print("[yellow]The file owner denied the download request.[/yellow]")
            raise typer.Exit(1)
        except IntegrityError as e:
            rich.print("\n[red]❌ Integrity check failed[/red]")
            rich.print("[yellow]The downloaded file may be corrupted or tampered with.[/yellow]")
            raise typer.Exit(2)
        except P2PError as e:
            rich.print(f"\n[red]❌ P2P Error: {e}[/red]")
            raise typer.Exit(1)
            
    except Exception as e:
        rich.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(2)

def main() -> None:
    """Entry point for the CLI application"""
    app()