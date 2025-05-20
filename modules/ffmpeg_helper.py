import os
import shutil
import logging
from pathlib import Path
import subprocess
import sys
import asyncio
from typing import Optional, Dict, Any, List

# Re-export AudioProcessor from the main implementation
from .audio_processor import AudioProcessor, AudioStats

def locate_ffmpeg() -> Optional[str]:
    """Locate FFmpeg executable with fallback to auto-install"""
    # First check system PATH
    ffmpeg_path = shutil.which('ffmpeg')
    if ffmpeg_path:
        return ffmpeg_path
        
    # Check common Windows locations
    common_paths = [
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        r"C:\ffmpeg\bin\ffmpeg.exe",
        str(Path.home() / "ffmpeg" / "bin" / "ffmpeg.exe"),
    ]
    
    for path in common_paths:
        if os.path.isfile(path):
            return path
            
    # If not found, try to install it
    try:
        logging.info("FFmpeg not found. Attempting to install...")
        setup_script = os.path.join(os.path.dirname(os.path.dirname(__file__)), 
                                  "setupfiles", "setup_ffmpeg.py")
        if os.path.exists(setup_script):
            subprocess.run([sys.executable, setup_script], check=True)
            # Check if installation was successful
            ffmpeg_path = shutil.which('ffmpeg')
            if ffmpeg_path:
                return ffmpeg_path
    except Exception as e:
        logging.error(f"Failed to install FFmpeg: {e}")
    
    return None

def get_ffmpeg_version(ffmpeg_path: str) -> Optional[str]:
    """Get FFmpeg version information"""
    try:
        result = subprocess.run([ffmpeg_path, "-version"], 
                              capture_output=True, text=True, check=True)
        return result.stdout.split('\n')[0]
    except Exception:
        return None

def validate_ffmpeg_installation() -> bool:
    """Validate FFmpeg installation and capabilities"""
    ffmpeg_path = locate_ffmpeg()
    if not ffmpeg_path:
        logging.error("FFmpeg not found and installation failed")
        return False
        
    version = get_ffmpeg_version(ffmpeg_path)
    if not version:
        logging.error("Could not verify FFmpeg version")
        return False
        
    logging.info(f"Found FFmpeg: {version}")
    return True
