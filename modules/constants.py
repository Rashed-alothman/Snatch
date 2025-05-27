"""
constants.py - Central location for all constants used in Snatch

This module defines version information, default paths, and other constants
that are used across the application.
"""

# Version Information
VERSION = "2.0.0"
APP_NAME = "Snatch Media Downloader"
APP_DESCRIPTION = "A modern, feature-rich media downloader"
AUTHOR = "Snatch Team"
AUTHOR_EMAIL = "support@snatchapp.org"
PROJECT_URL = "https://github.com/snatch-team/snatch"

# Default Directories
DEFAULT_CONFIG_DIR = "config"
DEFAULT_DOWNLOAD_DIR = "downloads"
DEFAULT_TEMP_DIR = "temp"
DEFAULT_CACHE_DIR = "cache"
DEFAULT_SESSION_DIR = "sessions"

# File Extensions
AUDIO_EXTENSIONS = [".mp3", ".flac", ".wav", ".aac", ".ogg", ".opus", ".m4a", ".wma"]
VIDEO_EXTENSIONS = [".mp4", ".mkv", ".webm", ".avi", ".mov", ".flv", ".wmv", ".m4v"]
SUBTITLE_EXTENSIONS = [".srt", ".vtt", ".ass", ".ssa"]
IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".webp", ".gif"]
DOCUMENT_EXTENSIONS = [".pdf", ".txt", ".doc", ".docx", ".epub"]

# File Organization Templates
FILE_ORGANIZATION_TEMPLATES = {
    "video": "{uploader}/{title}",
    "audio": "{artist}/{album}/{title}",
    "podcast": "Podcasts/{uploader}/{title}",
    "audiobook": "Audiobooks/{uploader}/{title}",
    "movie": "Movies/{title} ({upload_year})",
    "series": "Series/{uploader}/{title}"
}

# Network Settings
DEFAULT_TIMEOUT = 30  # seconds
DEFAULT_USER_AGENT = "Mozilla/5.0 Snatch Media Downloader/{VERSION}"
DEFAULT_CHUNK_SIZE = 1024 * 1024  # 1MB
DEFAULT_MAX_RETRIES = 5

# Sample command examples for help
EXAMPLES = """
Examples:
snatch https://www.youtube.com/watch?v=dQw4w9WgXcQ
snatch --audio-only https://soundcloud.com/artist/track
snatch --audio-only --upmix-7.1 --denoise https://example.com/audio
snatch --resolution 1080 https://vimeo.com/video_id
snatch --textual  # Launch modern textual interface
snatch --interactive  # Launch classic interactive mode
"""

# Audio processing settings
AUDIO_PROCESSING = {
    "upmix_settings": {
        "sample_rate": 96000,
        "bit_depth": 32,  # s32 format
        "channels": 8,    # 7.1 channels
        "bitrate": "2000k"
    },
    "denoise_settings": {
        "strength": "moderate",  # light, moderate, strong
        "spectral_gate": -25,
        "temporal_smoothing": 0.001
    }
}

# Process prefixes for logging purposes
PROCESS_PREFIXES = {
    "download": "[DOWNLOAD]",
    "extract": "[EXTRACT]",
    "convert": "[CONVERT]",
    "merge": "[MERGE]",
    "subtitle": "[SUBTITLE]",
    "thumbnail": "[THUMB]",
    "audio": "[AUDIO]",
    "organize": "[ORGANIZE]",
    "metadata": "[META]",
    "organize": "[ORGANIZE]",
    "config": "[CONFIG]",
    "cache": "[CACHE]",
    "session": "[SESSION]",
    "error": "[ERROR]"
}