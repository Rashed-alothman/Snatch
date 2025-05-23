import json
import logging
import os
import subprocess
import tempfile
import threading
import time
import asyncio
import yt_dlp
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from colorama import Fore, Style, init

from .defaults import (
    CONFIG_FILE,
    DEFAULT_CONFIG,
    DEFAULT_ORGANIZATION_TEMPLATES,
    CACHE_DIR
)
from .common_utils import is_windows
from .manager import DownloadManager

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

def _validate_ffmpeg_version(ffmpeg_path: str) -> Tuple[bool, Optional[float]]:
    """Validate FFmpeg version, returns (is_valid, version_number)"""
    if not ffmpeg_path:
        logger.warning("FFmpeg path is not specified")
        return False, None
    
    # Handle the case when path is a directory (like C:\ffmpeg\bin)
    if os.path.isdir(ffmpeg_path):
        # Try to find ffmpeg executable in the directory
        ffmpeg_exe = "ffmpeg.exe" if is_windows() else "ffmpeg"
        possible_paths = [
            os.path.join(ffmpeg_path, ffmpeg_exe),
            os.path.join(ffmpeg_path, "bin", ffmpeg_exe)
        ]
        
        for path in possible_paths:
            if os.path.isfile(path):
                logger.info(f"Found FFmpeg executable at: {path}")
                ffmpeg_path = path
                break
        else:
            logger.warning(f"FFmpeg executable not found in directory: {ffmpeg_path}")
            return False, None
    elif not os.path.exists(ffmpeg_path):
        logger.warning(f"FFmpeg not found at path: {ffmpeg_path}")
        return False, None
    
    if not os.path.isfile(ffmpeg_path):
        logger.warning(f"FFmpeg path is not a file: {ffmpeg_path}")
        return False, None
        
    try:
        result = subprocess.run(
            [ffmpeg_path, "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,  # Don't raise exception on non-zero exit
            timeout=5  # Add timeout to prevent hanging
        )
        
        if result.returncode != 0:
            logger.warning(f"FFmpeg validation failed with return code: {result.returncode}")
            return False, None
            
        version_info = (
            result.stdout.splitlines()[0] if result.stdout else ""
        )
        import re
        match = re.search(r"version\s+(\d+\.\d+)", version_info)
        if match:
            version = float(match.group(1))
            logger.info(f"FFmpeg version {version} found at: {ffmpeg_path}")
            return True, version
        else:
            logger.warning(f"Could not determine FFmpeg version from: {version_info}")
    except (subprocess.SubprocessError, OSError, ValueError) as e:
        logger.error(f"Error validating FFmpeg: {str(e)}")
    
    return False, None

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

def _validate_config_paths(config: dict) -> bool:
    """Validate and create output directories if needed"""
    from .config_helpers import validate_config_paths
    return validate_config_paths(config)

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
            is_valid, version = _validate_ffmpeg_version(ffmpeg_path)
            if is_valid and version and version < 4.0:
                _update_messages.append(
                    f"FFmpeg version {version} detected. Consider updating to version 4.0 or newer."
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

def _load_existing_config() -> Dict[str, Any]:
    """Load existing config file or return defaults"""
    config = DEFAULT_CONFIG.copy()
    
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                loaded_config = json.load(f)
            if isinstance(loaded_config, dict):
                config.update(loaded_config)
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
        if not config.get("ffmpeg_location") or not validate_ffmpeg_path(
            config["ffmpeg_location"]
        ):
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

def find_ffmpeg() -> Optional[str]:
    """Find FFmpeg in common locations or PATH with improved cross-platform support"""
    # Platform specific locations
    common_locations = []

    if is_windows():
        common_locations = [
            r"C:\ffmpeg\bin",
            r"C:\Program Files\ffmpeg\bin",
            r"C:\ffmpeg\ffmpeg-master-latest-win64-gpl\bin",
            r".\ffmpeg\bin",  # Relative to script location
        ]

        # Check if ffmpeg is in PATH on Windows
        try:
            result = subprocess.run(
                ["where", "ffmpeg"], capture_output=True, text=True, timeout=3
            )
            if result.returncode == 0:
                path = result.stdout.strip().split("\n")[0]
                return os.path.dirname(path)
        except (subprocess.SubprocessError, FileNotFoundError):
            pass
    else:
        common_locations = [
            "/usr/bin",
            "/usr/local/bin",
            "/opt/local/bin",
            "/opt/homebrew/bin",
        ]

        # Check if ffmpeg is in PATH on Unix-like systems
        try:
            result = subprocess.run(
                ["which", "ffmpeg"], capture_output=True, text=True, timeout=3
            )
            if result.returncode == 0:
                path = result.stdout.strip()
                return os.path.dirname(path)
        except (subprocess.SubprocessError, FileNotFoundError):
            pass

    # Check common locations for ffmpeg binary
    ffmpeg_exec = "ffmpeg.exe" if is_windows() else "ffmpeg"
    for location in common_locations:
        ffmpeg_path = os.path.join(location, ffmpeg_exec)
        if os.path.exists(ffmpeg_path):
            return location

    return None

def _find_ffmpeg_executable(ffmpeg_location: str) -> Optional[str]:
    """Find the FFmpeg executable path from a given location"""
    # Handle direct path to executable
    if not os.path.isdir(ffmpeg_location):
        return ffmpeg_location if os.path.exists(ffmpeg_location) else None
    
    # If it's a directory, search for the executable
    ffmpeg_exec = "ffmpeg.exe" if is_windows() else "ffmpeg"
    
    # Check common locations
    possible_paths = [
        os.path.join(ffmpeg_location, "bin", ffmpeg_exec),  # /path/to/ffmpeg/bin/ffmpeg[.exe]
        os.path.join(ffmpeg_location, ffmpeg_exec),        # /path/to/ffmpeg/ffmpeg[.exe]
    ]
    
    # Return the first valid path
    for path in possible_paths:
        if os.path.exists(path):
            return path
    
    # Not found
    logger.debug(f"FFmpeg executable not found in {ffmpeg_location}")
    return None

def _test_ffmpeg_executable(ffmpeg_path: str) -> bool:
    """Test if the FFmpeg executable works"""
    try:
        # Run with increased timeout and capture output
        result = subprocess.run(
            [ffmpeg_path, "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
            text=True,
        )
        
        if result.returncode == 0 and "ffmpeg version" in result.stdout.lower():
            # Log the version for debugging
            version_line = next((line for line in result.stdout.splitlines() 
                                if "ffmpeg version" in line.lower()), "")
            if version_line:
                logger.info(f"FFmpeg version: {version_line.strip()}")
            return True
        else:
            logger.warning(f"FFmpeg validation failed. Return code: {result.returncode}")
            if result.stderr:
                logger.debug(f"FFmpeg error output: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        logger.warning("FFmpeg validation timed out after 10 seconds")
        return False
    except (subprocess.SubprocessError, OSError) as e:
        logger.warning(f"Error validating FFmpeg: {str(e)}")
        return False

def validate_ffmpeg_path(ffmpeg_location: str) -> bool:
    """
    Validate that the specified ffmpeg_location contains valid FFmpeg binaries.

    Args:
        ffmpeg_location: Path to directory or direct path to FFmpeg executable

    Returns:
        bool: True if valid FFmpeg binaries found, False otherwise
    """
    # Early validation for empty path
    if not ffmpeg_location:
        logger.debug("Empty FFmpeg location provided")
        return False
    
    # Find the executable
    ffmpeg_path = _find_ffmpeg_executable(ffmpeg_location)
    if not ffmpeg_path:
        return False
    
    # Check if the path is actually executable (skip on Windows for .exe files)
    is_exe_on_windows = is_windows() and ffmpeg_path.lower().endswith('.exe')
    if not is_exe_on_windows and not os.access(ffmpeg_path, os.X_OK):
        logger.debug(f"FFmpeg at {ffmpeg_path} is not executable")
        return False
    
    # Test if executable works
    if _test_ffmpeg_executable(ffmpeg_path):
        logger.info(f"Valid FFmpeg found at: {ffmpeg_path}")
        return True
    
    return False

def print_ffmpeg_instructions():
    """Print instructions for installing FFmpeg with platform-specific guidance"""
    print(
        f"{Fore.YELLOW}FFmpeg not found! Please follow these steps to install FFmpeg:{Style.RESET_ALL}"
    )
    print("\n1. Download FFmpeg:")
    print("   - Visit: https://github.com/BtbN/FFmpeg-Builds/releases")
    print("   - Download: ffmpeg-master-latest-win64-gpl.zip")
    print("\n2. Install FFmpeg:")
    print("   - Extract the downloaded zip file")
    print("   - Copy the extracted folder to C:\\ffmpeg")
    print("   - Ensure ffmpeg.exe is in C:\\ffmpeg\\bin")
    print("\nAlternatively:")
    print("- Use chocolatey: choco install ffmpeg")
    print("- Use winget: winget install ffmpeg")
    print("\nAfter installation, either:")
    print("1. Add FFmpeg to your system PATH, or")
    print("2. Update config.json with the correct ffmpeg_location")
    print(
        "\nFor detailed instructions, visit: https://www.wikihow.com/Install-FFmpeg-on-Windows"
    )

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
