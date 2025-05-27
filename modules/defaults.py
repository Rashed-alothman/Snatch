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
VERSION = "1.8.1"  # Centralized version definition
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

# Video upscaling presets
UPSCALE_PRESETS = {
    "low": {
        "quality": "low",
        "speed": "fast",
        "threads": 2,
        "model": "realesrgan-x2plus"
    },
    "medium": {
        "quality": "medium", 
        "speed": "medium",
        "threads": 4,
        "model": "realesrgan-x4plus"
    },
    "high": {
        "quality": "high",
        "speed": "slow", 
        "threads": 8,
        "model": "realesrgan-x4plus-anime"
    }
}

# Upscaling method configurations
UPSCALE_METHODS = {
    "realesrgan": {
        "type": "ai",
        "quality": "highest",
        "speed": "slow",
        "models": ["realesrgan-x2plus", "realesrgan-x4plus", "realesrgan-x4plus-anime"]
    },
    "lanczos": {
        "type": "traditional",
        "quality": "high", 
        "speed": "medium",
        "algorithm": "lanczos"
    },
    "bicubic": {
        "type": "traditional",
        "quality": "good",
        "speed": "fast",
        "algorithm": "bicubic"
    },
    "bilinear": {
        "type": "traditional",
        "quality": "basic",
        "speed": "fastest",
        "algorithm": "bilinear"
    }
}

DEFAULT_CONFIG = {
    "ffmpeg_location": "",  # Will be auto-detected
    "video_output": str(Path.home() / "Videos"),
    "audio_output": str(Path.home() / "Music"),
    "max_concurrent": 3,
    # Add organization configs
    "organize": False,
    "organization_templates": DEFAULT_ORGANIZATION_TEMPLATES.copy(),
    # Video upscaling configuration
    "upscaling": {
        "enabled": False,
        "method": "realesrgan",  # Options: realesrgan, esrgan, bicubic, lanczos
        "scale_factor": 2,  # 2x, 4x upscaling
        "quality": "high",  # low, medium, high
        "preserve_aspect_ratio": True,
        "output_format": "mp4",
        "fallback_method": "lanczos",  # Fallback if AI upscaling fails
        "gpu_acceleration": True,
        "max_resolution": "4K",  # Don't upscale beyond this
    }
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
    - `Ctrl+T` to tutorial mode
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

# Format presets for common quality settings
FORMAT_PRESETS = {
    "audio": {
        "best": {
            "flac": {
                "codec": "flac",
                "quality": "0",  # Lossless
                "sample_rate": "96000",
                "bit_depth": "24",
                "channels": "2"
            },
            "opus": {
                "codec": "libopus",
                "bitrate": "256k",
                "vbr": "on",
                "compression_level": "10"
            },
            "mp3": {
                "codec": "libmp3lame",
                "bitrate": "320k",
                "quality": "0",
                "compression_level": "0"
            },
            "aac": {
                "codec": "aac",
                "bitrate": "256k",
                "profile": "aac_low",
                "quality": "1"
            }
        },
        "medium": {
            "opus": {
                "codec": "libopus",
                "bitrate": "128k",
                "vbr": "on",
                "compression_level": "8"
            },
            "mp3": {
                "codec": "libmp3lame",
                "bitrate": "192k",
                "quality": "4",
                "compression_level": "2"
            },
            "aac": {
                "codec": "aac",
                "bitrate": "128k",
                "profile": "aac_low",
                "quality": "3"
            }
        },
        "small": {
            "opus": {
                "codec": "libopus",
                "bitrate": "96k",
                "vbr": "on",
                "compression_level": "6"
            },
            "mp3": {
                "codec": "libmp3lame",
                "bitrate": "128k",
                "quality": "5",
                "compression_level": "4"
            },
            "aac": {
                "codec": "aac",
                "bitrate": "96k",
                "profile": "aac_low",
                "quality": "4"
            }
        }
    },
    "video": {
        "4k": {
            "codec": "libx264",
            "height": 2160,
            "crf": "18",
            "preset": "slow",
            "audio_codec": "aac",
            "audio_bitrate": "192k"
        },
        "1080p": {
            "codec": "libx264",
            "height": 1080,
            "crf": "20",
            "preset": "medium",
            "audio_codec": "aac",
            "audio_bitrate": "128k"
        },
        "720p": {
            "codec": "libx264", 
            "height": 720,
            "crf": "22",
            "preset": "fast",
            "audio_codec": "aac",
            "audio_bitrate": "96k"
        },
        "480p": {
            "codec": "libx264",
            "height": 480,
            "crf": "24",
            "preset": "superfast",
            "audio_codec": "aac",
            "audio_bitrate": "64k"
        }
    }
}

# Video upscaling presets for AI enhancement and quality improvement
UPSCALING_PRESETS = {
    "realesrgan": {
        "2x": {
            "model": "RealESRGAN_x2plus",
            "scale": 2,
            "denoise_level": 1,
            "face_enhance": False,
            "fp32": False,  # Use fp16 for better performance
            "gpu_id": 0
        },
        "4x": {
            "model": "RealESRGAN_x4plus",
            "scale": 4,
            "denoise_level": 1,
            "face_enhance": False,
            "fp32": False,
            "gpu_id": 0
        },
        "anime_2x": {
            "model": "RealESRGAN_x2plus_anime",
            "scale": 2,
            "denoise_level": 1,
            "face_enhance": False,
            "fp32": False,
            "gpu_id": 0
        },
        "anime_4x": {
            "model": "RealESRGAN_x4plus_anime_6B",
            "scale": 4,
            "denoise_level": 1,
            "face_enhance": False,
            "fp32": False,
            "gpu_id": 0
        }
    },
    "esrgan": {
        "2x": {
            "model": "ESRGAN_x2.pth",
            "scale": 2,
            "denoise_level": 0
        },
        "4x": {
            "model": "ESRGAN_x4.pth", 
            "scale": 4,
            "denoise_level": 0
        }
    },
    "traditional": {
        "bicubic_2x": {
            "method": "bicubic",
            "scale": 2,
            "quality": "high"
        },
        "bicubic_4x": {
            "method": "bicubic", 
            "scale": 4,
            "quality": "high"
        },
        "lanczos_2x": {
            "method": "lanczos",
            "scale": 2,
            "quality": "high"
        },
        "lanczos_4x": {
            "method": "lanczos",
            "scale": 4,
            "quality": "high"
        }
    }
}