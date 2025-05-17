from rich.markdown import Markdown

HELP_TEXT = """
# Snatch Download Manager Help

## Basic Commands
* `help` or `?` - Show this help
* `h` - Show quick help
* `exit`, `quit`, or `q` - Exit program
* `clear` - Clear screen

## Download Commands
* `!download <url>` - Download from URL
* `!batch <file>` - Download URLs from file
* `!resume <id>` - Resume failed download
* `!cancel <id>` - Cancel active download
* `!pause <id>` - Pause download
* `!list` - List active downloads

## System Commands
* `!stats` - Show system statistics
* `!speed` - Test download speed
* `!sites` - List supported sites
* `!config` - Show current configuration
* `!cache clear` - Clear download cache

## File Management
* `!open <id>` - Open download location
* `!delete <id>` - Delete downloaded file
* `!rename <id> <name>` - Rename download
* `!move <id> <path>` - Move download to path

## Advanced Options (F1)
* Format Selection
* Quality Settings
* Network Configuration
* Proxy Settings
* Download Scheduling
* Custom Filters

## Tips
* Use arrow keys to navigate history
* Tab completion is supported
* Press F1 for advanced options
* Press F2 to toggle sidebar
* Press F3 to show download queue
"""

QUICK_HELP = """
📥 Basic Commands:
  download <url>  - Download media
  batch <file>    - Batch download
  resume/pause/cancel <id>
  
⚙️ System:
  stats/speed/sites
  config/cache
  
📁 Files:
  open/delete/rename/move
  
❓ Help:
  help - Full help
  F1   - Advanced options
  F2   - Toggle sidebar
  F3   - Show queue
"""

def show_full_help(console) -> None:
    """Display full help text"""
    md = Markdown(HELP_TEXT)
    console.print(md)

def show_quick_help(console) -> None:
    """Display quick help"""
    console.print(QUICK_HELP)
