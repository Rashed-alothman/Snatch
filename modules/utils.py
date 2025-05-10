#small helpers (e.g. path, hashing)
import os
import re
import time
import shutil
import logging
import platform
import requests
import psutil
from pathlib import Path
from colorama import Fore, Style, init
from .common_utils import sanitize_filename
from .metadata import MetadataExtractor
from .defaults import DEFAULT_ORGANIZATION_TEMPLATES, webn_ext
from typing import (
    Any,
    Dict,
    Optional,
)

logger = logging.getLogger(__name__)

def display_system_stats():
    """Display detailed system resource statistics"""
    print(f"\n{Fore.CYAN}{'=' * 40}")
    print(f"{Fore.GREEN}SYSTEM STATISTICS{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'=' * 40}{Style.RESET_ALL}\n")

    # CPU information
    cpu_percent = psutil.cpu_percent(interval=1)
    cpu_count = psutil.cpu_count(logical=False)
    cpu_logical = psutil.cpu_count(logical=True)
    print(f"{Fore.YELLOW}CPU Usage:{Style.RESET_ALL} {cpu_percent}%")
    print(
        f"{Fore.YELLOW}CPU Cores:{Style.RESET_ALL} {cpu_count} physical, {cpu_logical} logical"
    )

    # Memory information
    mem = psutil.virtual_memory()
    print(f"\n{Fore.YELLOW}Memory Usage:{Style.RESET_ALL} {mem.percent}%")
    print(f"{Fore.YELLOW}Total Memory:{Style.RESET_ALL} {mem.total / (1024**3):.2f} GB")
    print(
        f"{Fore.YELLOW}Available Memory:{Style.RESET_ALL} {mem.available / (1024**3):.2f} GB"
    )
    print(f"{Fore.YELLOW}Used Memory:{Style.RESET_ALL} {mem.used / (1024**3):.2f} GB")

    # Disk information
    print(f"\n{Fore.YELLOW}Disk Information:{Style.RESET_ALL}")
    for part in psutil.disk_partitions(all=False):
        if os.name == "nt" and "cdrom" in part.opts or part.fstype == "":
            # Skip CD-ROM drives with no disk or other special drives
            continue
        usage = psutil.disk_usage(part.mountpoint)
        print(f"  {Fore.CYAN}Drive {part.mountpoint}{Style.RESET_ALL}")
        print(f"    Total: {usage.total / (1024**3):.2f} GB")
        print(f"    Used: {usage.used / (1024**3):.2f} GB ({usage.percent}%)")
        print(f"    Free: {usage.free / (1024**3):.2f} GB")

def list_supported_sites() -> bool:
    """Display a clean, organized list of supported sites with fallback for systems without pager."""
    from pathlib import Path
    import sys

    sites_file = Path("Supported-sites.txt")
    if not sites_file.exists():
        print(f"{Fore.RED}Supported-sites.txt not found. Cannot list supported sites.{Style.RESET_ALL}")
        return False

    try:
        with sites_file.open("r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
    except Exception as e:
        print(f"{Fore.RED}Error reading Supported-sites.txt: {e}{Style.RESET_ALL}")
        return False

    # Skip header lines if they start with "below is a list"
    header_end = 0
    for i, line in enumerate(lines):
        if line.lower().startswith("below is a list"):
            header_end = i + 1
            break
    sites = lines[header_end:]

    output_lines = []
    border = f"{Fore.CYAN}{'═' * 60}{Style.RESET_ALL}"
    title = f"{Fore.GREEN}{'SUPPORTED SITES':^60}{Style.RESET_ALL}"
    output_lines.append(border)
    output_lines.append(title)
    output_lines.append(border)
    output_lines.append("")

    total_sites = 0
    current_category = None
    category_separator = f"\n{border}\n"
    
    for line in sites:
        if line.startswith('"'):
            continue
        if ":" in line:
            category, site = map(str.strip, line.split(":", 1))
            cat_upper = category.upper()
            if current_category != cat_upper:
                if current_category is not None:
                    output_lines.append(category_separator)
                current_category = cat_upper
                output_lines.append(f"{Fore.MAGENTA}{current_category:^60}{Style.RESET_ALL}")
            if site:
                output_lines.append(f"{Fore.YELLOW} • {site}{Style.RESET_ALL}")
                total_sites += 1
        else:
            output_lines.append(f"{Fore.YELLOW} • {line}{Style.RESET_ALL}")
            total_sites += 1

    output_lines.append("")
    output_lines.append(f"{Fore.CYAN}Total supported sites: {total_sites}{Style.RESET_ALL}")
    output_lines.append(border)

    final_output = "\n".join(output_lines)
    
    # Try to use system pager, fall back to print if not available
    try:
        import pydoc
        pydoc.pager(final_output)
    except:
        print(final_output)
        
    return True

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
