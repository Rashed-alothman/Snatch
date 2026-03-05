"""
interactive_mode.py - Launcher for the Snatch interactive TUI.

Tries the Textual-based modern interface first, then falls back to a
simple Rich console prompt if Textual is unavailable.
"""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


def launch_enhanced_interactive_mode(config: Dict[str, Any]) -> None:
    """Launch the interactive TUI with automatic fallback."""
    try:
        from .theme.modern_interactive import run_modern_interactive
        run_modern_interactive(config)
    except Exception as e:
        logger.warning("Textual interface failed: %s", e)
        logger.info("Falling back to simple console interface...")
        _run_console_fallback(config)


def _run_console_fallback(config: Dict[str, Any]) -> None:
    """Minimal Rich-based console fallback when Textual is unavailable."""
    from rich.console import Console
    from rich.panel import Panel

    console = Console()
    console.print(Panel(
        "[bold cyan]Snatch Media Downloader[/]\n\n"
        "The interactive TUI could not start.\n"
        "Use CLI commands instead:\n\n"
        "  [green]snatch download <url>[/]          Download media\n"
        "  [green]snatch download -a <url>[/]       Download audio only\n"
        "  [green]snatch --help[/]                  Show all commands\n",
        title="Snatch",
        border_style="cyan",
    ))


# Backward-compatible aliases
def launch_textual_interface(config: Dict[str, Any]) -> None:
    """Alias for launch_enhanced_interactive_mode."""
    launch_enhanced_interactive_mode(config)


def run_interactive_mode(config: Dict[str, Any]) -> None:
    """Alias for launch_enhanced_interactive_mode."""
    launch_enhanced_interactive_mode(config)


def initialize_interactive_mode(config: Dict[str, Any]) -> None:
    """Alias for launch_enhanced_interactive_mode."""
    launch_enhanced_interactive_mode(config)
