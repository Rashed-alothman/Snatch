"""File organization and management utilities."""
from pathlib import Path
from typing import Dict, Any, Optional
import os
import shutil
import logging

logger = logging.getLogger(__name__)

class FileOrganizer:
    """Handles file organization and management for downloads."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize the file organizer with configuration."""
        self.config = config
        self.video_dir = config.get('video_output', 'videos')
        self.audio_dir = config.get('audio_output', 'audio')
        
        # Create output directories if they don't exist
        os.makedirs(self.video_dir, exist_ok=True)
        os.makedirs(self.audio_dir, exist_ok=True)

    def organize_file(self, filepath: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Organize a downloaded file into appropriate directory structure.
        
        Args:
            filepath: Path to the downloaded file
            metadata: Optional metadata for organizing

        Returns:
            str: New file path after organization
        """
        if not os.path.exists(filepath):
            logger.error(f"Cannot organize non-existent file: {filepath}")
            return filepath

        # Determine if it's an audio or video file
        is_audio = any(filepath.lower().endswith(ext) for ext in ['.mp3', '.m4a', '.flac', '.opus', '.ogg', '.wav'])
        
        # Select base directory
        base_dir = self.audio_dir if is_audio else self.video_dir
        
        if metadata and 'title' in metadata:
            # Create artist/album structure for audio files
            if is_audio and 'artist' in metadata:
                artist_dir = os.path.join(base_dir, self._sanitize_path(metadata['artist']))
                if 'album' in metadata:
                    base_dir = os.path.join(artist_dir, self._sanitize_path(metadata['album']))
                else:
                    base_dir = artist_dir

        # Create target directory
        os.makedirs(base_dir, exist_ok=True)
        
        # Move file to new location
        new_filepath = os.path.join(base_dir, os.path.basename(filepath))
        if filepath != new_filepath:
            try:
                shutil.move(filepath, new_filepath)
                logger.info(f"Moved file to {new_filepath}")
                return new_filepath
            except Exception as e:
                logger.error(f"Failed to move file: {e}")
                return filepath
                
        return filepath

    def _sanitize_path(self, path: str) -> str:
        """Sanitize a path component by removing invalid characters."""
        # Remove or replace invalid characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            path = path.replace(char, '_')
        return path.strip()
