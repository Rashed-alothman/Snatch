#all magic numbers & default settings
import re 
import sys
import signal
from rich.theme import Theme
from colorama import Fore, Style, init
from pathlib import Path 

# Global state variables
CONFIG_FILE = "config.json"
_config_initialized = False
_ffmpeg_validated = False
_background_init_complete = False
_config_updates_available = False
_update_messages = []

# Constants moved to top for better organization and maintainability
FLAC_EXT = ".flac"
opus_ext = ".opus"
webn_ext = ".webm"
part_ext = ".part"
speedtestresult = "speedtest_result.json"
bestaudio_ext = "bestaudio/best"
VERSION = "1.8.0"  # Centralized version definition
LOG_FILE = "download_log.txt"
SPINNER_CHARS = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
# Default throttling and retry constants
DEFAULT_THROTTLE_RATE = 0  # 0 means no throttling (bytes/second)
MAX_RETRIES = 10  # Maximum number of retry attempts
RETRY_SLEEP_BASE = 5  # Base seconds to wait before retry (used in exponential backoff)
MAX_CONCURRENT_FRAGMENTS = 10  # Maximum number of parallel fragment downloads
DEFAULT_TIMEOUT = 60  # Default connection timeout in seconds
DOWNLOAD_SESSIONS_FILE = "download_sessions.json"  # New session data file

# File organization templates
DEFAULT_ORGANIZATION_TEMPLATES = {
    "audio": "{uploader}/{album}/{title}",
    "video": "{uploader}/{year}/{title}",
    "podcast": "Podcasts/{uploader}/{year}-{month}/{title}",
    "audiobook": "Audiobooks/{uploader}/{title}",
}

# Safe filename characters regex pattern
SAFE_FILENAME_CHARS = re.compile(r"[^\w\-. ]")

DEFAULT_CONFIG = {
    "ffmpeg_location": "",  # Will be auto-detected
    "video_output": str(Path.home() / "Videos"),
    "audio_output": str(Path.home() / "Music"),
    "max_concurrent": 3,
    # Add organization configs
    "organize": False,
    "organization_templates": DEFAULT_ORGANIZATION_TEMPLATES.copy(),
}

# Enhanced spinner characters for better visual appearance
SPINNER_CHARS = ["⣾", "⣽", "⣻", "⢿", "⡿", "⣟", "⣯", "⣷"]
# Alternative spinners that users can select
SPINNER_STYLES = {
    "dots": ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"],
    "line": ["|", "/", "-", "\\"],
    "grow": ["▏", "▎", "▍", "▌", "▋", "▊", "▉", "█", "▉", "▊", "▋", "▌", "▍", "▎", "▏"],
    "pulse": ["█", "▓", "▒", "░", "▒", "▓"],
    "bounce": ["⠁", "⠂", "⠄", "⠂"],
    "moon": ["🌑", "🌒", "🌓", "🌔", "🌕", "🌖", "🌗", "🌘"],
    "aesthetic": ["⣾", "⣽", "⣻", "⢿", "⡿", "⣟", "⣯", "⣷"],
}

# Common file extensions by type for better categorization
AUDIO_EXTENSIONS = {".mp3", FLAC_EXT, ".wav", ".m4a", ".aac", ".ogg", opus_ext}
VIDEO_EXTENSIONS = {".mp4", webn_ext, ".mkv", ".avi", ".mov", ".flv", ".wmv", ".3gp"}

# Create a download cache directory for faster repeated downloads
CACHE_DIR = Path.home() / ".snatch" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Add system resource constraints to prevent overloading
MAX_MEMORY_PERCENT = 80  # Don't use more than 80% of system memory
DEFAULT_CHUNK_SIZE = 8192  # Optimal for most systems


# Set up a handler for SIGINT to ensure clean exits
def signal_handler(sig, frame):
    print(
        f"\n{Fore.YELLOW}Operation cancelled by user. Exiting gracefully...{Style.RESET_ALL}"
    )
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)

