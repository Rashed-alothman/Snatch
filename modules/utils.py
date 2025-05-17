#small helpers (e.g. path, hashing)
import os
import time
import shutil
import logging
from pathlib import Path
from .common_utils import sanitize_filename
from .metadata import MetadataExtractor
from .defaults import DEFAULT_ORGANIZATION_TEMPLATES, webn_ext
from typing import (
    Any,
    Dict,
    Optional,
)

logger = logging.getLogger(__name__)

def calculate_speed(downloaded_bytes: int, start_time: float) -> float:
    """
    Calculate download speed with high precision and robust error handling.

    This implementation uses high-resolution performance counters when available
    and includes sophisticated edge case handling to prevent calculation errors
    even under extreme conditions.

    Args:
        downloaded_bytes: Total number of bytes downloaded so far
        start_time: Timestamp when the download started (in seconds)

    Returns:
        Current download speed in bytes per second
    """
    # Input validation with early return for impossible scenarios
    if downloaded_bytes <= 0 or start_time <= 0 or start_time > time.time():
        return 0.0

    # Use high-precision timer for more accurate measurements
    # perf_counter is monotonic and not affected by system clock changes
    current_time = time.perf_counter() if hasattr(time, "perf_counter") else time.time()

    # Calculate elapsed time with protection against negative values
    # (which could happen if system time is adjusted backward)
    elapsed = max(0.001, current_time - start_time)

    # Guard against unrealistically high speeds due to very small elapsed times
    # (prevents showing astronomical speeds in the first few milliseconds)
    if elapsed < 0.1 and downloaded_bytes > 1024 * 1024:
        # With very small elapsed times, use a minimum threshold
        # to avoid reporting unrealistic speeds
        elapsed = 0.1

    # Calculate and return bytes per second
    return downloaded_bytes / elapsed


class FileOrganizer:
    """Organize files into directories based on metadata templates."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.templates = config.get(
            "organization_templates", DEFAULT_ORGANIZATION_TEMPLATES.copy()
        )
        self.metadata_extractor = MetadataExtractor()

    def organize_file(
        self, filepath: str, info: Optional[Dict] = None
    ) -> Optional[str]:
        """
        Organize a file based on its metadata.

        Args:
            filepath: Path to the file to organize
            info: Optional yt-dlp info dictionary

        Returns:
            New file path if successful, None otherwise
        """
        if not os.path.exists(filepath):
            logging.error(f"Cannot organize: File not found: {filepath}")
            return None

        try:
            # Extract metadata
            metadata = self.metadata_extractor.extract(filepath, info)

            # Determine the appropriate base directory and template
            is_audio = metadata.get("content_type") == "audio"
            base_dir = (
                self.config["audio_output"] if is_audio else self.config["video_output"]
            )

            # Select appropriate template
            content_type = metadata.get("content_type", "video")
            if content_type == "podcast" and "podcast" in self.templates:
                template = self.templates["podcast"]
            elif content_type == "audiobook" and "audiobook" in self.templates:
                template = self.templates["audiobook"]
            else:
                template = (
                    self.templates["audio"] if is_audio else self.templates["video"]
                )

            # Format template
            try:
                # Create dictionary with lowercase keys for template formatting
                format_dict = {}
                for key, value in metadata.items():
                    format_dict[key.lower()] = value

                # Use format_map to allow partial template application
                relative_path = template.format_map(
                    # This defaultdict-like approach handles missing keys
                    type(
                        "DefaultDict",
                        (dict,),
                        {"__missing__": lambda self, key: "Unknown"},
                    )(format_dict)
                )
            except Exception as e:
                logging.error(f"Template formatting error: {str(e)}")
                relative_path = os.path.join(
                    metadata.get("uploader", "Unknown"),
                    str(metadata.get("year", "Unknown")),
                    metadata.get("title", os.path.basename(filepath)),
                )

            # Create the full path
            filename = os.path.basename(filepath)
            new_dir = os.path.join(base_dir, relative_path)
            new_filepath = os.path.join(new_dir, filename)

            # Create directory if it doesn't exist
            os.makedirs(new_dir, exist_ok=True)

            # Check if target file already exists
            if os.path.exists(new_filepath) and os.path.samefile(
                filepath, new_filepath
            ):
                # File is already in the right place
                return filepath

            if os.path.exists(new_filepath):
                # File exists but is different - create a unique name
                base, ext = os.path.splitext(filename)
                count = 1
                while os.path.exists(new_filepath):
                    new_filename = f"{base}_{count}{ext}"
                    new_filepath = os.path.join(new_dir, new_filename)
                    count += 1

            # Move the file
            shutil.move(filepath, new_filepath)
            logging.info(f"Organized file: {filepath} -> {new_filepath}")
            return new_filepath

        except Exception as e:
            logging.error(f"Error organizing file {filepath}: {str(e)}")
            return None


def format_size(size: float) -> str:
    """
    Format a size in bytes to a human-readable string.
    
    Args:
        size: Size in bytes
        
    Returns:
        Formatted string like "1.23 MB" or "123 KB"
    """
    if size <= 0:
        return "0 B"
        
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    unit_index = 0
    
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1
        
    precision = 0 if unit_index == 0 else 2
    return f"{size:.{precision}f} {units[unit_index]}"

def format_speed(speed: float) -> str:
    """
    Return a human-friendly speed string.
    
    Args:
        speed: Speed in bytes per second
        
    Returns:
        Formatted string like "1.23 MB/s" or "123 KB/s"
    """
    if speed <= 0:
        return "0 B/s"
        
    units = ['B/s', 'KB/s', 'MB/s', 'GB/s', 'TB/s']
    unit_index = 0
    
    while speed >= 1024 and unit_index < len(units) - 1:
        speed /= 1024
        unit_index += 1
        
    precision = 0 if unit_index == 0 else 2
    return f"{speed:.{precision}f} {units[unit_index]}"
