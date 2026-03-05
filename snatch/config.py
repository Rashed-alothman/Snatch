import json
import logging
import os
import re
import threading
import time
import asyncio
import yt_dlp
from pathlib import Path
from typing import Dict, Any, Optional, List
from colorama import Fore, Style, init

from .defaults import (
    CONFIG_FILE,
    DEFAULT_CONFIG,
    DEFAULT_ORGANIZATION_TEMPLATES,
    CACHE_DIR
)
from .common_utils import is_windows
from .manager import DownloadManager
from .ffmpeg_helper import locate_ffmpeg, get_ffmpeg_version, validate_ffmpeg_installation

# Initialize colorama
init(autoreset=True)

# Module-level variables
logger = logging.getLogger(__name__)

# Configuration state variables
_config_initialized = False
_ffmpeg_validated = False
_background_init_complete = False
_config_updates_available = False
_update_messages: List[str] = []
_config_lock = threading.Lock()

def _get_default_directory(key: str) -> str:
    """Get default directory path for config keys"""
    base_dir = os.getcwd()
    
    if key == "video_output":
        return os.path.join(base_dir, "downloads", "video")
    elif key == "audio_output":
        return os.path.join(base_dir, "downloads", "audio")
    elif key == "thumbnails_dir":
        return os.path.join(base_dir, "thumbnails")
    elif key == "subtitles_dir":
        return os.path.join(base_dir, "subtitles")
    elif key == "sessions_dir":
        return os.path.join(base_dir, "sessions")
    elif key == "cache_dir":
        return os.path.join(base_dir, "cache")
    else:
        return os.path.join(base_dir, key.replace("_dir", "").replace("_output", ""))

def _create_directory(path: str) -> bool:
    """Create directory and return True if successful"""
    try:
        logger.info(f"Creating directory: {path}")
        os.makedirs(path, exist_ok=True)
        return True
    except OSError as e:
        logger.warning(f"Failed to create directory {path}: {str(e)}")
        return False

def _ensure_directory_exists(path: str) -> str:
    """Try to create directory and return the path or None if it fails."""
    if os.path.exists(path):
        return path
    try:
        logger.info(f"Creating directory: {path}")
        os.makedirs(path, exist_ok=True)
        return path
    except OSError as e:
        logger.warning(f"Failed to create directory {path}: {str(e)}")
        return None


def _get_fallback_directory(key: str) -> str:
    """Get fallback directory for a specific config key."""
    if key == "video_output":
        fallback = str(Path.home() / "Videos" / "Snatch")
    elif key == "audio_output":
        fallback = str(Path.home() / "Music" / "Snatch")
    else:
        fallback = os.path.join(tempfile.gettempdir(), "Snatch", key.replace("_dir", "").replace("_output", ""))

    try:
        os.makedirs(fallback, exist_ok=True)
        logger.info(f"Using fallback directory for {key}: {fallback}")
        return fallback
    except OSError:
        last_resort = os.path.join(os.getcwd(), "downloads", key.replace("_dir", "").replace("_output", ""))
        try:
            os.makedirs(last_resort, exist_ok=True)
            logger.warning(f"Using last resort directory for {key}: {last_resort}")
            return last_resort
        except OSError:
            logger.error(f"Failed to create any directory for {key}")
            return os.getcwd()


def _set_default_directories(config: dict) -> bool:
    """Set default values for missing directory configuration keys."""
    changed = False
    directory_keys = ["video_output", "audio_output", "thumbnails_dir", "subtitles_dir", "sessions_dir", "cache_dir"]

    for key in directory_keys:
        if key not in config or not config[key]:
            base_dir = os.getcwd()
            defaults_map = {
                "video_output": os.path.join(base_dir, "downloads", "video"),
                "audio_output": os.path.join(base_dir, "downloads", "audio"),
                "thumbnails_dir": os.path.join(base_dir, "thumbnails"),
                "subtitles_dir": os.path.join(base_dir, "subtitles"),
                "sessions_dir": os.path.join(base_dir, "sessions"),
                "cache_dir": os.path.join(base_dir, "cache"),
            }
            config[key] = defaults_map.get(key, os.path.join(base_dir, key.replace("_dir", "").replace("_output", "")))
            logger.info(f"Setting default directory for {key}: {config[key]}")
            changed = True

    return changed


def _validate_config_paths(config: dict) -> bool:
    """Validate and create output directories if needed."""
    changed = _set_default_directories(config)
    directory_keys = ["video_output", "audio_output", "thumbnails_dir", "subtitles_dir", "sessions_dir", "cache_dir"]

    for key in directory_keys:
        path = os.path.abspath(os.path.expanduser(config[key]))
        config[key] = path
        if not os.path.exists(path):
            result = _ensure_directory_exists(path)
            if not result:
                fallback = _get_fallback_directory(key)
                config[key] = fallback
                changed = True
                logger.info(f"Updated {key} path to fallback: {fallback}")

    return changed