# Examples text updated
EXAMPLES = """
╔══════════════════════════════════════════════════════════════════════════╗
║                          SNATCH COMMAND CENTER                           ║
╠══════════════════════════════════════════════════════════════════════════╣
║                                                                          ║
║  📥 QUICK DOWNLOAD SYNTAX:                                              ║     
║    <URL> <format|quality>      ← URL FIRST, then format or quality       ║
║                                                                          ║
║    Examples:                                                             ║
║      https://example.com/video flac    Download audio in FLAC format     ║
║      https://example.com/video 1080    Download video in 1080p quality   ║
║      https://example.com/music opus    Download audio in Opus format     ║
║                                                                          ║
║  🎵 AUDIO COMMANDS:                                                      ║
║    audio <URL>               Download audio (default format)             ║
║    flac <URL>                Download in lossless FLAC format            ║
║    mp3 <URL>                 Download in MP3 format (320kbps)            ║
║    opus <URL>                Download in Opus format (high quality)      ║
║    wav <URL>                 Download in WAV format (uncompressed)       ║
║    m4a <URL>                 Download in M4A format (AAC)                ║
║                                                                          ║
║  🎬 VIDEO COMMANDS:                                                      ║
║    download, dl <URL>        Download in best available quality          ║
║    video <URL>               Download video (prompts for resolution)     ║
║    <URL> 720                 Download in 720p resolution                 ║
║    <URL> 1080                Download in 1080p resolution                ║
║    <URL> 2160|4k             Download in 4K resolution                   ║
║                                                                          ║
║  ⚙️ DOWNLOAD OPTIONS:                                                    ║
║    --audio-only              Download only audio track                   ║
║    --resolution <res>        Specify video resolution (480/720/1080/2160)║
║    --filename <name>         Set custom output filename                  ║
║    --audio-format <format>   Set audio format (mp3/flac/opus/wav/m4a)    ║
║    --audio-channels <num>    Set audio channels (2=stereo, 8=surround)   ║
║    --output-dir <path>       Specify output directory                    ║
║    --organize                Enable metadata-based file organization     ║
║                                                                          ║
║  🛠️ ADVANCED OPTIONS:                                                    ║
║    --resume                  Resume interrupted downloads                ║
║    --stats                   Show download statistics                    ║
║    --format-id <id>          Select specific format ID                   ║
║    --no-cache                Skip using cached media info                ║
║    --throttle <speed>        Limit download speed (e.g., 2M)             ║
║    --aria2c                  Use aria2c for faster downloads             ║
║    --speedtest               Run network speed test                      ║
║                                                                          ║
║  🔗 P2P SHARING:                                                         ║
║    share <file>              Share a file via P2P (encrypted)            ║
║    fetch <code>              Download a shared file                      ║
║    fetch <code> -o <dir>     Download to specific directory              ║
║                                                                          ║
║  📋 UTILITY COMMANDS:                                                   ║
║    help, ?                   Show this help menu                         ║
║    clear, cls                Clear the screen                            ║
║    list, sites               List supported sites                        ║
║    speedtest, test           Run network speed test                      ║
║    exit, quit, q             Exit the application                        ║
║                                                                          ║
║  📚 BATCH OPERATIONS:                                                   ║
║    python Snatch.py "URL1" "URL2" "URL3"                                 ║
║    python Snatch.py "URL1" "URL2" --audio-only --stats                   ║
║                                                                          ║
╚══════════════════════════════════════════════════════════════════════════╝
"""



# Add this to your existing defaults
THEME = Theme({
    # Basic styles
    "info": "cyan",
    "success": "bold green",
    "warning": "bold yellow",
    "error": "bold red",
    "highlight": "bold magenta",
    
    # Custom interactive mode styles
    "banner": "bright_cyan",
    "preview_label": "bold bright_white",
    "preview_value": "#00ffff",
    "matrix_border": "#9400d3",
    "surround_channel": "bold bright_blue",
    "surround_level": "#00ff00",
    "surround_bar": "#00ff00",
    "help_border": "bright_yellow",
    "stats_label": "dim cyan",
    "stats_value": "bold bright_white"
})

BANNER_ART = r"""
  _____ _   _  _____ _______ ______  _   _   
 / ____| \ | |/ ____|__   __|  ____|| | | |  
| (___ |  \| | |      | |  | |__   | |_| |  
 \___ \| . ` | |      | |  |  __|  |  _  |  
 ____) | |\  | |____  | |  | |____ | | | |  
|_____/|_| \_|\_____| |_|  |______||_| |_|  
"""

HELP_CONTENT = {
    "main": """
    ## Interactive Mode Guide
    
    **Navigation:**
    - `Tab`/`Shift+Tab`: Switch between panels
    - `Ctrl+H`: Toggle help
    - `↑/↓`: Scroll through options
    
    **Quality Presets:**
    - Lossless: Original quality
    - Master: Studio-grade
    - High: Balanced quality
    """,
    "welcome": """
    ## Welcome to Snatch Premium!
    
    Start by entering a media URL or:
    - Press `F1` for advanced options
    - `Ctrl+T` for tutorial mode
    - `Ctrl+Q` to exit
    """
}

QUALITY_PRESETS = {
    "lossless": {"video": "best", "audio": "best"},
    "master": {"video": "4K", "audio": "flac"},
    "high": {"video": "1080p", "audio": "320kbps"}
}

SURROUND_PROFILES = {
    "FL": 9, "FR": 9, "FC": 7,
    "LFE": 6, "BL": 8, "BR": 8,
    "SL": 7, "SR": 7
}
# In defaults.py
SUBTITLE_STYLES = {
    "default": {
        "font": "Arial",
        "font_size": 24,
        "color": "#FFFFFF",
        "background": "#00000080",
        "outline": 2,
        "outline_color": "#000000",
        "alignment": "center",
        "margin": 10
    },
    "cinema": {
        "font": "Helvetica Neue",
        "font_size": 28,
        "color": "#FFFF00",
        "background": "#00000000",
        "outline": 3,
        "outline_color": "#000000",
        "alignment": "center",
        "margin": 50
    },
    "modern": {
        "font": "Roboto",
        "font_size": 22,
        "color": "#00FF00",
        "background": "#1A1A1ACC",
        "outline": 1,
        "outline_color": "#FFFFFF",
        "alignment": "bottom-center",
        "margin": 20
    },
    "classic": {
        "font": "Times New Roman",
        "font_size": 26,
        "color": "#FFFFFF",
        "background": "#000000AA",
        "outline": 0,
        "alignment": "top-center",
        "margin": 30
    },
    "animated": {
        "font": "Futura",
        "font_size": 24,
        "color": "#FFA500",
        "background": "#00000000",
        "outline": 2,
        "outline_color": "#000000",
        "alignment": "dynamic",
        "margin": 15,
        "effects": ["fade", "scroll"]
    },
    "formats": {
        "srt": {
            "max_lines": 2,
            "line_spacing": 8
        },
        "ass": {
            "styles": ["Bold", "Italic"],
            "wrap_style": 0
        },
        "vtt": {
            "cue_settings": "vertical:rl line:50%"
        }
    }
}