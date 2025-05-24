"""
Helper functions for configuration management.
"""

import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Tuple

# Setup logger
logger = logging.getLogger(__name__)

def is_windows() -> bool:
    """Check if running on Windows"""
    return os.name == 'nt'

def ensure_directory_exists(path: str) -> str:
    """
    Try to create directory and return either the original path or None if it fails.
    
    Args:
        path: Directory path to create
        
    Returns:
        The original path if directory exists or was created, None if creation failed
    """
    if os.path.exists(path):
        return path
        
    # Try to create the directory
    try:
        logger.info(f"Creating directory: {path}")
        os.makedirs(path, exist_ok=True)
        return path
    except OSError as e:
        logger.warning(f"Failed to create directory {path}: {str(e)}")
        

def validate_ffmpeg_path(ffmpeg_path: str) -> Tuple[bool, Optional[str]]:
    """
    Validate FFmpeg path and find the executable
    
    Args:
        ffmpeg_path: Directory or file path to FFmpeg
        
    Returns:
        Tuple of (is_valid, executable_path)
    """
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
                return True, path
        
        logger.warning(f"FFmpeg executable not found in directory: {ffmpeg_path}")
        return False, None
    
    # Direct file path case
    if os.path.isfile(ffmpeg_path):
        return True, ffmpeg_path
    
    logger.warning(f"FFmpeg not found at path: {ffmpeg_path}")
    return False, None

def get_ffmpeg_version(ffmpeg_path: str) -> Optional[float]:
    """
    Get FFmpeg version from executable
    
    Args:
        ffmpeg_path: Path to FFmpeg executable
        
    Returns:
        Version as float or None if error
    """
    try:
        result = subprocess.run(
            [ffmpeg_path, "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            timeout=5
        )
        
        if result.returncode != 0:
            logger.warning(f"FFmpeg validation failed with return code: {result.returncode}")
            return None
            
        version_info = result.stdout.splitlines()[0] if result.stdout else ""
        import re
        match = re.search(r"version\s+(\d+\.\d+)", version_info)
        if match:
            version = float(match.group(1))
            logger.info(f"FFmpeg version {version} found at: {ffmpeg_path}")
            return version
        
        logger.warning(f"Could not determine FFmpeg version from: {version_info}")
    except (subprocess.SubprocessError, OSError, ValueError) as e:
        logger.error(f"Error validating FFmpeg: {str(e)}")
    
    return None

def get_fallback_directory(key: str) -> str:
    """
    Get fallback directory for a specific config key
    
    Args:
        key: Configuration key (e.g., "video_output", "audio_output")
        
    Returns:
        Path to fallback directory
    """
    # First try user's Videos/Music folder
    if key == "video_output":
        fallback = str(Path.home() / "Videos" / "Snatch")
    elif key == "audio_output":
        fallback = str(Path.home() / "Music" / "Snatch")
    else:
        # For non-media directories, use temp subdirectories
        fallback = os.path.join(tempfile.gettempdir(), "Snatch", key.replace("_dir", "").replace("_output", ""))
    
    # Try to create the fallback
    try:
        os.makedirs(fallback, exist_ok=True)
        logger.info(f"Using fallback directory for {key}: {fallback}")
        return fallback
    except OSError:
        # Last resort: use a directory in the current working directory
        last_resort = os.path.join(os.getcwd(), "downloads", key.replace("_dir", "").replace("_output", ""))
        try:
            os.makedirs(last_resort, exist_ok=True)
            logger.warning(f"Using last resort directory for {key}: {last_resort}")
            return last_resort
        except OSError:
            logger.error(f"Failed to create any directory for {key}")
            return os.getcwd()  # Ultimate fallback - current directory

def set_default_directories(config: dict) -> bool:
    """
    Set default values for missing directory configuration keys
    
    Args:
        config: Configuration dictionary
        
    Returns:
        True if config was modified, False otherwise
    """
    changed = False
    directory_keys = ["video_output", "audio_output", "thumbnails_dir", "subtitles_dir", "sessions_dir", "cache_dir"]
    
    for key in directory_keys:
        if key not in config or not config[key]:
            # Get default directory for this key
            base_dir = os.getcwd()
            if key == "video_output":
                default_dir = os.path.join(base_dir, "downloads", "video")
            elif key == "audio_output":
                default_dir = os.path.join(base_dir, "downloads", "audio")
            elif key == "thumbnails_dir":
                default_dir = os.path.join(base_dir, "thumbnails")
            elif key == "subtitles_dir":
                default_dir = os.path.join(base_dir, "subtitles")
            elif key == "sessions_dir":
                default_dir = os.path.join(base_dir, "sessions")
            elif key == "cache_dir":
                default_dir = os.path.join(base_dir, "cache")
            else:
                default_dir = os.path.join(base_dir, key.replace("_dir", "").replace("_output", ""))
                
            config[key] = default_dir
            logger.info(f"Setting default directory for {key}: {default_dir}")
            changed = True
    
    return changed

def validate_config_paths(config: dict) -> bool:
    """
    Validate and create output directories if needed
    
    Args:
        config: Configuration dictionary
        
    Returns:
        True if config was modified, False otherwise
    """
    # First set any missing defaults
    changed = set_default_directories(config)
    
    # Now validate each directory
    directory_keys = ["video_output", "audio_output", "thumbnails_dir", "subtitles_dir", "sessions_dir", "cache_dir"]
    
    for key in directory_keys:
        # Normalize path
        path = os.path.abspath(os.path.expanduser(config[key]))
        config[key] = path  # Update with normalized path
        
        # Ensure directory exists, get fallback if not
        if not os.path.exists(path):
            result = ensure_directory_exists(path)
            if not result:
                fallback = get_fallback_directory(key)
                config[key] = fallback
                changed = True
                logger.info(f"Updated {key} path to fallback: {fallback}")
    
    return changed