def _update_organization_templates(config: dict) -> bool:
    """Update organization templates with any missing defaults"""
    if "organization_templates" not in config:
        config["organization_templates"] = DEFAULT_ORGANIZATION_TEMPLATES.copy()
        return True
    
    changed = False
    for key, value in DEFAULT_ORGANIZATION_TEMPLATES.items():
        if key not in config["organization_templates"]:
            config["organization_templates"][key] = value
            changed = True
    return changed

def _run_background_init(config: dict) -> None:
    """Run background configuration validation and updates"""
    global _ffmpeg_validated, _background_init_complete, _config_updates_available, _update_messages
    
    try:
        any_updates_found = False
        
        # Validate FFmpeg version if path exists
        if ffmpeg_path := config.get("ffmpeg_location"):
            version_str = get_ffmpeg_version(ffmpeg_path)
            if version_str:
                match = re.search(r"version\s+(\d+\.\d+)", version_str)
                if match and float(match.group(1)) < 4.0:
                    _update_messages.append(
                        f"FFmpeg version {match.group(1)} detected. Consider updating to version 4.0 or newer."
                    )
                any_updates_found = True

        # Check for missing optional fields with defaults
        optional_fields = {
            "theme": "default",
            "download_history": True,
            "concurrent_fragment_downloads": 16,
            "auto_update_check": True,
            "bandwidth_limit": 0,
            "preferred_video_codec": "h264",
            "preferred_audio_codec": "aac",
        }

        for field, default_value in optional_fields.items():
            if field not in config:
                config[field] = default_value
                any_updates_found = True

        # Save if updates were made
        if any_updates_found:
            _config_updates_available = True
            try:
                with open(CONFIG_FILE, "w") as f:
                    json.dump(config, f, indent=4)
            except Exception as error:
                logger.error(f"Failed to save config updates: {str(error)}")

    except Exception as error:
        logger.error(f"Background initialization error: {str(error)}")
    finally:
        _background_init_complete = True

def _ensure_config_directory() -> None:
    """Create config directory if it doesn't exist"""
    config_dir = os.path.dirname(CONFIG_FILE)
    if config_dir:
        os.makedirs(config_dir, exist_ok=True)

_cached_config: Optional[Dict[str, Any]] = None
_config_mtime: float = 0.0


def _load_existing_config() -> Dict[str, Any]:
    """Load existing config file or return cached copy if unchanged on disk."""
    global _cached_config, _config_mtime

    config = DEFAULT_CONFIG.copy()

    if os.path.exists(CONFIG_FILE):
        try:
            current_mtime = os.path.getmtime(CONFIG_FILE)
            if _cached_config is not None and current_mtime == _config_mtime:
                return _cached_config.copy()

            with open(CONFIG_FILE) as f:
                loaded_config = json.load(f)
            if isinstance(loaded_config, dict):
                config.update(loaded_config)

            _cached_config = config
            _config_mtime = current_mtime
        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"Failed to parse config file: {e}")

    return config

def _ensure_output_directories(config: Dict[str, Any]) -> None:
    """Ensure output directories exist and are valid"""
    for key in ["video_output", "audio_output"]:
        if key not in config or not config[key]:
            config[key] = str(Path.home() / ("Videos" if key == "video_output" else "Music") / "Snatch")
        
        try:
            os.makedirs(config[key], exist_ok=True)
        except OSError as e:
            logger.error(f"Failed to create {key} directory: {e}")
            fallback = str(Path.home() / ("Videos" if key == "video_output" else "Music"))
            config[key] = fallback
            os.makedirs(fallback, exist_ok=True)

def get_default_config() -> Dict[str, Any]:
    """Get default configuration values"""
    config_dir = os.path.dirname(os.path.dirname(__file__))
    
    base_paths = {
        "sessions_dir": os.path.join(config_dir, "sessions"),
        "cache_dir": os.path.join(config_dir, "cache"),
        "download_dir": os.path.join(config_dir, "downloads"),
        "video_output": os.path.join(os.path.expanduser("~"), "Videos"),
        "audio_output": os.path.join(os.path.expanduser("~"), "Music")
    }
    
    # Create required directories
    for path in base_paths.values():
        os.makedirs(path, exist_ok=True)
    
    return {
        **base_paths,  # Include all base paths
        "session_file": os.path.join(base_paths["sessions_dir"], "download_sessions.json"),
        "auto_organize": True,
        "max_retries": 3,
        "retry_delay": 5,
        "exponential_backoff": True,
        "concurrent_downloads": min(os.cpu_count() or 4, 16),
        "chunk_size": 1024 * 1024,  # 1MB
        "session_expiry": 7 * 24 * 60 * 60,  # 7 days
        "auto_save_interval": 30,  # seconds
    }

def _ensure_file_parent_directories(config: Dict[str, Any]) -> None:
    """Ensure parent directories exist for file paths in config"""
    for key, value in config.items():
        if isinstance(value, str) and key.endswith('_file') and os.path.isabs(value):
            parent_dir = os.path.dirname(value)
            if parent_dir and not os.path.exists(parent_dir):
                try:
                    os.makedirs(parent_dir, exist_ok=True)
                    logger.info(f"Created parent directory for {key}: {parent_dir}")
                except OSError as e:
                    logger.warning(f"Failed to create directory {parent_dir}: {str(e)}")

