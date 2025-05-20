import json
import logging
import os
import subprocess
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
    try:
        result = subprocess.run(
            [ffmpeg_path, "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        version_info = (
            result.stdout.splitlines()[0] if result.stdout else ""
        )
        import re
        match = re.search(r"version\s+(\d+\.\d+)", version_info)
        if match:
            return True, float(match.group(1))
    except (subprocess.SubprocessError, OSError, ValueError):
        pass
    return False, None

def _validate_config_paths(config: dict) -> bool:
    """Validate and create output directories if needed"""
    changed = False
    for key in ["video_output", "audio_output"]:
        if key in config and not os.path.exists(config[key]):
            try:
                os.makedirs(config[key], exist_ok=True)
            except OSError:
                config[key] = str(Path.home() / ("Videos" if key == "video_output" else "Music"))
                changed = True
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

async def initialize_config_async(*, force_validation: bool = False) -> Optional[Dict[str, Any]]:
    """Initialize configuration asynchronously with proper defaults"""
    global _config_initialized, _background_init_complete
    
    try:
        with _config_lock:
            config = load_config()
            
            # If no config was loaded, get the defaults
            if not config:
                config = get_default_config()
            
            # Ensure critical paths exist and are set
            for key, value in config.items():
                if isinstance(value, str) and (key.endswith('_dir') or key.endswith('_file') or key.endswith('_output')):
                    if os.path.isabs(value):  # Only create absolute paths
                        os.makedirs(os.path.dirname(value), exist_ok=True)
            
            # Reset state if forcing validation
            if force_validation:
                _background_init_complete = False
            
            # Start background validation if needed
            if not _background_init_complete or force_validation:
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

def validate_ffmpeg_path(ffmpeg_location: str) -> bool:
    """
    Validate that the specified ffmpeg_location contains valid FFmpeg binaries.

    Args:
        ffmpeg_location: Path to directory containing FFmpeg binaries

    Returns:
        bool: True if valid FFmpeg binaries found, False otherwise
    """
    if not ffmpeg_location or not os.path.exists(ffmpeg_location):
        return False

    # Check for ffmpeg executable
    ffmpeg_exec = "ffmpeg.exe" if is_windows() else "ffmpeg"
    ffmpeg_path = os.path.join(ffmpeg_location, ffmpeg_exec)

    if not os.path.exists(ffmpeg_path):
        return False

    # Test if executable works
    try:
        result = subprocess.run(
            [ffmpeg_path, "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=3,
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, OSError):
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
