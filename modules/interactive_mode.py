#!/usr/bin/env python3
"""
interactive_mode.py

Centralizes interactive prompt logic for the Snatch CLI tool.
Features:
  - Interactive selection of media type, codecs, channels, resolution
  - Non-interactive (scriptable) overrides via flags
  - SpinnerAnimation for background feedback
  - CommandHistory for REPL command recall
  - Clean error handling and defaults
  - Integration hooks for snatch_api (extract_info, download)
"""
import sys
import threading
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

import typer
from colorama import Fore, Style, init as colorama_init

from .logging_config import setup_logging
from .utils import sanitize_filename

# Initialize Colorama for ANSI support
colorama_init(autoreset=True)

app = typer.Typer(add_completion=False)

# --- Spinner for background tasks ---
class SpinnerAnimation:
    def __init__(self, message: str = "Working..."):
        self.message = message
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._spin, daemon=True)

    def _spin(self):
        chars = "|/-\\"
        idx = 0
        while not self._stop.is_set():
            sys.stdout.write(f"\r{chars[idx % len(chars)]} {self.message}")
            sys.stdout.flush()
            idx += 1
            time.sleep(0.1)
        sys.stdout.write("\r" + " " * (len(self.message) + 2) + "\r")

    def start(self):
        self._stop.clear()
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._thread.join(0.1)

# --- Interactive Selectors ---
def select_media_type(non_interactive: bool = False, default: str = "video") -> str:
    if non_interactive:
        return default
    choice = typer.prompt("Select media type", default="1",
                          show_default=False,
                          type=typer.Choice(["1", "2"], case_sensitive=False))
    return "audio" if choice == "2" else "video"

def select_audio_codec(available: List[str], non_interactive: bool = False, default: Optional[str] = None) -> str:
    if non_interactive:
        return default or available[-1]
    typer.echo("Available audio codecs:")
    for i, c in enumerate(available, 1):
        typer.echo(f"  {i}) {c}")
    idx = typer.prompt("Choose codec", default=str(len(available)))
    try:
        return available[int(idx) - 1]
    except Exception:
        return available[-1]

def select_audio_channels(non_interactive: bool = False, default: int = 2) -> int:
    opts = [1, 2, 6]
    if non_interactive:
        return default
    typer.echo("Audio channel options:")
    for i, c in enumerate(opts, 1):
        typer.echo(f"  {i}) {c} channels")
    idx = typer.prompt("Choose channels", default="2")
    try:
        return opts[int(idx) - 1]
    except Exception:
        return default

def select_video_format(formats: List[Dict[str, Any]], non_interactive: bool = False, default: Optional[str] = None) -> str:
    # derive unique sorted resolutions
    res_list = sorted({f.get("resolution") for f in formats if f.get("resolution")})
    if not res_list:
        raise ValueError("No video resolutions available")
    if non_interactive:
        return default or res_list[-1]
    typer.echo("Available resolutions:")
    for i, r in enumerate(res_list, 1):
        typer.echo(f"  {i}) {r}")
    idx = typer.prompt("Choose resolution", default=str(len(res_list)))
    try:
        return res_list[int(idx) - 1]
    except Exception:
        return res_list[-1]

# --- High-level Interactive Command ---
@app.command("download")
def download(
    url: str = typer.Argument(..., help="URL to download"),
    media: Optional[str] = typer.Option(None, "--media", help="media type: video|audio"),
    codec: Optional[str] = typer.Option(None, "--codec", help="audio codec (if audio)"),
    channels: Optional[int] = typer.Option(None, "--channels", help="audio channels (if audio)"),
    resolution: Optional[str] = typer.Option(None, "--resolution", help="video resolution"),
    non_interactive: bool = typer.Option(False, "--no-interactive", help="use defaults without prompts"),
):
    """
    Download a URL with optional interactive format selection.
    """
    setup_logging()
    from .manager import DownloadManager
    from .cli import snatch_api

    # Extract metadata
    spinner = SpinnerAnimation("Fetching format info...")
    spinner.start()
    try:
        info = snatch_api["extract_info"](url)
    finally:
        spinner.stop()

    if not info or "formats" not in info:
        typer.secho("Error: Could not retrieve format information. Try `snatch inspect <URL>`.", fg=typer.colors.RED)
        raise typer.Exit(code=2)

    # Determine media type
    chosen_media = media or select_media_type(non_interactive, default="video")

    opts: Dict[str, Any] = {}
    if chosen_media == "audio":
        acodecs = sorted({f["acodec"] for f in info["formats"] if f.get("acodec")})
        opts["codec"] = codec or select_audio_codec(acodecs, non_interactive)
        opts["channels"] = channels or select_audio_channels(non_interactive)
        format_str = f"bestaudio[acodec={opts['codec']}][channels={opts['channels']}]"
    else:
        opts["resolution"] = resolution or select_video_format(info["formats"], non_interactive)
        format_str = f"bestvideo[resolution={opts['resolution']}] + bestaudio"

    typer.echo(f"Downloading with format: {format_str}")
    downloader = DownloadManager()
    output = downloader.download(url, {"format": format_str})
    typer.secho(f"Download complete: {output}", fg=typer.colors.GREEN)

# --- Entry for REPL mode if needed ---
def start_interactive_mode(snatch_api: Dict[str, Any]):
    """
    Launch interactive REPL using Typer.
    """
    from .cli import app as repl_app
    sys.argv = ["snatch"]  # reset argv
    repl_app()

if __name__ == "__main__":
    typer.echo("This module should not be run directly.", err=True)
    sys.exit(1)