def _save_config(config: Dict[str, Any]) -> bool:
    """Save configuration to disk"""
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)
            logger.info("Configuration saved")
        return True
    except Exception as e:
        logger.warning(f"Failed to save configuration: {str(e)}")
        return False

async def initialize_config_async(*, force_validation: bool = False) -> Optional[Dict[str, Any]]:
    """Initialize configuration asynchronously with proper defaults"""
    global _config_initialized, _background_init_complete
    
    try:
        with _config_lock:
            # Load or get default config
            config = load_config() or get_default_config()
            
            # Validate paths and save if changed
            if _validate_config_paths(config):
                logger.info("Configuration paths were updated")
                _save_config(config)
            
            # Ensure file parent directories exist
            _ensure_file_parent_directories(config)
            
            # Start background validation if needed
            if force_validation or not _background_init_complete:
                _background_init_complete = False
                await asyncio.to_thread(_run_background_init, config)
            
            _config_initialized = True
            return config
        
    except Exception as error:
        logger.error(f"Failed to initialize config: {str(error)}")
        return None

def load_config() -> Dict[str, Any]:
    """Load configuration from file with defaults and error handling"""
    global _config_initialized

    try:
        # Get default configuration first
        config = get_default_config()
        
        # If config file exists, load and merge with defaults
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                loaded_config = json.load(f)
                
            # Ensure loaded config is a dictionary
            if isinstance(loaded_config, dict):
                config.update(loaded_config)
            else:
                logger.warning("Invalid config format in file, using defaults")
        else:
            logger.info("No config file found, using defaults")
            
        # Ensure sessions directory exists
        sessions_dir = config.get("sessions_dir")
        if sessions_dir:
            os.makedirs(sessions_dir, exist_ok=True)
            if "session_file" not in config:
                config["session_file"] = os.path.join(sessions_dir, "download_sessions.json")
                
        # Save config if it was created or updated
        if not os.path.exists(CONFIG_FILE):
            with _config_lock:
                with open(CONFIG_FILE, "w") as f:
                    json.dump(config, f, indent=4)
                    
        _config_initialized = True
        return config
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse config file: {str(e)}")
        return get_default_config()
    except Exception as error:
        logger.error(f"Unexpected error loading config: {str(error)}")
        return get_default_config()

def test_functionality() -> bool:
    """Run basic tests to verify functionality"""
    print(f"{Fore.CYAN}Running basic tests...{Style.RESET_ALL}")
    try:
        # Test configuration initialization
        print(f"{Fore.CYAN}Testing configuration...{Style.RESET_ALL}")
        config = initialize_config_async(force_validation=True)

        # Check if FFmpeg is available in the config
        if not config.get("ffmpeg_location") or not validate_ffmpeg_installation():
            print(f"{Fore.RED}FFmpeg not found or invalid!{Style.RESET_ALL}")
            return False
        # Wait briefly for background validation to complete
        for _ in range(10):  # Wait up to 1 second
            if _ffmpeg_validated:
                break
            time.sleep(0.1)
        if _ffmpeg_validated:
            print(
                f"{Fore.GREEN}FFmpeg found at: {config['ffmpeg_location']}{Style.RESET_ALL}"
            )
        else:
            print(
                f"{Fore.YELLOW}FFmpeg validation still in progress...{Style.RESET_ALL}"
            )

        print(
            f"{Fore.GREEN}FFmpeg found at: {config['ffmpeg_location']}{Style.RESET_ALL}"
        )

        print(
            f"{Fore.GREEN}yt-dlp version: {yt_dlp.version.__version__}{Style.RESET_ALL}"
        )

        # Test download manager
        print(f"{Fore.CYAN}Testing download manager...{Style.RESET_ALL}")
        config = load_config()
        manager = DownloadManager(config)
        manager.interactive_mode()
        print(f"{Fore.GREEN}Download manager initialized successfully{Style.RESET_ALL}")

        return True
    except Exception as e:
        print(f"{Fore.RED}Test failed: {str(e)}{Style.RESET_ALL}")
        return False

async def check_for_updates() -> None:
    """
    Check if any configuration updates were detected in the background thread.
    If so, display notifications to the user.
    """
    # Wait a brief moment to allow background init to complete
    while not _background_init_complete:
        await asyncio.sleep(0.1)  # Short sleep to allow other tasks to run
        
    if _config_updates_available:
        print(f"\n{Fore.YELLOW}Configuration Updates Available:{Style.RESET_ALL}")
        for message in _update_messages:
            print(f"  {Fore.CYAN}• {message}{Style.RESET_ALL}")
        print(
            f"{Fore.YELLOW}Run with --update-config to apply all recommended updates.{Style.RESET_ALL}"
        )
